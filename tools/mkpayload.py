#!/usr/bin/env python3
"""Pack an xnu kernel Mach-O + ADT into the payload the sweet shim boots.

  mkpayload.py KERNEL ADT OUT [--cmdline "..."] [--ramdisk IMAGE]

The kernel is linked as a PIE with LC_DYLD_CHAINED_FIXUPS. Nobody else
(no kmutil, no iBoot) resolves those for us, and xnu only rebases static
kernelcaches itself, so the chains are walked here and every pointer is
rewritten to its unslid target. The shim then only copies flat segments.

Payload layout (little endian, all offsets from payload start):
  0x000  char  magic[8] = "SWEETXNU"
  0x008  u32   version = 1, nsegs
  0x010  u64   virt_base      kernel VA that maps to phys_base
  0x018  u64   entry_va       LC_UNIXTHREAD pc
  0x020  u64   adt_off, adt_size
  0x030  u64   kernel_end_va  end of the highest segment (page aligned)
  0x038  u64   phys_base      kernel-managed RAM (same values as the ADT's dram-base/size)
  0x040  u64   mem_size
  0x048  char  cmdline[608]
  0x2a8  seg[nsegs] { u64 vmaddr, vmsize, file_off(in payload), file_size }

--ramdisk appends IMAGE as one more segment right after the kernel and moves
kernel_end past it, so the shim needs no changes: the image lands below the
ADT and boot_args, inside topOfKernelData (never handed to the VM), and the
ADT gets /chosen/memory-map "RAMDisk" = <phys, size> for IOFindBSDRoot to
turn into md0 (boot with rd=md0).
"""
import argparse, hashlib, os, struct, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

LC_SEGMENT_64, LC_UNIXTHREAD, LC_DYLD_CHAINED_FIXUPS = 0x19, 0x5, 0x80000034
PAGE = 0x4000
BOOT_LINE_LENGTH = 608
CMDLINE = 0x48
SEG_TABLE = CMDLINE + BOOT_LINE_LENGTH	# 0x2a8


def parse_macho(buf):
    magic, cputype, cpusub, ftype, ncmds, sizeofcmds, flags, _ = struct.unpack_from('<8I', buf, 0)
    assert magic == 0xfeedfacf, 'not a 64-bit Mach-O'
    segs, entry, fixups = [], None, None
    off = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', buf, off)
        if cmd == LC_SEGMENT_64:
            name = buf[off + 8:off + 24].split(b'\0')[0].decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<4Q', buf, off + 24)
            segs.append(dict(name=name, vmaddr=vmaddr, vmsize=vmsize, fileoff=fileoff, filesize=filesize))
        elif cmd == LC_UNIXTHREAD:
            flavor, count = struct.unpack_from('<II', buf, off + 8)
            # arm_thread_state64: x0..x28, fp, lr, sp, pc, cpsr
            entry, = struct.unpack_from('<Q', buf, off + 16 + 32 * 8)
        elif cmd == LC_DYLD_CHAINED_FIXUPS:
            fixups = struct.unpack_from('<II', buf, off + 8)	# dataoff, datasize
        off += size
    return dict(cputype=cputype, cpusub=cpusub & 0xff, segs=segs, entry=entry, fixups=fixups)


def apply_chained_fixups(buf, m):
    """Rewrite every chained rebase in buf (the whole file) to its plain target VA."""
    if not m['fixups']:
        return 0
    data_off, _ = m['fixups']
    _, starts_off, _, _, imports_count, _, _ = struct.unpack_from('<7I', buf, data_off)
    assert imports_count == 0, 'kernel has binds; only rebases are supported'
    image_base = m['segs'][0]['vmaddr']		# __TEXT, holds the mach header
    seg_count, = struct.unpack_from('<I', buf, data_off + starts_off)
    nfix = 0
    for i in range(seg_count):
        seg_info, = struct.unpack_from('<I', buf, data_off + starts_off + 4 + 4 * i)
        if not seg_info:
            continue
        base = data_off + starts_off + seg_info
        size, page_size, fmt, seg_offset, max_valid, page_count = struct.unpack_from('<IHHQIH', buf, base)
        starts = struct.unpack_from('<%dH' % page_count, buf, base + 22)
        seg = m['segs'][i]
        for p, start in enumerate(starts):
            if start == 0xffff:
                continue
            assert not start & 0x8000, 'DYLD_CHAINED_PTR_START_MULTI not supported'
            loc = seg['fileoff'] + p * page_size + start
            while True:
                raw, = struct.unpack_from('<Q', buf, loc)
                target, nxt, stride = decode(raw, fmt, image_base)
                struct.pack_into('<Q', buf, loc, target)
                nfix += 1
                if not nxt:
                    break
                loc += nxt * stride
    return nfix


