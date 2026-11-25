"""A3 hardware overlay for the pinned J3 donor. Compile-only, never flash."""
from pathlib import Path
import sys

def replace(s, old, new):
    if s.count(old) != 1:
        raise ValueError("missing/ambiguous J3 source anchor: " + old[:100])
    return s.replace(old, new, 1)

def prepare(root):
    changes = {
        "config/MASTER.arm64.j3y17lte": [
            ("[ vm_pressure_events memorystatus ", "[ vm_pressure_events jetsam memorystatus "),
        ],
        "bsd/sweet_hfs/core/kext-config.h": [
            ("#if (TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR) // iOS (real hardware)", "#if (TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR) && !defined(J3_DONOR_MACOS_HFS_PROFILE) // iOS (real hardware)"),
        ],
        "bsd/sweet_hfs/sweet_hfs_compat.h": [
            ("#include \"core/kext-config.h\"", "/* Match the donor's original macOS HFS configuration for this compile-only target. */\n#define J3_DONOR_MACOS_HFS_PROFILE 1\n#include \"core/kext-config.h\""),
        ],
        "bsd/sweet_hfs/hfs_encodings/hfs_encodings.h": [
            ("#if !TARGET_OS_IPHONE", "#if !TARGET_OS_IPHONE || defined(J3_DONOR_MACOS_HFS_PROFILE)"),
            ("#ifdef __APPLE_API_UNSTABLE", "#if defined(__APPLE_API_UNSTABLE) || defined(J3_DONOR_MACOS_HFS_PROFILE)"),
        ],
        "libsyscall/xcodescripts/mach_install_mig.sh": [
            ("    MACHINE_ARCH=armv7\n", "    MACHINE_ARCH=armv7\n    if [ \"${PLATFORM_NAME:-}\" = iphoneos ]; then\n        export IPHONEOS_DEPLOYMENT_TARGET=10.0\n    fi\n"),
        ],
        "iokit/KernelConfigTables.cpp": [
            ("'samsung,j3y17lte';", "'samsung,a3y17lte';"),
            ("'samsung,j3y17lte-display';", "'samsung,a3y17lte-display';"),
        ],
        "iokit/Kernel/arm/SweetPlatformExpert.cpp": [
            ("J3Y17LTE: starting device-tree platform expert", "A3_J3_REBASE_V1: starting device-tree platform expert"),
        ],
        "iokit/Kernel/arm/SweetFramebuffer.cpp": [
            ("#define SWEET_FB_DOT_PITCH              294", "#define SWEET_FB_DOT_PITCH              312"),
            ("j3_backlight_set(bool on)\n{", "j3_backlight_set(bool on)\n{\n\t/* A3 AMOLED: never drive the J3 LCD BLIC GPIO. */\n\t(void)on;\n\treturn;"),
        ],
        "bsd/dev/j3y17lte_input.c": [
            ('(void)PE_parse_boot_argn("j3touch", &touch_enabled, sizeof(touch_enabled));', '(void)PE_parse_boot_argn("j3touch", &touch_enabled, sizeof(touch_enabled));\n\t/* Different touch controller and board GPIOs. */\n\tenabled = 0;'),
        ],
        "bsd/dev/j3y17lte_emmc.c": [
            ('(void)PE_parse_boot_argn("emmcwrite", &enable_write, sizeof(enable_write));', '(void)PE_parse_boot_argn("emmcwrite", &enable_write, sizeof(enable_write));\n\t/* The J3 GPT extent is not an A3 extent. Compile-only. */\n\tenable_write = 0;'),
        ],
        "osfmk/vm/vm_init.c": [
            ("if (j3y17lte_bank1_hotadd_enabled) {", "j3y17lte_bank1_hotadd_enabled = false; /* A3 reserved-memory map not yet wired */\n\tif (j3y17lte_bank1_hotadd_enabled) {"),
        ],
    }
    # Stage all edits before writing; never silently skip a failed anchor.
    staged = {}
    for rel, pairs in changes.items():
        p = root / rel
        s = p.read_text()
        for old, new in pairs:
            s = replace(s, old, new)
        staged[p] = s
    for p, s in staged.items():
        p.write_text(s)
    print("A3_J3_REBASE_V1: staged hardware guards; COMPILE ONLY")

if __name__ == "__main__":
    prepare(Path(sys.argv[1]).resolve())
