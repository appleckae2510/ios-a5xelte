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

## 2026-11-20 — Apple launchd reached the fsck boot task on an SM-A320FL

The device photo shows Darwin Bootstrapper 7.0.0 and launchd creating
system services. It stops when launchd checks whether /sbin/fsck is a
platform binary. This is later than the prior static MAC registry fault.
No fsck result, SpringBoard execution or peripheral service is shown.

Private read-only CI audited all three published parts of the A3IOSROOT
20H392 release against their SHA-256 values and mounted the resulting
HFSX volume read-only. The original d21ap restore manifest was fingerprinted
and its static trust cache checked by SHA-384. Ten arm64 CodeDirectory
hashes matched. Nine executables passed standalone strict codesign
verification. The SpringBoard executable hash matches, but macOS rejects
its bundle's legacy resource envelope in strict mode. For fsck the
cache entry is e1a3f12fb8be72d6e9a4e4178ebe152513bc599a, category 3.
The two optional macOS-style filesystem-bundle paths are absent.
All helpers tested in /sbin are present. No Apple executable was
published. The normalized measurements are in tests/a3-20h392-startup.json.

The A3 combined packer can now hand off the exact d21ap static cache
through /chosen/memory-map/TrustCache. It preserves the original v2
module with all 2,754 entries, hash types, flags and constraint categories.
The address and unpadded byte length use XNU's two-word DT ABI. The whole
module occupies its own reserved loader segment after the diagnostic RAM
disk. Supply the original Firmware/087-86694-044.dmg.trustcache from
20H392 using the packer's --a3-static-cache option.

All eleven EL1/EL2 and display control loader trials of the engineering
image reached the native entry marker and compared the destination
bytes. The A53 test runs the linked kernel's SecureDT lookup, early
cache initialization, MAC lockdown, HFS and PID 1 path preparation. It
then tests static cache capabilities and looks up all ten measured
hashes plus negative inputs. On the v0.9.1 native kernel, capabilities
returned KERN_NOT_SUPPORTED (46), zero caches, and each static lookup
returned KERN_NOT_FOUND (56). The native provider is still required for
executable identity and launch policy. A packaged trust cache by itself
does not grant any platform status. The check uses a single CPU model.
A pass on this lookup criterion will still need a real device boot.

The native build workflow calls the combined check with --require-lookup.
A kernel with this known missing service fails the qualification step
even if compilation succeeds. No new flash package has been issued.

## 2026-11-20 — Protected identity measurement and combined boot qualification

Commit 2b4707ab87af41e07883d4b21387bdcb5475b01e implements measurement
of the exact 20H392 v2 cache in the native arm64 kernel. The loader passes
the original module through the device tree. XNU validates the range
against boot arguments, copies the module into the pre-lockdown private
buffer and verifies SHA-384 over that copy before making it available.
Search results preserve each stock launch-constraint category. The MAC
diagnostic for launchd, fsck and mount records the ordinary platform
decision. The measurement makes no change to authorization decisions.

