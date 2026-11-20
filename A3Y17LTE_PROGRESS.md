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

## 2026-11-18 — full XNU build succeeded

Run 44279066970 / job 134714629781 completed successfully at source commit
358a8532cff6a871b854dd65e06594237699228e. All mandatory A3 source, no-LSE and
binary marker checks passed. Artifact a3-xnu-kernel: 14416297843.
Downloaded kernel: 17,656,024 bytes; SHA-256:
748843e76d3c28fea64ef8c0543f17ccc7fd9e0029568a08c267dae85bf1490c.
Local ARM64 Mach-O/segment inspection and real-kernel payload packing passed
(17,027,680-byte payload). Kernel identifies xnu-8796.141.3 / Darwin 22.6.0.
No physical A3 boot or iOS runtime test has taken place; no device partition
was written. BOOT/live memory evidence from A3-Diagnose remains the next input.

## 2026-11-18 — standalone Windows diagnostic package

Added tools/windows-a3-diagnose: a PowerShell 5.1-compatible collector and CMD
launchers, without a Python requirement. It locates existing ADB, pins every
device command to the selected A3, streams BOOT as binary, hashes the backup,
and creates the manifest/ZIP consumed by the entry-image tooling. It never
sends phone write/flash/reboot commands. ADB is obtained separately from Google.
Seven integration checks passed with an ADB simulator in PowerShell 7.7 on Linux:
binary integrity, ambiguous/foreign devices, missing TWRP root, interrupted copy,
missing optional files and an unknown BOOT format. Script parsing also passed.
Actual Windows USB/phone operation has not been tested in this environment.

## 2026-11-18 — Windows BOOT backup v1.1 correction

Reproduced v1.0's misleading cable error with a complete transfer followed by
remote dd status counters. ADB's raw exec-out protocol merges remote stderr
into stdout; dd's record counters were included in the binary byte count.
The collector now redirects remote stderr before transport, reads 1-MiB chunks
using 64-KiB dd blocks, retries only a failed chunk up to three times, and checks
the original serial/TWRP root/device/BOOT mapping again before retries. It accepts
both device and recovery states instead of using wait-for-device in TWRP.
Before publishing boot.img, it compares SHA-256 with the device (or two independent
complete reads when the recovery has no SHA-256 utility). A hash mismatch permits
one complete re-read; unverified data never becomes a success ZIP. Failure logs
include real ADB exit codes, byte counts and PowerShell locations without inferring
a cable defect. Optional raw reads also suppress remote error text.

Seventeen simulator integration tests passed in PowerShell 7.7/Linux, including
the original stderr regression, non-aligned final chunk, short/disconnected reads,
per-chunk recovery, same-size corruption, persistent corruption, missing hash
utilities, inconsistent double reads, source identity changes and oversize data.
PowerShell parsing passed. Native Windows USB and a physical A3 remain untested.

## 2026-11-18 — user A320FL evidence and first entry image

Received A3-Diagnose.zip from Windows collector v1.1. All 18 manifest file sizes
and SHA-256 values and ZIP CRCs matched. The 32-MiB BOOT backup was reported as
device-SHA-256-verified. Its bootloader/model evidence identifies SM-A320FL,
a3y17lte; live TWRP model is EUR rev03, hardware revision 4 (the DTBH rev03..255
entry applies). Device dumps and identifiers stay outside git.

BOOT: legacy Android header, 2048-byte pages, original digest includes the empty
second component; four Exynos7870 A3Y17 EUR DTBH profiles. All profiles and the
uploaded memory properties agree on lower RAM 0x40000000+0x3e400000, upper RAM
0x80000000+0x40000000, and FB handover 0x67000000+0x00a00000. The candidate XNU
window 0x92000000..0xae000000 fits upper RAM and does not overlap static reserved
regions in any profile. TWRP reports 32-bpp, 2880-byte rows, virtual 720x2560 and
mode 720x1280p-59. These are Linux observations, not an S-Boot scanout guarantee.
The optional live FDT export is absent; original DTBH/FDT profiles are available.

