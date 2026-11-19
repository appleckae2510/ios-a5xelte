"""Prepare the resolved A3 board sources for the native XNU configuration."""

from pathlib import Path
import sys


def prepare(root, board):
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
