#!/usr/bin/env python3
"""Replay compiled A3 loader validation on an ARM64 CPU with modeled RAM."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import zlib

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm64_const import (
    UC_CPU_ARM64_A53, UC_ARM64_REG_PC, UC_ARM64_REG_SP,
    UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_LR,
)


BASE = 0x40080000
SOURCE = 0x41000000
STACK = 0x45000000
STOP = 0x46000000
DEST = 0x92000000
LOG = 0x679fe000
VIRT = 0xfffffff006000000
TABLE = 0x2a8


def symbols(path):
    result = subprocess.run(['nm', '-n', str(path)], check=True,
                            text=True, capture_output=True)
    return {line.split()[2]: BASE + int(line.split()[0], 16)
            for line in result.stdout.splitlines() if len(line.split()) == 3}


def payload():
    data = bytearray(TABLE + 64)
    first = len(data)
    data.extend(bytes([0x42]) * 4096)
    second = len(data)
    data.extend(bytes([0x24]) * 64)
    tree = len(data)
    data.extend(bytes([0x73]) * 16)
    struct.pack_into('<8sII7Q', data, 0, b'SWEETXNU', 1, 2, VIRT,
                     VIRT + 0x4000, tree, 16, VIRT + 0x8000, DEST, 0x10000)
    data[0x48:0x48 + 6] = b'rd=md0'
    struct.pack_into('<4Q', data, TABLE, VIRT + 0x4000, 4096, first, 4096)
    struct.pack_into('<4Q', data, TABLE + 32, VIRT + 0x6000, 4096, second, 64)
    return data


def wrap(data, legacy=False, bad_crc=False):
    if legacy:
        return b'A3XNPAY1' + struct.pack('<Q', len(data)) + data
    crc = zlib.crc32(data) ^ int(bad_crc)
    return b'A3XNPAY2' + struct.pack('<II', len(data), crc) + data


class Loader:
    def __init__(self, binary, elf):
        self.binary = binary.read_bytes()
        self.symbols = symbols(elf)

    def prepare(self, data, legacy=False, bad_crc=False):
        cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        cpu.ctl_set_cpu_model(UC_CPU_ARM64_A53)
        for address, size in ((BASE, 0x4000), (SOURCE, 0x20000),
                              (STACK, 4096), (STOP, 4096),
                              (LOG, 4096), (DEST, 0x10000)):
            cpu.mem_map(address, size)
        cpu.mem_write(BASE, self.binary)
        cpu.mem_write(SOURCE, wrap(data, legacy, bad_crc))
        original = bytes([0xa5]) * 0x10000
        cpu.mem_write(DEST, original)
        cpu.reg_write(UC_ARM64_REG_SP, STACK + 4080)
        cpu.reg_write(UC_ARM64_REG_X0, LOG)
        cpu.reg_write(UC_ARM64_REG_X1, SOURCE)
        cpu.reg_write(UC_ARM64_REG_LR, STOP)
        writes = []
        cpu.hook_add(UC_HOOK_MEM_WRITE, lambda _c, _a, address, size, value, _u:
                     writes.append((address, size)), begin=DEST, end=DEST + 0xffff)

        # Drawing depends on DECON. Its hardware cases are replayed separately.
        def display(c, _address, _size, _user):
            c.reg_write(UC_ARM64_REG_PC, c.reg_read(UC_ARM64_REG_LR))

        cpu.hook_add(UC_HOOK_CODE, display,
                     begin=self.symbols['a3_display'], end=self.symbols['a3_display'])
        cpu.emu_start(self.symbols['a3_prepare_xnu'], STOP, count=2000000)
        assert cpu.reg_read(UC_ARM64_REG_PC) == STOP, 'loader failed to return'
        entry = cpu.reg_read(UC_ARM64_REG_X0)
        stage = struct.unpack('<q', cpu.mem_read(LOG + 80, 8))[0]
        memory = bytes(cpu.mem_read(DEST, 0x10000))
        return entry, stage, writes, memory, original

    def board(self, tree):
        cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        cpu.ctl_set_cpu_model(UC_CPU_ARM64_A53)
        cpu.mem_map(BASE, 0x4000)
        cpu.mem_write(BASE, self.binary)
        cpu.mem_map(SOURCE, (len(tree) + 4095) & ~4095)
        cpu.mem_write(SOURCE, bytes(tree))
        cpu.mem_map(STACK, 4096)
        cpu.mem_map(STOP, 4096)
        cpu.reg_write(UC_ARM64_REG_SP, STACK + 4080)
        cpu.reg_write(UC_ARM64_REG_X0, SOURCE)
        cpu.reg_write(UC_ARM64_REG_LR, STOP)
        cpu.emu_start(self.symbols['a3_board_ok'], STOP, count=2000000)
        assert cpu.reg_read(UC_ARM64_REG_PC) == STOP
        return cpu.reg_read(UC_ARM64_REG_X0)


def invalid_payloads():
    # Every case is given a new correct CRC so the structural test must run.
    mutations = [
        ('late-file-too-large', TABLE + 32 + 24, 8192, -4),
        ('virtual-overlap', TABLE + 32, VIRT + 0x4000, -4),
        ('file-overlap', TABLE + 32 + 16, TABLE + 64, -4),
        ('file-covers-header', TABLE + 16, 0x100, -4),
        ('segment-beyond-kernel', TABLE + 32, VIRT + 0x8000, -4),
        ('segment-wraps', TABLE + 32, 0xfffffffffffff000, -4),
        ('segment-zero-length', TABLE + 32 + 8, 0, -4),
        ('segment-unaligned', TABLE + 32, VIRT + 0x6001, -4),
        ('entry-in-gap', 24, VIRT + 0x5000, -5),
        ('entry-in-zero-fill', 24, VIRT + 0x6080, -5),
        ('entry-unaligned', 24, VIRT + 0x4001, -3),
        ('entry-beyond-kernel', 24, VIRT + 0x9000, -5),
        ('kernel-wraps', 48, 0xfffffffffffff000, -3),
        ('kernel-unaligned', 48, VIRT + 0x8001, -3),
        ('memory-too-small', 64, 0x8000, -3),
        ('memory-wraps', 64, 0xffffffffffffffff, -3),
        ('adt-covers-header', 32, 0x200, -4),
        ('adt-unaligned', 32, 0x301, -2),
        ('adt-outside-payload', 32, 0xfffffffffffffff8, -2),
        ('adt-zero-length', 40, 0, -2),
        ('adt-overflows', 40, 0xffffffffffffffff, -2),
    ]
    for name, offset, value, stage in mutations:
        data = payload()
        struct.pack_into('<Q', data, offset, value)
        yield name, data, stage
    for name, offset, value in [('no-segments', 12, 0), ('too-many-segments', 12, 33),
                                ('unknown-version', 8, 2)]:
        data = payload()
        struct.pack_into('<I', data, offset, value)
        yield name, data, -2
    data = payload()
    data[0x2a7] = 1
    yield 'unterminated-command-line', data, -2
    yield 'truncated-header', payload()[:100], -2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', type=Path, required=True, help='loader Image binary')
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--dtb', type=Path, action='append', default=[])
    p.add_argument('--baseline-image', type=Path)
    p.add_argument('--baseline-elf', type=Path)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    loader = Loader(args.image, args.elf)
    results = []
    for legacy in (False, True):
        entry, stage, writes, memory, _ = loader.prepare(payload(), legacy=legacy)
        assert entry == DEST + 0x4000 and stage == 5 and writes
        assert memory[0x4000:0x5000] == bytes([0x42]) * 4096
        assert memory[0x6000:0x7000] == bytes([0x24]) * 64 + bytes(4096 - 64)
        assert struct.unpack_from('<6Q', memory, 0x9000 + 40) == (0x67000000, 1, 2880, 720, 1280, 32)
        results.append({'case': 'valid-v1' if legacy else 'valid-v2', 'passed': True})
    entry, stage, writes, memory, original = loader.prepare(payload(), bad_crc=True)
    assert entry == 0 and stage == -6 and not writes and memory == original
    results.append({'case': 'damaged-payload-crc', 'passed': True, 'stage': stage})
    for name, data, expected in invalid_payloads():
        entry, stage, writes, memory, original = loader.prepare(data)
        assert entry == 0 and stage == expected, (name, entry, stage, expected)
        assert not writes and memory == original, name + ': kernel RAM changed'
        results.append({'case': name, 'passed': True, 'stage': stage})
    for path in args.dtb:
        data = bytearray(path.read_bytes())
        assert loader.board(data) == 1, path.name
        results.append({'case': 'board-' + path.name, 'passed': True})
        for name in ('misaligned-structure', 'bad-string-range', 'premature-end', 'wrong-board'):
            broken = bytearray(data)
            if name == 'misaligned-structure':
                struct.pack_into('>I', broken, 8, 57)
            elif name == 'bad-string-range':
                struct.pack_into('>I', broken, 32, 0xffffffff)
            elif name == 'premature-end':
                struct.pack_into('>I', broken, struct.unpack_from('>I', data, 8)[0], 9)
            else:
                broken = broken.replace(b'A3Y17 ', b'J7Y17 ')
            assert loader.board(broken) == 0, name
            results.append({'case': path.name + '-' + name, 'passed': True})
    if bool(args.baseline_image) != bool(args.baseline_elf):
        raise ValueError('supply both baseline files')
    if args.baseline_image:
        baseline = Loader(args.baseline_image, args.baseline_elf)
        name, data, _ = next(invalid_payloads())
        entry, _stage, writes, _memory, _original = baseline.prepare(data, legacy=True)
        assert entry == 0 and writes, 'old-loader negative control did not reproduce'
        results.append({'case': 'old-loader-partial-write-reproduced', 'passed': True})
    args.report.write_text(json.dumps({'cpu': 'Cortex-A53', 'model': True,
                                     'cases': results}, indent=2) + '\n')
    for result in results:
        print('PASS', result['case'])
    print(f'{len(results)} compiled-loader regression cases passed')


if __name__ == '__main__':
    main()