Packaged A3-A320FL-XNU-Entry-Test-v0.2.img using the already verified full A3 XNU
kernel and loader. Size: 18,849,808 bytes, below BOOT's 33,554,432 bytes. Original
ramdisk and all DTBH bytes are preserved. One CPU, touch/GPU/eMMC probing off,
and sector writes rejected by the A3 kernel. No HFS RAM root or iOS userspace is
included; a stop at root resolution is expected if execution reaches that stage.
Five A3 packer/collector tests passed. The image is a first hardware trial, not a
working iOS ROM; it has not been flashed or booted. Next observation: loader/XNU
screen or failure state, while preserving an off-device original BOOT and EFS.

## 2026-11-18 — SM-A320FL early display and XNU entry v0.3

The phone photo shows the Samsung Galaxy A3 / Powered by Android splash. A single
photo gives no evidence of the execution stage. The v0.3 loader draws LOADING
XNU after the board check and before the first XNU segment copy. It requests a
new frame on a matching live Exynos7870 command-mode window and draws STARTING
XNU immediately before handoff. There is no display dwell or trigger wait.
The arm64 header matches the original load offset and flags. Tests used the
previously built A3 XNU from run 44279066970, without an iOS root filesystem.

The packed image executed in Cortex-A53 emulation using the A320FL rev03 FDT.
Five runs covered hardware trigger, software trigger and the second framebuffer,
display power or clocks off, and non-secure EL2 entry. Each reached EL1, passed
the loaded segment/boot_args/ADT checks, entered XNU at 0x934a3488 and observed
XNU write XNUELTE1 at 0x679ff100. In the v0.2 control, framebuffer writes
followed the first kernel copy. All five A3 packaging tests also passed.
The emulator models the registers; physical AMOLED behavior and progress on
the A320FL under v0.3 still require a device observation.

## 2026-11-18 — XNU console on the A320FL and v0.4 RAM-root test

After the v0.3 handoff, the user supplied a handset photo showing the XNU
console. AppleCLCD reports 720×1280, stride 2880 at 0x67000000 and a 750×1334
logical canvas. The kernel reports one initialized CPU, SGI1 verified and a
timer wake after 21056 microseconds. It also prints MAC framework initialization,
IOCoreSurfaceRoot and HID service registration. The battery value is explicitly
reported as a static fallback. Actual touch events, a mount of md0, PID 1 and
SpringBoard are not visible. The build ID is not printed in the photo.

Prepared a separate v0.4 BOOT test with the same loader and XNU segments.
The packer embeds the project's static ARM64 init as md0 for mockfs, and emits
the exact DT passed to the kernel, including /chosen/memory-map/RAMDisk.
The image is 18,866,192 bytes. Three Cortex-A53 runs verified the 11 loaded
segments, the kernel boot arguments and initial XNU execution. The RAM root
uses 20,480 bytes at 0x94560000. All four code-signature page hashes of init
matched. The executable produced the runtime PID supplied in separate syscall
unit tests with PID 1 and PID 7. Both completed two heartbeat writes.
The next device evidence is BSD root: md0 followed by the init PID and
heartbeat. The enhanced host tests passed. This package contains no Apple
userspace and has not been run on the handset.

## 2026-11-18 — RAM-root PID 1 demonstrated and HFS+ root v0.5 prepared

The user's three photos show the A3Y17LTE_PORT_V1_720X1280_IST3038H marker
with touch=0, BSD root md0, the diagnostic init running as PID 1 and repeated
SWEET init: still alive messages. This demonstrates continued execution of
the test process on the handset. Its mockfs root was the executable itself.
The photos also show a single initialized CPU and the display console.
Touch registration, loopback/gif/stf software interfaces and the static battery
fallback do not establish touch, Wi-Fi, Bluetooth or battery measurement.

Prepared a separate v0.5 image with an 8 MiB HFS+ volume named A3TestRoot.
Its /sbin/launchd is byte-identical to the init in the hardware-tested v0.4
package. The volume has root-owned 0755 directories /dev and /sbin and a
root-owned 0755 executable. hfsprogs 540.1-Linux completed its full read-only
check successfully. File extraction matched the source hash. Both volume
headers match and the clean-unmounted flag is set, with journaling off.
Used the Debian trixie hfsprogs package verified against its published SHA256
and mozilla/libdmg-hfsplus e18579b391950589b9ed16ee630c54ce4319bb29.

