/* SPDX-License-Identifier: GPL-2.0-only
 * Minimal Samsung EL1/MMU-off loader for mkpayload.py version 1 (Galaxy A3 2017).
 * One CPU, 4 KiB XNU, 448 MiB within the A320FL BOOT device-tree RAM bank.
 */
#include <stdint.h>
#include "display_console.h"

#define LOG_BASE 0x679fe000UL   /* scratch within source-declared 10 MiB fb_handover */
#define RAM_BASE 0x92000000UL
#define RAM_END  0xae000000UL
#define PAGE_SIZE 4096UL
#define BOOT_LINE_LENGTH 608
#define EMBEDDED_MAGIC "A3XNPAY1"
#define CHECKED_MAGIC  "A3XNPAY2"
#define EMBEDDED_MAX_SIZE (64UL * 1024UL * 1024UL)

const char a3_loader_format[] __attribute__((used)) = CHECKED_MAGIC;

struct embedded_header {
    char magic[8];
    union {
        uint64_t legacy_size;
        struct { uint32_t payload_size, crc32; } checked;
    } data;
};
struct payload_seg {
    uint64_t vmaddr, vmsize, file_off, file_size;
};
struct payload {
    char magic[8];
    uint32_t version, nsegs;
    uint64_t virt_base, entry_va, adt_off, adt_size, kernel_end;
    uint64_t phys_base, mem_size;
    char cmdline[BOOT_LINE_LENGTH];
    struct payload_seg segs[];
};
struct boot_video {
    uint64_t v_baseAddr, v_display, v_rowBytes, v_width, v_height, v_depth;
};
struct boot_args {
    uint16_t Revision, Version;
    uint64_t virtBase, physBase, memSize, topOfKernelData;
    struct boot_video Video;
    uint32_t machineType;
    uint64_t deviceTreeP;
    uint32_t deviceTreeLength;
    char CommandLine[BOOT_LINE_LENGTH];
    uint64_t bootFlags, memSizeActual;
};

_Static_assert(__builtin_offsetof(struct payload, segs) == 0x2a8, "payload layout");
_Static_assert(__builtin_offsetof(struct boot_args, CommandLine) == 108, "boot_args layout");
_Static_assert(sizeof(struct boot_args) == 736, "boot_args size");

typedef uint64_t alias_word __attribute__((__may_alias__));

static void zero_bytes(uintptr_t dst, uint64_t size)
{
    while ((dst & 7U) && size) { *(volatile uint8_t *)dst++ = 0; --size; }
    while (size >= 8) { *(volatile alias_word *)dst = 0; dst += 8; size -= 8; }
    while (size--) *(volatile uint8_t *)dst++ = 0;
}

static void copy_bytes(uintptr_t dst, uintptr_t src, uint64_t size)
{
    /* Payload segments are aligned. Byte accesses also handle an odd tail. */
    if (((src | dst) & 7U) == 0) {
        while (size >= 8) {
            *(volatile alias_word *)dst = *(const volatile alias_word *)src;
            src += 8; dst += 8; size -= 8;
        }
    }
    while (size--) *(volatile uint8_t *)dst++ = *(const volatile uint8_t *)src++;
}

void a3_clean_range(uintptr_t start, uintptr_t end)
{
    uint64_t ctr;
    __asm__ volatile("mrs %0, CTR_EL0" : "=r" (ctr));
    uintptr_t line = 4UL << ((ctr >> 16) & 0xf);
    for (uintptr_t p = start & ~(line - 1); p < end; p += line)
        __asm__ volatile("dc cvac, %0" : : "r" (p) : "memory");
    __asm__ volatile("dsb sy" : : : "memory");
}

static int magic_ok(const char *value)
{
    const char *want = "SWEETXNU";
    for (unsigned i = 0; i < 8; ++i)
        if (value[i] != want[i])
            return 0;
    return 1;
}

static int same_magic(const char *value, const char *want)
{
    for (unsigned i = 0; i < 8; ++i)
        if (value[i] != want[i])
            return 0;
    return 1;
}

/* IEEE CRC-32 catches damaged transfers before any destination is changed. */
static uint32_t payload_crc32(const uint8_t *data, uint64_t size)
{
    static const uint32_t table[16] = {
        0x00000000, 0x1db71064, 0x3b6e20c8, 0x26d930ac,
        0x76dc4190, 0x6b6b51f4, 0x4db26158, 0x5005713c,
        0xedb88320, 0xf00f9344, 0xd6d6a3e8, 0xcb61b38c,
        0x9b64c2b0, 0x86d3d2d4, 0xa00ae278, 0xbdbdf21c
    };
    uint32_t crc = 0xffffffffU;
    while (size--) {
        crc ^= *data++;
        crc = (crc >> 4) ^ table[crc & 15];
        crc = (crc >> 4) ^ table[crc & 15];
    }
    return ~crc;
}

