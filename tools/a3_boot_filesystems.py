"""Exercise native HFS registration and PID 1 path setup with final VM permissions.

The VM interface, kernel allocator, locks and I/O services use single-core fixtures.
Stop before process credentials, executable validation and userspace execution.
"""
import struct

from unicorn import UcError, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.arm64_const import (UC_ARM64_REG_LR, UC_ARM64_REG_PC, UC_ARM64_REG_SP,
                                  UC_ARM64_REG_X0, UC_ARM64_REG_X29)


class Fixture:
    def __init__(self, kernel, cpu):
        self.kernel = kernel
        self.cpu = cpu
        self.area = 0x40000000
        self.sentinel = self.area + 0x100
        self.userpage = self.area + 0x10000
        self.proc = self.area + 0x20000
        self.heap = self.area + 0x80000
        cpu.mem_map(self.area, 0x600000)
        self.observed = []
        self.boundary = None
        self.err = None
        def badmem(uc, access, addr, size, value, ctx):
            self.err = f'access {access}, VA {addr:#x}, {size} bytes'
            return False
        cpu.hook_add(UC_HOOK_MEM_INVALID, badmem)

    def arg(self, n):
        return self.cpu.reg_read(UC_ARM64_REG_X0 + n)

    def return_(self, value=0):
        self.cpu.reg_write(UC_ARM64_REG_X0, value)
        self.cpu.reg_write(UC_ARM64_REG_PC, self.cpu.reg_read(UC_ARM64_REG_LR))

    def hook(self, name, fn):
        def invoke(cpu, pc, size, ctx):
            fn()
        addr = self.kernel.symbols[name]
        self.cpu.hook_add(UC_HOOK_CODE, invoke, begin=addr, end=addr)

    def stub(self, names, result=0):
        for name in names.split():
            self.hook(name, lambda: self.return_(result))

    def allocate(self):
        # Each scratch allocation has a zero-filled 16 KiB backing page.
        ptr = self.heap
        self.heap += 0x4000
        assert self.heap < self.area + 0x600000
        self.return_(ptr)

    def stop(self, label):
        self.boundary = label
        self.cpu.emu_stop()

    def call(self, name, args=(), boundary=None):
        self.boundary = self.err = None
        for n, a in enumerate(args):
            self.cpu.reg_write(UC_ARM64_REG_X0 + n, a)
        self.cpu.reg_write(UC_ARM64_REG_LR, self.sentinel)
        self.cpu.reg_write(UC_ARM64_REG_SP, self.area + 0x70000)
        try:
            self.cpu.emu_start(self.kernel.symbols[name], self.sentinel, timeout=8000000, count=1000000)
        except UcError as e:
            pc = self.cpu.reg_read(UC_ARM64_REG_PC)
            near = max((v, n) for n, v in self.kernel.symbols.items() if v <= pc)
            lr = self.cpu.reg_read(UC_ARM64_REG_LR)
            caller = max(((v, n) for n, v in self.kernel.symbols.items() if v <= lr), default=(0, 'fixture'))
            fp = self.cpu.reg_read(UC_ARM64_REG_X29)
            stack = []
            while self.area <= fp < self.area + 0x70000 and len(stack) < 12:
                next_fp, ret = struct.unpack('<QQ', self.cpu.mem_read(fp, 16))
                stack.append(max(((v, n) for n, v in self.kernel.symbols.items() if v <= ret), default=(0,'fixture'))[1])
                if next_fp <= fp:
                    break
                fp = next_fp
            stack = " -> ".join(stack)
            raise RuntimeError(f'{name}: {e}, {near[1]}+{pc-near[0]:#x}, caller {caller[1]}+{lr-caller[0]:#x}, {self.err}, {stack}') from e
        assert self.boundary == boundary, (name, self.boundary, boundary)
        if boundary is None:
            assert self.cpu.reg_read(UC_ARM64_REG_PC) == self.sentinel, name

    def cstring(self, addr, limit=128):
        return bytes(self.cpu.mem_read(addr,limit)).split(b'\0',1)[0].decode()

    def u32(self, name):
        return struct.unpack('<I', self.cpu.mem_read(self.kernel.symbols[name],4))[0]

    def u64(self, name):
        return struct.unpack('<Q', self.cpu.mem_read(self.kernel.symbols[name],8))[0]


def check_filesystems(kernel, cpu):
    f = Fixture(kernel, cpu)
    # Read-only Mach-O mappings remain enforced during every included BSD routine.
    f.stub('_vntblinit _vfs_event_init _nchinit '
           '_lck_mtx_init _mount_list_lock _mount_list_unlock _sysctl_register_oid '
           '_PE_i_can_has_kernel_configuration _kfree_type_impl_internal _lck_rw_lock_exclusive _lck_rw_unlock_exclusive _lck_rw_done')
    f.stub('__ZN9IOService15publishResourceEPKcP8OSObject')
    for name in ('_kalloc_type_impl_internal','_kalloc_ext','_IOMallocTypeImpl',
                 '_lck_grp_attr_alloc_init','_lck_grp_alloc_init','_lck_attr_alloc_init','_zone_create'):
        f.hook(name, f.allocate)
    f.stub('_sysctlbyname', 2)
    f.hook('_vfs_opv_init', lambda: f.stop('vnode descriptors initialized'))
    f.call('_vfsinit', boundary='vnode descriptors initialized')
    assert 10 < f.u32('_vfs_opv_numops') < 2048
    old_types = f.u32('_numregistered_fses')
    f.call('_sweet_hfs_register')
    assert f.u32('_numregistered_fses') == old_types + 1
    assert f.u64('_sweet_hfs_vfs_handle') and f.u64('_hfs_vnodeop_p')
    print('PASS: native vnode descriptors, HFS converters, vfs_fsadd, HFS registration and operation vectors')

    f.stub('_current_map', f.area + 0x30000)
    f.stub('_vm_map_page_size', 16384)
    def vm_page():
        assert f.arg(2) == 16384
        f.cpu.mem_write(f.arg(1), struct.pack('<Q', f.userpage))
        f.return_()
    f.hook('_mach_vm_allocate_kernel', vm_page)
    f.stub('_memorystatus_init_at_boot_snapshot _PE_parse_boot_argn')
    f.stub('_proc_is64bit', 1)
    def candidate():
        p, scratch, path = (f.arg(i) for i in range(3))
        assert p == f.proc and scratch == f.userpage
        path = f.cstring(path)
        f.observed.append(path)
        if path == '/usr/appleinternal/sbin/launchd.development':
            f.return_(2)  # Standard installation has no internal development launchd.
        else:
            assert path == '/sbin/launchd'
            # Continue the kernel's own release-path setup.
    f.hook('_load_init_program_at_path', candidate)
    def copyout():
        src, dst, size = (f.arg(i) for i in range(3))
        assert f.userpage <= dst <= f.userpage + 16384 - size and 0 < size <= 16384
        f.cpu.mem_write(dst, bytes(f.cpu.mem_read(src, size)))
        f.return_()
    f.hook('_copyout', copyout)
    f.hook('_set_security_token', lambda: f.stop('exec credential setup'))
    f.call('_load_init_program', (f.proc,), 'exec credential setup')
    assert f.observed == ['/usr/appleinternal/sbin/launchd.development','/sbin/launchd']
    assert f.cstring(f.userpage) == '/sbin/launchd'
    assert struct.unpack('<3Q', f.cpu.mem_read(f.userpage+16,24)) == (f.userpage,0,0)
    print('PASS: actual DEVELOPMENT lookup, release /sbin/launchd path and 64-bit argv; stopped before credential setup and exec')
