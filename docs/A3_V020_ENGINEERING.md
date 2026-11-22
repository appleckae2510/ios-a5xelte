# Galaxy A3 2017 – v0.20 engineering candidate

Date: 2026-11-22
Device: Samsung SM-A320FL / a3y17lte
Base: native iOS 16.7.16 (20H392) boot v0.18; v0.19 only modified boot arguments.

## Verified device evidence
- dmd and ScreenTimeAgent terminate with SIGABRT (6) at the same unslid
  shared-cache PC: 0x1c0617198 in v0.17, and 0x1c0617198 in v0.18.
  This is a shared crash path, NOT proof of the original failure cause.
- tccd reports OS_REASON_SANDBOX, "com.apple.tccd: profile not found".
- locationd reports SIGTRAP (5).
- Apple boot logo and framebuffer activity do not prove SpringBoard ready.
- A3 device reports 10–14 fps, ~28 ms full-frame CPU copy; cpus=1.

## Code changes
- 0412: arm the next VSync timer before the CPU framebuffer present
  rather than after it. Timer callbacks share the IOWorkLoop, so rearming
  does not start a second concurrent CPU copy. Avoid per-frame
  IOMallocData/IOFreeData for the 0x46c byte pending record: use the
  callback's stack snapshot, copy under the existing fLock.
- 0413: log a capped first set of tccd / dmd / ScreenTimeAgent /
  locationd / SpringBoard Sandbox calls (op 1 / 0x43 / EPERM).
  Preserve the existing CodeDirectory allowlist and deny by default.

## Known limits / do not falsely declare fixed
- tccd's named profile may require real Seatbelt/profile data and APIs,
  not merely a successful return from Sandbox op 1.
- dmd / ScreenTimeAgent shared abort must be symbolicated using the
  exact 20H392 dyld_shared_cache_arm64 (and matching root image).
- locationd SIGTRAP is not yet symbolicated.
- The framebuffer is still software-rendered and cpus=1. A 30 Hz
  requested refresh does not imply that 30 frames/s can be sustained.
- Enabling SMP on Exynos7870 requires board-specific MPIDR/PSCI/GIC
  audit. The donor's SMP code assumes Aff1 core IDs and must not simply
  be exposed with cpus=2 on the A3 without a separate bring-up.
- A successful GitHub Actions build tests kernel binary and host
  regressions; only a phone can confirm the boot and real fps.

## Test images
Use v0.20 PERFORMANCE (sweetfb_hz=30, hidden console, crash scanning off)
for FPS comparisons, and v0.20 DIAGNOSE (console visible, heap scans for
named daemons) to capture the next FIRST failure.
Back up BOOT and full USERDATA; flash Boot only in TWRP. Never wipe
USERDATA as part of a BOOT-only upgrade.
