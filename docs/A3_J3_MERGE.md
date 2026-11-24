# A3/J3 compatibility candidate (2026-11-24)

Base: experiment/a3y17lte-iphoneos-20261119 @ 67934d16c1a775037b1062705342ad0ef0ae4e4e. Reference: https://github.com/imusingwinxp-ops/j3y17lte-xnu/blob/main/xnu/patches/0178-j3y17lte-boot-completion-fixes.patch.

Integrated in the A3 native build:
- Clamp boot-progress position before subtracting on the 720x1280 panel; handle zero scale. Existing -noprogress remains unchanged.
- Default DLIL thread affinity off and check the setting inside the shared setter, covering callers that did not test it. The existing net_affinity=1 boot argument restores the original behavior for comparison. This is a scheduling hypothesis, not a demonstrated A3 failure.
- Exact-anchor checks reject unexpected source versions. Host tests cover idempotence and missing/ambiguous anchors. Existing A3 write boundaries and security-policy checks are unchanged.

Not blindly imported: J3 is Exynos7570 (4 cores), A3 Exynos7870 (8 cores, two clusters). J3 secondary CPU/GIC/PSCI/PMU registers and RAM bank constants need A3-specific physical verification. Keep cpus=1 for the first comparison, no J3 touch driver (TD4100 vs A3 IST3038H), no J3 GPT geometry, no raw persistent-log writes. The UFS SWEETLOG donor is not an A3 eMMC backend. No changes to AMFI/Sandbox policy or Apple binaries. J3 patches 0148 and 0152 are not direct replacements; A3 already has bounded USERDATA writes in 0402. Existing A3 0412 VSync code stays.

Next: inspect actual boot-current.img and source checkpoint; verify physical A3 CPU topology and framebuffer geometry, then stage SMP and persistent diagnostics separately. No promise that SpringBoard boots or that tccd/dmd crashes are resolved. No flash instructions until a verified build and matching device boot envelope exist.