The image is 27,238,416 bytes and preserves all ten XNU segments, Android
ramdisk, DTBH profiles, boot addresses and boot arguments. RAMDisk is 8 MiB
at physical 0x94560000, bounded inside the existing XNU RAM window. Three
Cortex-A53 loader runs verified all 11 copied segments, boot_args and ADT,
and reached the kernel's entry marker. Host emulation ends in early XNU and
does not demonstrate an HFS mount on the phone. Next device result needed is
the HFS mount of A3TestRoot followed by the PID 1 heartbeat. Full Apple
userland, writable storage and SpringBoard remain pending.

## 2026-11-18 — HFS+ root confirmed on SM-A320FL and read-only eMMC test v0.6

The latest handset photo shows `hfs: mounted A3TestRoot on device b(1, 0)`,
the project init running as PID 1 and two heartbeats. This demonstrates the
v0.5 filesystem mount and execution of its diagnostic init on the phone.

With the same loader, kernel and HFS+ volume, adding `--probe-emmc` to the
A3 BOOT packer enables the GPT probe for USERDATA. The package keeps
`rd=md0 emmcwrite=0 a5log=0`. It reads the GPT header and entries during
IOFindBSDRoot. The A3 kernel also returns EROFS from the sector write path.
Stock recovery identifies USERDATA as mmcblk0p24 with 11853807 KiB. All
four stock FDT profiles and the payload ADT agree on the DW-MMC register
window at 0x13540000 (size 0x2000). The stock profiles specify a 64-entry FIFO.

The 27238416-byte image differs from v0.5 only in the storage options, the
fresh ADT seed and the BOOT digest. The three Cortex-A53 loader tests reached
the early XNU marker. Separately, the actual packed kernel instructions ran
from the IOFindBSDRoot probe option check through the GPT scan on a simulated
host. A synthetic GPT with 128 entries produced 33 CMD17 reads and the
correct USERDATA extent. Corrupt header, corrupt entries, missing partition
and disabled clock fixtures reported their respective errors. No card write
commands occurred in these runs. Physical eMMC access remains unverified
until the phone prints `GPT USERDATA first=… sectors=… read-only`.

## 2026-11-18 — requested radio, audio, camera and modem integration

Reviewed current Note FE 76abd2e6d97e9b60464255d1c6cf1d2e57a9325d
and S7 2aafd7a0a1422a538399c449e160219b8aeba65e references. Their Apple-facing
audio/capture/HCI interfaces are useful references. The A3 uses QCA6174 over
UART0 and Qualcomm SDIO WLAN, COD3026X with TFA9896, and IMX258/IMX219.
The source identifies an SS315AP modem. These need A3-specific transports,
power and firmware integration. No physical success for these is claimed.

Added A3-only patch 0401 for source-derived GPIO/clock/power observations and
an opt-in H4 Read Local Version transaction. It transmits only when the source
and peripheral clocks, power pins, mux and UART mode are ready. The existing
UART baud configuration is observed. An aggregate poll budget bounds waiting.
This stage does not initialize a powered-off chip or load Qualcomm firmware.
The packer requires the new binary marker for --probe-hardware, while ordinary
v0.5/v0.6 boot options retain their existing behavior.

A separate 10 GiB HFSX iOS root candidate is building in the owner's existing
private root project, run 44339908078. It uses Apple's iPhone 8 Plus iOS 16.7.16
20H392 source, d21ap product metadata, full apps and stock assets. It has no
A3 phone installation step. iOS root boot and all five requested hardware
features remain pending physical and driver integration.

The first full-assets 10 GiB root attempt, run 44339908078, failed with
No space left on device while copying shared-cache part .37. The adjusted
11 GiB run is 44344309173, source f79b8d035feea9b53cfc873fb4a1acdab355d12d.
It measures uncompressed allocation before copying and omits the six asset
families recorded in docs/a3y17lte-hardware.md and cache local-symbol files.
The Audio tree is included. Build success remains pending.

