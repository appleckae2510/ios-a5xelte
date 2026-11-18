# A3Y17LTE handoff, 2026-11-17

User requested an iOS 16 port using hoaan1911/ios-on7xelte and the Samsung A3
Android device tree. Implemented a first entry-stage overlay; no phone attached.

Evidence: donor HEAD f11e5d503398d814813899ffe531ad6521521b51; Android tree aex
a2b47c740a2a42aa99d42a71d60d403d55038bb2; Samsung kernel aosp
f55a360868d7ae306de49590aade312037d1c67f. Hardware mapping and proof boundaries
are in docs/a3y17lte-bringup.md. Upstream README/NOTES claims were not changed.

Implemented: source-derived 720x1280 entry geometry; A3 loader with actual-FDT
model check; candidate 448 MiB RAM window; A3 ADT; four GPIO keys; opt-in
IST3038H packet/combined-I2C path; disabled donor fuel-gauge scanning; eMMC write
rejection; A3-only kernel patch/workflow; own-device DTBH boot packer; read-only
TWRP BOOT/evidence collector for Windows/macOS/Linux.

Observed: loader successfully compiles with Zig 0.14.1 / Cortex-A53, 9552 bytes.
Kernel overlay applies to reconstructed affected donor sources. Protocol and
Python tool checks passed. This is not a full XNU build. Workflow prepared but
not dispatched; no authenticated gh CLI. No physical boot or iOS runtime evidence.

Next: user runs A3-Diagnose, provides actual BOOT/live FDT. Review memory/DTBH,
run full XNU CI, then decide a BOOT-only entry trial. Need S-Boot EL/MMU/FDT,
AMOLED command-mode refresh and touch-rail/clock evidence. Keep device dumps,
identifiers and downloaded Apple binaries out of git. Do not flash prebuilt loader.

## 2026-11-18 — full XNU CI started

After the user re-enabled Actions, commit 358a8532cff6a871b854dd65e06594237699228e
started run 44279066970 (job 134714629781) on macos-15-intel. Dependency setup
completed and the XNU build step started at 09:47:03 UTC. Outcome is pending;
this is a CI start, not a successful compile or physical phone boot.
