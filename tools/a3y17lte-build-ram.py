#!/usr/bin/env python3
"""Build the 8 MiB HFS fallback for --combined. Writes only the output image."""
import argparse
from pathlib import Path
import subprocess
import tempfile

import mkinit

TOOLS = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    compiler = parser.add_mutually_exclusive_group()
    compiler.add_argument('--clang', default='clang', help='Clang with ARM64 Mach-O support')
    compiler.add_argument('--zig', help='use Zig cc in place of Clang')
    parser.add_argument('--mkfs', default='mkfs.hfsplus')
    parser.add_argument('--hfsplus', default='hfsplus', help='libdmg-hfsplus file utility')
    parser.add_argument('--fsck', default='fsck.hfsplus')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
        stage = Path(temp)
        image = stage / 'fallback.hfs'
        with image.open('xb') as f:
            f.truncate(8 * 1024 * 1024)
        subprocess.run([args.mkfs, '-v', 'A3Combined', image], check=True)

        def hfs(*arguments):
            subprocess.run([args.hfsplus, image, *arguments], check=True)

        def add_file(path, data, mode):
            source = stage / 'import-file'
            copy = stage / 'readback'
            source.write_bytes(data)
            hfs('add', source, path)
            hfs('chmod', mode, path)
            hfs('extract', path, copy)
            if copy.read_bytes() != data:
                raise ValueError(f'HFS readback mismatch for {path}')

        for folder in ('/sbin', '/dev', '/etc'):
            hfs('mkdir', folder)
        cc = [args.zig, 'cc', '-target', 'aarch64-ios', '-mcpu=cortex_a53'] if args.zig else [
            args.clang, '-target', 'arm64-apple-ios16.0', '-mcpu=cortex-a53']
        for name, defines in (('launchd', []), ('a3-userland', ['-DA3_RAM_USERLAND'])):
            obj = stage / (name + '.o')
            subprocess.run([*cc, '-g0', '-c', *defines, TOOLS / 'a3y17lte-ram-init.S', '-o', obj], check=True)
            add_file('/sbin/' + name, mkinit.build(obj.read_bytes()), '755')
        add_file('/etc/a3-boot-id', b'A3RAM08!', '644')
        subprocess.run([args.fsck, '-fn', image], check=True)
        image.replace(args.output)


if __name__ == '__main__':
    main()
