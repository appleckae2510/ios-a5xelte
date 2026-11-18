import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import adt
import mkadt_a3y17lte as board


def module(name, file):
    s = importlib.util.spec_from_file_location(name, ROOT / 'tools' / file)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


pack = module('a3pack', 'a3y17lte-pack-boot.py')
collector = module('a3collect', 'a3y17lte-collect.py')


def fixture(model=b'Samsung A3Y17 LTE EUR rev03 board\0'):
    # Minimal FDT fixture, only a root model; the packer must preserve its exact bytes.
    strings = b'model\0'
    tokens = struct.pack('>I', 1) + b'\0\0\0\0' + struct.pack('>III', 3, len(model), 0)
    tokens += model + b'\0' * (-len(model) % 4) + struct.pack('>II', 2, 9)
    off = 56
    dtb = struct.pack('>10I', 0xd00dfeed, off+len(tokens)+len(strings), off,
                      off+len(tokens), 40, 17, 16, 0, len(strings), len(tokens))
    dtb += b'\0' * 16 + tokens + strings
    body = dtb.ljust(2048, b'\0')
    dt = struct.pack('<4sII8I', b'DTBH', 2, 1, 7870, 0x50a6, 0x217584da,
                     3, 255, 2048, len(body), 0x20).ljust(2048, b'\0') + body
    kernel, ramdisk = b'original Linux kernel', b'original ramdisk'
    h = bytearray(2048); h[:8] = b'ANDROID!'
    struct.pack_into('<9I', h, 8, len(kernel), 0x10008000, len(ramdisk), 0x11000000,
                     0, 0x10f00000, 0x10000100, 2048, len(dt))
    h[576:596] = pack.boot_digest(kernel, ramdisk, dt, True)
    pad = lambda x: x + b'\0' * (-len(x) % 2048)
    return (bytes(h) + pad(kernel) + pad(ramdisk) + pad(dt) + b'SEANDROIDENFORCE').ljust(2**20, b'\0')