static uintptr_t align_page(uintptr_t value)
{
    return (value + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
}

/* Check the root model in the actual FDT before using A3 MMIO/RAM. */
int a3_board_ok(uintptr_t base)
{
    if (!base || (base & 3)) return 0;
    const uint32_t *h = (const uint32_t *)base;
    if (__builtin_bswap32(h[0]) != 0xd00dfeedu) return 0;
    uint32_t total = __builtin_bswap32(h[1]);
    uint32_t off = __builtin_bswap32(h[2]), strings = __builtin_bswap32(h[3]);
    uint32_t string_size = __builtin_bswap32(h[8]);
    uint32_t struct_size = __builtin_bswap32(h[9]);
    if (total < 40 || total > 0x200000 || off < 40 || (off & 3) ||
        off > total || struct_size > total - off ||
        strings < 40 || strings > total || string_size > total - strings ||
        __builtin_bswap32(h[5]) != 17 || __builtin_bswap32(h[6]) > 17)
        return 0;
    uint32_t end = off + struct_size;
    if (off < strings + string_size && strings < end) return 0;
    const uint8_t *b = (const uint8_t *)base;
    unsigned depth = 0, roots = 0, found = 0;
    while (off <= end && end - off >= 4) {
        uint32_t tok = __builtin_bswap32(*(const uint32_t *)(b + off)); off += 4;
        if (tok == 1) {
            if (!depth && roots++) return 0;
            ++depth;
            while (off < end && b[off]) ++off;
            if (off == end) return 0;
            off = (off + 4) & ~3u;
        } else if (tok == 2) {
            if (!depth) return 0;
            --depth;
        } else if (tok == 3) {
            if (!depth || off > end || end - off < 8) return 0;
            uint32_t len = __builtin_bswap32(*(const uint32_t *)(b + off));
            uint32_t no = __builtin_bswap32(*(const uint32_t *)(b + off + 4)); off += 8;
            if (len > end - off || no >= string_size) return 0;
            const char *key = (const char *)(b + strings + no);
            uint32_t key_size = 0;
            while (key_size < string_size - no && key[key_size]) ++key_size;
            if (key_size == string_size - no) return 0;
            if (depth == 1 && key_size == 5 &&
                key[0]=='m' && key[1]=='o' && key[2]=='d' && key[3]=='e' && key[4]=='l' && !key[5]) {
                const char *value = (const char *)(b + off);
                if (found || !len || value[len - 1] != 0) return 0;
                for (uint32_t i = 0; i + 6 <= len; ++i)
                    if (value[i]=='A' && value[i+1]=='3' && value[i+2]=='Y' &&
                        value[i+3]=='1' && value[i+4]=='7' && value[i+5]==' ')
                        found = 1;
                if (!found) return 0;
            }
            off = (off + len + 3) & ~3u;
        } else if (tok == 9) {
            return depth == 0 && roots == 1 && found && off == end;
        } else if (tok != 4) return 0;
    }
    return 0;
}

/* The assembly entry already checked the firmware FDT. */
uintptr_t a3_prepare_xnu(volatile uint64_t *log, uintptr_t embedded)
{
    a3_display(A3_SCREEN_LOADING, log);
    log[10] = (uint64_t)-1;
    if (!embedded || (embedded & 7) || embedded > RAM_END - sizeof(struct embedded_header))
        return 0;

    const struct embedded_header *eh = (const struct embedded_header *)embedded;
    int checked = same_magic(eh->magic, CHECKED_MAGIC);
    uint64_t length = checked ? eh->data.checked.payload_size : eh->data.legacy_size;
    if ((!checked && !same_magic(eh->magic, EMBEDDED_MAGIC)) || !length ||
        length > EMBEDDED_MAX_SIZE || length > RAM_END - embedded - sizeof(*eh))
        return 0;

    uintptr_t payload_start = embedded + sizeof(*eh);
    uintptr_t payload_end = payload_start + length;
    const struct payload *p = (const struct payload *)payload_start;
    log[11] = payload_start;
    log[12] = payload_end;

    log[10] = (uint64_t)-6;
    if (checked && payload_crc32((const uint8_t *)payload_start, length) != eh->data.checked.crc32)
        return 0;

    log[10] = (uint64_t)-2;
    if (length < sizeof(*p) || !magic_ok(p->magic) || p->version != 1 ||
        !p->nsegs || p->nsegs > 32 ||
        __builtin_offsetof(struct payload, segs) + p->nsegs * sizeof(struct payload_seg) > length ||
        !p->adt_size || (p->adt_off & 7) || p->adt_off > length ||
        p->adt_size > length - p->adt_off || p->cmdline[BOOT_LINE_LENGTH - 1] != 0)
        return 0;
    log[10] = (uint64_t)-3;
    if (p->phys_base < RAM_BASE || p->phys_base >= RAM_END ||
        !p->mem_size || p->mem_size > RAM_END - p->phys_base ||
        p->entry_va < p->virt_base || (p->entry_va & 3) ||
        p->kernel_end < p->virt_base || (p->kernel_end & (PAGE_SIZE - 1)) ||
        p->kernel_end - p->virt_base >= p->mem_size)
        return 0;
    log[13] = p->phys_base;
    log[14] = p->mem_size;
    uintptr_t memory_end = p->phys_base + p->mem_size;
    uintptr_t kernel_end = p->phys_base + (p->kernel_end - p->virt_base);
    if (payload_start < memory_end && p->phys_base < payload_end)
        return 0;

    /* Validate every mapping before copying the first byte. A malformed later
     * segment must not leave a partially installed kernel in RAM. */
    int entry_backed = 0;
    uint64_t table_end = sizeof(*p) + p->nsegs * sizeof(struct payload_seg);
    log[10] = (uint64_t)-4;
    if (p->adt_off < table_end) return 0;
    for (uint32_t i = 0; i < p->nsegs; ++i) {
        const struct payload_seg *s = &p->segs[i];
        if (s->vmaddr < p->virt_base || s->vmaddr > p->kernel_end ||
            !s->vmsize || ((s->vmaddr | s->vmsize) & (PAGE_SIZE - 1)) ||
            s->file_size > s->vmsize || s->file_off < table_end ||
            (s->file_off & 7) || s->file_off > p->adt_off ||
            s->file_size > p->adt_off - s->file_off ||
            s->vmsize > p->kernel_end - s->vmaddr)
            return 0;
        if (p->entry_va >= s->vmaddr && p->entry_va - s->vmaddr < s->file_size)
            entry_backed = 1;
        for (uint32_t j = 0; j < i; ++j) {
            const struct payload_seg *t = &p->segs[j];
            if ((s->vmaddr < t->vmaddr + t->vmsize && t->vmaddr < s->vmaddr + s->vmsize) ||
                (s->file_size && t->file_size && s->file_off < t->file_off + t->file_size &&
                 t->file_off < s->file_off + s->file_size))
                return 0;
        }
    }
    log[10] = (uint64_t)-5;
    uintptr_t adt_pa = kernel_end;
    if (!entry_backed || p->adt_size > memory_end - adt_pa ||
        memory_end - adt_pa - p->adt_size < PAGE_SIZE)
        return 0;
    uintptr_t ba_pa = align_page(adt_pa + p->adt_size);
    if (ba_pa > memory_end - PAGE_SIZE) return 0;

    for (uint32_t i = 0; i < p->nsegs; ++i) {
        const struct payload_seg *s = &p->segs[i];
        uintptr_t dst = p->phys_base + (s->vmaddr - p->virt_base);
        copy_bytes(dst, payload_start + s->file_off, s->file_size);
        zero_bytes(dst + s->file_size, s->vmsize - s->file_size);
        a3_clean_range(dst, dst + s->vmsize);
    }
    log[10] = 4;
    copy_bytes(adt_pa, payload_start + p->adt_off, p->adt_size);
    zero_bytes(ba_pa, PAGE_SIZE);
    volatile struct boot_args *ba = (volatile struct boot_args *)ba_pa;
    ba->Revision = 2;
    ba->Version = 2;
    ba->virtBase = p->virt_base;
    ba->physBase = p->phys_base;
    ba->memSize = p->mem_size;
    ba->topOfKernelData = ba_pa + PAGE_SIZE;
    ba->deviceTreeP = p->virt_base + (adt_pa - p->phys_base);
    ba->deviceTreeLength = (uint32_t)p->adt_size;
    for (unsigned i = 0; i < BOOT_LINE_LENGTH; ++i)
        ba->CommandLine[i] = p->cmdline[i];
    ba->memSizeActual = p->mem_size;
    ba->Video.v_baseAddr = 0x67000000UL;
    ba->Video.v_display = 1;
    ba->Video.v_rowBytes = 2880;
    ba->Video.v_width = 720;
    ba->Video.v_height = 1280;
    ba->Video.v_depth = 32;
    a3_clean_range(adt_pa, ba_pa + PAGE_SIZE);

    uintptr_t entry_pa = p->phys_base + (p->entry_va - p->virt_base);
    log[15] = entry_pa;
    log[16] = p->nsegs;
    log[17] = ba_pa;
    log[10] = 5;
    a3_display(A3_SCREEN_STARTING, log);
    a3_clean_range(LOG_BASE, LOG_BASE + PAGE_SIZE);
    __asm__ volatile("ic iallu; dsb sy; isb" : : : "memory");
    return entry_pa;
}