def decode(raw, fmt, image_base):
    """Return (unslid target VA, next, stride) for one chained pointer."""
    if fmt in (2, 6):		# DYLD_CHAINED_PTR_64 / _64_OFFSET
        assert not raw >> 63, 'bind in kernel'
        target = raw & ((1 << 36) - 1)
        high8 = (raw >> 36) & 0xff
        nxt = (raw >> 51) & 0xfff
        if fmt == 6:
            target += image_base
        return target | (high8 << 56), nxt, 4
    if fmt == 8:		# DYLD_CHAINED_PTR_64_KERNEL_CACHE
        target = raw & ((1 << 30) - 1)
        nxt = (raw >> 51) & 0xfff
        return image_base + target, nxt, 4
    if fmt in (1, 7, 9, 12):	# arm64e variants (stock VMAPPLE kernel only; PAC is not re-signed)
        auth = raw >> 63
        nxt = (raw >> 51) & 0x7ff
        stride = 4 if fmt in (7, 12) else 8
        if auth:
            target = raw & 0xffffffff
        else:
            target = raw & ((1 << 43) - 1)
            target |= ((raw >> 43) & 0xff) << 56
        if fmt in (7, 9, 12) or auth:
            target += image_base
        return target, nxt, stride
    raise ValueError(f'unsupported chained pointer format {fmt}')


def add_memory_range(adt_blob, name, phys, size):
    root, _ = adt.parse(adt_blob)
    if name == 'TrustCache' and b'samsung,a3y17lte' not in (root.prop('compatible') or b'').split(b'\0'):
        raise ValueError('20H392 A3 cache requested on a different board')
    chosen = next(c for c in root.children if c.name == 'chosen')
    mmap = next(c for c in chosen.children if c.name == 'memory-map')
    if mmap.prop(name) is not None:
        raise ValueError(f'ADT already has a {name} range')
    mmap.props.append((name, 0, struct.pack('<2Q', phys, size)))
    return adt.serialize(root)


def add_ramdisk_to_adt(adt_blob, phys, size):
    return add_memory_range(adt_blob, 'RAMDisk', phys, size)


def a3_release_cache(component):
    """Build XNU's single-module offset table from the pinned d21ap static cache."""
    # SHA-384 from the d21ap erase identity in Apple's 20H392 BuildManifest.
    digest = ('9318c3d22caf985f70ca35e9df4bf0b1c023bb108ba165179fc66adc644fde00'
              '18bdf4fa3c20fb85999ac72d60d483a6')
    if hashlib.sha384(component).hexdigest() != digest:
        raise ValueError('static trust cache differs from iOS 16.7.16 (20H392)')
    module, info = adt.im4p_payload(component)
    if info['type'] != 'trst' or info['encrypted']:
        raise ValueError('unexpected 20H392 static-cache envelope')
    # Preserve every entry and constraint in Apple's module.
    return struct.pack('<II', 1, 8) + module


A3_CRYPTEX_TABLE_SHA384 = '125420ed05e44818aefa99819dfc8558071563cae9698c40ec5b663f2e2150f8a45b7e3e6c6d54a63cc6a0f1e41d83d1'


def a3_cryptex_release_cache(app_component, system_component):
    """Keep the original App/System Cryptex modules, authenticated to 20H392."""
    modules = []
    for component, digest, count in (
        (app_component, 'a58d8b89f43b8f0eeb097dc554df95def3ea62692b3bd9b0aeda2b710a1203815f829f56ef14e1c993245c130247f0ca', 30),
        (system_component, '204e476a45650adde5bedb65ff93af211cb5f2c0e20ec8ae274025df5017a988d598512846b9115cd5c77ac5ebcc08e1', 61),
    ):
        if hashlib.sha384(component).hexdigest() != digest:
            raise ValueError('Cryptex trust cache differs from original d21ap 20H392')
        module, info = adt.im4p_payload(component)
        if info['type'] != 'trst' or info['encrypted'] or len(module) != 24 + count*24 or struct.unpack_from('<I16xI',module) != (2,count):
            raise ValueError('unexpected 20H392 Cryptex module')
        modules.append(module)
    table = struct.pack('<3I', 2, 12, 12+len(modules[0])) + b''.join(modules)
    if hashlib.sha384(table).hexdigest() != A3_CRYPTEX_TABLE_SHA384:
        raise ValueError('Cryptex module layout differs')
    return table


def add_a3_cryptex_cache(adt_blob, app_component, system_component):
    root, end = adt.parse(adt_blob)
    if end != len(adt_blob) or b'samsung,a3y17lte' not in (root.prop('compatible') or b'').split(b'\0'):
        raise ValueError('Cryptex handoff requires an A3 tree')
    if root.prop('a3-cryptex-trustcache') is not None:
        raise ValueError('duplicate Cryptex property')
    root.props.append(('a3-cryptex-trustcache', 0, a3_cryptex_release_cache(app_component, system_component)))
    return adt.serialize(root)


def adt_dram(adt_blob):
    """Kernel-managed RAM <base, size> from the ADT's /chosen dram-base/dram-size."""
    root, _ = adt.parse(adt_blob)
    chosen = next(c for c in root.children if c.name == 'chosen')
    return (struct.unpack('<Q', chosen.prop('dram-base'))[0],
            struct.unpack('<Q', chosen.prop('dram-size'))[0])


