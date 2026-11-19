"""Check the device kernel's Mach-O and the compile command for its exec path."""

from pathlib import Path
import re
import struct
import sys


def target(kernel):
    data = kernel.read_bytes()
    if len(data) < 32:
        raise ValueError("short Mach-O header")
    magic, arch, subtype, kind, ncmds, cmdsize, _, _ = struct.unpack_from("<8I", data)
    if (magic, arch, subtype & 0xffffff, kind) != (0xfeedfacf, 0x0100000c, 0, 2):
        raise ValueError("expected a thin ARM64_ALL MH_EXECUTE kernel")
    cursor, limit, versions = 32, 32 + cmdsize, []
    if limit > len(data):
        raise ValueError("truncated load commands")
    for _ in range(ncmds):
        if cursor + 8 > limit:
            raise ValueError("short load command")
        command, size = struct.unpack_from("<2I", data, cursor)
        if size < 8 or size % 8 or cursor + size > limit:
            raise ValueError("bad load command size")
        if command == 0x32:
            if size < 24:
                raise ValueError("short LC_BUILD_VERSION")
            platform, version, _, tools = struct.unpack_from("<4I", data, cursor + 8)
            if size < 24 + 8 * tools:
                raise ValueError("truncated build tools")
            versions.append((platform, version))
        elif command in (0x24, 0x25, 0x2f, 0x30):
            if size != 16:
                raise ValueError("bad LC_VERSION_MIN size")
            platform = {0x24: 1, 0x25: 2, 0x2f: 3, 0x30: 4}[command]
            versions.append((platform, struct.unpack_from("<I", data, cursor + 8)[0]))
        cursor += size
    if cursor != limit or len(versions) != 1:
        raise ValueError(f"ambiguous target {versions}")
    return versions[0]


def verify(kernel, log):
    platform, version = target(kernel)
    print(f"Mach-O platform={platform}, minOS={version >> 16}.{(version >> 8) & 255}.{version & 255}")
    if (platform, version) != (2, 0x100700):
        raise ValueError("expected the iOS device platform and deployment target 16.7")
    found = False
    with log.open(errors="replace") as stream:
        for line in stream:
            if not (re.search(r'(?:^|\s)-c(?:\s|$)', line) and 'kern_exec.c' in line):
                continue
            if '-DXNU_TARGET_OS_OSX' in line or '-DXNU_TARGET_OS_IOS' not in line:
                raise ValueError("kern_exec.c was not compiled for iOS")
            found = True
    if not found:
        raise ValueError("missing kern_exec.c compiler invocation")


if __name__ == "__main__":
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
