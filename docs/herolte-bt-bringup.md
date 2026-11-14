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
4. Use herobt=1 only. Do NOT use herobt=2 or remove bluetoothd from heronoexec yet.
5. After boot, pull the persistent log via tools/herolte-log-pull.py and inspect HEROLTE BT lines.

Read-only MMIO may still fail if the hardware clocks are gated, so this stage is experimental.

## Unfinished integration gates

1. Determine UART1 clock parent, rate, pinmux and gating from the new register dump.
2. Initialise UART and RTS/CTS; verify real HCI Reset and Read Local Version commands.
3. Load an owner-sourced matching Murata or Semco BCM4359 .hcd patchram and verify post-load firmware.
4. Implement reliable H4 packet framing and iOS kernel control transport com.apple.uart.bluetooth.
5. Supply BlueTool startup integration and Apple Device Tree bluetooth node, then enable bluetoothd.
6. Verify iOS Settings toggle, scanning, pairing, reconnect, and audio. None of these is achieved by the probe.

Status: Successful boot and MMIO snapshot, no working Bluetooth controller integration yet.
