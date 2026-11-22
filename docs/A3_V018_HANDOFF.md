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
- native GitHub Actions build and physical-device boot: PENDING

Next evidence:
1. First post-v0.18 boot: capture the log around "A3 Sandbox", especially op 67;
   capture the first SIGABRT and the lines before it (avoid recursive crash loops).
2. Symbolicate with exact 20H392 dyld_shared_cache_arm64 and tools/sweet-crash.py.
3. Prove that SpringBoard reaches "First boot is finished" or identify its
   actual reason for not dismissing the boot logo. Framebuffer swaps alone
   do not establish SpringBoard success.
4. Never reflash USERDATA just to update BOOT. Preserve backups.
