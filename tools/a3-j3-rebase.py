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
            ("[ vm_pressure_events memorystatus ", "[ vm_pressure_events jetsam memorystatus config_ubsan_minimal "),
        ],
        "bsd/sweet_hfs/core/kext-config.h": [
            ("#if (TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR) // iOS (real hardware)", "#if (TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR) && !defined(J3_DONOR_MACOS_HFS_PROFILE) // iOS (real hardware)"),
        ],
        "bsd/sweet_hfs/sweet_hfs_compat.h": [
            ("#include \"core/kext-config.h\"", "/* Match the donor's original macOS HFS configuration for this compile-only target. */\n#define J3_DONOR_MACOS_HFS_PROFILE 1\n#include \"core/kext-config.h\""),
        ],
        "bsd/sweet_hfs/hfs_encodings/hfs_encodings.h": [
            ("#if !TARGET_OS_IPHONE", "#if !TARGET_OS_IPHONE || defined(J3_DONOR_MACOS_HFS_PROFILE)"),
        ],
        "bsd/kern/syscalls.master": [
            ("#if CONFIG_EMBEDDED || defined(ARM64_BOARD_CONFIG_SWEET)\n435", "#if CONFIG_EMBEDDED || defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_J3Y17LTE)\n435"),
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
        # A3 initial VM ownership is the existing loader's verified single
        # contiguous staging range, not the J3 donor's two-bank aperture.
        "osfmk/arm/arm_init.c": [
            ("\tconst_boot_args = *args;\n", "\tconst_boot_args = *args;\n\t/* A3 bootstrap: refuse memory outside the existing loader window. */\n\tif (const_boot_args.physBase != 0x92000000ULL ||\n\t    const_boot_args.memSize == 0 || const_boot_args.memSize > 0x1c000000ULL ||\n\t    (const_boot_args.memSize & 0xfffULL) != 0 ||\n\t    const_boot_args.topOfKernelData < const_boot_args.physBase ||\n\t    const_boot_args.topOfKernelData - const_boot_args.physBase >= const_boot_args.memSize) {\n\t\tpanic(\"A3 RAM: invalid loader memory window\");\n\t}\n"),
        ],
        "osfmk/arm/pmap/pmap_data.c": [
            ("const vm_size_t j3_pmap_metadata_span = 0x80000000ULL;", "const vm_size_t j3_pmap_metadata_span = mem_size; /* A3: only loader-managed pages */"),
        ],
        "osfmk/arm/pmap/pmap_data.h": [
            ("0x7e800000ULL", "0x7e400000ULL"),
            ("return j3y17lte_upper_ram_online &&\n\t    (pa >= 0x80000000ULL) && (pa < 0xc0000000ULL);", "return false; /* A3: no unverified late RAM ownership */"),
        ],
        "osfmk/arm/pmap/pmap.c": [
            ("#define J3_RAM_HOLE_START ((pmap_paddr_t)0x7e800000ULL)", "#define J3_RAM_HOLE_START ((pmap_paddr_t)0x7e400000ULL)"),
        ],
        "osfmk/mach/arm/vm_param.h": [
            ("#define isphysmem(a)            (((((vm_address_t)(a) - gPhysBase) < gPhysSize) && \\\n\t!(((uint64_t)(a) >= 0x7e800000ULL) && ((uint64_t)(a) < 0x80000000ULL))) || \\\n\t(((uint64_t)(a) >= 0x80000000ULL) && ((uint64_t)(a) < 0xc0000000ULL)))", "#define isphysmem(a)            (((vm_address_t)(a) - gPhysBase) < gPhysSize) /* A3: managed RAM only */"),
            ("((uint64_t)(addr) < 0x7e800000ULL)", "((uint64_t)(addr) < 0x7e400000ULL)"),
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
        if rel == "config/MASTER.arm64.j3y17lte":
            # A feature in the VM group needs a matching options declaration.
            if "CONFIG_UBSAN_MINIMAL" in s:
                raise ValueError("unexpected existing minimal UBSan option")
            s += "\noptions CONFIG_UBSAN_MINIMAL # <config_ubsan_minimal>\n"
        staged[p] = s
    for p, s in staged.items():
        p.write_text(s)
    print("A3_J3_REBASE_V1: staged hardware guards; COMPILE ONLY")

if __name__ == "__main__":
    prepare(Path(sys.argv[1]).resolve())
