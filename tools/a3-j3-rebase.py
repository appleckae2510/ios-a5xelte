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
    # A3 v0.32: readable boot progress in three rows between the panic
    # barcode (ends at y=435) and stage grid (starts at y=488).
    # Use the same mapped framebuffer and existing font; no printf, locks,
    # allocator, new MMIO mapping, timer, or policy changes.
    progress_text = r'''
	/* A3 status strip, 3 x 90 characters, inside the existing aperture. */
	if (label && ((stage >= 367u && stage <= 388u) ||
	    (stage >= 41u && stage <= 59u) || stage == 326u || stage == 80u)) {
		extern unsigned char iso_font[256 * 16];
		static unsigned int a3_progress_row;
		unsigned int y0 = 440u + (a3_progress_row++ % 3u) * 16u;
		uint32_t fg = (stage == 326u || stage == 80u || stage == 385u ||
		    stage == 387u) ? 0xffff6060u : 0xffffffffu;
		unsigned int ended = 0u;
		for (unsigned int col = 0; col < 90u; col++) {
			unsigned char ch;
			if (col == 0u) {
				ch = '[';
			} else if (col == 1u) {
				ch = '0' + (stage / 100u) % 10u;
			} else if (col == 2u) {
				ch = '0' + (stage / 10u) % 10u;
			} else if (col == 3u) {
				ch = '0' + stage % 10u;
			} else if (col == 4u) {
				ch = ']';
			} else if (col == 5u) {
				ch = ' ';
			} else {
				ch = ended ? ' ' : (unsigned char)label[col - 6u];
				if (!ch) {
					ended = 1u;
					ch = ' ';
				}
			}
			const unsigned char *glyph = iso_font + (unsigned int)ch * 16u;
			for (unsigned int gy = 0; gy < 16u; gy++) {
				volatile uint32_t *row = early_fb +
				    (y0 + gy) * J3_EARLY_STRIDE_PIXELS + col * 8u;
				for (unsigned int gx = 0; gx < 8u; gx++) {
					row[gx] = (glyph[gy] & (1u << gx)) ? fg : 0xff000000u;
				}
			}
		}
		__asm__ volatile("dsb sy" ::: "memory");
	}

'''
    changes["osfmk/arm64/sweet_early.c"] += [
        ("\tunsigned int marker_stage;\n\tunsigned int marker_y;", progress_text + "\tunsigned int marker_stage;\n\tunsigned int marker_y;"),
    ]
    changes["bsd/kern/kern_exec.c"] += [
        ('\tsweet_early_mark(382, "A3 init scratch allocation returned");', '\tsweet_early_mark(scratch_addr ? 382u : 387u, scratch_addr ? "OK: init scratch address allocated" : "ERROR: no init scratch address");'),
        ('\tsweet_early_mark(383, "A3 invoking initial execve");', '\tsweet_early_mark(388, path);\n\tsweet_early_mark(383, "START: initial execve");'),
        ('\tsweet_early_mark(error == 0 ? 384u : 385u, "A3 initial execve result");', '\tsweet_early_mark(error == 0 ? 384u : 385u, error == 0 ? "OK: initial execve returned success" : "ERROR: initial execve failed");'),
    ]
    # A3 v0.33: keep the successful init milestones visible, with the
    # last diagnostic I/O result on a separate row. No storage or policy changes.
    changes["osfmk/arm64/sweet_early.c"] += [
        ("stage <= 388u", "stage <= 394u"),
        ("unsigned int y0 = 440u + (a3_progress_row++ % 3u) * 16u;",
         "unsigned int row = a3_progress_row++ % 3u;\n\t\tif (stage == 383u || stage == 384u || stage == 385u) row = 0u;\n\t\telse if (stage == 386u || stage == 388u) row = 1u;\n\t\telse if (stage >= 389u && stage <= 394u) row = 2u;\n\t\tunsigned int y0 = 440u + row * 16u;"),
        ("stage == 387u) ? 0xffff6060u : 0xffffffffu;",
         "stage == 387u || stage == 390u || stage == 392u) ? 0xffff6060u :\n\t\t    (stage == 384u || stage == 386u || stage == 389u || stage == 391u || stage == 393u ? 0xff70ff90u : 0xffffffffu);"),
    ]
    changes["bsd/kern/kern_prot.c"] += [
        ('"A3 PID1 executed getpid syscall"', '"OK: PID1 running in diagnostic userland"'),
    ]
    changes["bsd/kern/sys_generic.c"] = [
        ("\treturn read_internal(p, uap->fd, uap->cbuf, uap->nbyte, (off_t)-1, 0,\n\t           retval);",
         "\tint error = read_internal(p, uap->fd, uap->cbuf, uap->nbyte, (off_t)-1, 0,\n\t           retval);\n\tif (proc_getpid(p) == 1) {\n\t\tstatic int last = -1;\n\t\tint state = error ? 2 : (*retval > 0 ? 1 : 0);\n\t\tif (state != last) {\n\t\t\tlast = state;\n\t\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\t\tsweet_early_mark(error ? 390u : 389u, error ? \"ERROR: PID1 read failed\" : (*retval > 0 ? \"OK: PID1 read returned data\" : \"PID1 read returned EOF\"));\n\t\t}\n\t}\n\treturn error;"),
        ("\treturn write_internal(p, uap->fd, uap->cbuf, uap->nbyte, (off_t)-1, 0,\n\t           NULL, retval);",
         "\tint error = write_internal(p, uap->fd, uap->cbuf, uap->nbyte, (off_t)-1, 0,\n\t           NULL, retval);\n\tif (proc_getpid(p) == 1) {\n\t\tstatic int last = -1;\n\t\tint state = error ? 2 : (*retval > 0 ? 1 : 0);\n\t\tif (state != last) {\n\t\t\tlast = state;\n\t\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\t\tsweet_early_mark(error ? 392u : 391u, error ? \"ERROR: PID1 write failed\" : (*retval > 0 ? \"OK: PID1 write transferred data\" : \"PID1 write returned zero\"));\n\t\t}\n\t}\n\treturn error;"),
    ]
    changes["bsd/kern/sys_pipe.c"] = [
        ("\tproc_fdunlock(p);\n\treturn 0;\n\nfreepipes:", "\tproc_fdunlock(p);\n\tif (proc_getpid(p) == 1) {\n\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\tsweet_early_mark(393u, \"OK: PID1 pipe created\");\n\t}\n\treturn 0;\n\nfreepipes:"),
    ]
    # A3 v0.34: separate persistent storage diagnostic line.
    # No new register access, partition writes or root selection changes.
    changes["osfmk/arm64/sweet_early.c"] += [
        ("(stage >= 367u && stage <= 394u)", "(stage >= 367u && stage <= 400u)"),
        ("unsigned int y0 = 440u + row * 16u;",
         "unsigned int y0 = (stage >= 395u && stage <= 400u) ? 424u : 440u + row * 16u;"),
        ("stage == 390u || stage == 392u) ? 0xffff6060u :",
         "stage == 390u || stage == 392u || stage == 396u || stage == 398u) ? 0xffff6060u :"),
        ("stage == 391u || stage == 393u ? 0xff70ff90u",
         "stage == 391u || stage == 393u || stage == 397u || stage == 399u ? 0xff70ff90u"),
    ]
    changes["bsd/dev/j3y17lte_emmc.c"] += [
        ("void\nj3y17lte_emmc_probe(void)\n{\n\tif (!emmc_map_host()) {\n\t\t(void)emmc_find_root_partition();\n\t}\n}",
         "void\nj3y17lte_emmc_probe(void)\n{\n\textern void sweet_early_mark(unsigned int, const char *);\n\tsweet_early_mark(395u, \"START: eMMC controller probe\");\n\tint error = emmc_map_host();\n\tif (error) {\n\t\tsweet_early_mark(396u, \"ERROR: eMMC controller mapping failed\");\n\t\treturn;\n\t}\n\tsweet_early_mark(397u, \"OK: eMMC mapped; START: read GPT\");\n\terror = emmc_find_root_partition();\n\tsweet_early_mark(error ? 398u : 399u, error ? \"ERROR: eMMC GPT/partition read failed\" : \"OK: eMMC GPT and requested partition found\");\n}"),
    ]
    # A3 v0.35: inspect only the selected partition's filesystem signature.
    # Preserve the read-only storage policy and the diagnostic RAM root.
    fs_probe_old = r'''	sweet_early_mark(error ? 398u : 399u, error ? "ERROR: eMMC GPT/partition read failed" : "OK: eMMC GPT and requested partition found");'''
    fs_probe_new = r'''	if (error) {
		sweet_early_mark(398u, "ERROR: eMMC GPT/partition read failed");
		return;
	}
	sweet_early_mark(400u, "START: GPT OK; reading filesystem header");
	if (emmc_nsectors < 3 || emmc_first_lba > UINT32_MAX - 2u) {
		sweet_early_mark(398u, "ERROR: partition too small or out of range");
		return;
	}
	uint8_t header[512] = { 0 };
	error = emmc_read_sector((uint32_t)(emmc_first_lba + 2u), header);
	if (error) {
		sweet_early_mark(398u, "ERROR: filesystem header read failed");
		return;
	}
	if (header[0] == 0x48u && header[1] == 0x2bu) {
		sweet_early_mark(399u, "OK: GPT and HFS+ signature found");
	} else if (header[0] == 0x48u && header[1] == 0x58u) {
		sweet_early_mark(399u, "OK: GPT and HFSX signature found");
	} else if (header[56] == 0x53u && header[57] == 0xefu) {
		sweet_early_mark(400u, "GPT OK: ext filesystem signature; not HFS+");
	} else {
		sweet_early_mark(400u, "GPT OK: filesystem signature unknown");
	}'''
    changes["bsd/dev/j3y17lte_emmc.c"] += [
        (fs_probe_old, fs_probe_new),
    ]
    # A3 v0.38: record critical process exit details before coredump/panic.
    # Preserve the normal process-exit and security behavior.
    # Two fixed rows within the existing 2 MiB framebuffer mapping
    # (720*4*712 = 2050560 bytes); outside the existing stage grid.
    changes["osfmk/arm64/sweet_early.c"] += [
        ("unsigned int y0 = (stage >= 395u && stage <= 400u) ? 424u : 440u + row * 16u;",
         "unsigned int y0 = stage == 394u ? 696u : (stage == 388u ? 680u : ((stage >= 395u && stage <= 400u) ? 424u : 440u + row * 16u));"),
        ("stage == 396u || stage == 398u) ? 0xffff6060u :",
         "stage == 396u || stage == 398u || stage == 394u) ? 0xffff6060u :"),
    ]
    changes["bsd/kern/kern_prot.c"] += [
        ('"OK: PID1 running in diagnostic userland"', '"OK: PID1 executed getpid syscall"'),
    ]
    changes["bsd/kern/kern_exit.c"] = [
        ("\tchar *exit_reason_desc = exit_reason_get_string_desc(p->p_exit_reason);",
         "\tchar a3_exit_line[84];\n\textern void sweet_early_mark(unsigned int, const char *);\n\t(void)snprintf(a3_exit_line, sizeof(a3_exit_line), \"EXIT: %.16s pid=%d signal=%d status=%d\", p->p_name, proc_getpid(p), WTERMSIG(rv), WEXITSTATUS(rv));\n\tsweet_early_mark(394u, a3_exit_line);\n\tchar *exit_reason_desc = exit_reason_get_string_desc(p->p_exit_reason);"),
    ]
    # A3 v0.39: explicit, bounded USERDATA write opt-in. The recovery
    # inventory gives 11853807 KiB USERDATA and 15388672 KiB total disk.
    # The candidate start assumes a standard 34-sector end GPT reservation.
    # Do NOT authorize writes unless live, CRC-checked GPT matches exactly.
    changes["bsd/dev/j3y17lte_emmc.c"] += [
        ("/* The J3 GPT extent is not an A3 extent. Compile-only. */\n\tenable_write = 0;",
         "/* A3: write access must be explicitly requested and verified below. */"),
        ("emmc_first_lba == 6713344ULL && emmc_nsectors == 24051712ULL",
         "emmc_first_lba == 7069696ULL && emmc_nsectors == 23707614ULL"),
        ("\tif (enable_write == 1 && !emmc_writable) {",
         "\tif (emmc_writable) {\n\t\tuint8_t a3_header[512] = {0};\n\t\tif (emmc_read_sector((uint32_t)(emmc_first_lba + 2u), a3_header) != 0 ||\n\t\t    a3_header[0] != 0x48u || a3_header[1] != 0x58u ||\n\t\t    a3_header[2] != 0u || a3_header[3] != 5u) {\n\t\t\temmc_writable = false;\n\t\t}\n\t}\n\tif (enable_write == 1 && !emmc_writable) {"),
        ("\t\t*dev = emmc_bdev;", "\t\t*dev = emmc_bdev;") if False else
        ("\t*dev = emmc_bdev;\n\treturn 0;\n}",
         "\t*dev = emmc_bdev;\n\treturn 0;\n}\n\nbool\nj3y17lte_emmc_root_writable(dev_t dev)\n{\n\treturn emmc_ready && emmc_writable && dev == emmc_bdev;\n}"),
    ]
    # Only the verified eMMC root can become writable; no generic VFS or
    # filesystem protection changes, and no new raw-write interfaces.
    changes["bsd/vfs/vfs_subr.c"] = [
        ('\t\tmp->mnt_devvp = rootvp;\n#if defined(ARM64_BOARD_CONFIG_SWEET)',
         '\t\tmp->mnt_devvp = rootvp;\n#if defined(ARM64_BOARD_CONFIG_J3Y17LTE)\n\t\t{\n\t\t\textern bool j3y17lte_emmc_root_writable(dev_t);\n\t\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\t\tuint32_t rootrw = 0;\n\t\t\tif (PE_parse_boot_argn("rootrw", &rootrw, sizeof(rootrw)) && rootrw == 1u) {\n\t\t\t\tif (j3y17lte_emmc_root_writable(rootdev)) {\n\t\t\t\t\tmp->mnt_flag &= ~MNT_RDONLY;\n\t\t\t\t\tsweet_early_mark(399u, "USERDATA RW authorized; mounting root");\n\t\t\t\t} else {\n\t\t\t\t\tsweet_early_mark(398u, "RW refused: USERDATA geometry/header mismatch");\n\t\t\t\t}\n\t\t\t}\n\t\t}\n#elif defined(ARM64_BOARD_CONFIG_SWEET)'),
    ]
    # A3 v0.40: measure GPT geometry and the mount failure without guessing
    # a write extent. Explicitly keep the write driver disabled for this test.
    changes["bsd/dev/j3y17lte_emmc.c"] += [
        ("/* A3: write access must be explicitly requested and verified below. */",
         "/* A3 v0.40: measure geometry before permitting any writes. */\n\tenable_write = 0;\n\t{\n\t\tchar a3_geometry[84];\n\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\t(void)snprintf(a3_geometry, sizeof(a3_geometry), \"GPT %.15s start=%llu sectors=%llu\", emmc_partition_name, (unsigned long long)emmc_first_lba, (unsigned long long)emmc_nsectors);\n\t\tsweet_early_mark(401u, a3_geometry);\n\t}"),
    ]
    changes["osfmk/arm64/sweet_early.c"] += [
        ("stage > 400", "stage > 402"),
        ("(stage >= 367u && stage <= 400u)", "(stage >= 367u && stage <= 402u)"),
        ("unsigned int y0 = stage == 394u ?", "unsigned int y0 = stage == 401u ? 712u : (stage == 402u ? 664u : (stage == 394u ?"),
        ("424u : 440u + row * 16u));", "424u : 440u + row * 16u))));"),
        ("\tunsigned int marker_stage;\n\tunsigned int marker_y;", "\tif (stage >= 401u) {\n\t\treturn; /* dedicated text only, within the mapped framebuffer */\n\t}\n\tunsigned int marker_stage;\n\tunsigned int marker_y;"),
    ]
    changes["bsd/vfs/vfs_syscalls.c"] = [
        ("\tif (need_nameidone) {\n\t\tnameidone(&nd);\n\t}\n\n\treturn error;\n}\n\n/*\n * common mount implementation",
         "\tif (need_nameidone) {\n\t\tnameidone(&nd);\n\t}\n\tif (proc_getpid(p) == 3) {\n\t\tchar a3_mount_path[40] = {0};\n\t\tchar a3_mount_line[84];\n\t\tsize_t a3_path_len = 0;\n\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\tif (copyinstr(uap->path, a3_mount_path, sizeof(a3_mount_path), &a3_path_len)) {\n\t\t\tstrlcpy(a3_mount_path, \"(unavailable)\", sizeof(a3_mount_path));\n\t\t}\n\t\t(void)snprintf(a3_mount_line, sizeof(a3_mount_line), \"MOUNT %.12s %.32s errno=%d flags=%x\", fstypename, a3_mount_path, error, (unsigned int)flags);\n\t\tsweet_early_mark(402u, a3_mount_line);\n\t}\n\n\treturn error;\n}\n\n/*\n * common mount implementation"),
    ]
    # A3 v0.41: use the actual CRC-checked GPT geometry measured on v0.40.
    # Preserve the HFSX version guard, explicit opt-in and per-sector bounds.
    # No changes to bindfs authorization, error returns or panic behavior.
    changes["bsd/dev/j3y17lte_emmc.c"] += [
        ("emmc_first_lba == 7069696ULL && emmc_nsectors == 23707614ULL",
         "emmc_first_lba == 7069696ULL && emmc_nsectors == 23707615ULL"),
        ("/* A3 v0.40: measure geometry before permitting any writes. */\n\tenable_write = 0;",
         "/* A3 v0.41: exact measured geometry and HFSX guard required for opt-in. */"),
    ]
    changes["osfmk/arm64/sweet_early.c"] += [
        ("stage > 402", "stage > 403"),
        ("(stage >= 367u && stage <= 402u)", "(stage >= 367u && stage <= 403u)"),
        ("unsigned int y0 = stage == 401u ? 712u :", "unsigned int y0 = stage == 403u ? 648u : stage == 401u ? 712u :"),
    ]
    changes["bsd/vfs/vfs_syscalls.c"] += [
        ("\t\tsweet_early_mark(402u, a3_mount_line);",
         "\t\tsweet_early_mark(402u, a3_mount_line);\n\t\tif (strcmp(fstypename, \"bindfs\") == 0) {\n\t\t\tchar a3_source[56] = {0};\n\t\t\tsize_t a3_source_len = 0;\n\t\t\tint a3_copy_error = copyinstr(uap->data, a3_source, sizeof(a3_source), &a3_source_len);\n\t\t\tif (a3_copy_error == 0) {\n\t\t\t\t(void)snprintf(a3_mount_line, sizeof(a3_mount_line), \"BINDFS source: %s target_lookup=%s\", a3_source, need_nameidone ? \"OK\" : \"FAIL\");\n\t\t\t} else {\n\t\t\t\t(void)snprintf(a3_mount_line, sizeof(a3_mount_line), \"BINDFS source copy errno=%d target_lookup=%s\", a3_copy_error, need_nameidone ? \"OK\" : \"FAIL\");\n\t\t\t}\n\t\t\tsweet_early_mark(403u, a3_mount_line);\n\t\t}"),
    ]
    # A3 v0.42: expose critical boot-task abort details without changing
    # code signing, mount authorization, exit or panic behavior.
    changes["osfmk/arm64/sweet_early.c"] += [
        ("stage > 403", "stage > 407"),
        ("(stage >= 367u && stage <= 403u)", "(stage >= 367u && stage <= 407u)"),
        ("unsigned int y0 = stage == 403u ?", "unsigned int y0 = stage == 404u ? 176u : stage == 405u ? 192u : stage == 406u ? 208u : stage == 407u ? 224u : stage == 403u ?"),
    ]
    changes["bsd/kern/kern_exit.c"] += [
        ("\tchar *exit_reason_desc = exit_reason_get_string_desc(p->p_exit_reason);",
         "\tchar *exit_reason_desc = exit_reason_get_string_desc(p->p_exit_reason);\n\tif (p->p_exit_reason != OS_REASON_NULL) {\n\t\t(void)snprintf(a3_exit_line, sizeof(a3_exit_line), \"REASON ns=%u code=0x%llx\", (unsigned)p->p_exit_reason->osr_namespace, (unsigned long long)p->p_exit_reason->osr_code);\n\t\tsweet_early_mark(404u, a3_exit_line);\n\t\tif (exit_reason_desc) sweet_early_mark(405u, exit_reason_desc);\n\t} else {\n\t\tsweet_early_mark(404u, \"REASON: no OS exit reason recorded\");\n\t}"),
        ("\treturn 0;\n}\n\nint\nos_fault_with_payload", "\treturn 0;\n}\n\nint\nos_fault_with_payload") if False else
        ("abort_with_payload(struct proc *cur_proc, struct abort_with_payload_args *args,\n    __unused void *retval)\n{",
         "abort_with_payload(struct proc *cur_proc, struct abort_with_payload_args *args,\n    __unused void *retval)\n{\n\tif (strncmp(cur_proc->p_name, \"launchd_cache_lo\", 16) == 0) {\n\t\tchar a3_abort[84] = {0};\n\t\tsize_t a3_len = 0;\n\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\tif (args->reason_string && copyinstr(args->reason_string, a3_abort, sizeof(a3_abort), &a3_len) == 0) {\n\t\t\tsweet_early_mark(406u, a3_abort);\n\t\t}\n\t}"),
    ]
    changes["bsd/kern/sys_generic.c"] += [
        ("\tint error = write_internal(p, uap->fd, uap->cbuf, uap->nbyte, (off_t)-1, 0,\n\t           NULL, retval);",
         "\tif (uap->fd == 2 && strncmp(p->p_name, \"launchd_cache_lo\", 16) == 0 && uap->nbyte != 0) {\n\t\tchar a3_stderr[84] = {0};\n\t\tsize_t a3_n = MIN((size_t)uap->nbyte, sizeof(a3_stderr) - 1);\n\t\tif (copyin(uap->cbuf, a3_stderr, a3_n) == 0) {\n\t\t\tfor (size_t j = 0; j < a3_n; ++j) {\n\t\t\t\tunsigned char c = (unsigned char)a3_stderr[j];\n\t\t\t\tif (c < 32 || c > 126) a3_stderr[j] = ' ';\n\t\t\t}\n\t\t\textern void sweet_early_mark(unsigned int, const char *);\n\t\t\tsweet_early_mark(407u, a3_stderr);\n\t\t}\n\t}\n\tint error = write_internal(p, uap->fd, uap->cbuf, uap->nbyte, (off_t)-1, 0,\n\t           NULL, retval);"),
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
