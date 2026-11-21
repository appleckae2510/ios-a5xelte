/* Read-only A320FL boot-volume check. HFSX binary catalog keys use UTF-16BE.
 * Read only the catalog nodes needed for the paths below. Unsupported catalog
 * layouts, unreadable sectors and incomplete volumes all select the RAM root.
 * The caller runs synchronously during initial BSD root selection.
 */
enum { A3_SECTOR = 512, A3_MAX_NODE = 32768 };
static struct {
    uint64_t catalog_bytes;
    uint32_t blocks, sectors_per_block, nodes, root, depth;
    uint16_t node_size;
    uint8_t extents[64], node[A3_MAX_NODE];
    uint32_t cached;
    bool cached_valid;
} a3vol;

static uint16_t a3_be16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] << 8 | p[1]);
}

static uint32_t a3_be32(const uint8_t *p)
{
    return (uint32_t)a3_be16(p) << 16 | a3_be16(p + 2);
}

/* The catalog's initial eight extents cover ordinary freshly staged volumes. */
static bool a3_catalog_sector(uint64_t sector, uint8_t *out)
{
    if (sector >= a3vol.catalog_bytes / A3_SECTOR) return false;
    for (unsigned i = 0; i < 8; ++i) {
        const uint8_t *ex = a3vol.extents + i * 8;
        uint32_t start = a3_be32(ex), count = a3_be32(ex + 4);
        if (!count || start >= a3vol.blocks || count > a3vol.blocks - start) return false;
        uint64_t length = (uint64_t)count * a3vol.sectors_per_block;
        if (sector < length) {
            return a3_volume_read((uint64_t)start * a3vol.sectors_per_block + sector, out);
        }
        sector -= length;
    }
    return false;
}

static bool a3_catalog_node(uint32_t num)
{
    if (num == 0 || num >= a3vol.nodes) return false;
    if (a3vol.cached_valid && a3vol.cached == num) return true;
    a3vol.cached_valid = false;
    uint64_t first = (uint64_t)num * a3vol.node_size / A3_SECTOR;
    for (unsigned off = 0; off < a3vol.node_size; off += A3_SECTOR) {
        if (!a3_catalog_sector(first + off / A3_SECTOR, a3vol.node + off)) return false;
    }
    a3vol.cached = num;
    a3vol.cached_valid = true;
    return true;
}

/* Compare a validated catalog key with an ASCII path component. */
static int a3_key_order(const uint8_t *key, uint32_t parent, const char *name)
{
    uint32_t id = a3_be32(key + 2);
    if (id != parent) return id < parent ? -1 : 1;
    unsigned n = a3_be16(key + 6);
    for (unsigned i = 0; i < n; ++i) {
        uint16_t unit = a3_be16(key + 8 + i * 2);
        unsigned char target = (unsigned char)name[i];
        if (!target || unit != target) return unit < target ? -1 : 1;
    }
    return name[n] ? -1 : 0;
}

/* HFS+ index records point to the subtree beginning at their key. */
static uint32_t a3_lookup(uint32_t parent, const char *name, uint16_t type)
{
    uint32_t node = a3vol.root;
    for (uint32_t height = a3vol.depth; height; --height) {
        if (!a3_catalog_node(node)) return 0;
        const uint8_t *data = a3vol.node;
        bool leaf = height == 1;
        if (data[8] != (leaf ? 0xffu : 0u) || data[9] != height) return 0;
        uint16_t records = a3_be16(data + 10);
        if (!records || (unsigned)(records + 1) * 2 > (unsigned)a3vol.node_size - 14u) return 0;
        unsigned table = (unsigned)a3vol.node_size - (records + 1u) * 2u;
        uint32_t child = 0;
        for (unsigned i = 0; i < records; ++i) {
            unsigned tail = (unsigned)a3vol.node_size - 2u * (i + 1);
            unsigned off = a3_be16(data + tail), end = a3_be16(data + tail - 2);
            if (off < 14 || off > end || end > table || end - off < 8) return 0;
            const uint8_t *key = data + off;
            unsigned length = a3_be16(key), chars = a3_be16(key + 6);
            if (chars > 255 || length != 6u + chars * 2u || length + 2 > end - off) return 0;
            int order = a3_key_order(key, parent, name);
            if (order > 0) break;
            const uint8_t *value = key + 2 + length;
            unsigned space = (end - off) - (2 + length);
            if (!leaf) {
                if (space < 4) return 0;
                child = a3_be32(value);
            } else if (!order) {
                if (space < (type == 1 ? 88u : 248u) || a3_be16(value) != type) return 0;
                return a3_be32(value + 8);
            }
        }
        if (!child || child == node) return 0;
        node = child;
    }
    return 0;
}

