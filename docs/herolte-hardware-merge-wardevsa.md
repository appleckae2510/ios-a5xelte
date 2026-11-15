# Combined Galaxy S7 iOS Hardware & Bluetooth experimental build

Base: `experiment/notefe-bluetooth-crossport` (BCM4359 UART/clock bring-up; unverified on physical S7).
Additional hardware source: [wardevsa/ios-a5xelte herolte](https://github.com/wardevsa/ios-a5xelte/tree/herolte), its 2026-11-14 changes. Source patch content retained apart from explicitly identified safety/default changes.

## Added patches (in build order)

| New path | Upstream Wardevsa source | Notes |
| --- | --- | --- |
| 0342-herolte-vgr0-early-splash-safe.patch | 0337-vgr0-test-early-fb2-fix.patch | Fix FB2 fallback, match existing 0336 VGR0 test default off |
| 0343-herolte-vgr0-display-present.patch | 0338-vgr0-present.patch | Hardware VGR0 scaling for iOS; disable with `herovgr=0`; opt-in color-test `herovgrtest=1` |
| 0344-herolte-haptic-driver.patch | 0339-haptic-motor.patch | Shared I2C1 mutex, MAX77854 / haptic driver; boot test disabled by default, opt in `herohaptictest=1`; disable driver with `herohaptic=0` |
| 0345-herolte-mfc-readonly-probe.patch | 0340-mfc-probe.patch | **Read-only** Exynos 8890 MFC register probe; no H.264/HEVC decoder |
| 0346-herolte-haptic-pwm-prescaler.patch | 0341-haptic-pwm-prescaler.patch | Safe conditional PWM prescaler fix when timer0 not running |

All patch IDs are renamed to avoid the original 0338–0341 collision with the experimental Bluetooth patches 0338–0341. We intentionally did **not** overwrite existing Bluetooth or audio source. The existing 0336 experimental VGR0 patch remains in place (it differs from upstream 0336 only in two default-test lines). Patch 0342 is adjusted to match those two lines. The normal 0338 VGR0 test had an eight-second four-colour splash; the combined branch keeps `herovgrtest` default OFF to preserve the XNU-loader credits screen until iOS takes the display.

## Limits and validation

Building cleanly and a structurally valid Android BOOT IMG are necessary but insufficient. Before actual flash, keep a known-good BOOT image and recovery access. Test on **Samsung Galaxy S7 Exynos SM-G930F** only; do not transplant to Snapdragon or G935 without rechecking device tree and bootloader. Retain original ADT, ramdisk, DT and storage layout. If video display is unstable: test with `herovgr=0` at the next repack; if haptic trouble: `herohaptic=0`; if Bluetooth fails: persistent HCI log is required. New MFC probe is not a working decoder and Wardevsa's vibrate test does not prove full iOS CoreHaptics integration.

## Credits and licensing

Engineering source and attribution to `wardevsa/ios-a5xelte`, `egemengunel/ios-a5xelte` and original `ios-sweet` project. Keep original copyright headers, provenance and licensing terms.
