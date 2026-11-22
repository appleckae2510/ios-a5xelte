# A3Y17LTE v0.19 performance profile (2026-11-22)

**Status:** BOOT envelopes validated offline. Physical A320FL FPS not measured.
**Base:** v0.18 source-built kernel SHA256 `079502f1cc083e09251452c961f2b09d7f40b2834f2e34384997be4832a2195c`; existing BOOT SHA256 `37a62b206e9731c3a22f4a87f3c94d33c45a36c2e4694bfa87ad6dcf68221af7`.

## Performance test (does NOT repair daemons)
- Boot args changed only: `sweetfb_hz=30 a5fb_noconsole=1 sweetscan=- sweetiolog=- sweetsample=- sweetnull=-`.
- The donor `xnu/patches/0056-sweet-fb-throttled-present.patch` uses `sweetfb_hz` to select the flush interval from a 60 Hz timer; a target of 30 does not guarantee 30 physically presented frames.
- Prevent repeated SIGABRT heap-scan overhead on the one active Cortex-A53 and stop drawing console glyphs over CoreAnimation.
- No additional CPUs, higher core voltage, or undocumented DVFS changes.
- BOOT: `Galaxy-A3-A320FL-BOOT-v0.19-PERFORMANCE-TEST.img`, SHA256 `8b327b0f7374672685c3fa3c04abcc5f20d513cea9e8fb000a7de7bb1b00ee7c`.

## Visible diagnosis comparison
- `sweetfb_hz=30 a5fb_noconsole=0` with original crash tracing left enabled.
- BOOT: `Galaxy-A3-A320FL-BOOT-v0.19-DIAGNOSE-TEST.img`, SHA256 `39662da3d02b5ff869579732d14ddbee5ca597abdca1f068bc3397860d86ad91`.
- Compare `A5XELTE FB: frames=..., elapsed_ms=..., fps=...` only after launchd and active userland. The diagnostic console adds overhead, so these measurements are not a reliable number for the muted-performance mode.
- Image files distributed through ChatGPT; they are not checked into GitHub.

## Known unresolved blockers
1. `tccd` terminates with OS_REASON_SANDBOX `com.apple.tccd: profile not found`. The A3 policy registered by 0409+0411 is a small compatibility layer, **not** Apple's compiled Seatbelt profiles. Returning success for more unrelated operations would mask missing semantics, not install the profile.
2. `ScreenTimeAgent` and `dmd` keep reaching the same unslid code address `0x1c0617198` (v0.17 slide `0x47974000`; v0.18 slide `0x49234000`), then abort. Symbolication against the *exact installed* 20H392 dyld shared cache is needed before a real function fix.
3. `locationd` SIGTRAP and SpringBoard stuck behind the Apple boot logo are still unproven dependencies. No confirmed GUI / home screen.
4. A3 uses `cpus=1`, CPU software rendering and panel memory copies of about 3.7 MiB/frame. User photo averages about 28 ms per copy and 10-14 frames/s. A 30 Hz present target is a ceiling, not an achieved benchmark.

## Integrity / rollback
- New images and v0.18 rollback retain unchanged kernel, RAMdisk, trust cache and Samsung DTBH; only boot args, wrapper CRC and Android header SHA1 differ.
- Built and checked with local Python script shipped in the ZIP.
- Always backup BOOT and full USERDATA externally first; flash **BOOT only**; BOOT rollback does not undo USERDATA writes.
