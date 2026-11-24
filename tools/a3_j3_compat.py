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
)


def apply(root):
    staged = {}
    for rel, old, new in CHANGES:
        path = root / rel
        original = staged[path] if path in staged else path.read_text()
        staged[path] = replace_exact(original, old, new)
    for path, content in staged.items():
        path.write_text(content)
    print("A3 J3 compatibility: progress bounds and DLIL scheduling applied")
