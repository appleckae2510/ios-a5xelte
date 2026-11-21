#!/usr/bin/env python3
"""Package an A3 entry test using its own backed-up BOOT/DTBH. Never flashes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import zipfile
import zlib

import adt
import mkadt_a3y17lte as board
import mkpayload


def unpack_boot(blob):
    if len(blob) < 2048 or blob[:8] != b'ANDROID!': raise ValueError('Not an Android BOOT image')
    ks, ka, rs, ra, ss, sa, tags, page, ds = struct.unpack_from('<9I', blob, 8)
    if page != 2048 or ss or not ks or not ds: raise ValueError('Unsupported Samsung BOOT layout')
    align = lambda n: (n + page - 1) & ~(page - 1)
    ro = page + align(ks)
    do = ro + align(rs)
    if do + ds > len(blob): raise ValueError('BOOT components exceed the backup')
    kernel, ramdisk, dt = blob[page:page+ks], blob[ro:ro+rs], blob[do:do+ds]
    if dt[:4] != b'DTBH': raise ValueError('A3 Samsung DTBH missing; no donor DTBH fallback')
    version, count = struct.unpack_from('<II', dt, 4)
    if version != 2 or not 1 <= count <= 64 or 12 + count * 32 > len(dt):
        raise ValueError('Unsupported DTBH table')
    for i in range(count):
        chip, _, _, lo, hi, off, size, _ = struct.unpack_from('<8I', dt, 12 + 32 * i)
        if chip != 7870 or lo > hi or off < 12 + count * 32 or off + size > len(dt):
            raise ValueError('Invalid A3 DTBH entry')
        fdt = dt[off:off+size]
        if fdt[:4] != b'\xd0\x0d\xfe\xed' or len(fdt) < 40:
            raise ValueError('DTBH entry is not an FDT')
        # Conservative identity gate; no J7 or Japanese A3 Prime profiles.
        if b'A3Y17' not in fdt or b'A3Y17P' in fdt or b'a3y17plte' in fdt:
            raise ValueError('DTBH entry is not the supported A3Y17 board')
    return blob[:page], kernel, ramdisk, dt


def boot_digest(kernel, ramdisk, dt, include_second):
    h = hashlib.sha1()
    pieces = [kernel, ramdisk] + ([b''] if include_second else []) + [dt]
    for data in pieces:
        h.update(data); h.update(struct.pack('<I', len(data)))
    return h.digest()


def repack_boot(original, image):
    header, oldkernel, ramdisk, dt = unpack_boot(original)
    variant = next((v for v in (False, True)
                    if boot_digest(oldkernel, ramdisk, dt, v) == header[576:596]), None)
    if variant is None: raise ValueError('Unknown stock BOOT digest convention; manual inspection required')
    hdr = bytearray(header)
    struct.pack_into('<I', hdr, 8, len(image))
    hdr[576:608] = boot_digest(image, ramdisk, dt, variant).ljust(32, b'\0')
    pad = lambda b: b + b'\0' * (-len(b) % 2048)
    result = bytes(hdr) + pad(image) + pad(ramdisk) + pad(dt) + b'SEANDROIDENFORCE'
    if len(result) > len(original): raise ValueError('Entry image exceeds actual BOOT partition backup')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True, type=Path, help='private A3-Diagnose.zip')
    p.add_argument('--kernel', required=True, type=Path, help='A3-specific XNU from a3-xnu CI')
    p.add_argument('--loader', required=True, type=Path)
    p.add_argument('--ramdisk', type=Path, help='optional md0 image (HFS volume or mockfs test executable)')
    p.add_argument('--a3-static-cache', type=Path, metavar='20H392-IM4P',
                   help='pass the original d21ap 20H392 static trust cache to XNU')
    p.add_argument('--product-adt', type=Path, help='matching Apple product metadata from the root build')
    p.add_argument('--ios-root', action='store_true',
                   help='boot a separately installed HFSX iOS root from USERDATA with writes inside that partition')
    p.add_argument('--combined', action='store_true',
                   help='check the board and select the prepared read-only iOS root or the included diagnostic HFS')
    p.add_argument('--writable-userdata', action='store_true',
                   help='with --combined, allow the validated USERDATA root to accept iOS mount updates and writes')
    p.add_argument('--probe-emmc', action='store_true',
                   help='read the internal GPT and report USERDATA while booting from md0')
    p.add_argument('--probe-hardware', action='store_true',
                   help='report A3 power/clock state and try HCI version on an initialized UART')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-unverified-handoff', action='store_true',
                   help='acknowledge that each new image needs a hardware trial')
    a = p.parse_args()
    if a.ios_root and a.ramdisk:
        p.error('--ios-root and --ramdisk select different root devices')
    if a.combined and (a.ios_root or not a.ramdisk or not a.product_adt):
        p.error('--combined requires --ramdisk and --product-adt and selects the root automatically')
    if a.a3_static_cache and not a.combined:
        p.error('--a3-static-cache requires the combined A3 boot profile')
    if a.writable_userdata and not a.combined:
        p.error('--writable-userdata requires --combined')
    if not a.allow_unverified_handoff:
        p.error('Review the handoff for this image and pass --allow-unverified-handoff to build it.')
    with zipfile.ZipFile(a.evidence) as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('target') != 'a3y17lte' or manifest.get('phone_writes') is not False:
            raise ValueError('Unexpected evidence bundle')
        original = z.read('boot.img')
        proof = manifest['files']['boot.img']
        if len(original) != proof['size'] or hashlib.sha256(original).hexdigest() != proof['sha256']:
            raise ValueError('BOOT backup hash mismatch')
        props = json.loads(z.read('device.json'))
        if not any(props.get(k, '').lower() in {'a3y17lte','a3y17ltexx','a3y17ltexc','a3y17ltelk'}
                   for k in ('ro.product.device', 'ro.build.product')):
            raise ValueError('Evidence device is not a3y17lte')
    unpack_boot(original)
    kernel = a.kernel.read_bytes()
    if board.MARKER not in kernel: raise ValueError('Kernel lacks A3 marker; J7/S7 kernels are refused')
    if (a.probe_hardware or a.combined) and b'A3Y17LTE_HARDWARE_V2' not in kernel:
        raise ValueError('Hardware probe needs the A3 kernel with patch 0403 (CP registers skipped)')
    if a.combined and b'A3 COMBINED: RAM root' not in kernel:
        raise ValueError('Combined boot needs the A3 kernel with patch 0404')
    if a.writable_userdata and b'A3 USERDATA: validated writable root' not in kernel:
        raise ValueError('Writable combined boot requires the A3 mount-update kernel')
    if a.ios_root and b'A3Y17LTE_USERDATA_RW_V1' not in kernel:
        raise ValueError('USERDATA root needs the A3 kernel with patch 0402')
    m = mkpayload.parse_macho(kernel)
    if m['cputype'] != 0x100000c or m['cpusub'] != 0 or m['entry'] is None:
        raise ValueError('Need plain ARM64 A3 Mach-O, not ARM64e/PAC')
    loader = a.loader.read_bytes()
    if len(loader) > 0x4000 or loader[56:60] != b'ARMd' or b'A3 2017 XNU LOADER' not in loader:
        raise ValueError('Not the compiled A3 entry loader')
    if b'A3XNPAY2' not in loader:
        raise ValueError('Use the A3 loader with checked-payload support')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    storage_args = 'emmcprobe=1 emmcroot=USERDATA' if a.probe_emmc else 'emmcprobe=0'
    storage_args += ' emmcwrite=0'
    root_device = 'md0'
    if a.ios_root:
        root_device = 'emmcroot0'
        storage_args = 'emmcprobe=0 emmcroot=USERDATA emmcwrite=1'
    if a.combined:
        # Resolve rd in IOFindBSDRoot, then report the actual BSD root to VFS.
        root_device = 'a3auto'
        storage_args = 'emmcprobe=0 emmcroot=USERDATA emmcwrite=0 a3combined=1 ignition_level=1'
        if a.writable_userdata:
            storage_args = storage_args.replace('emmcwrite=0', 'emmcwrite=1')
    hardware_args = ' a3hwprobe=1 a3btprobe=1' if a.probe_hardware or a.combined else ''
    cmdline = (f'debug=0xc serial=3 cpus=1 keepsyms=1 -noprogress rd={root_device} '
               'j7hw=1 j7keys_layout=1 a3touch=0 j7fg=0 j7gpu=0 a5gpu=0 '
               f'{storage_args} a5log=0 sweetfb_scale=1 sweetfb_lw=750 sweetfb_lh=1334'
               f'{hardware_args}')
    with tempfile.TemporaryDirectory() as staging:
        tree_path = Path(staging) / 'board.adt'
        if a.product_adt and not a.product_adt.is_file():
            raise ValueError('Product ADT file is missing')
        tree_path.write_bytes(adt.serialize(board.build(a.product_adt)))
        payload, info = mkpayload.build(str(a.kernel), str(tree_path), cmdline,
                                        str(a.ramdisk) if a.ramdisk else None,
                                        a3_static_cache=a.a3_static_cache)
    crc = zlib.crc32(payload)
    combined = (bytearray(loader.ljust(0x4000, b'\0')) + b'A3XNPAY2' +
                struct.pack('<II', len(payload), crc) + payload)
    struct.pack_into('<Q', combined, 16, (len(combined) + 0x10000 + 4095) & ~4095)
    # S-Boot's conventional low-memory staging must stay below firmware logs.
    if len(combined) >= 32 * 1024 * 1024: raise ValueError('Embedded kernel exceeds 32 MiB staging limit')
    result = repack_boot(original, combined)
    a.output.write_bytes(result)
    # The packer adds RAMDisk to the in-payload tree when a root is present.
    dt_offset, dt_length = struct.unpack_from('<QQ', payload, 0x20)
    a.output.with_suffix('.adt').write_bytes(payload[dt_offset:dt_offset + dt_length])
    stage = 'RAM ROOT TEST' if a.ramdisk else 'ENTRY TEST ONLY'
    root_source = 'RAM disk' if a.ramdisk else 'none; expected stop at root resolution'
    if a.ios_root:
        stage = 'USERDATA IOS ROOT CANDIDATE'
        root_source = 'pre-installed HFSX iOS root in USERDATA'
    if a.combined:
        stage = 'COMBINED READ-ONLY BOOT'
        root_source = 'verified A3IOSROOT catalog in USERDATA or diagnostic HFS on md0'
        if a.writable_userdata:
            stage = 'COMBINED USERDATA READ-WRITE BOOT'
    report = {'target': 'a3y17lte', 'stage': stage, 'phone_boot_tested': False,
              'emmc_probe_requested': a.probe_emmc or a.combined,
              'hardware_probe_requested': a.probe_hardware or a.combined,
              'root': root_source,
              'size': len(result), 'sha256': hashlib.sha256(result).hexdigest(),
              'dtbh_source': 'unaltered device BOOT backup', 'flashed': False,
              'kernel_sha256': hashlib.sha256(kernel).hexdigest(), 'cmdline': cmdline,
              'payload': info, 'userdata_writes_enabled': a.writable_userdata or a.ios_root,
              'loader': {'wrapper_version': 2, 'payload_crc32': f'{crc:08x}',
                         'sha256': hashlib.sha256(loader).hexdigest()}}
    a.output.with_suffix('.json').write_text(json.dumps(report, indent=2))
    print(f'{a.output}: built entry test, {len(result)} bytes. NOT a working iOS ROM. Not flashed.')


if __name__ == '__main__':
    main()