def build(kernel_path, adt_path, cmdline, ramdisk_path=None, *, a3_static_cache=None, a3_app_cache=None, a3_system_cache=None):
    buf = bytearray(open(kernel_path, 'rb').read())
    m = parse_macho(buf)
    nfix = apply_chained_fixups(buf, m)
    segs = [s for s in m['segs'] if s['vmsize']]
    text = m['segs'][0]
    assert text['name'] == '__TEXT' and text['fileoff'] == 0
    # virt_base: 32MB (16K-granule L2 block) below the mach header, so start.s's
    # block mapping that starts at the header's block begins exactly at phys_base.
    virt_base = text['vmaddr'] & ~(0x2000000 - 1)
    kernel_end = max(s['vmaddr'] + s['vmsize'] for s in segs)
    kernel_end = (kernel_end + PAGE - 1) & ~(PAGE - 1)

    adt_blob = open(adt_path, 'rb').read()
    # The ADT decides where the kernel's RAM is (mkadt.py --highmem).
    if (a3_app_cache is None) != (a3_system_cache is None):
        raise ValueError('both original Cryptex components are required')
    if a3_app_cache is not None:
        if a3_static_cache is None:
            raise ValueError('Cryptex caches require the original static cache')
        adt_blob = add_a3_cryptex_cache(adt_blob, Path(a3_app_cache).read_bytes(), Path(a3_system_cache).read_bytes())
    PHYS_BASE, MEM_SIZE = adt_dram(adt_blob)
    pieces = [(s['vmaddr'], s['vmsize'], buf[s['fileoff']:s['fileoff'] + s['filesize']]) for s in segs]
    ramdisk = None
    if ramdisk_path:
        image = open(ramdisk_path, 'rb').read()
        rd_size = (len(image) + PAGE - 1) & ~(PAGE - 1)
        rd_va = kernel_end
        kernel_end = rd_va + rd_size
        rd_pa = rd_va - virt_base + PHYS_BASE
        pieces.append((rd_va, rd_size, image))
        adt_blob = add_ramdisk_to_adt(adt_blob, rd_pa, rd_size)
        ramdisk = (hex(rd_pa), hex(rd_size))

    if a3_static_cache is not None:
        table = a3_release_cache(Path(a3_static_cache).read_bytes())
        table_pa = PHYS_BASE + (kernel_end - virt_base)
        extent = (len(table) + PAGE - 1) & ~(PAGE - 1)
        adt_blob = add_memory_range(adt_blob, 'TrustCache', table_pa, len(table))
        pieces.append((kernel_end, extent, table))
        kernel_end += extent
        # The Samsung A3 shim reserves boot_args on its own 4 KiB boundary.
        shim_page = 4096
        adt_extent = (len(adt_blob) + shim_page - 1) & ~(shim_page - 1)
        if kernel_end - virt_base + adt_extent + shim_page > MEM_SIZE or len(pieces) > 32:
            raise ValueError('A3 loader has insufficient space for the static cache and boot arguments')

    hdr_size = SEG_TABLE + 32 * len(pieces)
    out = bytearray(hdr_size)
    seg_table = []
    for vmaddr, vmsize, data in pieces:
        off = len(out)
        out += data
        out += b'\0' * (-len(out) & 0xf)
        seg_table.append((vmaddr, vmsize, off, len(data)))
    adt_off = len(out)
    out += adt_blob
    out += b'\0' * (-len(out) & 0xf)

    struct.pack_into('<8sII', out, 0, b'SWEETXNU', 1, len(pieces))
    struct.pack_into('<7Q', out, 0x10, virt_base, m['entry'], adt_off, len(adt_blob), kernel_end,
                     PHYS_BASE, MEM_SIZE)
    cl = cmdline.encode()[:BOOT_LINE_LENGTH - 1]
    out[CMDLINE:CMDLINE + len(cl)] = cl
    for i, t in enumerate(seg_table):
        struct.pack_into('<4Q', out, SEG_TABLE + 32 * i, *t)
    info = dict(cputype=hex(m['cputype']), cpusub=m['cpusub'], fixups=nfix, virt_base=hex(virt_base),
                entry=hex(m['entry']), kernel_end=hex(kernel_end), ramdisk=ramdisk, size=len(out),
                segs=[(s['name'], hex(s['vmaddr']), hex(s['vmsize'])) for s in segs])
    if a3_static_cache is not None:
        info['static_cache'] = dict(build='20H392', physical_address=hex(table_pa), byte_length=len(table))
    if a3_app_cache is not None:
        info['cryptex_cache'] = dict(build='20H392', app_entries=30, system_entries=61,
                                    handoff='a3-cryptex-trustcache ADT property', byte_length=2244)
    return bytes(out), info


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('kernel'); ap.add_argument('adt'); ap.add_argument('out')
    ap.add_argument('--cmdline', default='debug=0xc serial=3 cpus=1 keepsyms=1')
    ap.add_argument('--ramdisk', help='root image for md0 (boot with rd=md0)')
    a = ap.parse_args()
    blob, info = build(a.kernel, a.adt, a.cmdline, a.ramdisk)
    open(a.out, 'wb').write(blob)
    for k, v in info.items():
        if k != 'segs':
            print(f'{k}: {v}')
    for s in info['segs']:
        print('  ', *s)