[Build and qualification in GitHub Actions](https://github.com/appleckae2510/ios-a5xelte/actions/runs/44794529811)

The kernel and loaders compiled. The kernel artifact SHA-256 is
9ae54f16544f4a974d985b23c122e31f2453e1af756115a26970c9697e9b8d14.
Tests exercised the linked SecureDT, MAC initialization and lockdown,
HFS registration and the call path that prepares PID 1. A modified
constraint was rejected. All ten measured identities matched after
lockdown and retained their original constraint categories after the
loader source was overwritten in the test. The system static-cache API
returned status 46 with zero caches and status 56 on all ten lookups.
The requested qualification consequently finished with status 3.

Locally packaged SM-A320FL engineering BOOT SHA-256:
24a30a4590f284038fb33def7ff3250a3e974fe277d08b73f66217a71cff4318.
The package was replayed through eleven loader cases covering EL1/EL2,
four device-tree variants and display-control conditions. Seventeen
combined storage and board scenarios picked the expected root (five
eMMC, twelve diagnostic RAM) without issuing eMMC writes. The packaged
RAM disk matched the diagnostic programs tested. These are modeled
checks. A physical boot of this candidate, Apple's platform authorization
for fsck, SpringBoard and peripheral operation remain unverified. The
latest handset photo still identifies the boot-task policy check as the
first fatal error. No new flash package was issued.

## 2026-11-20 — Engineering files delivered at the user's request

Galaxy-A3-A320FL-Entwicklungsstand-2026-11-20.zip contains the existing
2b4707ab87af compiled kernel, its matching 27,250,704-byte BOOT, ADT,
profile, the 11-loader/17-root-selection logs, the failing native
qualification log and German instructions. Its 17 files include a
Windows SHA-256/size checker. File checks complete with status 3 to make
the unresolved boot qualification visible. A corrupt or missing file
produces status 1. The archive documents that the new Windows checker
has not been executed on a Windows host.

ZIP size: 14,822,350 bytes.
ZIP SHA-256: 58b39b74d008392a620e9bc79b54e4a93886fbe89d1c275b2fea714a24f86fdf.

Archive CRC, manifest membership, byte lengths and every declared SHA-256
were verified after packaging. The kernel and BOOT match the earlier
run and engineering metadata. No new kernel compilation was needed for
this handoff. The supplied TWRP steps describe an optional BOOT diagnostic
trial and restoration from the user's own BOOT backup. The complete
Apple root is a prerequisite and is not part of this delivery.

The known fsck platform authorization blocker is still open. This
delivery does not establish successful SpringBoard or camera, audio,
Wi-Fi, Bluetooth, modem or touch operation. Completing those services
requires further kernel and board work followed by hardware tests.

## 2026-11-21 — Loader validation and original boot-program platform policy

The new photo shows the exact diagnostic line for fsck, match=1,
category=3, platform=0. Apple launchd then reports the same platform
boot-task panic. This confirms the measured identity in hardware.
The photograph does not identify the exact BOOT by hash.

The compiled A3 loader now validates the entire segment set before
copying. It rejects overlapping file/destination ranges, header/ADT
overlaps, segments beyond kernel_end, overflow/unaligned mappings,
unbacked or unaligned entry points, truncated metadata and an
unterminated command line. Firmware FDT parsing respects its actual
structure and string extents, rejects invalid names/root structure
and preserves all four diagnosed A3 variants.

A3XNPAY2 retains the 16-byte wrapper and adds CRC-32 over the complete
payload. A3XNPAY1 remains accepted for existing packages. The packer
requires a loader that supports the checked format. Fifty compiled
ARM64 regression cases passed, including reproducing the original
loader's partial-write defect as a negative control. Eleven complete
EL1/EL2 and display-state trials reached the existing kernel's first
marker. Seventeen combined root-selection scenarios passed.
The only ADT difference from the previous engineering payload was its
fresh 64-byte random seed. This is modeled execution.

Native patch 0407 registers the existing signature hook before lockdown
through mac_policy_initmach. Only exact CDHashes and matching hash types
from the pinned original 20H392 module on MNT_ROOTFS|MNT_RDONLY receive
CS_SIGNED|CS_PLATFORM_BINARY through the MAC signature decision. File
names alone supply no authority. Unknown identities, incorrect hash types
and writable/non-root mounts preserve their input flags. Kernel signature
and page validation continue normally. The policy never registers the
donor permissive sandbox. The global Image4 trust-cache service is still
unsupported and is reported independently. The CI criterion now exercises
the native boot policy, retaining --require-lookup for the separate API.

Patch application and the host policy test passed. The host test checked
all 2,754 original identities, malformed cache input and mount/hash
negative cases. A native iPhoneOS compilation, linked boot-policy
qualification and a hardware boot are pending. The previous kernel is
a negative control for the new --require-platform-policy criterion.
A full GUI boot and all peripheral services remain unverified.

## 2026-11-21 — BOOT v0.10 built, qualified and delivered

The GCC-only loader compilation initially found a pre-existing freestanding
dependency on memcpy generated for the aggregate video assignment.
Commit 8db4823ae09f4cf3ee7e667a5971a2508c8f83c4 uses explicit volatile
field assignments and tests the resulting six video fields. Run
44887575375 then passed and produced loader artifact 14700661428.
The 9,200-byte delivered loader SHA-256 is
38dfe5c7ce6636b99fec60d51370d0124db6082108d0fd64b270610f342587b6.
Its 29 portable CI cases passed. The downloaded GCC binary passed all
50 local compiled ARM64 cases, including four actual board trees and
the old loader as the partial-write negative control.

Kernel commit bd95d3f9d49173d967aa17fd6bf8adc3fb137627 restricts the
native registration to A3BootIdentity, containing only the verified
signature hook. Its configuration and handle reside in read-only
__DATA_CONST after lockdown. It does not register the donor dyld-policy
syscall or permissive sandbox. Run 44887841371 completed successfully
(build job 136797277176, qualification job 136799579831).
Kernel artifact 14700582414 contains 17,582,848 bytes, SHA-256
b0b1ea56d35fe6fd2c18c5fbdadb4c72683f25412b1d292e7e722634bd7c4846.

The linked-kernel test ran early MAC registration, sealing, HFS setup,
PID-1 path preparation and the original cache measurement. All ten
audited stock identities receive the signature/platform flags on
read-only root. Forty-two mount/hash-type/unknown-hash controls and
a modified cache are rejected. The final local paired-image check
also confirms the two new policy objects have read-only mappings.
The global Image4 static-cache service still returns status 46 with
zero caches. This is reported independently. The boot-policy criterion
passes with exit 0. Actual Apple exec and credential setup remain
outside the model.

The final BOOT uses the downloaded GCC loader and downloaded native
kernel, original A3 DTBH and the diagnostic RAM disk. Every kernel segment
was checked by the native fixture against the linked Mach-O. Eleven
full loader cases covering four FDTs at EL1/EL2 and display-state variants
reached the first XNU marker. Seventeen combined board/storage/root
cases passed without eMMC media writes. The diagnostic RAM disk bytes
match the exercised fallback programs.
BOOT size 27,250,704 bytes, SHA-256
069230fbad4760c8ac54b4b237eba40421e36d4d00967ae9b0e5d981d9a56235.

Delivered Galaxy-A3-A320FL-BOOT-v0.10-Windows.zip, 14,857,105 bytes,
35 files, SHA-256
72eb85d39354edd795bc6eeb2f988570b5f329bf65232cc3de6b6ec46e082fa0.
Archive CRC, manifest membership and all declared sizes/hashes were
verified. It includes the matching kernel, loader ELF, source, test logs,
German TWRP BOOT-only instructions and restoration through the user's
existing BOOT backup. The local Windows checker has not been run on a
Windows host. The separate original A3IOSROOT remains a prerequisite.

The v0.10 device boot remains pending. The newest photo still belongs to
the previous measurement stage and shows platform=0. The expected new
diagnostic is fsck match=1 category=3 platform=1. Neither successful
SpringBoard nor camera/audio/Wi-Fi/Bluetooth/modem/touch operation is
established by these model tests. Unknown later faults remain possible.

## 2026-11-21 — mount-phase-1 reaches platform=1 and needs writable storage

The user's new photo has mount match=1 category=3 platform=1. fsck has
advanced and mount-phase-1 reports Read-only file system, then exits 1.
The generic panic-handshake footer is secondary. The optional preboot
firmware lookup fails with ENOENT. The photo does not show the exact
BOOT hash or SpringBoard.

Sources consulted include Apple's hfs mount_hfs/mount_hfs.c and
core/hfs_vfsops.c, the donor's NOTES.md and A5XELTE's write-path evidence.
GetMasterBlock's device open uses O_RDONLY|O_NDELAY. An already mounted
device can return EBUSY during that probe. The actual HFS update must
successfully reopen the device for write before clearing HFS_READ_ONLY.
The previous combined A3 profile explicitly disabled that write-open.
The donor documents the same mount[3] exited failure and the later
writable-root continuation.

Native patch 0408 accepts explicit emmcwrite=1 only with the selected
USERDATA profile and logging disabled, retains original geometry/catalog
checks and revokes write access for rejected volumes. The existing
per-sector writer still bounds every CMD24 to USERDATA. Dirty journaled
roots can reach Apple's normal journal handling. Dirty non-journaled or
inconsistent roots still require repair.

The pinned CodeDirectory/hash-type check now works on root both before
and after its normal read-write remount. Writable or read-only non-root
mounts and unknown signatures gain no platform flags. The SHA-384 module
measurement, immutable cache and ordinary code-page validation remain.
The native signature test exercises both mount states.

The packer's new explicit --writable-userdata requires --combined and
the new kernel marker. Other combined callers retain their read-only
profile. This new boot mode writes the existing iOS USERDATA volume.
A fresh backup or the original restore image is needed to undo those
root-volume writes in addition to restoring BOOT.

The native writer's nine synthetic-controller cases passed on the old
linked kernel, including the actual FWRITE open, first/last-sector data,
out-of-range sectors, disabled access, wrong partition and log redirection.
The fresh build will repeat them on the newly linked kernel. The native
policy host check passes root authorization before/after remount.
Patch application and Python/YAML checks passed. Native compilation,
combined root selection and a new device boot remain pending.

Primary sources
https://github.com/apple-oss-distributions/hfs/blob/main/mount_hfs/mount_hfs.c
https://github.com/apple-oss-distributions/hfs/blob/main/core/hfs_vfsops.c
https://github.com/dipa-studio/ios-sweet/blob/main/NOTES.md
https://github.com/wardevsa/ios-a5xelte/blob/herolte/A5XELTE_PROGRESS.md


## 2026-11-21 — BOOT v0.11 native mount update completed

The latest real-device photo has progressed to mount-phase-1. Original mount
is match=1 category=3 platform=1; it then exits 1 after mount_hfs reports
Read-only file system on /dev/emmcroot0. Optional preboot firmware lookup
also returns ENOENT. This is observed device evidence, not a verified v0.11 boot.

BOOT v0.11 is built and delivered. Kernel code commit:
eae451d7b62368a29e63fdb51bec4bee5ab13c07
Successful CI: https://github.com/appleckae2510/ios-a5xelte/actions/runs/44893326915
Native build job 136813621687; policy/write qualification job 136815311413.
Kernel artifact 14703018168, authenticated ZIP digest:
0c34a0243f8d1a0e19ddf08dbd0b13642899617c73aaa071ec2dd86f5d207801
Kernel bytes 17582880, SHA256:
98c155df91e9032a3901e9a587def241fb382c7d3aef8dd52cb3d700a988e953

New explicit --combined --writable-userdata enables emmcwrite=1 only for the
validated USERDATA root. Ordinary combined packing stays read-only. Rejected
Android, damaged or incomplete volumes lose write access and select md0.
Dirty journaled HFSX may reach Apple's native journal handling; dirty
non-journaled or inconsistent volumes still require repair. The normal HFS
read-only-to-read-write update can now open the selected device FWRITE.
Exact pinned original Apple CodeDirectory identities retain platform status
on MNT_ROOTFS after the remount; unknown hashes/types and non-root mounts
are still denied. Normal signature/page checks remain. No Apple executables
were replaced and no panic or HFS success result was fabricated.
The global Image4 trust-cache service remains unsupported and is reported.

Apple HFS sources and donor boot notes informed the fix; see progress.
The canonical board volume include is staged before native patches even
when restoring the old native source checkpoint. Builds 44891780803 and
44892929112 failed validation/preparation respectively and were not released;
the strict validator remains enabled in the successful final run.

Exact final image: A3-A320FL-BOOT-v0.11.img, 27250704 bytes, SHA256:
59659df0cb931707c32e17de4c1b870d016a11713fa433491761d0aa77549ab7
Uses unchanged GCC loader from 8db4823ae09f4cf3ee7e667a5971a2508c8f83c4,
CI 44887575375/artifact 14700661428. Loader SHA256:
38dfe5c7ce6636b99fec60d51370d0124db6082108d0fd64b270610f342587b6
Payload wrapper A3XNPAY2 CRC32 and all segment bounds are checked.

Passed on the exact final bytes: 11 full loader trials (four real A3 DT
profiles at EL1/EL2 plus display controls); 20 combined hardware/root cases
(six iOS selections, fourteen RAM fallbacks), FWRITE state checked after
selection, no media writes during selection. Nine native ARM64 sector-write
cases verify first/last USERDATA sectors and seven rejected access/range
controls using a synthetic controller. Six C journal-profile checks passed.
Native kernel/cache qualification passed ten original identities before and
after remount, 32 negative controls and modified-cache rejection; the old
kernel fails the new read-write-root identity check. The original 50-case
loader regression remains valid for the unchanged exact loader.
CPU models are not an actual Apple userland or device-storage boot test.

Delivered Galaxy-A3-A320FL-BOOT-v0.11-Windows.zip: 14872738 bytes, 43 files,
SHA256 b7dd1b06427a288130ace70a119d3a343b6535ad54e180f68468275f02eaaa0b
Library ID libfile_0c8b45830e708191801794b4fa140d00.
Contains image, matching symbols/loader, source, checksums, test logs and
German TWRP/Windows instructions. Windows checker not run on real Windows.

NEXT: user must back up BOOT and the full USERDATA partition or retain the
full original iOS image, flash only this BOOT image in TWRP, then report the
first complete new panic/log or successful SpringBoard. This mode writes the
existing root volume during boot; restoring BOOT alone cannot undo volume
changes. No phone attached, no physical flash or USERDATA write performed.
Full launchd/service startup, journal replay, SpringBoard, touchscreen,
camera, audio, WLAN, Bluetooth and modem remain unverified. No guarantee
against unknown or future panics.

Primary sources read for this fix:
https://github.com/apple-oss-distributions/hfs/blob/main/mount_hfs/mount_hfs.c
https://github.com/apple-oss-distributions/hfs/blob/main/core/hfs_vfsops.c
https://github.com/dipa-studio/ios-sweet/blob/main/NOTES.md
https://github.com/wardevsa/ios-a5xelte/blob/herolte/A5XELTE_PROGRESS.md

GetMasterBlock opens the raw device O_RDONLY|O_NDELAY and can report EBUSY
for an existing mount; the fatal observed operation is the read-write HFS
mount update. The HFS update path opens the device FWRITE before clearing
its read-only state. The optional env=0 preboot ENOENT was not disguised
or repaired by fabricating firmware directories. No new hardware validation
is inferred from a registered placeholder service.


## 2026-11-21 — explicit launchd-cache development profile

Latest real-device photo: launchd_cache_loader[23] aborts with namespace 7,
subcode 1, "Unable to find AMFI". Earlier tzinit/PRNG boot tasks ran. The
previous mount-phase-1 read-only failure is no longer visible. The photo
does not contain an image digest, so it cannot prove a specific flashed hash.
This is further startup progress, not SpringBoard or successful full boot.

Native A3BootIdentity validates pinned original program identities; it does
not implement the AppleMobileFileIntegrity IOKit service that cache_loader
looks up (IOServiceOpen type 0, external method selector 6). Renaming the
MAC policy would not provide that service. Donor notes document the exact
same 20H392 failure and the launchd_unsecure_cache=1 development boot path.

A new explicit --development-launchd-cache packer option appends only this
argument and requires combined + writable-userdata + the pinned static
cache. IMPORTANT: this intentionally SKIPS launchd job-cache signature and
AMFI validation. It is a development workaround, not a completed AMFI
implementation, not a secure production boot, and not a guarantee of a GUI.
Ordinary profiles do not enable it. No Apple executable is patched.
Normal native program-identity checks have not been globally disabled.
No personal/confidential data should be used on this development system.

Packer source commit 836bbde6b3a7d2a033573bae35034c8ba257d340.
No kernel rebuild was needed; the native kernel and GCC loader are
byte-identical to delivered v0.11:
kernel source eae451d7b62368a29e63fdb51bec4bee5ab13c07
CI https://github.com/appleckae2510/ios-a5xelte/actions/runs/44893326915
kernel SHA256 98c155df91e9032a3901e9a587def241fb382c7d3aef8dd52cb3d700a988e953
loader source 8db4823ae09f4cf3ee7e667a5971a2508c8f83c4
loader SHA256 38dfe5c7ce6636b99fec60d51370d0124db6082108d0fd64b270610f342587b6

A3-A320FL-BOOT-v0.12-DEV.img, 27250704 bytes, SHA256:
9e0fc737985b665811097af51b91095134bb74096e1686e3334684b85b53a3aa
Passed on exact packed bytes: 11 full loader starts, 20 joint hardware/root
cases, original kernel policy/cache qualification (10 identities, 32 negative
controls), payload CRC32 and exact segment comparison. Profile comparison
normalizes only the expected fresh 64-byte random seed; otherwise all load
segments, ADT data, md0 and original static cache remain unchanged and only
the command line gains launchd_unsecure_cache=1. Three incomplete development
profile combinations are rejected. The unchanged kernel/loader retain their
previously completed 9 native write, 6 journal-profile and 50 loader cases.
Tests do NOT execute Apple's launchd_cache_loader. Its development branch
on this A3 remains a physical-device test, as does all subsequent userland.
Global Image4 static trust-cache API remains unsupported.

Delivered Galaxy-A3-A320FL-BOOT-v0.12-DEV-Windows.zip:
14872915 bytes, 44 files, SHA256:
aebed4be952a09ed3320ec95bf906f3a3a880cbf86e1f24609116160fe2e4b0c
Library ID libfile_aa903e021a308191b64a0a7c251bcb7b.
Package contains image, matching symbols/loader, source, checksums,
test reports and German installation/security-limit instructions.
Windows checker remains physically untested.

NEXT: user backs up BOOT and full USERDATA (or retains full original root
image), flashes only v0.12 DEV to Boot in TWRP, reports cache-loader
"Using unsecure cache" or the next complete panic and preceding lines.
USERDATA remains writable during boot. BOOT-only rollback cannot undo root
volume writes. No physical flash or phone writes were performed here.
SpringBoard and touch/camera/WLAN/BT/audio/modem remain unverified.

Primary evidence:
https://github.com/dipa-studio/ios-sweet/blob/main/NOTES.md
Entries for boots 0038e and 0039u, same 20H392 release. Reddit r/hackios was
also searched explicitly at the user's request; no direct verified exact
fix was found, and direct Reddit search could not be fetched. Do not label
this workaround a Reddit-verified A3 fix.


## Device evidence after v0.12 DEV — 2026-11-21

New user photos show repeating USERSPACE crashes, then a later genuine kernel
panic. backboardd SIGABRT (signal 6, reason ns 2/code 6); mediaserverd SIGSEGV
(signal 11, code 0x100000001, FAR 0). Shared-cache slide 0x0534c000.
mediaserverd PC 0x18c1aa0cc, LR 0x19ae29f30; backboardd PC 0x1c7963198,
LR 0x1d6ef25f8. backboardd main-image return offsets repeatedly include
+0x9334 (e.g. mh 0x1007cc000, return 0x1007d5334), matching the donor's
window-server startup wrapper. This similarity does not identify the
specific exception reason or prove that the display driver is the cause.

HID logs show SweetHIDTouch and SweetHIDButtons opened by
IOHIDEventServiceUserClient. This confirms userland opening those services,
not working physical touch or a rendered screen. No SpringBoard frame shown.

Later photo: "memorystatus_jetsam_thread: no victim! available pages:5693
@kern_memorystatus.c:4138", after Too many corpses and EXC_CORPSE_NOTIFY
send failures -308. Source review at the matching XNU tree shows this path
already attempts memorystatus_dump_caches(true) before panicking on remaining
critical memory pressure. Do NOT assert that uncollected corpses alone cause
the panic, or disable the Jetsam panic to present a false successful boot.

Native A3 policy still has only A3BootIdentity; the donor's named Sandbox
compatibility policy is not registered on this native path. The donor
records denied XPC lookups from missing Sandbox as a backboardd dependency.
This is a candidate native compatibility defect, not yet a measured cause
of this phone's specific SIGABRT. The CPU-monitor entitlement warning on
mediaserverd does not itself establish why it dereferences NULL.
Do not globally grant new entitlements based on that warning.

Existing diagnostics: Sweet crash-string scan defaults to backboardd and
SpringBoard and is limited to the first four scans on A5XELTE; matching IOKit
trace is also bounded. The later user photos omit the early diagnostic lines.
NEXT REQUIRED EVIDENCE: record a video from boot through the FIRST backboardd
crash, including STR/IOK lines and the preceding error. Full kernel log or
symbolication with the exact 20H392 shared cache would be preferable.
A3 has no established working live-log/USB link in this session. Do not claim
ADB logcat works in this native XNU boot or flash another device's drivers.

Apple XNU has a native -no_corpses development flag (corpse.c:159,
corpses_enabled returns !corpses_disabled). It can reduce crash-dump retention
but does not repair either service and does not guarantee avoiding Jetsam.
It has NOT been added to the delivered BOOT or tested on the phone.
No v0.13 image or new kernel is built in this diagnostic milestone.
Current delivery remains v0.12 DEV with its explicitly disclosed cache
signature-check skip. No physical phone write performed.



## Video milestone — 2026-11-21, v0.13 work in progress

The supplied 291.633 s boot video confirms "Using unsecure cache" and "Cache
sent to launchd successfully" around 01:05. Around 02:10-02:20 the first
backboardd heap diagnostics show "Failed at lookup with error 159 - Sandbox
restriction" and "NSInvalidArgumentException ... NSURL initFileURLWithPath:
nil string parameter". Unlike the earlier stills this directly establishes
a failed Sandbox lookup in the process immediately preceding its failure.
The missing container path is the immediate exception; whether the next
lookup succeeds on the A3 still needs a real-device boot. The media process
SIGSEGV and eventual Jetsam exhaustion are separate effects still to verify.

Prepared native patch 0409 registers a named Sandbox compatibility policy
before lockdown, with sealed config and handle. It permits init/check/note/
bulk-check operations only for pinned original 20H392 platform binaries.
Path/extension requests return ENOENT; unknown operations return ENOPOLICY;
unknown hashes, wrong hash type or non-platform processes return EPERM.
Only PRIV_WORK_INTERVAL can be granted, under the same stock-process gate.
No arbitrary entitlements, container paths or extension tokens are invented.
This is a restricted development compatibility policy, NOT a Seatbelt engine.

New explicit packer option --disable-crash-snapshots adds Apple's existing
-no_corpses flag only to the development profile. It reduces retained crash
snapshots, does not suppress process crashes or the Jetsam panic and does
not by itself fix memory pressure. Existing launchd cache signature-check
skip remains explicitly disclosed. Userland and actual storage are untested.

The new native regression requires the Sandbox policy; v0.12 kernel fails
this added requirement with exit 3 while retaining its passing original
identity tests. Local Python syntax and patch application preflight pass.
Next: CI compilation and native/whole-image regressions. No v0.13 release yet.


## 2026-11-21 — BOOT v0.13 DEV native Sandbox compatibility and corpse control

The user's 291.633-second video is inspected. At about 01:05 it shows
"Using unsecure cache" and "Cache sent to launchd successfully": the earlier
AMFI cache-loader abort is passed. At about 02:10-02:25 the bounded
backboardd heap-string diagnostic contains "Failed at lookup with error 159
- Sandbox restriction" and NSInvalidArgumentException, NSURL
initFileURLWithPath: nil string parameter. These are diagnostic strings in
the failed process, not a complete execution trace proving all causality.
The donor A5XELTE notes localize the same exception to a missing system-
container path. Current native code lacked the named Sandbox policy.
Repeated mediaserverd SIGSEGV and a later Jetsam no-victim panic were shown
in earlier stills. No full GUI boot is shown and photos/video carry no hash.

NEW NATIVE KERNEL BUILT:
Source 733bb3fa12f8190c22ce65b44022d820f257b83e
CI https://github.com/appleckae2510/ios-a5xelte/actions/runs/44911647525
Native build job 136868551923 and qualification job 136870893429 succeeded.
Artifact 14710019103 (kernel ZIP digest
b917c8486039cc4ee9a13cbf07d89bbedecd56aaa90aa16e319bb298a4eb9599).
Kernel 17599616 bytes, SHA256:
417bd37280dfec9d29902e7ab3668f02d762e5f36fb7435bf94c881a5b24d4a0
First attempt 45d877e59508086ed3309ad8f63af3ae83dae22e / run 44910801670
failed compilation because PROC_NULL is not defined in this native TU.
733bb3 replaces that sentinel with NULL. Failed artifact was not released.

Patch 0409 registers a named Sandbox compatibility policy before lockdown
with readonly config and handle. It only accepts measured original 20H392
identities with their original hash type and current platform status.
Init/check/note/bulk-check operations succeed for these original programs;
paths and extension operations return ENOENT without fabricated data,
unsupported operations return ENOPOLICY, and unknown/non-platform identities
return EPERM. Only PRIV_WORK_INTERVAL is grantable under the same stock gate.
This is NOT a complete Seatbelt engine. Original entitlements are unchanged.
No new blanket entitlement or CPU-monitor exemption was added.
Missing-container-path, media and graphical startup still require hardware
verification; do not claim every userland fault is fixed.

Explicit --disable-crash-snapshots adds native -no_corpses only with the
development cache profile. The real linked kernel tunable initializer and
corpses_enabled were replayed: without flag 1, with shipped command 0.
This reduces retained crash snapshots, does NOT hide daemon failures or the
Jetsam panic, and is not proof that all memory pressure is resolved.
launchd_unsecure_cache=1 remains active and still skips launchd job-cache
signature/AMFI validation. No complete AMFI IOKit or Image4 service is supplied.

Exact final image A3-A320FL-BOOT-v0.13-DEV.img, 27250704 bytes, SHA256:
4158bb293e44ac9f6daabf762c5b4029c893c3d7f07b2b4d298f021bb83cd53a
Same validated GCC loader from 8db4823ae09f4cf3ee7e667a5971a2508c8f83c4,
loader SHA256 38dfe5c7ce6636b99fec60d51370d0124db6082108d0fd64b270610f342587b6.
Payload remains A3XNPAY2 with CRC32, exact diagnostic RAM volume retained.

PASSED ON FINAL BYTES:
11 loader trials, 20 combined hardware/root-selection cases, 9 native
bounded USERDATA-write cases; native startup/MAC sealing and original
cache/boot identities (10 originals, 32 negative controls); 144 native
Sandbox identity/operation cases plus null-process rejection; two actual
named MAC syscall dispatch cases; two actual native corpse-tunable cases.
The old kernel fails the new Sandbox requirement and returns ENOPOLICY for
the actual named Sandbox syscall; the new finds it and rejects the deliberately
null process with EPERM. Copying user strings and audit context are modeled.
Positive stock identity decisions are tested on the actual native decision
helper, NOT on a complete live process/credential simulation.
Host-C check also ran the exact new helper against all 2754 cache entries
and invalid-type/non-platform/unknown-op controls. The exact unchanged
loader retains its 50-case regression; 6 journal-profile checks unchanged.
No test executes Apple's full launchd/backboardd or native device hardware.

DELIVERED Galaxy-A3-A320FL-BOOT-v0.13-DEV-Windows.zip
14887928 bytes, 53 files, SHA256:
a19a0a15cdd218c1a965dcdc61784804c5d53cd01b152542057fbaf48c8ef995
Library ID libfile_bdbaaa6d391c81919ae6032f20908d88
Includes image, matching kernel/loader, source, replay helpers, complete
file checksums and German TWRP/Windows instructions and explicit limits.
ZIP CRC, membership, all member lengths/SHA256 were verified.
The PowerShell checker has not been run on real Windows.

NEXT DEVICE TRIAL:
User backs up BOOT and full USERDATA (or retains original full iOS root
image), flashes ONLY this IMG to Boot in TWRP, records boot. Look for
"A3 stock Sandbox compatibility registered before lockdown" and
"A3 Sandbox: ... op 2 -> 0", then the first complete error or real GUI.
USERDATA remains writable. BOOT-only rollback cannot undo volume writes.
No phone flash or physical storage write performed here.
SpringBoard, working physical touch, camera, WLAN, BT, audio and modem
remain unverified. Unknown future panics cannot be ruled out.


## 2026-11-21 — original Cryptex caches, v0.14 work in progress

New photo: userspace panic "unexpected exec of non-platform binary"
/System/Cryptexes/App/usr/libexec/webbookmarksd, PID315. Framebuffer reports
copy/swap frames (~12.5 fps); this is not proof of SpringBoard or a complete
GUI. v0.13 has progressed to further userland but a physical flashed-image
digest is not shown.

The original d21ap 20H392 AppOS component (10MiB APFS) was downloaded by
exact IPSW byte range and verified with CRC/length and SHA384 from the
BuildManifest. Original ARM64 webbookmarksd slice verified all 38 signed
code-page hashes. CodeDirectory hash b0a439a33ae99ae3ca1bc102fe61802394582d36,
hash type2, original App-cache constraint category1. ARM64 SHA256
17805387dcc42b957efae50cd0013b12c1105cf8842f830e29946c21719294ff.
It is absent from the existing 2754-entry root cache and present in the
separate 30-entry App Cryptex cache. No arbitrary platform flag is justified.

Patch 0410 adds the original 30 App and 61 Cryptex-System entries, preserving
both original module bytes/UUIDs/types/constraints. The packer authenticates
both IM4P components against the d21ap Erase BuildManifest fingerprints and
places their 2244-byte canonical two-module table in an A3 ADT property.
The native kernel checks ADT bounds, hashes the entire fixed table and
copies it to protected pre-lockdown memory. Original root-cache layout is
unchanged. Native identity lookup tries root then the two Cryptex modules.
Only original Cryptex identities may additionally use a non-root read-only
mount; unrelated writable mounts and wrong hashes/types still fail.
The existing Sandbox stock-process gate consequently covers those genuine
Cryptex programs too. This does not implement the global Image4/AMFI API.

Additional regression requires the exact Cryptex modules, rejects altered
constraints, checks all 91 original records and mount scope, and explicitly
covers the audited original webbookmarksd platform/Sandbox identity.
The old v0.13 kernel/profile fails the new requirement (exit3) and refuses
that App identity without its module. Host-C checks and patch/Python
preflight passed. Next: native CI build and final whole-image tests.
No v0.14 image released yet. Existing development cache-signature skip and
-no_corpses remain disclosed. Actual successful iOS boot remains unverified.

Downloaded Apple components/binaries remain private and outside git.
