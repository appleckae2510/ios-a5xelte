#!/usr/bin/env python3
"""Compile the A3 loader only. Output is not a flashable Android boot image."""
import argparse
from pathlib import Path
import struct
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig', help='path to Zig 0.14.1 (optional; otherwise use GCC cross compiler)')
    p.add_argument('--cross', default='aarch64-linux-gnu-')
    a = p.parse_args()
    root = Path(__file__).resolve().parent
    out = root / 'out'
    out.mkdir(exist_ok=True)
    cc = [str(Path(a.zig).resolve()), 'cc', '-target', 'aarch64-freestanding-none'] if a.zig else [a.cross + 'gcc']
    flags = ['-O2', '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
             '-fno-pic', '-fno-pie', '-nostdlib', '-fno-asynchronous-unwind-tables',
             '-fno-unwind-tables', '-mgeneral-regs-only', '-mstrict-align',
             '-mcpu=cortex_a53' if a.zig else '-march=armv8-a', '-Wall', '-Wextra', '-Werror']
    objects = []
    for name in ['xnu_boot.S', 'xnu_boot.c', 'display_console.c']:
        obj = out / (name.replace('.', '_') + '.o')
        subprocess.run(cc + flags + ['-c', str(root / name), '-o', str(obj)], check=True)
        objects.append(str(obj))
    elf = out / 'a3y17lte-loader.elf'
    subprocess.run(cc + ['-nostdlib', '-static', '-Wl,-T,' + str(root / 'xnu_boot.ld'),
                         '-Wl,--build-id=none'] + objects + ['-o', str(elf)], check=True)
    image = out / 'a3y17lte-loader.Image'
    objcopy = [str(Path(a.zig).resolve()), 'objcopy'] if a.zig else [a.cross + 'objcopy']
    subprocess.run(objcopy + ['-O', 'binary', str(elf), str(image)], check=True)
    data = image.read_bytes()
    if data[56:60] != b'ARMd' or len(data) > 0x4000:
        raise SystemExit('Invalid Image header or loader overlaps the payload area')
    if struct.unpack_from('<Q', data, 8)[0] != 0x80000 or struct.unpack_from('<Q', data, 24)[0] != 0:
        raise SystemExit('Unexpected A320FL arm64 Image placement fields')
    print(f'Compiled A3 loader: {len(data)} bytes; phone boot UNTESTED; not flashable on its own.')


if __name__ == '__main__':
    main()
