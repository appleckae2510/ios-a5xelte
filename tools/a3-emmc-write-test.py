"""Test actual A3 ARM64 sector-write code on an isolated synthetic controller."""
import json
import struct
import argparse
import importlib.util
from pathlib import Path
from mkpayload import parse_macho, apply_chained_fixups
spec = importlib.util.spec_from_file_location('boot_regression', Path(__file__).with_name('a3-boot-regression.py'))
regression = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regression)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('kernel', type=Path)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
kernel = regression.Kernel(args.kernel)
syms = kernel.symbols
payload = bytearray(kernel.data)
apply_chained_fixups(payload, parse_macho(payload))
segs = [(v, vs, off, size) for _, v, vs, off, size, _ in kernel.segments]
def va(address): return address
def addr(name): return syms[name]
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import (UC_CPU_ARM64_A53, UC_ARM64_REG_PSTATE,
                                UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_LR,
                                UC_ARM64_REG_PC, UC_ARM64_REG_SP)


def run(case):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.ctl_set_cpu_model(UC_CPU_ARM64_A53)
    uc.reg_write(UC_ARM64_REG_PSTATE, 0x3c5)
    uc.cpr_write(3, 0, 1, 0, 2, 3 << 20)
    for base, size, offset, length in segs:
        uc.mem_map(va(base), (size + 4095) & ~4095)
        uc.mem_write(va(base), bytes(payload[offset:offset + length]))
    stack, stop, buffer, mmio = 0x50000000, 0x51000000, 0x50001000, 0x13540000
    uc.mem_map(stack, 0x20000)
    uc.mem_map(stop, 4096)
    data = bytes(range(256))*2
    uc.mem_write(buffer,data)
    uc.reg_write(UC_ARM64_REG_SP, stack+0x1f000)
    uc.reg_write(UC_ARM64_REG_LR,stop)
    first, sectors, lba = 12288, 32768, 12288
    if case == 'last-sector': lba = first+sectors-1
    if case == 'before': lba = first-1
    if case == 'after': lba = first+sectors
    if case == 'empty': sectors = 0
    def state(name, value, size):
        uc.mem_write(addr(name),value.to_bytes(size,'little'))
    state('_emmc_regs',mmio,8)
    state('_emmc_ready',int(case!='unregistered'),1)
    state('_emmc_writable',int(case!='read-only'),1)
    state('_emmc_first_lba',first,8)
    state('_emmc_nsectors',sectors,8)
    part = b'SYSTEM' if case == 'wrong-partition' else b'USERDATA'
    uc.mem_write(addr('_emmc_partition_name'),part.ljust(16,b'\0'))
    if case == 'log-outside':
        lba = 2048
        state('_emmc_log_enabled',1,1)
        state('_emmc_log_first_lba',2048,8)
    reads, writes, commands, fifo = [], [], [], bytearray()
    regs = {4:1,0x10:1,0x6c:0x240a,0x70:2<<7,0xa8:1<<16}
    def read(uc, off, width, _):
        reads.append(off)
        assert width==4
        return regs.get(off,0)
    def write(uc, off, width, value, _):
        writes.append(off)
        assert width==4
        if off==0x2c:
            assert value & 63==24 and value & (1<<10)
            assert regs[0x1c]==regs[0x20]==512
            commands.append(regs[0x28])
            regs[0x44]=(1<<4)|(1<<3)|(1<<2)
        elif off in (0x200,0x204):
            assert off==0x200+len(fifo)%8 and commands==[lba]
            fifo.extend(value.to_bytes(4,'little'))
        elif off==0x44: regs[off]=regs.get(off,0)&~value
        elif off==0: regs[off]=value&~2
        else:
            assert off in (0x14,0x1c,0x20,0x24,0x28)
            regs[off]=value
    uc.mmio_map(mmio,0x2000,read,None,write,None)
    # HFS's read-only-to-read-write update first opens the device FWRITE.
    uc.reg_write(UC_ARM64_REG_X0,0)
    uc.reg_write(UC_ARM64_REG_X1,2)
    uc.emu_start(addr('_emmc_open'),stop,count=10000)
    assert uc.reg_read(UC_ARM64_REG_PC)==stop
    opened=uc.reg_read(UC_ARM64_REG_X0)&0xffffffff
    expected_open=6 if case=='unregistered' else 30 if case=='read-only' else 0
    assert opened==expected_open,(case,opened)
    uc.reg_write(UC_ARM64_REG_SP,stack+0x1f000)
    uc.reg_write(UC_ARM64_REG_LR,stop)
    uc.reg_write(UC_ARM64_REG_X0,lba)
    uc.reg_write(UC_ARM64_REG_X1,buffer)
    uc.emu_start(addr('_emmc_write_sector'),stop,timeout=3000000,count=3000000)
    assert uc.reg_read(UC_ARM64_REG_PC)==stop
    result=uc.reg_read(UC_ARM64_REG_X0)&0xffffffff
    if case in ('first-sector','last-sector'):
        assert result==0 and commands==[lba] and fifo==data
    else:
        assert result==30 and not reads and not writes and not commands
    print(case,'PASS','return',result,'CMD24',len(commands),flush=True)
    return {'case':case,'errno':result,'CMD24_count':len(commands),
            'denied_before_MMIO':not reads and not writes,'synthetic_sector':lba,
            'write_open_errno':opened}


if __name__=='__main__':
    cases=['first-sector','last-sector','before','after','empty','unregistered','read-only','wrong-partition','log-outside']
    results=[run(case) for case in cases]
    args.report.write_text(json.dumps(results,indent=2)+'\n')
