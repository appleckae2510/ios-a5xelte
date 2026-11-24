"""A3-only J3-inspired boot fixes; do not import J3 board constants."""
from pathlib import Path


def replace_exact(source, old, new):
    if source.count(new) == 1:
        return source
    if source.count(old) != 1:
        raise ValueError("J3 compatibility anchor missing or ambiguous: " + old[:100])
    return source.replace(old, new, 1)


CHANGES = (
    ("pexpert/arm/pe_init.c", "\t\twhile (((unsigned)(*delta + image_size)) >= (display_size / 2)) {\n\t\t\t*delta -= 50 * scale;", "\t\twhile (((unsigned)(*delta + image_size)) >= (display_size / 2)) {\n\t\t\t/* A3/J3 small-panel progress: stop before a negative offset. */\n\t\t\tif (scale == 0 || scale > (unsigned int)*delta / 50u) {\n\t\t\t\t*delta = 0;\n\t\t\t\tbreak;\n\t\t\t}\n\t\t\t*delta -= 50 * scale;"),
    ("bsd/net/dlil.c", "unsigned int net_affinity = 1;", "unsigned int net_affinity = 0; /* A3: ordinary scheduling by default; net_affinity=1 opts in. */"),
    ("bsd/net/dlil.c", "dlil_affinity_set(struct thread *tp, u_int32_t tag)\n{\n\tthread_affinity_policy_data_t policy;", "dlil_affinity_set(struct thread *tp, u_int32_t tag)\n{\n\t/* A3/J3: cover all callers, not only callers checking net_affinity. */\n\tif (!net_affinity) {\n\t\treturn KERN_NOT_SUPPORTED;\n\t}\n\tthread_affinity_policy_data_t policy;"),
    ("osfmk/kern/exception.c", "\tuint64_t scanned = 0;\n\tint lines = 0;", "\tuint64_t scanned = 0, attempted = 0;\n\tunsigned int regions = 0;\n\tint lines = 0;"),
    ("osfmk/kern/exception.c", "\twhile (lines < 700 && scanned < (96ull << 20)) {", "\t/* Bound diagnostic work even when pages cannot be read. */\n\twhile (lines < 100 && attempted < (16ull << 20) && regions++ < 1024) {"),
    ("osfmk/kern/exception.c", "\t\tvm_map_offset_t base = addr;\n\t\taddr += size;", "\t\tvm_map_offset_t base = addr;\n\t\tif (size == 0 || addr + size <= addr) {\n\t\t\tbreak;\n\t\t}\n\t\taddr += size;"),
    ("osfmk/kern/exception.c", "\t\tfor (vm_map_offset_t off = 0; off < size && lines < 700; off += 65536) {\n\t\t\tsize_t len = (size - off) < 65536 ? (size_t)(size - off) : 65536;\n\t\t\tif (copyin", "\t\tfor (vm_map_offset_t off = 0; off < size && lines < 100 && attempted < (16ull << 20); off += 65536) {\n\t\t\tsize_t len = (size - off) < 65536 ? (size_t)(size - off) : 65536;\n\t\t\tif (len > (16ull << 20) - attempted) {\n\t\t\t\tlen = (size_t)((16ull << 20) - attempted);\n\t\t\t}\n\t\t\tattempted += len;\n\t\t\tif (copyin"),
    ("osfmk/kern/exception.c", "\t\tfor (size_t i = 0; i <= len; i++) {", "\t\tfor (size_t i = 0; i <= len && lines < 100; i++) {"),
)


def apply(root):
    staged = {}
    for rel, old, new in CHANGES:
        path = root / rel
        original = staged[path] if path in staged else path.read_text()
        staged[path] = replace_exact(original, old, new)
    for path, content in staged.items():
        path.write_text(content)
    print("A3 J3 compatibility: progress bounds, DLIL scheduling and crash diagnostic limits applied")
