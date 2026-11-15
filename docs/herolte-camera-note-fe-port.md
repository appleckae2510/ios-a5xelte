# Galaxy S7 S5K4E6 front camera bring-up (Note FE reference)

**Status: hardware compatibility established from S7's own DTB; only read-only stage-1 probing compiled. No claim that Camera.app works on S7.**

## Sources (2026-11-15)

- Note FE camera progress: https://github.com/egemengunel/ios-a5xelte/blob/gracerlte/docs/gracerlte-camera.md — a front S5K4E6 live preview of about 15 fps is documented there, with significant colour/FOV issues.
- Note FE kernel patches 0437–0445, 0463, 0467: https://github.com/egemengunel/ios-a5xelte/tree/gracerlte/xnu/patches
- Note FE iOS capture userland (camera_device.c, camera_isp.c, inject.c): https://github.com/egemengunel/ios-a5xelte/tree/gracerlte/gracerlte/camera
- S7 hardware: Device Tree extracted directly from owner's herolte Android BOOT image, DTBH v2, 3 FDTs; first FDT begins at offset 0x800 and is 0x2ed1e bytes, and includes a matching FIMC/CSI camera path.

## Matching S7 DT data (not assumptions)

* Front: `/fimc-is_sensor_4e6@6A` — `samsung,exynos5-fimc-is-sensor-4e6`, `id=1`, `position=1`, `mclk_ch=2`, `sensor_i2c_ch=1`, `sensor_i2c_addr=0x6a` (8-bit bus address; 7-bit address 0x35).
* Front CSIS: `/fimc_is_sensor@14100000` — `id=1`, `csi_ch=2`, `reg=0x14100000`.
* Front MCLK GPIO: GPK0 pin 2; reset: GPC0 pin 4; standby: GPC1 pin 1, all present via GPIO phandles.
* Camera PMIC: `/hsi2c@13680000/s2mpb02_pmic@59`; Note FE uses the same PMIC family, but per-rail voltage requirements must be checked against S7's regulator child nodes.
* Rear: `/fimc-is_sensor_2l1@5A`, `/fimc-is_sensor_imx260@34`, plus the companion/preprocessor. Rear path does not become functional from the front camera code.
* DMA reserved memory: `/reserved-memory/camera` at `0xd0800000` with length `0x0e400000`, **never use it for capture until all S7 reserved/secure memory overlaps and mappings are checked**.
* The S7 DT also contains `/phy_cam1_csi@145F1050` and `/iommu-domain_fimc-is/sysmmu@0x141E0000`, matching Note FE's CSI family.

The SM-G930F image contains three revision-specific DTBs (at DTBH offsets 0x800, 0x2f800 and 0x5e800). All three were inspected: they agree on front sensor ID, CSI channel, I2C address, MCLK channel and reset/standby pin indices. GPIO *phandle* numbers differ between DTBs, which is expected; do not hard-code those phandle numbers as physical addresses.

## Integrated into XNU

`xnu/patches/0347-herolte-camera-front-readonly-preflight.patch` adds `herocam=1` as an optional early *read-only* probe:
- logs PMU camera domain configuration/status and CMU TOP sensor clock multiplexers/dividers;
- logs PERIC0 HSI2C9 gate and front-camera pinmux state;
- never writes PMIC, clock, GPIO, sensor I2C, CSIS, SysMMU, or DMA;
- does **not** read CSIS registers while its clock/power domain may be off;
- outputs `HEROLTE CAM:` lines in persistent HEROLTE boot logging.

The previous Bluetooth/VGR0/haptic/MFC patches remain enabled. The original XNU-loader text credits remain unchanged.

## Why the Note FE's live camera is not plug-and-play

A full live preview requires:
1. S7-specific power-up validation for S2MPB02 BUCK and LDO supplies, MCLK, sensor reset and 0x35 model-ID acknowledgment.
2. Safe, S7-specific CSIS2 and SysMMU DMA setup against the reserved memory map, and a working RAW10 capture ring.
3. The kernel `/dev/hakios-camera` API plus an exact matching iOS 16 userspace camera capture plugin installed on the iOS root (mediaserverd, MobileGestalt and ADT configuration); **a kernel BOOT image alone cannot install those dylibs**.
4. White balance, picture rotation, frame timing, autofocus/companion support as later stages.

The Note FE's front-camera example can shorten steps 1–3, but only once logs show the S7 rail state and sensor model; wrong writes to a camera PMIC can affect other devices on shared rails.

Keep a verified BOOT backup. After boot, extract `HEROLTE CAM:` lines from persistent log using the already-provided recovery diagnostic tool; do not flash unverified rear-camera or companion firmware.
