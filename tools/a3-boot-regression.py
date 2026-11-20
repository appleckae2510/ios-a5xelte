"""Check the native A3 startup path and the immutable policy table in the linked kernel."""

import argparse
import struct
from pathlib import Path


class Kernel:
    def __init__(self, path):
        self.data = path.read_bytes()
        magic, arch, _, kind, count, size = struct.unpack_from("<6I", self.data)
        if (magic, arch, kind) != (0xfeedfacf, 0x0100000c, 2):
            raise ValueError("expected the linked ARM64 kernel")
        self.segments = []
        self.symbols = {}
        offset = 32
        for _ in range(count):
            command, length = struct.unpack_from("<II", self.data, offset)
            if length < 8 or offset + length > size + 32:
                raise ValueError("invalid Mach-O load command")
            if command == 0x19:
                name, address, extent, fileoff, filesz, _, prot = struct.unpack_from(
                    "<16s4Q2I", self.data, offset + 8)
                if extent:
                    self.segments.append((name.rstrip(b"\0").decode(), address, extent,
                                          fileoff, filesz, prot))
            elif command == 2:
                symoff, nsym, stroff, strsize = struct.unpack_from("<4I", self.data, offset + 8)
                table = self.data[stroff:stroff + strsize]
                for i in range(nsym):
                    idx, typ, sect, _, addr = struct.unpack_from("<IBBHQ", self.data, symoff + i * 16)
                    if sect and typ & 0x0e == 0x0e:
                        end = table.index(b"\0", idx)
                        self.symbols[table[idx:end].decode(errors="replace")] = addr
            offset += length
        if offset != size + 32 or not self.symbols:
            raise ValueError("incomplete Mach-O commands or symbols")

    def segment(self, address):
        for segment in self.segments:
            _, begin, length, *_ = segment
            if begin <= address < begin + length:
                return segment
        raise ValueError(f"no segment at {address:#x}")

    def calls(self, function):
        start = self.symbols[function]
        _, base, _, fileoff, filesz, _ = self.segment(start)
        end = min(addr for addr in self.symbols.values() if addr > start)
        if end > base + filesz:
            raise ValueError(f"bad function extent for {function}")
        result = []
        for pc in range(start, end, 4):
            word, = struct.unpack_from("<I", self.data, fileoff + pc - base)
            if word >> 26 in (0x25, 0x05):  # BL, or B for a tail call
                delta = word & 0x3ffffff
                if delta & 0x2000000:
                    delta -= 0x4000000
                result.append(pc + delta * 4)
        return result


def startup_path(kernel):
    steps = {
        "_kernel_bootstrap_thread": ("_mac_policy_initmach", "_machine_lockdown", "_bsd_init"),
        "_bsd_init": ("_mac_policy_initbsd", "_sweet_hfs_register", "_IOFindBSDRoot", "_vfs_mountroot"),
        "_IOFindBSDRoot": ("_a5xelte_touch_probe", "_a3_ios_boot_candidate"),
        "_bsdinit_task": ("_load_init_program",),
        "_load_init_program": ("_load_init_program_at_path",),
    }
    for function, targets in steps.items():
        branches = kernel.calls(function)
        cursor = 0
        for target in targets:
            try:
                cursor = branches.index(kernel.symbols[target], cursor) + 1
            except ValueError as exc:
                raise ValueError(f"{function} no longer reaches {target} in expected order") from exc
    for name in ("_mac_policy_list", "_mac_policy_static_entries", "_startup_phase"):
        segment, *_, prot = kernel.segment(kernel.symbols[name])
        if segment != "__DATA_CONST" or prot != 1:
            raise ValueError(f"{name} is not in a read-only Mach-O segment")
    late = kernel.calls("_bsd_init")
    for name in ("_sweet_amfi_policy_register", "_mac_policy_register", "_mac_policy_unregister"):
        if kernel.symbols.get(name) in late:
            raise ValueError(f"BSD startup can still modify the sealed table via {name}")
    print("PASS: Mach startup, lockdown, BSD, HFS, root selection and PID 1 call paths")


