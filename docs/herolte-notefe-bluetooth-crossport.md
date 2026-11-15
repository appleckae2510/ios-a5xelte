# Galaxy S7 (herolte) cross-port reference: egemengunel/ios-a5xelte

Status: **experimental reference branch only**. No claim that Bluetooth works on the Galaxy S7. Do not flash until a complete BOOT backup, successful build, image checks, and an on-device test.

## Sources inspected (2026-11-15)

- https://github.com/egemengunel/ios-a5xelte/tree/gracerlte
- [0432: BCM4359 pins and clock-register probe](https://github.com/egemengunel/ios-a5xelte/blob/gracerlte/xnu/patches/0432-notefe-bt-probe.patch)
- [0433: UART1/HCI bring-up](https://github.com/egemengunel/ios-a5xelte/blob/gracerlte/xnu/patches/0433-notefe-bt-uart-hci.patch)
- [0434: owner-provided .hcd firmware](https://github.com/egemengunel/ios-a5xelte/blob/gracerlte/xnu/patches/0434-notefe-bt-patch.patch)
- [0435: iOS kernel-control / Skywalk transport](https://github.com/egemengunel/ios-a5xelte/blob/gracerlte/xnu/patches/0435-notefe-bt-transport.patch)
- [0436: HCI/LE event counters](https://github.com/egemengunel/ios-a5xelte/blob/gracerlte/xnu/patches/0436-notefe-bt-event-counts.patch)
- [GRACERLTE_PROGRESS.md](https://github.com/egemengunel/ios-a5xelte/blob/gracerlte/GRACERLTE_PROGRESS.md), Nov 14-15, 2026

Upstream's `herolte` branch has no dedicated Bluetooth patches. Its `gracerlte` branch is the relevant comparison because Note FE and S7 use Exynos8890/BCM4359 family hardware, **not because their DTBs and firmware are interchangeable**. The upstream `herolte-ios18` branch includes some unrelated Beryllium Qualcomm Bluetooth code; do not copy it for the S7.

## What was ported into experimental patch 0341

- Read clock source from CMU_TOP (PLL, BUS0 mux, UART1 source and divider), following Note FE 0433, rather than assuming a hard-coded 76.8 MHz S7 UART1 rate.
- Keep the parent selected by the bootloader; verify CMU_PERIC1's one-hot mux status instead of forcing a different parent.
- Use the Exynos8890 UART1 `UFRACVAL` fractional *number* (0..15) at offset `0x2c`, not legacy bit-mask `UDIVSLOT` encoding.
- Reject unknown BUS1 clock selection and unrepresentable baudrates rather than guessing.
- Print relevant parent/PLL/divider information for the next real-device bootlog.

On the **Note FE only**, the source reports 132 MHz UART1 (BUS0_PLL 1056 MHz /2 /4) and `UBRDIV=70, UFRACVAL=9` for 115200 baud. The actual values on the **Galaxy S7 still require measurement**.

## Remaining Bluetooth work (not included in patch 0341)

1. Build green, retain known-good BOOT, verify the S7 UART loopback at measured 115200 baud; then verify HCI_Reset and Read_Local_Version (Broadcom manufacturer 0x000f), with a timeout.
2. Load the exact BCM4359 .hcd for this phone from a lawful/owner-provided backup; verify each record, Launch_RAM, and post-firmware HCI. **Do not copy Note FE firmware to S7 solely because the chipset matches.**
3. The current S7 kernel control `com.apple.uart.bluetooth` is not the complete Apple path; study Note FE 0435 for `com.apple.uart.sk.bluetooth` and the Skywalk channel. This is a substantial transport port, not a one-line patch.
4. Validate launchd/bluetoothd and BlueTool starting order, ADT Bluetooth node, and MobileGestalt expectations. Do not mark the hardware as working because a UI switch appears.
5. Observe genuine HCI LE scan commands and advertising events before declaring scanning/pairing functional. Avoid silently falsifying controller status except with a clearly labeled, separately tested compatibility shim.

## Other hardware reference areas

- Note FE `0437` onward: camera sensor, MCLK, CSIS and frame capture **for later port research only**. Camera routing and PMIC rails differ; never write those registers on S7 without board-specific confirmation.
- Note FE `0418`-`0420`: screen brightness/backlight control, adaptable only after identifying S7 panel/backlight control.
- Note FE `0469`-`0470`: load-based CPU governor; performance/temperature risks demand S7 telemetry.
- Keep current S7 GPU, WLAN, touchscreen and audio patches unless a measured regression warrants a change.

## Build/test discipline

All experimental changes go to branch `experiment/notefe-bluetooth-crossport`; the stable `herolte` branch, credits-only boot splash and existing BOOT images remain unchanged. CI must assert that patch 0341 was applied (patch tools may silently skip malformed changes). Boot on hardware only with existing TWRP recovery and verifiable BOOT backup/restore path. A successful compile or a live HCI port is not proof of iOS Bluetooth scanning/pairing.

Source attribution: engineering ideas taken from egemengunel's gracerlte changes; prior ios-a5xelte and ios-sweet creators retain their credits. This document paraphrases reference material and is not a claim of authorship of upstream code.
