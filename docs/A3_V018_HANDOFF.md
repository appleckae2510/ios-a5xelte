# Galaxy A3 2017 native iOS v0.18 candidate

Branch: experiment/a3y17lte-iphoneos-20261119

Observed 2026-11-22: iOS 16.7.16 20H392 reaches launchd and starts daemons.
ScreenTimeAgent and dmd both SIGABRT at PC 0x209f8b198, LR 0x21951a5f8,
shared-cache slide 0x47974000. They share early backtrace frames; it is
not established that the sandbox policy causes these aborts.
backboardd renders the Apple boot logo, but SpringBoard readiness is not proven.

The v0.17 binary patched sandbox result codes 12,15,16,28 only. Its daemon
crashes persist, so those four returns are insufficient. This version
restates them in source for parity and adds a true output-writing handler
for Sandbox op 0x43 (sandbox_get_container_expected) after the existing
pinned Apple CodeDirectory identity gate. Unsupported operations remain
ENOPOLICY; container path and extension-token functions remain ENOENT.
New logging includes op 0x43. This is still a development-only partial
Seatbelt substitute, not real iOS security.

Validation:
- local host C harness: valid/invalid user pointers, output zeros: PASS
- patch application against reconstructed post-0409 native policy: PASS
- native GitHub Actions build: PASSED (see below); physical-device boot: PENDING

Next evidence:
1. First post-v0.18 boot: capture the log around "A3 Sandbox", especially op 67;
   capture the first SIGABRT and the lines before it (avoid recursive crash loops).
2. Symbolicate with exact 20H392 dyld_shared_cache_arm64 and tools/sweet-crash.py.
3. Prove that SpringBoard reaches "First boot is finished" or identify its
   actual reason for not dismissing the boot logo. Framebuffer swaps alone
   do not establish SpringBoard success.
4. Never reflash USERDATA just to update BOOT. Preserve backups.

## Build completed — 2026-11-22

Commit a4da8c7a9ff2d2f25b33e3317bc8800236623c2d triggered
GitHub Actions https://github.com/appleckae2510/ios-a5xelte/actions/runs/45021946337
Build job 137206593418: SUCCESS
Loader job 137206593687: SUCCESS
Cortex-A53 policy + USERDATA job 137208486162: SUCCESS
Artifact a3-native-kernel id 14754615729, ZIP SHA256
49666f33de10cf0db48410fc8188501d9fcfdd68ca1d2f2cb75b0faf8f896bd7
Linked kernel SHA256
079502f1cc083e09251452c961f2b09d7f40b2834f2e34384997be4832a2195c

Image repacked from the original verified A320FL v0.17 device envelope;
RAMDisk, original static TrustCache, exact original 2244-byte Cryptex table,
and Samsung DTBH kept unchanged. Loader wrapper CRC32 and Android boot
SHA-1 verified. The A3 Mach startup static test passed.
Image: Galaxy-A3-A320FL-BOOT-v0.18-CONTAINER-TEST.img
Size 27252752 bytes, SHA256
37a62b206e9731c3a22f4a87f3c94d33c45a36c2e4694bfa87ad6dcf68221af7
Kernel console deliberately remains visible: a5fb_noconsole=0.

NOT verified: successful iOS/SpringBoard boot; working ScreenTimeAgent,
dmd, locationd; USB debug; touch, Wi-Fi, Bluetooth or modem.
Next device trial: verify installed BOOT digest, preserve BOOT and USERDATA
backups, flash only BOOT, record first new failure and especially sandbox op 67.