def policy_lifecycle(kernel):
    """Run the real MAC entry points on one modeled core, with the Mach-O protections."""
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm64_const import (UC_CPU_ARM64_A53, UC_ARM64_REG_LR,
                                     UC_ARM64_REG_PC, UC_ARM64_REG_PSTATE, UC_ARM64_REG_SP,
                                     UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2)

    from mkpayload import apply_chained_fixups, parse_macho

    cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    cpu.ctl_set_cpu_model(UC_CPU_ARM64_A53)
    cpu.reg_write(UC_ARM64_REG_PSTATE, 0x3c5)
    cpu.cpr_write(3, 0, 1, 0, 2, 3 << 20)
    image = bytearray(kernel.data)
    apply_chained_fixups(image, parse_macho(image))

    def at(name):
        return kernel.symbols[name]

    for name, addr, length, off, size, prot in kernel.segments:
        start = addr
        cpu.mem_map(start, length, prot | (2 if name == "__DATA_CONST" else 0))
        cpu.mem_write(start, bytes(image[off:off + size]))

    temp = 0x50000000
    stop = temp + 0x18000
    cpu.mem_map(temp, 0x20000)
    def external_return(uc, address, size, context):
        uc.reg_write(UC_ARM64_REG_X0, 0)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))

    # This model is single-threaded. Keep the actual policy functions and their data;
    # only console output, mutex entry/exit and the empty wakeup queue are modeled.
    for name in ("_printf", "_lck_mtx_lock", "_lck_mtx_unlock", "_thread_wakeup_prim"):
        address = at(name)
        cpu.hook_add(UC_HOOK_CODE, external_return, begin=address, end=address)

    def call(name, *arguments):
        for register, value in zip((UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2), arguments):
            cpu.reg_write(register, value)
        cpu.reg_write(UC_ARM64_REG_SP, temp + 0x10000)
        cpu.reg_write(UC_ARM64_REG_LR, stop)
        cpu.emu_start(at(name), stop, count=200000)
        if cpu.reg_read(UC_ARM64_REG_PC) != stop:
            raise ValueError(f"{name} failed to return")
        return cpu.reg_read(UC_ARM64_REG_X0) & 0xffffffff

    table, entries = at("_mac_policy_list"), at("_mac_policy_static_entries")
    call("_mac_policy_init")
    expected = (0, 8, 0, 0, 1, 0, entries)
    if struct.unpack("<6IQ", cpu.mem_read(table, 32)) != expected:
        raise ValueError("native early MAC table initialization failed")

    # One ordinary, inert test policy with no access-control callbacks. Exercise
    # native early registration and later BSD traversal of an occupied table.
    conf, ops, handle = temp, temp + 4096, temp + 0x4000
    cpu.mem_write(temp + 512, b"a3-test\0A3 lifecycle test\0")
    cpu.mem_write(conf, struct.pack("<QQ16xQ", temp + 512, temp + 520, ops))
    cpu.mem_write(handle, b"\xff" * 4)
    if call("_mac_policy_register", conf, handle, 0) != 0:
        raise ValueError("early MAC registration failed")
    if cpu.mem_read(handle, 4) != bytes(4) or struct.unpack("<Q", cpu.mem_read(entries, 8))[0] != conf:
        raise ValueError("early policy registration did not install its handle")

    call("_mac_policy_initmach")
    if struct.unpack("<I", cpu.mem_read(at("_mac_late"), 4))[0] != 1:
        raise ValueError("Mach policy initialization did not finish")
    # Native services can still register between initmach and lockdown.
    second = temp + 0x3000
    cpu.mem_write(temp + 640, b"a3-next\0second early policy\0")
    cpu.mem_write(second, struct.pack("<QQ16xQ", temp + 640, temp + 648, ops))
    if call("_mac_policy_register", second, handle + 4, 0) != 0:
        raise ValueError("pre-lockdown MAC registration failed after initmach")
    if struct.unpack("<I", cpu.mem_read(handle + 4, 4))[0] != 1 or struct.unpack("<I", cpu.mem_read(table, 4))[0] != 2:
        raise ValueError("second early policy did not receive a distinct active slot")
    # Model XNU's normal transition into STARTUP_SUB_LOCKDOWN and its final mappings.
    cpu.mem_write(at("_startup_phase"), struct.pack("<I", 0xffffffff))
    for _, addr, length, _, _, prot in kernel.segments:
        cpu.mem_protect(addr, length, prot)

    before = (cpu.mem_read(table, 32), cpu.mem_read(entries, 8 * 8))
    call("_mac_policy_initbsd")
    cpu.mem_write(handle, b"\xf1" * 4)
    if call("_mac_policy_register", conf, handle, 0) != 1:
        raise ValueError("late MAC registration should fail with EPERM")
    if call("_mac_policy_unregister", 0) != 16:
        raise ValueError("late MAC unregistration should fail with EBUSY")
    if before != (cpu.mem_read(table, 32), cpu.mem_read(entries, 64)) or cpu.mem_read(handle, 4) != b"\xf1" * 4:
        raise ValueError("sealed policy registry or rejected handle changed")
    print("PASS: Cortex-A53 early registration, Mach, lockdown, BSD and rejected late mutation")
    from a3_boot_filesystems import check_filesystems
    check_filesystems(kernel, cpu)
    if before != (cpu.mem_read(table, 32), cpu.mem_read(entries, 64)):
        raise ValueError("filesystem or PID 1 setup modified the sealed registry")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    kernel = Kernel(args.kernel)
    startup_path(kernel)
    if not args.static_only:
        policy_lifecycle(kernel)
