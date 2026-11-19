"""Compile Apple's exec and Mach-O loaders with the A3 headers and the device SDK."""

from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys


def xcrun(*args):
    return subprocess.check_output(["xcrun", "--sdk", "iphoneos", *args], text=True).strip()


def compile_loaders(base, apple, log):
    unit_names = {"kern_exec.c", "mach_loader.c"}
    done = set()
    build = base / "build/xnu.obj/DEVELOPMENT_ARM64_A5XELTE/bsd/DEVELOPMENT"
    sdk = xcrun("--show-sdk-path")
    clang = xcrun("--find", "clang")
    with log.open(errors="replace") as stream:
        for line in stream:
            if " -c " not in line or "-DXNU_TARGET_OS_OSX" not in line:
                continue
            if not any("/" + name in line for name in unit_names - done):
                continue
            argv = shlex.split(line)
            suffix = next((a for a in argv if any(a.endswith("/bsd/kern/" + n)
                           for n in unit_names - done)), None)
            if suffix is None:
                continue
            old = suffix[:suffix.index("/xnu/bsd/kern/")]
            name = Path(suffix).name
            source = base / "xnu/bsd/kern" / name
            shutil.copyfile(apple / "bsd/kern" / name, source)
            out = base / (source.stem + ".iphoneos.o")
            args = [clang, "-isysroot", sdk]
            orig = iter(argv[1:])
            for a in orig:
                if a in {"-o", "-MF", "-MT", "-MQ"}:
                    next(orig)
                elif a.startswith("-mmacosx-version-min="):
                    args.append("-miphoneos-version-min=16.7")
                elif a.startswith("-I/Applications/"):
                    continue
                elif a not in {"-MP", "-MD"}:
                    args.append(a.replace(old, str(base)).replace("XNU_TARGET_OS_OSX", "XNU_TARGET_OS_IOS")
                                .replace("XNU_PLATFORM_MacOSX", "XNU_PLATFORM_iPhoneOS"))
            args.extend(["-o", str(out)])
            subprocess.run(args, cwd=build, check=True)
            data = out.read_bytes()
            magic, arch, subtype, kind, count, size = struct.unpack_from("<6I", data)
            assert (magic, arch, subtype & 0xffffff, kind) == (0xfeedfacf, 0x100000c, 0, 1)
            assert size <= len(data) - 32
            at, targets = 32, []
            for _ in range(count):
                cmd, length = struct.unpack_from("<II", data, at)
                assert 8 <= length <= 32 + size - at
                if cmd == 0x32:
                    targets.append(struct.unpack_from("<II", data, at + 8))
                at += length
            assert targets == [(2, 0x100700)], targets
            print(f"A3 COMPILE {name}: native ARM64 iOS 16.7 object, {len(data)} bytes", flush=True)
            done.add(name)
    if done != unit_names:
        raise ValueError("Missing compiler invocation: " + ", ".join(sorted(unit_names - done)))


if __name__ == "__main__":
    compile_loaders(*(Path(arg).resolve() for arg in sys.argv[1:]))
