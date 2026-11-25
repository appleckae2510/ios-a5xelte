"""Select native iPhoneOS in the pinned builder for J3Y17LTE, not A5XELTE."""
from pathlib import Path
import sys

def edit(s, old, new, n=1):
    if s.count(old) != n:
        raise ValueError("builder anchor changed: " + old)
    return s.replace(old, new)

def prepare(s):
    target = "SDKROOT=iphoneos SDKVERSION=16.7 ARCH_STRING_FOR_CURRENT_MACHINE_CONFIG=arm64"
    xt = "-sdk iphoneos SUPPORTED_PLATFORMS=iphoneos IPHONEOS_DEPLOYMENT_TARGET=16.7"
    s = edit(s, 'if [ ! -d "${KDKROOT}" ]; then', 'if [ "$MACHINE_CONFIG" != J3Y17LTE ] && [ ! -d "${KDKROOT}" ]; then', 3)
    s = edit(s, '    if [ ! -d "$KDKROOT" ]; then', '    if [ "$MACHINE_CONFIG" = J3Y17LTE ]; then\n        info "J3 open-source target; KDK unused"\n        return\n    fi\n    if [ ! -d "$KDKROOT" ]; then')
    s = edit(s, '    patches\n    venv', '    patches\n    python3 "../tools/a3-j3-rebase.py" "$WORK_DIR/xnu"\n    venv')
    s = edit(s, 'make installhdrs SDKROOT=macosx ARCH_CONFIGS="X86_64 ARM64"', f"make installhdrs {target} ARCH_CONFIGS=ARM64")
    s = edit(s, "SDKROOT=macosx TARGET_CONFIGS=", f"{target} TARGET_CONFIGS=", 3)
    s = edit(s, "xcodebuild installhdrs -sdk macosx", f"xcodebuild installhdrs {xt}", 2)
    s = edit(s, '-target libfirehose_kernel -sdk macosx ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"', f'-target libfirehose_kernel {xt} ARCHS=arm64 VALID_ARCHS=arm64 OTHER_CFLAGS="-mkernel -nostdinc -Wno-packed -mcpu=cortex-a53 -march=armv8-a+crypto -I${{WORK_DIR}}/xnu/EXTERNAL_HEADERS -idirafter$(xcrun --sdk iphoneos --show-sdk-path)/usr/include"')
    # No silent rejection of numbered donor patches.
    s = edit(s, 'warning "Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}"', 'warning "Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}"\n                if [[ "$(basename "$PATCH")" =~ ^[0-9]{4}- ]]; then\n                    echo "Required donor patch rejected: $PATCH" >&2\n                    exit 1\n                fi')
    return s

if __name__ == "__main__":
    p = Path(sys.argv[1])
    p.write_text(prepare(p.read_text()))
