# A3 J3-first source rebase — 2026-11-25
Donor: https://github.com/imusingwinxp-ops/j3y17lte-xnu/tree/ad394acd811af83ac55dac9410ac2920e9c51e11
179 donor patches and 3 staging scripts. No donor BOOT image, loader source, ADT or release asset is published in that repository. The build workflow stages the J3 donor series, not the A5XELTE/J7 donor series. The machine target is J3Y17LTE for this compile-only prototype; it is NOT an A3 bootable kernel yet.

A3 hardware verified from all four Samsung DTBH variants in the existing v0.23 image:
- Exynos7870, Cortex-A53 MPIDRs 0,1,2,3,0x100,0x101,0x102,0x103; PSCI SMC CPU_ON 0xc4000003. First cluster resembles the donor. Initial device test must start with one CPU, expand to four, then audit second cluster.
- GICv2 distributor 0x104e1000, CPU interface 0x104e2000. eMMC controller 0x13540000; framebuffer 0x67000000, 720x1280, 2880 bytes/row. DECON 0x14830000.
- RAM banks [0x40000000,0x7e400000) and [0x80000000,0xc0000000). The J3 donor has a different hole boundary (0x7e800000). A3 also reserves modem, GNSS, framebuffer, crypto and video buffers. Do not simply expose the J3 physical aperture. Existing A3 loader supplies only 448 MiB at 0x92000000.
- A3 IST30xx touchscreen on 0x13890000 address 0x50; J3 TD4100 and LCD backlight GPIO must not be driven. A3 eMMC partition geometry is not the J3 geometry.

Source overlay changes A3 platform/display names, panel pitch, and explicitly disables donor-specific input, backlight, storage writes and RAM hot-add. This is a compile-only guard, not a full hardware implementation. The donor's fixed RAM aperture, early markers and firmware handoff still require audit. No changes to security policies in this overlay; inherited donor security behavior has not been qualified and is unsuitable for production. No claim that tccd/dmd/SpringBoard now work.

Next gates before packaging: recover the actual J3 loader and ADT or implement independently documented compatible A3 loader/ADT; model A3 memory reservations and validate all loaded segment/stack/DT ranges; qualify native eMMC/HFSX in read-only mode; validate device-specific boot envelope and then test hardware. Do not flash the compile-only output. Existing A3 branches and v0.23 image are unaffected.

## CI repair 2026-11-25
Run 45620801846 applied the full numbered J3 donor series through 0182 and the A3 overlay, then failed in libsyscall MIG header generation: armv7 rejects IPHONEOS_DEPLOYMENT_TARGET=16.7. Reuse the proven old A3 header-only fix: set the deployment target to 10.0 inside the armv7 MIG branch for iphoneos only. The ARM64 kernel target remains iOS 16.7. This is a build-system fix, not a physical boot fix. Next CI run must qualify it.
