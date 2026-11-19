"""Select iPhoneOS for device products in the pinned XNU builder."""

from pathlib import Path
import sys


def select_target(source):
    make_target = "SDKROOT=iphoneos SDKVERSION=16.7 ARCH_STRING_FOR_CURRENT_MACHINE_CONFIG=arm64"
    xcode_target = "-sdk iphoneos SUPPORTED_PLATFORMS=iphoneos IPHONEOS_DEPLOYMENT_TARGET=16.7"
    replacements = [
        ("    patches\n    venv",
         '    patches\n    python3 "../tools/a3-native-sources.py" "$WORK_DIR/xnu" '
         '"../xnu/a3y17lte-patches/0404-a3y17lte-combined-userland.patch"\n    venv', 1),
        ('make installhdrs SDKROOT=macosx ARCH_CONFIGS="X86_64 ARM64"',
         f"make installhdrs {make_target} ARCH_CONFIGS=ARM64", 1),
        ("SDKROOT=macosx TARGET_CONFIGS=", f"{make_target} TARGET_CONFIGS=", 3),
        ("xcodebuild installhdrs -sdk macosx", f"xcodebuild installhdrs {xcode_target}", 2),
        ('-target libfirehose_kernel -sdk macosx ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"',
         f"-target libfirehose_kernel {xcode_target} ARCHS=arm64 VALID_ARCHS=arm64 "
         'OTHER_CFLAGS="-mkernel -nostdinc -Wno-packed -mcpu=cortex-a53 -march=armv8-a+crypto"', 1),
    ]
    for old, new, expected in replacements:
        if source.count(old) != expected:
            raise ValueError(f"unexpected upstream device build command: {old}")
        source = source.replace(old, new)
    return source


if __name__ == "__main__":
    builder = Path(sys.argv[1])
    builder.write_text(select_target(builder.read_text()))
