#!/usr/bin/env python3
"""A3 (2017) entry ADT; hardware handoff remains unverified on a phone."""
import argparse
from pathlib import Path

import adt
import mkadt
import mkadt_j7prime as donor

RAM_BASE = 0x92000000
RAM_END = 0xAE000000
FB_BASE, WIDTH, HEIGHT, STRIDE = 0x67000000, 720, 1280, 2880
MARKER = b'A3Y17LTE_PORT_V1_720X1280_IST3038H'


def build(product_adt=None):
    root = donor.build('d21ap', product_adt, iphone8=True)
    chosen = donor.child(root, 'chosen')
    donor.set_prop(chosen, 'dram-base', mkadt.u64(RAM_BASE))
    donor.set_prop(chosen, 'dram-size', mkadt.u64(RAM_END - RAM_BASE))
    donor.set_prop(chosen, 'firmware-version', mkadt.cstr('a3y17lte-entry-v1'))
    donor.set_prop(chosen, 'system-firmware-version', mkadt.cstr('a3y17lte-entry-v1'))
    # Preserve the shared A5XELTE platform-expert match, remove J7 board identity.
    compat = root.prop('compatible').replace(b'samsung,on7xelte\0', b'samsung,a3y17lte\0')
    donor.set_prop(root, 'compatible', compat)
    donor.set_prop(root, 'a3-port-marker', MARKER + b'\0')
    arm_io = donor.child(root, 'arm-io')
    # GPU service is deliberately absent until power/clock handoff is measured.
    arm_io.children = [n for n in arm_io.children if n.name != 'gpu']
    fb = donor.child(root, 'a5xelte-fbcon')
    for name, value in [('reg', mkadt.u64(FB_BASE, STRIDE * HEIGHT)),
                        ('width', mkadt.u32(WIDTH)), ('height', mkadt.u32(HEIGHT)),
                        ('stride', mkadt.u32(STRIDE))]:
        donor.set_prop(fb, name, value)
    # 750x1334 is an iOS-supported canvas; kernel scales to native 720x1280.
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--product-adt', type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    blob = adt.serialize(build(args.product_adt))
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes; A3 entry tree, physical boot unverified')