static const char *a3_check_ios_volume(uint64_t partition_sectors)
{
    uint8_t hdr[A3_SECTOR];
    const uint64_t issued_bytes = 11ULL * 1024 * 1024 * 1024;
    a3vol.cached_valid = false;
    if (partition_sectors < 3 || !a3_volume_read(2, hdr)) return "volume header unreadable";
    if (a3_be16(hdr) != 0x4858 || a3_be16(hdr + 2) != 5) return "no iOS HFSX volume";
    uint32_t block = a3_be32(hdr + 40), blocks = a3_be32(hdr + 44);
    if (block < 512 || block > 65536 || (block & (block - 1)) || !blocks ||
        (uint64_t)block * blocks != issued_bytes || issued_bytes / A3_SECTOR > partition_sectors) {
        return "unexpected A3 iOS volume size";
    }
    uint32_t attributes = a3_be32(hdr + 4);
    /* Permit normal journal replay on a writable journaled root after an
     * interrupted boot. Apple's HFS mount code performs the replay. A dirty
     * non-journaled volume or one marked inconsistent still needs repair. */
    if ((attributes & 0x800) || (!(attributes & 0x100) &&
        (!emmc_writable || !(attributes & 0x2000)))) return "HFSX needs repair";
    a3vol.sectors_per_block = block / A3_SECTOR;
    a3vol.blocks = blocks;
    a3vol.catalog_bytes = ((uint64_t)a3_be32(hdr + 272) << 32) | a3_be32(hdr + 276);
    if (!a3vol.catalog_bytes || a3vol.catalog_bytes > issued_bytes) return "invalid HFSX catalog";
    memcpy(a3vol.extents, hdr + 288, sizeof(a3vol.extents));
    if (!a3_volume_read(issued_bytes / A3_SECTOR - 2, hdr) ||
        a3_be16(hdr) != 0x4858 || a3_be16(hdr + 2) != 5 ||
        a3_be32(hdr + 40) != block || a3_be32(hdr + 44) != blocks) return "invalid alternate volume header";
    if (!a3_catalog_sector(0, hdr) || hdr[8] != 1 || hdr[51] != 0xbc) return "unreadable HFSX catalog header";
    a3vol.depth = a3_be16(hdr + 14);
    a3vol.root = a3_be32(hdr + 16);
    a3vol.node_size = a3_be16(hdr + 32);
    a3vol.nodes = a3_be32(hdr + 36);
    if (!a3vol.depth || a3vol.depth > 16 || a3vol.node_size < 4096 || a3vol.node_size > A3_MAX_NODE ||
        (a3vol.node_size & (a3vol.node_size - 1)) || !a3vol.nodes ||
        (uint64_t)a3vol.nodes * a3vol.node_size > a3vol.catalog_bytes) return "unsupported HFSX catalog";
    if (a3_lookup(1, "A3IOSROOT", 1) != 2) return "A3IOSROOT not identified";
    uint32_t sbin = a3_lookup(2, "sbin", 1);
    if (!sbin || !a3_lookup(sbin, "launchd", 2)) return "launchd missing or unreadable";
    uint32_t usr = a3_lookup(2, "usr", 1);
    uint32_t lib = usr ? a3_lookup(usr, "lib", 1) : 0;
    if (!lib || !a3_lookup(lib, "dyld", 2)) return "dyld missing or unreadable";
    uint32_t system = a3_lookup(2, "System", 1);
    uint32_t library = system ? a3_lookup(system, "Library", 1) : 0;
    uint32_t caches = library ? a3_lookup(library, "Caches", 1) : 0;
    uint32_t dyld = caches ? a3_lookup(caches, "com.apple.dyld", 1) : 0;
    if (!dyld || !a3_lookup(dyld, "dyld_shared_cache_arm64", 2)) return "arm64 shared cache missing or unreadable";
    uint32_t services = a3_lookup(library, "CoreServices", 1);
    uint32_t sb = services ? a3_lookup(services, "SpringBoard.app", 1) : 0;
    if (!sb || !a3_lookup(sb, "SpringBoard", 2)) return "SpringBoard missing or unreadable";
    return NULL;
}