class A3Tools(unittest.TestCase):
    def test_adt_geometry_memory_and_identity(self):
        r = board.build()
        b = adt.serialize(r); q, n = adt.parse(b)
        self.assertEqual(n, len(b))
        chosen = next(c for c in q.children if c.name == 'chosen')
        self.assertEqual(struct.unpack('<Q', chosen.prop('dram-base'))[0], 0x92000000)
        self.assertEqual(struct.unpack('<Q', chosen.prop('dram-size'))[0], 0x1c000000)
        fb = next(c for c in q.children if c.name == 'a5xelte-fbcon')
        self.assertEqual(struct.unpack('<I', fb.prop('stride'))[0], 2880)
        self.assertEqual(struct.unpack('<I', fb.prop('height'))[0], 1280)
        self.assertIn(b'samsung,a3y17lte\0', q.prop('compatible'))
        self.assertNotIn(b'samsung,on7xelte', b)
        self.assertFalse(any(c.name == 'gpu' for c in next(c for c in q.children if c.name == 'arm-io').children))

    def test_repack_preserves_device_dt_and_ramdisk(self):
        original = fixture()
        result = pack.repack_boot(original, b'new A3 kernel image')
        a, k, r, d = pack.unpack_boot(original)
        h, k2, r2, d2 = pack.unpack_boot(result)
        self.assertEqual(r, r2); self.assertEqual(d, d2)
        self.assertEqual(h[12:48], a[12:48])
        self.assertEqual(h[576:596], pack.boot_digest(k2, r2, d2, True))

    def test_rejects_wrong_devices_and_oversized_image(self):
        for model in (b'Samsung ON7XE LTE\0', b'Samsung A3Y17P LTE\0'):
            with self.assertRaises(ValueError): pack.unpack_boot(fixture(model))
        with self.assertRaises(ValueError): pack.repack_boot(fixture(), b'K' * 2**21)

    def test_end_to_end_pack_with_synthetic_kernel(self):
        loader = ROOT / 'shim/a3y17lte/out/a3y17lte-loader.Image'
        if not loader.exists(): loader = ROOT / 'prebuilt/a3y17lte-loader.Image'
        self.assertTrue(loader.exists(), 'Build loader or include the prebuilt for this check')
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            original = fixture()
            props = json.dumps({'ro.product.device': 'a3y17lte'}).encode()
            proof = {'target': 'a3y17lte', 'phone_writes': False,
                     'files': {'boot.img': {'size': len(original), 'sha256': hashlib.sha256(original).hexdigest()}}}
            with zipfile.ZipFile(d / 'evidence.zip', 'w') as z:
                z.writestr('boot.img', original); z.writestr('device.json', props)
                z.writestr('manifest.json', json.dumps(proof))
            k = bytearray(512)
            struct.pack_into('<8I', k, 0, 0xfeedfacf, 0x100000c, 0, 2, 2, 360, 0, 0)
            va = 0xfffffff007004000
            struct.pack_into('<II16s4Q4I', k, 32, 0x19, 72, b'__TEXT', va, 4096, 0, 512, 7, 5, 0, 0)
            struct.pack_into('<4I', k, 104, 5, 288, 6, 68)
            struct.pack_into('<Q', k, 104 + 16 + 32 * 8, va + 0x100)
            k[400:400+len(board.MARKER)] = board.MARKER
            (d / 'kernel').write_bytes(k)
            argv = ['packer','--evidence',str(d/'evidence.zip'),'--kernel',str(d/'kernel'),
                    '--loader',str(loader),'--output',str(d/'entry.img'),'--allow-unverified-handoff']
            with patch.object(sys, 'argv', argv): pack.main()
            _, kernel, _, dt = pack.unpack_boot((d/'entry.img').read_bytes())
            self.assertEqual(kernel[0x4000:0x4008], b'A3XNPAY1')
            self.assertEqual(kernel[0x4010:0x4018], b'SWEETXNU')
            self.assertEqual(dt, pack.unpack_boot(original)[3])
            self.assertFalse(json.loads((d/'entry.json').read_text())['phone_boot_tested'])
            test_root = d / 'ramdisk.bin'
            test_root.write_bytes(b'A3 root placement test')
            # Hold the ADT seed fixed only in this comparison of two test fixtures.
            with patch('mkadt_j7prime.os.urandom', return_value=bytes(range(64))), \
                    patch.object(sys, 'argv', argv + ['--ramdisk', str(test_root)]):
                pack.main()
            payload = pack.unpack_boot((d/'entry.img').read_bytes())[1][0x4010:]
            offset, size = struct.unpack_from('<QQ', payload, 0x20)
            tree = (d/'entry.adt').read_bytes()
            self.assertEqual(tree, payload[offset:offset + size])
            root, _ = adt.parse(tree)
            chosen = next(node for node in root.children if node.name == 'chosen')
            mmap = next(node for node in chosen.children if node.name == 'memory-map')
            rd_address, rd_size = struct.unpack('<QQ', mmap.prop('RAMDisk'))
            count, = struct.unpack_from('<I', payload, 12)
            va, size, off, length = struct.unpack_from('<4Q', payload, 0x2a8 + 32 * (count - 1))
            virt_base, = struct.unpack_from('<Q', payload, 0x10)
            self.assertEqual((rd_address, rd_size), (board.RAM_BASE + va - virt_base, size))
            self.assertEqual(payload[off:off + length], test_root.read_bytes())
            default_args = payload[0x48:0x2a8].split(b'\0', 1)[0].decode().split()
            self.assertEqual(default_args.count('emmcprobe=0'), 1)
            self.assertFalse(any(arg.startswith('emmcroot=') for arg in default_args))
            for arg in ('rd=md0', 'emmcwrite=0', 'a5log=0'):
                self.assertEqual(default_args.count(arg), 1)
            with patch('mkadt_j7prime.os.urandom', return_value=bytes(range(64))), \
                    patch.object(sys, 'argv', argv + ['--ramdisk', str(test_root), '--probe-emmc']):
                pack.main()
            probe = pack.unpack_boot((d/'entry.img').read_bytes())[1][0x4010:]
            expected_args = default_args.copy()
            index = expected_args.index('emmcprobe=0')
            expected_args[index:index+1] = ['emmcprobe=1', 'emmcroot=USERDATA']
            self.assertEqual(probe[0x48:0x2a8].split(b'\0', 1)[0].decode().split(), expected_args)
            self.assertEqual((probe[:0x48], probe[0x2a8:]), (payload[:0x48], payload[0x2a8:]))
            self.assertTrue(json.loads((d/'entry.json').read_text())['emmc_probe_requested'])
            with patch.object(sys, 'argv', argv + ['--probe-hardware']):
                with self.assertRaisesRegex(ValueError, 'patch 0401'):
                    pack.main()
            with patch.object(sys, 'argv', argv + ['--ios-root']):
                with self.assertRaisesRegex(ValueError, 'patch 0402'):
                    pack.main()
            marker = b'A3Y17LTE_USERDATA_RW_V1'
            k[472:472+len(marker)] = marker
            (d/'kernel').write_bytes(k)
            with patch.object(sys, 'argv', argv + ['--ios-root']):
                pack.main()
            ios_payload = pack.unpack_boot((d/'entry.img').read_bytes())[1][0x4010:]
            ios_args = ios_payload[0x48:0x2a8].split(b'\0', 1)[0].decode().split()
            for arg in ('rd=emmcroot0', 'emmcroot=USERDATA', 'emmcwrite=1', 'a5log=0'):
                self.assertEqual(ios_args.count(arg), 1)
            self.assertNotIn('rd=md0', ios_args)
            self.assertEqual(struct.unpack_from('<I', ios_payload, 12)[0], 1)

    def test_collector_only_reads_phone(self):
        props = {'ro.product.device': 'a3y17lte', 'ro.build.product': 'a3y17lte',
                 'ro.product.model': 'SM-A320F', 'ro.twrp.version': '3.7.0'}
        seen = []
        def run(argv, **kwargs):
            args = argv[1:]; seen.append(args)
            data, rc = b'', 0
            if args == ['devices']: data = b'List of devices attached\nFAKE\trecovery\n'
            elif args == ['shell','id','-u']: data = b'0\n'
            elif args[:2] == ['shell','getprop']: data = props.get(args[2], '').encode()
            elif args[:1] == ['shell'] and args[1].startswith('find '): data = b'/dev/block/platform/13540000.dwmmc0/by-name\n'
            elif args[:3] == ['shell','readlink','-f']: data = b'/dev/block/mmcblk0p10\n'
            elif args[:3] == ['shell','blockdev','--getsize64']: data = str(2**20).encode()
            elif args[:2] == ['exec-out','dd']: data = fixture()
            elif args[:2] == ['exec-out','cat']: rc = 1
            elif args == ['exec-out','dmesg']: data = b'A3 test log'
            elif args[0] == 'shell' and args[1].startswith('ls -l '): data = b'BOOT -> /dev/block/mmcblk0p10'
            else: self.fail('Unexpected phone command: ' + repr(args))
            from subprocess import CompletedProcess
            return CompletedProcess(argv, rc, data, b'')
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'diagnose.zip'
            with patch.object(sys, 'argv', ['collector','--adb','fake-adb','--output',str(out)]), \
                 patch.object(collector.subprocess, 'run', run): collector.main()
            with zipfile.ZipFile(out) as z:
                manifest = json.loads(z.read('manifest.json'))
                self.assertFalse(manifest['phone_writes'])
                self.assertEqual(manifest['files']['boot.img']['sha256'], hashlib.sha256(fixture()).hexdigest())
        self.assertTrue(seen)
        self.assertFalse(any(any('of=' in arg or arg in ('push','reboot','flash','su') for arg in cmd) for cmd in seen))


if __name__ == '__main__': unittest.main()