Patch 0402 prepares the separately selected USERDATA iOS root. Sector writes
require emmc_ready, emmc_writable, USERDATA and an LBA inside its selected GPT
extent before any host-register access. The BOOT-only diagnostic profile
still uses md0 with emmcwrite=0. No handset USERDATA installation is performed.
The active full-kernel build is 44344673671 at source
1f6addf7d0169e9ba0be0e834d951cbb8259a2d9. Two earlier queued builds were
superseded while reviewing the nonsecure PMU read and the root-write path.

Local protocol and source compilation checks passed. All five A3 Python
tool tests passed, including old-kernel rejection for the hardware and
USERDATA profiles. Eighteen Windows collector tests passed, including the
new firmware cases for good data, transient corruption, persistent corruption
and independent reads when remote SHA-256 is unavailable. Their peripheral
and USB devices are simulations. Handset behavior remains unverified.

Full kernel run 44344673671 completed successfully, including source, no-LSE
and binary marker checks. Artifact 14445479907 has ZIP SHA-256
689ceace7c751152d7cdcc8474f486b5310591523011013d41e7a5f17a9b95ef.
The kernel is 17672472 bytes, SHA-256
f24d72e7e3f85fc14da7c66378af600822afade68ece573cb77fb3ba3b501b22.

Prepared v0.7 with the same 8 MiB HFS+ diagnostic root and Apple's matching
d21ap product metadata. BOOT size is 27256848 bytes; SHA-256
a521de6192b4df7a75ab09d9c01b955eec059e0a6fa52b55a0274094dc3d8fa4.
All ten XNU segments, the HFS contents, boot arguments, original ramdisk,
DTBH and header addresses were verified. Two Cortex-A53 loader runs reached
the early kernel marker, covering EL1 and EL2-to-EL1 handoff.

The actual kernel instructions passed eight hardware fixtures, five GPT
fixtures and nine sector-write fixtures. A prepared UART received the
synthetic HCI version and reported the expected six fields. Disabled clocks,
power, mux and DMA-mode fixtures transmitted nothing. Missing reply consumed
the one-second wait budget. Valid first and last USERDATA sectors wrote one
synthetic sector each. Unregistered/read-only roots, wrong partition, empty
extent, out-of-bounds sectors and the donor log range returned EROFS before
MMIO. These are emulated controller results. Physical radio, camera, audio,
storage writes and modem functions are still pending.

Root run 44344309173 completed successfully. Its case-sensitive journaled
HFS+ volume A3IOSROOT passed fsck_hfs. Raw size is 11811160064 bytes (11 GiB),
with 4672229869 compressed bytes split into three private release assets.
The pre-copy estimate was 9043593216 bytes. The matching d21ap ADT is
185432 bytes with SHA-256
8c5fa57d3cfbc702936b49198971a22ab317bcb81e105d931d74f94c71dc7909.
The root report, space plan, ADT and checksum manifest were checked against
the release asset digests. The root remains untested on the A3 handset.

A separate 18868240-byte USERDATA boot candidate was assembled and its
loader reached the early XNU marker in Cortex-A53 emulation. It is outside
the hardware-test download. The handset still needs the v0.7 hardware/GPT
observation before planning a USERDATA installation.

The public vendor reference also provides the firmware. Eleven files
(5198423 bytes) matched the Git blob IDs in tree
3f7ccfe439bc5f3f5971c9c53bb9ed96801fa9fc. QCA NVM type 2 has a 1997-byte
payload and the type-1 rampatch has a 68896-byte payload. Reference blobs
stay outside git. The Windows collector can compare the installed versions.

## SM-A320FL v0.7 data abort and v0.7.1 correction

