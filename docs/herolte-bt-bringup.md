# Galaxy S7 SM-G930F: BCM4359 Bluetooth bring-up

Updated 2026-11-14. This is diagnostic work, not yet functioning iOS Bluetooth.

## Confirmed by device log, herobt=1

- XNU started with the 0335 kernel and continued to iOS after the read-only probe.
- UART1 MMIO base 0x14c20000: ULCON=0, UCON=0x3000, UTRSTAT=0x6, UBRDIV=0, UDIVSLOT=0.
- GPIO snapshots: GPJ1_7 cfg=0/dat=0x23; GPI2_3 cfg=0x1/dat=0x7; GPA2_3 cfg=0/dat=0x54.
- Probe reported "snapshot complete; no writes". There is NO evidence of HCI packets or firmware running.
- bluetoothd is disabled in the current heronoexec boot argument. It must remain so until the HCI transport works.
- Full device-specific logs and proprietary firmware must remain off public GitHub.

## Next diagnostic: UART1 clocks (read-only)

CMU_PERIC1 physical base = 0x14c80000. In XNU patch 0335, herobt=1 now samples:

| Purpose | Offset | Notes |
| --- | --- | --- |
| UART1 mux selector | 0x0224 | raw |
| UART1 mux status | 0x0624 | raw |
| PCLK gate | 0x0800 | UART1 bit 13 |
| UART1 SCLK gate | 0x0860 | UART1 bit 0 |
| Manual PCLK gate | 0x1800 | raw |
| Manual SCLK gate | 0x1860 | raw |
| SCLK status | 0x1c60 | raw |
| UART1 QSTATE | 0x2424 | raw, meaning to be established |

Reference: https://lkml.iu.edu/hypermail/linux/kernel/2510.2/02932.html (Linux CMU_PERIC1)
UART1 base/256-byte FIFO: https://www.spinics.net/lists/linux-samsung-soc/msg96164.html

## Safe test

1. Rebuild XNU in GitHub Actions with MACHINE_CONFIG=HEROLTE; verify artifact is from this change, not the old successful build.
2. Repack a new BOOT candidate using the known working loader and device-specific ADT and Samsung DTBH.
3. Preserve working hero_out.img and a verified BOOT partition backup outside the phone, with a recovery path through TWRP.
4. The original read-only diagnostic uses herobt=1; the new active test uses herobt=2. Neither enables bluetoothd or an iOS Bluetooth controller.
5. After boot, pull the persistent log via tools/herolte-log-pull.py and inspect HEROLTE BT lines.

Read-only MMIO may still fail if the hardware clocks are gated, so this stage is experimental.

## Active UART+HCD code, 2026-11-14

PR #2 (commit 62b506919bb3398e62ad6ebfb52b39bde7b69103) adds the first **active**
herobt=2 stage (currently undergoing GitHub Actions build test).

- UART1 clock source is set to XTCXO 76.8 MHz; only UART1 QSTATE and the UART1
  PCLK/SCLK manual gates are modified.
- The Samsung UART divisors are set for 115200 baud, 8N1 with RTS/CTS.
- GPJ1_7 BT_EN and GPI2_3 BT_WAKE are toggled after pin mux setup.
- HCI Reset 0x0c03 and Read Local Version 0x1001 are sent.
- If an owner-sourced /private/var/herolte/bt/fw.hcd is present, its 0xfc4c
  Write_RAM + final 0xfc4e Launch_RAM commands are validated and sent after
  Download Minidriver 0xfc2e. Firmware is not committed to GitHub.
- Post-firmware HCI Reset and version are logged; BT_EN returns LOW at the
  end of the test. No iOS H4 transport, bluetooth service or daemon is
  enabled; the userland remains unchanged.

The owner's HCD files, extracted from their own S7, have validated command
counts: BCM4359C0 Murata 304; BCM4359C0 Semco 305. **The correct module
is unknown**. Do not substitute firmware for a different module. A separate
host-side drop package updater retains all existing GPU, Wi-Fi, audio, autorun
and other entries in HERODRP1 instead of replacing the package wholesale.

The test was not executed on the phone when this text was recorded.
Do not flash a new BOOT until its kernel CI build succeeds and a full,
recoverable BOOT backup exists.

## Unfinished integration gates

1. Determine UART1 clock parent, rate, pinmux and gating from the new register dump.
2. Initialise UART and RTS/CTS; verify real HCI Reset and Read Local Version commands.
3. Load an owner-sourced matching Murata or Semco BCM4359 .hcd patchram and verify post-load firmware.
4. Implement reliable H4 packet framing and iOS kernel control transport com.apple.uart.bluetooth.
5. Supply BlueTool startup integration and Apple Device Tree bluetooth node, then enable bluetoothd.
6. Verify iOS Settings toggle, scanning, pairing, reconnect, and audio. None of these is achieved by the probe.

Status: Successful boot and MMIO snapshot, no working Bluetooth controller integration yet.
