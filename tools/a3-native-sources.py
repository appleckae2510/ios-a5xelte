"""Prepare the resolved A3 board sources for the native XNU configuration."""

from pathlib import Path
import subprocess
import sys


def upstream(root, name):
    return subprocess.check_output(["git", "show", "HEAD:" + name], cwd=root)


def prepare(root, board):
    # Start these shared subsystems at the pinned Apple release. Device I/O has
    # already been resolved from the board's ordered patch history.
    for name in ("bsd/kern/kern_exec.c", "bsd/kern/mach_loader.c",
                 "bsd/kern/kern_trustcache.c", "bsd/kern/ubc_subr.c",
                 "osfmk/vm/vm_shared_region.c", "osfmk/kern/exception.c"):
        (root / name).write_bytes(upstream(root, name))

    # Keep the native mount path and attach just the two board-specific pieces.
    name = "bsd/kern/bsd_init.c"
    source = upstream(root, name).decode()
    anchor = "\tvfsinit();"
    if source.count(anchor) != 1:
        raise ValueError("unexpected bsd_init filesystem registration")
    hfs = "\n#if SWEET_HFS\n\textern void sweet_hfs_register(void);\n\tsweet_hfs_register();\n#endif"
    (root / name).write_text(source.replace(anchor, anchor + hfs))
    subprocess.run(["git", "apply", "--include=" + name, str(board)], cwd=root, check=True)

    omitted = {"sweet_amfi.c", "SweetEntitlements.cpp", "SweetKeyStore.cpp"}
    for table in ("bsd/conf/files", "iokit/conf/files.arm64"):
        path = root / table
        kept = []
        for line in path.read_text().splitlines(keepends=True):
            fields = line.split()
            if fields and Path(fields[0]).name in omitted:
                (root / fields[0]).unlink()
            else:
                kept.append(line)
        path.write_text("".join(kept))

    # The Apple header generator deliberately preprocesses vm_map_internal for
    # a 32-bit ABI. Give only that MIG preprocessing step a supported min OS.
    path = root / "libsyscall/xcodescripts/mach_install_mig.sh"
    source = path.read_text()
    anchor = "    MACHINE_ARCH=armv7\n"
    if source.count(anchor) != 1:
        raise ValueError("unexpected header-generator architecture selection")
    extra = '    if [ "${PLATFORM_NAME:-}" = iphoneos ]; then\n        export IPHONEOS_DEPLOYMENT_TARGET=10.0\n    fi\n'
    path.write_text(source.replace(anchor, anchor + extra))
    for name in ("bsd/dev/a3_boot_volume.inc", "bsd/dev/a3_hardware.inc", "bsd/dev/a3_touch.inc"):
        if not (root / name).is_file():
            raise ValueError("A3 hardware overlay missing: " + name)


if __name__ == "__main__":
    prepare(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