The handset video shows the framebuffer and CPU timer running. The panic
screen appears about 36 seconds into the recording. It reports a kernel
data abort at PC 0xfffffff00750846c, ESR 0x96000210. The v0.7 binary
resolves that PC to _a5xelte_touch_probe+0x16c. The hardware diagnostic
inlined there executes `ldr w8, [x21, #0x30]`. The displayed FAR minus
x21 is 0x30, the offset of CP_CTRL_NS in the mapped PMU.

Using the v0.7 BOOT payload with the CP control page unavailable and the
domain-status page accessible, the A53 fixture stops at the same PC on
a four-byte read of physical 0x10480030. Earlier fixtures allowed this
read and missed the handset failure.

Patch 0403 omits both CP register reads. The diagnostic maps the single
domain-status page at 0x10484000 for audio and camera. The host regression
rejects a broad PMU mapping. The packer requires the hardware V2 marker
when hardware probing is requested. The diagnostic still boots from md0
with emmcwrite=0. The skipped modem probe provides no cellular status.

Full XNU run 44386100921 succeeded at source
11e3972a6bd3b3132375a102fb0fb520f0f12017. Kernel artifact 14467364320
has archive SHA-256 55a3a5350268392d968785ead430610a29e221c9e091dadd325dee5ccdf6ad93.
The rebuilt kernel SHA-256 is
d58992a4f3aaf1ce8b87321b730478c04b97b9bf71f47559c2055a9f6a298e5a.
The 27256848-byte v0.7.1 BOOT image SHA-256 is
f7a14c90c37bd1f97227110de19703bb3ef76782fc107f5ab6c29b3c3d729884.

The packed ARM64 probe returned in all nine peripheral fixtures with the
CP page inaccessible. The five IOFindBSDRoot fixtures executed the probe,
continued through the corresponding eMMC result and reached mdevlookup(0).
These tests cover valid GPT, both bad CRCs, missing USERDATA and a gated
host. They issued only card reads. The loader reached the early kernel
marker from EL1 and EL2. The embedded HFS root matches v0.5. The physical
v0.7.1 boot, including the diagnostic heartbeat, awaits a handset result.

The subsequent two handset photos show the 720x1280 display and a panic
with PC 0xfffffff00750846c, ESR 0x96000210 and FAR equal to x21 + 0x30.
At this PC the distributed v0.7 BOOT contains `ldr w8, [x21, #48]`;
the distributed v0.7.1 BOOT contains `add x0, x0, #3694`. Only the former
instruction reads memory. The currently installed BOOT cannot be read
from the photos. A fresh boot after checking the partition is pending.

START-BOOTCHECK.cmd compares the first 27256848 bytes of the A320FL BOOT
partition with both released images. The remaining bytes in the 32 MiB
partition are outside both images. The helper stages the verified fix at
a versioned path in recovery RAM if needed. The operator chooses Boot in
TWRP, then the helper rereads the partition before reboot.

## A320FL combined boot and hardware evidence

The owner confirmed the corrected v0.7.1 image on the SM-A320FL. The photo
shows HARDWARE_V2, the skipped CP registers, a readable GPT USERDATA entry,
the A3TestRoot HFS mount and repeated PID 1 heartbeat messages. UART clocks
are present, with BT mux, enable and shared supply at zero. WLAN enable and
camera supply/reset pins read zero. Chip names in the log identify
the board configuration. Camera capture, sound, Wi-Fi, pairing, cellular and
touch input still need functional testing on this handset.

The combined v0.8 profile runs the board handoff checks and uses the eMMC
controller in read-only mode. Before choosing the native root it checks both
11 GiB HFSX headers, the binary catalog, the volume name and the entries for
launchd, dyld, the shared cache and SpringBoard. It then continues through
the ordinary emmcroot0 mount and BSD init path. The md0 in the same BOOT
serves as the fallback. Its first process checks HFS, console and pipe I/O
and execs a second RAM program as PID 1. A 20H392 root that is already on
USERDATA is required for the Apple path. The profile never installs it.

Private root validation run 44413192297 verified all three compressed parts
of the previously released root and selected the actual volume with 675
sector reads. This checks the catalog selector on the real filesystem bytes.
The new version has not been run on the handset.

