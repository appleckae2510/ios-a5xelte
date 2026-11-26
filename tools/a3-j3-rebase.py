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
    # Decode the exact sleh.c panic signature without calling the normal
    # logging path or modifying exception handling.
    panic_anchor = "\t/*\n\t * Stage 80 is reserved as the unambiguous panic indicator.\n\t */"
    exception_diag = r'''
	/* A3: capture the actual message and PC/LR of panic_with_thread_kernel_state. */
	if (!early_disabled && fmt != 0 && args != 0) {
		static const char prefix[] = "%s at pc 0x%016llx, lr 0x%016llx";
		unsigned int matches = 1u;
		for (unsigned int i = 0; i < sizeof(prefix) - 1u; i++) {
			if (fmt[i] != prefix[i]) {
				matches = 0u;
				break;
			}
		}
		if (matches) {
			va_list copy;
			va_copy(copy, *args);
			const char *msg = va_arg(copy, const char *);
			uint64_t pc = va_arg(copy, uint64_t);
			uint64_t lr = va_arg(copy, uint64_t);
			va_end(copy);
			/* Message: 16 bytes, 8 bits per column, y=90..165. */
			unsigned int ended = (msg == 0);
			for (unsigned int i = 0; i < 16u; i++) {
				unsigned char ch = ended ? 0u : (unsigned char)msg[i];
				if (ch == 0u) {
					ended = 1u;
				}
				for (unsigned int bit = 0; bit < 8u; bit++) {
					uint32_t colour = (ch & (1u << (7u - bit))) ?
					    0xff00ffffu : 0xffff2040u;
					for (unsigned int dy = 0; dy < 6u; dy++) {
						volatile uint32_t *row = early_fb +
						    (90u + bit * 10u + dy) * J3_EARLY_STRIDE_PIXELS;
						for (unsigned int dx = 0; dx < J3_MARK_W; dx++) {
							row[96u + i * J3_MARK_STEP + dx] = colour;
						}
					}
				}
			}
			/* PC and LR: 16 nibbles each, y=250..285 and y=300..335. */
			for (unsigned int reg = 0; reg < 2u; reg++) {
				uint64_t value = reg == 0u ? pc : lr;
				for (unsigned int i = 0; i < 16u; i++) {
					unsigned int nibble = (unsigned int)((value >> ((15u - i) * 4u)) & 0xfu);
					for (unsigned int bit = 0; bit < 4u; bit++) {
						uint32_t colour = (nibble & (1u << (3u - bit))) ?
						    0xff00ffffu : 0xffff2040u;
						for (unsigned int dy = 0; dy < 6u; dy++) {
							volatile uint32_t *row = early_fb +
							    (250u + reg * 50u + bit * 10u + dy) * J3_EARLY_STRIDE_PIXELS;
							for (unsigned int dx = 0; dx < J3_MARK_W; dx++) {
								row[96u + i * J3_MARK_STEP + dx] = colour;
							}
						}
					}
				}
			}
			__asm__ volatile("dsb sy" ::: "memory");
		}
	}

'''
    changes["osfmk/arm64/sweet_early.c"] = [(panic_anchor, exception_diag + panic_anchor)]
    # A3 v0.28: v0.27 fault PC resolves to the first read of the
    # Exynos7570 PMU in j3y17lte_prepare_smp_pmu. Do not touch the donor
    # PMU on the Exynos7870. Keep coherency and the normal CPU handshake.
    changes["iokit/Kernel/arm/SweetCPU.cpp"] = [
        ("\tj3y17lte_prepare_smp_pmu();\n\tj3y17lte_enable_smp_coherency();",
         "\t/* A3 single-core bring-up: no Exynos7570 PMU accesses. */\n\tif (ml_get_topology_info()->num_cpus != 1) {\n\t\tpanic(\"A3: SMP PMU not validated; require single CPU\");\n\t}\n\tj3y17lte_enable_smp_coherency();"),
    ]
    # A3 v0.29: iPhoneOS has a static MAC policy table in __DATA_CONST.
    # Register existing built-in providers before machine_lockdown(), using
    # the normal MAC lifecycle. Do not change the policy callbacks or page
    # permissions. Keep other donor targets on their original path.
    changes["bsd/kern/bsd_init.c"] = [
        ('#if defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_J3Y17LTE)\n\t/* AMFI\'s MAC policy is built in on SWEET (bsd/kern/sweet_amfi.c). */\n\textern void sweet_amfi_policy_register(void);\n\tsweet_amfi_policy_register();\n#endif',
         '#if defined(ARM64_BOARD_CONFIG_SWEET) && !defined(ARM64_BOARD_CONFIG_J3Y17LTE)\n\t/* Original SWEET path. A3 uses pre-lockdown registration. */\n\textern void sweet_amfi_policy_register(void);\n\tsweet_amfi_policy_register();\n#endif'),
    ]
    changes["osfmk/kern/startup.c"] = [
        ('\tkernel_bootstrap_log("mac_policy_initmach");\n\tmac_policy_initmach();',
         '#if defined(ARM64_BOARD_CONFIG_J3Y17LTE) && !XNU_TARGET_OS_OSX\n\t/* Register built-in policies while the static MAC table is writable. */\n\textern void sweet_amfi_policy_register(void);\n\tsweet_amfi_policy_register();\n#endif\n\tkernel_bootstrap_log("mac_policy_initmach");\n\tmac_policy_initmach();'),
    ]
    # A3 v0.30: post-root-mount progress markers, no behavior changes.
    changes["bsd/kern/bsd_init.c"] += [
        ('\tinit_rootvnode = NULLVP;  /* use rootvnode after this point */', '\tinit_rootvnode = NULLVP;  /* use rootvnode after this point */\n\tsweet_early_mark(377, "A3 root vnode established");'),
        ('\t\tdevfs_kernel_mount(mounthere);', '\t\tdevfs_kernel_mount(mounthere);\n\t\tsweet_early_mark(378, "A3 devfs mounted");'),
        ('\tbsd_utaskbootstrap();', '\tbsd_utaskbootstrap();\n\tsweet_early_mark(379, "A3 user task bootstrap returned");'),
        ('\tload_init_program(p);', '\tsweet_early_mark(380, "A3 entering load_init_program");\n\tload_init_program(p);'),
    ]
    # A3 v0.31: distinguish an exec attempt from a successful PID1 syscall.
    # Preserve the normal exec, validation, and error paths.
    changes["osfmk/arm64/sweet_early.c"] += [
        ("stage > 380", "stage > 400"),
        ("\t\tmarker_stage = stage - 361;\n\t\tmarker_y = 500u;", "\t\tif (stage <= 380u) {\n\t\t\tmarker_stage = stage - 361;\n\t\t\tmarker_y = 500u;\n\t\t} else {\n\t\t\tmarker_stage = stage - 381;\n\t\t\tmarker_y = 488u;\n\t\t}"),
    ]
    changes["bsd/kern/kern_exec.c"] = [
        ("load_init_program(proc_t p)\n{", "load_init_program(proc_t p)\n{\n\textern void sweet_early_mark(unsigned int, const char *);\n\tsweet_early_mark(381, \"A3 entered init loader\");"),
        ("\t(void) mach_vm_allocate_kernel(map, &scratch_addr, map_page_size, VM_FLAGS_ANYWHERE, VM_KERN_MEMORY_NONE);", "\t(void) mach_vm_allocate_kernel(map, &scratch_addr, map_page_size, VM_FLAGS_ANYWHERE, VM_KERN_MEMORY_NONE);\n\tsweet_early_mark(382, \"A3 init scratch allocation returned\");"),
        ("\treturn execve(p, &init_exec_args, retval);", "\textern void sweet_early_mark(unsigned int, const char *);\n\tsweet_early_mark(383, \"A3 invoking initial execve\");\n\terror = execve(p, &init_exec_args, retval);\n\tsweet_early_mark(error == 0 ? 384u : 385u, \"A3 initial execve result\");\n\treturn error;"),
    ]
    changes["bsd/kern/kern_prot.c"] = [
        ("getpid(proc_t p, __unused struct getpid_args *uap, int32_t *retval)\n{\n\t*retval = proc_getpid(p);", "getpid(proc_t p, __unused struct getpid_args *uap, int32_t *retval)\n{\n\t*retval = proc_getpid(p);\n\tif (*retval == 1) {\n\t\tstatic bool marked;\n\t\tif (!marked) {\n\t\t\tmarked = true;\n\t\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\t\tsweet_early_mark(386, \"A3 PID1 executed getpid syscall\");\n\t\t}\n\t}"),
    ]
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