The final kernel source is 5e88373e1475bf853cf1e6199722cacb3215ede4
(run 44415023180, artifact 14480890403). The kernel is 17672608 bytes,
SHA-256 e18ba2bf813fa6d3e8c3d5a204c96f5fecbab567dc176edceefc230bd057e518.
The released BOOT is 27256848 bytes, SHA-256
4e374e367c60b15919694b6c521c8865be2ba7dc96e7f891f04b8477be0c97a5.
It uses rd=a3auto. The BSD RAM-root predicate follows the resolved device.

An A53 replay executed the board probe, actual sector I/O and IOFindBSDRoot
from the packaged image. With the original release catalog it issued 33 GPT
reads and 675 HFSX reads and printed the native emmcroot0 BSD root. For an
Android-like header and the observed A3 handoff it issued 34 reads and
selected md0. Other scenarios exercised HCI readiness, both invalid GPT
CRCs, missing USERDATA, a gated clock, a bad alternate volume header and a
mount retry. All nine issued zero media writes. The RAM Mach-O replay
continued through execve into its second PID 1 program. EL1 and EL2 loader
replays both reached the first linked XNU marker. These use modeled devices
and syscall services. Apple's launchd was not executed in the emulator.

The Windows package entry START-GESAMTTEST.cmd uses the packer's JSON,
verifies the local image and TWRP staging, and checks the BOOT prefix
after the operator flashes Boot. Thirteen modeled TWRP transfer/check cases
ran against the released bytes.

## Native iPhoneOS BOOT v0.9, 2026-11-20

The user's last photo reached the mounted A3IOSROOT volume and then reported
launchd SIGKILL with namespace 9 code 0xe. In xnu-8796.141.3 these values
identify OS_REASON_EXEC and EXEC_EXIT_REASON_WRONG_PLATFORM. The previous
A3 kernel was compiled with XNU_TARGET_OS_OSX and Mach-O platform 1.
The kernel is now built with XNU_TARGET_OS_IOS, iPhoneOS SDK, ARM64_ALL,
Cortex-A53, and deployment target 16.7. Its Mach-O target is platform 2.

The complete build succeeded in run 44615970616, job 135884629518, source
2abdc33f805944bca26a063867e2f41407a9de6e. The native build required Jetsam
and the minimal UBSan runtime in the A5XELTE configuration. The final
workflow collects fakeroot/mach.development.a5xelte and compares it with
the freshly linked object. Native platform, compiler flags, A3 markers
and the Cortex-A53 no-LSE checks passed.

Kernel artifact 14574933930 contains 17516824 bytes, SHA-256
7fdf1b7b280016628539434aebf2ac44b7751b031107eb3350f7c55c8d5a207c.
The artifact ZIP digest is
688ea767327eabf8c879277458eef47386182255040ea94de02383dafd1cb74a.
The corresponding build log is artifact 14576365730.

The package Galaxy-A3-A320FL-iOS16-BOOT-v0.9-Windows.zip contains the
27117584-byte A3-A320FL-iOS16-BOOT-v0.9.img, the profile, Windows staging
and BOOT verification commands, checksums, and a German tutorial.
BOOT SHA-256 is
e9d967df8187690753dcb69a4ef4235337abb485d916224b25641be25b61474a.
ZIP size is 7780744 bytes, SHA-256
8f9db810538554107e63d64f3765f7f8459f2326b08eb979eb04072645aaa483.

The packer verified every loaded segment against this exact native kernel,
the device BOOT layout, DTBH, Samsung ramdisk, payload and embedded ADT.
EL1 and EL2 A53 loader replays reached the linked kernel entry marker.
Nine combined root-selection scenarios ran from the new packed bytes.
The iOS catalog selected emmcroot0 after 708 sector reads. Error and
fallback cases selected md0. All scenarios issued zero media writes.
The replay now enters IOFindBSDRoot at its actual function entry, so its
own instructions establish the stack and callee-saved registers.

Fourteen Windows/TWRP fixture cases passed with these released bytes.
The checker pins the v0.9 image hash and size in addition to validating
the JSON profile. A mixed package with an older image and matching older
profile is rejected. Transfer retries, partial writes to staging, and
post-flash BOOT readback were exercised using modeled TWRP services.

Physical boot of v0.9 remains untested. The emulator did not execute
Apple launchd, dyld, or SpringBoard. The available board probes do not
establish working camera, Wi-Fi, Bluetooth, audio, modem or touch.
The next hardware step is this BOOT-only update over the existing
A3IOSROOT installation, followed by the first panic or console photo.
The combined profile uses rd=a3auto and emmcwrite=0. Services requiring
writable storage may stop later. No new USERDATA installation is needed
for this kernel platform change.

## 2026-11-20 — v0.9.1 native MAC policy lifetime and boot regression

The physical v0.9 report says `Unexpected fault in kernel static region`.
Its PC resolves in the exact v0.9 Mach-O to `mac_policy_register + 0x474`.
The store's address is `mac_policy_list.freehint` (+0x14); the input is the
donor policy configuration. The fault is during a BSD-time registration
after `machine_lockdown`. The generic panic-handshake footer is separate.

In the A3 native iOS build, ordinary Mach registrations remain possible
before lockdown. BSD uses those policies and continues to HFS. The
native register/unregister APIs return EPERM/EBUSY once the static table
is sealed. The donor BSD call that attempted two late registrations is
omitted. Exec and signature verification were not relaxed, the original
panic handlers remain active, and the immutable segment retains read-only
permissions. A working native policy provider may still be needed by Apple
services. USERDATA stays read-only and the package stages only BOOT.

Build 44743123110, job 136311520104, commit 5d69c5dc464e286d87670edd0ac4e72629221f76.
The XNU source is xnu-8796.141.3, ARM64_ALL, native iOS 16.7/Cortex-A53.
Kernel artifact 14631434741 (17533208 bytes);
SHA-256 f0afc719b9a9909dfc54a5ef4e0392483cd94edc555bfb735fc4e17a1b7eb782.
Image 27117584 bytes, SHA-256 97de7ab315484b58f6e72123672e84b1b0eccb354ff5f962b46f9312f6a01bb9.
Galaxy-A3-A320FL-iOS16-BOOT-v0.9.1-Windows.zip (7782839 bytes),
SHA-256 1743cab9d12c483f7139a2fd417733e539abc70659c5f5f5b3da48c8e352fdbd. The pinned donor checkout became unavailable during
this run. The build uses the same pre-existing source checkpoint, now
verified by SHA-256 before extraction and retained in an Actions cache.

The native build runs a static call-order/placement check and a single-core
Cortex-A53 replay on the linked executable. Both early registration windows,
BSD initialization, rejected late register/unregister operations, actual HFS
registration, release init path lookup and 64-bit argv setup share one VM
with final Mach-O permissions after lockdown. The old v0.9 executable is a
negative control for the obsolete late call. The test uses modeled memory
allocation, locks and I/O services and stops before process credentials/exec.

Local tests used the exact distributed BOOT, with all kernel segment bytes
matched back to the artifact. Eleven loader trials covered all four stock
Samsung DT variants from EL1 and EL2, software update trigger/second display
buffer, unpowered and clock-gated display. Seventeen combined A3 hardware
and volume selections used modeled peripherals. Five valid release catalog
cases selected emmcroot0 after 708 sector reads and rejected a subsequent
write with EROFS without any media write. These include ready, silent and
malformed Bluetooth replies and an unavailable PMU status mapping. Twelve
cases selected the RAM diagnosis and ran its test payloads under modeled
Darwin system calls, including one synthetic HFSX case per missing launchd,
dyld, shared cache and SpringBoard entry. Fourteen PowerShell/TWRP cases
covered model/partition identity, staging, retry and byte-verified readback.

The prior native release audit established iOS 16.7/arm64 metadata for the
real Apple launchd, dyld and SpringBoard in the prepared 20H392 root.
Their execution on an SM-A320FL with v0.9.1 has not been observed. Hardware
radio, camera, audio and touch service functionality remain unverified.
The next hardware evidence is the first new boot milestone or panic after
a confirmed BOOT-only update on the existing root.
