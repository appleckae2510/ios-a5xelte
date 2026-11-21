"""Exercise the A3 cache handoff and the native kernel's lookup of stock boot tasks."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import urllib.request
import zlib

import adt
import mkadt_a3y17lte
import mkpayload

TOOLS = Path(__file__).resolve().parent
BASELINE = TOOLS.parent / "tests/a3-20h392-startup.json"
# Only the pinned static component is read; the packer verifies its manifest digest.
APPLE_IPSW = ("https://updates.cdn-apple.com/2025FallFCS/fullrestores/122-76738/"
              "B6C604B4-548E-401F-BBFF-916E3FFDF235/iPhone_5.5_P3_16.7.16_20H392_Restore.ipsw")


def fetch_component():
    start, end = 6031110591, 6031110591 + 59790 + 2047
    request = urllib.request.Request(APPLE_IPSW, headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/6158048697":
            raise ValueError("unexpected Apple IPSW range")
        block = response.read(end - start + 2)
    if len(block) != end - start + 1 or block[:4] != b"PK\x03\x04" or struct.unpack_from("<H", block, 8)[0] != 8:
        raise ValueError("unexpected ZIP header or range length")
    nl, extra = struct.unpack_from("<HH", block, 26)
    if block[30:30+nl] != b"Firmware/087-86694-044.dmg.trustcache":
        raise ValueError("wrong ZIP member")
    pos = 30 + nl + extra
    return zlib.decompress(block[pos:pos+59790], -15)


class TrustFixture:
    def __init__(self, kernel_path, payload, component, baseline):
        if payload[:8] != b"SWEETXNU":
            raise ValueError("expected a native A3 payload")
        self.files = baseline["files"]
        self.results = {}
        self.platform_ready = False
        table = mkpayload.a3_release_cache(component)
        virt, _, adtoff, adtlen, kernel_end, phys, memory = struct.unpack_from("<7Q", payload, 16)
        self.tree = payload[adtoff:adtoff+adtlen]
        root, end = adt.parse(self.tree)
        if end != len(self.tree) or b"samsung,a3y17lte" not in root.prop("compatible").split(b"\0"):
            raise ValueError("not an A3 device tree")
        chosen = next(n for n in root.children if n.name == "chosen")
        mmap = next(n for n in chosen.children if n.name == "memory-map")
        self.physical, size = struct.unpack("<2Q", mmap.prop("TrustCache"))
        ram_pa, ram_size = struct.unpack("<2Q", mmap.prop("RAMDisk"))
        if size != len(table) or self.physical < ram_pa + ram_size or self.physical % 4096:
            raise ValueError("incorrect trust cache placement relative to md0")
        count = struct.unpack_from("<I", payload, 12)[0]
        segments = [struct.unpack_from("<4Q", payload, 0x2a8 + i*32) for i in range(count)]
        kernel_data = bytearray(kernel_path.read_bytes())
        macho = mkpayload.parse_macho(kernel_data)
        mkpayload.apply_chained_fixups(kernel_data, macho)
        image_segments = [s for s in macho["segs"] if s["vmsize"]]
        if len(segments) != len(image_segments) + 2:
            raise ValueError("expected kernel, diagnostic RAM disk and one static cache")
        for mapped, linked in zip(segments, image_segments):
            address, length, offset, data_size = mapped
            if (address, length, data_size) != (linked["vmaddr"], linked["vmsize"], linked["filesize"]):
                raise ValueError("linked kernel layout differs from the supplied payload")
            start = linked["fileoff"]
            if payload[offset:offset+data_size] != kernel_data[start:start+data_size]:
                raise ValueError("linked kernel bytes differ from the supplied payload")
        matches = [s for s in segments if phys + s[0] - virt == self.physical]
        if len(matches) != 1:
            raise ValueError("device-tree range lacks a unique loader segment")
        va, extent, off, fsize = matches[0]
        self.table = payload[off:off+fsize]
        aligned = (size + mkpayload.PAGE - 1) & ~(mkpayload.PAGE - 1)
        if self.table != table or extent != aligned or va + extent != kernel_end:
            raise ValueError("table, occupied memory or end of loader segments differs")
        if kernel_end - virt + ((adtlen + 4095) // 4096 + 1)*4096 > memory:
            raise ValueError("device tree and boot args exceed A3 memory")
        module_count, module_off = struct.unpack_from("<II", table)
        version = struct.unpack_from("<I", table, module_off)[0]
        entries = struct.unpack_from("<I", table, module_off + 20)[0]
        if (module_count, module_off, version, entries) != (1, 8, 2, baseline["count"]):
            raise ValueError("unexpected stock trust cache table")
        values = dict((h.hex(), (t, f, c, r)) for h,t,f,c,r in struct.iter_unpack("<20sBBBB", table[module_off + 24:]))
        if len(values) != entries or list(values) != sorted(values):
            raise ValueError("duplicate or unordered CDHashes")
        for f in self.files:
            if values.get(f["cdhash"]) != (2, 0, f["category"], 0):
                raise ValueError(f"cache differs from audited release for {f['path']}")
        self.absent = hashlib.sha256(b"A3 20H392 negative control").digest()[:20]
        if self.absent.hex() in values:
            raise ValueError("negative control occurs in stock cache")
        self.virt, self.phys, self.mem = virt, phys, memory
        self.table_va = virt + self.physical - phys
        self.area = kernel_end
        self.boot_args = kernel_end + ((adtlen + 4095) // 4096) * 4096
        self.buffer = 0x52000000
        print(f"PASS: {entries} original static entries, {len(self.files)} release identities and their constraints in the payload")

    def install_boot_inputs(self, kernel, cpu, call):
        # The boot_args offsets are shared with the A3 loader. Set the native
        # physical map to the same linear boot mapping, then use XNU phystokv.
        cpu.mem_map(self.area, self.boot_args - self.area + 4096)
        cpu.mem_write(self.area, self.tree)
        cpu.mem_protect(self.area, self.boot_args - self.area, 1)
        cpu.mem_map(self.buffer, 4096)
        mapped = (len(self.table) + 4095) // 4096 * 4096
        cpu.mem_map(self.table_va, mapped, 1)
        cpu.mem_write(self.table_va, self.table)
        top = self.phys + self.boot_args - self.virt + 4096
        args = bytearray(108)
        struct.pack_into("<HH4x4Q", args, 0, 2, 2, self.virt, self.phys, self.mem, top)
        struct.pack_into("<QI", args, 96, self.area, len(self.tree))
        cpu.mem_write(self.boot_args, bytes(args))
        for name, val in (("_gVirtBase", self.virt), ("_gPhysBase", self.phys),
                          ("_real_phys_size", self.mem)):
            cpu.mem_write(kernel.symbols[name], struct.pack("<Q", val))
        # LP64 PE_state.bootArgs follows initialized (8 incl. padding),
        # PE_Video (144) and deviceTreeHead (8).
        cpu.mem_write(kernel.symbols["_PE_state"] + 160, struct.pack("<Q", self.boot_args))
        for name in ("_a3_measured_module", "_a3_measured_ready"):
            seg = kernel.segment(kernel.symbols[name])
            if seg[0] != "__DATA_CONST" or seg[-1] != 1:
                raise ValueError("the measured identity table must be protected at lockdown")
        call("_SecureDTInit", self.area, len(self.tree))
        out = self.buffer
        path = b"chosen/memory-map\0"
        cpu.mem_write(out + 128, path + b"TrustCache\0")
        if call("_SecureDTLookupEntry", 0, out+128, out) != 1:
            raise ValueError("linked XNU did not find chosen/memory-map")
        node = int.from_bytes(cpu.mem_read(out, 8), "little")
        if call("_SecureDTGetProperty", node, out+128+len(path), out+8, out+16) != 1:
            raise ValueError("linked XNU did not find TrustCache")
        pointer, size = struct.unpack("<QI", cpu.mem_read(out+8, 12))
        if size != 16 or not self.area <= pointer <= self.area + len(self.tree) - size:
            raise ValueError("XNU returned an invalid property view")
        pa, length = struct.unpack("<QQ", cpu.mem_read(pointer, size))
        if (pa, length) != (self.physical, len(self.table)) or cpu.mem_read(call("_phystokv", pa, wide=True), length) != self.table:
            raise ValueError("XNU device-tree view differs from the shipped module")
        print("PASS: linked XNU SecureDT read the complete cache range reserved by the loader")
        first = bytes.fromhex(self.files[0]["cdhash"])
        cpu.mem_write(out + 96, first)
        # Change only a constraint byte in the copy delivered by the loader.
        # The real kernel must hash the entire module, including this field.
        changed_pos = 8 + 24 + 22
        original = self.table[changed_pos]
        cpu.mem_write(self.table_va + changed_pos, bytes([original ^ 1]))
        call("_a3_measure_boot_cache")
        if call("_a3_measured_identity", out+96, wide=True):
            raise ValueError("a modified static cache produced an identity")
        if "_a3_authorize_boot_flags" in kernel.symbols:
            if call("_a3_authorize_boot_flags", out+96, 2, 0x4001, 0x1234) != 0x1234:
                raise ValueError("a modified cache granted platform identity")
        cpu.mem_write(self.table_va + changed_pos, bytes([original]))
        print("PASS: native measurement rejects a modified launch constraint")

    def query_boot_files(self, cpu, call):
        buf = self.buffer
        cpu.mem_write(buf, b"\0" * 256)
        rc = call("_static_trust_cache_capabilities", buf, buf+8, buf+16)
        num = int.from_bytes(cpu.mem_read(buf, 4), "little")
        print(f"Native static trust cache capabilities: status={rc}, count={num}")
        # Once measured, the immutable kernel copy must survive a change
        # to the loader's backing memory. Access and policy results are separate.
        cpu.mem_write(self.table_va, bytes(len(self.table)))
        for f in self.files:
            raw = bytes.fromhex(f["cdhash"])
            cpu.mem_write(buf+96, raw)
            match = call("_a3_measured_identity", buf+96, wide=True)
            if not match or cpu.mem_read(match, 24) != raw + bytes((2, 0, f["category"], 0)):
                raise ValueError(f"native measurement disagrees with the release for {f['path']}")
            result = call("_query_trust_cache", 1, buf+96, 0)
            self.results[f["path"]] = result
            print(f"  {f['path']}: measured category={f['category']}, system lookup={result}")
            if "_a3_authorize_boot_flags" in call.symbols:
                flags = 0x1234
                # The signed flags are read from XNU's cs_blobs.h. Test exact
                # stock identities with read-only root and the entry's hash type.
                expected = flags | 0x20000000 | 0x04000000
                if call("_a3_authorize_boot_flags", buf+96, 2, 0x4001, flags) != expected:
                    raise ValueError(f"stock root identity was not authorized for {f['path']}")
                for hash_type, mount in ((1, 0x4001), (2, 0x4000), (2, 1), (2, 0)):
                    if call("_a3_authorize_boot_flags", buf+96, hash_type, mount, flags) != flags:
                        raise ValueError("platform identity escaped its original hash type/read-only-root scope")
        print(f"PASS: native kernel matched {len(self.files)} original identities and constraints after lockdown")
        cpu.mem_write(buf+96, self.absent)
        if "_a3_authorize_boot_flags" in call.symbols:
            for pointer in (buf+96, 0):
                if call("_a3_authorize_boot_flags", pointer, 2, 0x4001, 0x1234) != 0x1234:
                    raise ValueError("an unknown or absent identity acquired platform flags")
            self.platform_ready = True
            print("PASS: 10 original root identities authorized, 42 negative policy controls rejected")
        if call("_a3_measured_identity", buf+96, wide=True) or call("_a3_measured_identity", 0, wide=True):
            raise ValueError("negative input incorrectly matched a release entry")
        if call("_query_trust_cache", 1, buf+96, 0) != 56:
            raise ValueError("unknown CDHash was not rejected as KERN_NOT_FOUND")
        if call("_query_trust_cache", 1, 0, 0) != 4:
            raise ValueError("missing hash was not rejected as KERN_INVALID_ARGUMENT")
        self.lookup_ready = rc == 0 and num > 0 and all(s == 0 for s in self.results.values())
        if not self.lookup_ready and (rc != 46 or num != 0 or any(s != 56 for s in self.results.values())):
            raise ValueError("partial or unexpected native trust-cache results; inspect each result")
        print("PASS: negative lookup controls")
        message = ("Stock static-cache lookup available in the kernel model." if self.lookup_ready else
                   "Global static-cache API unavailable: KERN_NOT_SUPPORTED. See the separate native boot policy result.")
        print(message)
        if path := os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(path, "a") as stream:
                print("### A3 boot-task identity\n\n" + message +
                      "\n\nA positive lookup alone does not verify a boot to SpringBoard.\n", file=stream)


def run():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("kernel", type=Path)
    p.add_argument("--cache", type=Path, help="original d21ap 20H392 static cache IM4P; otherwise read from Apple's IPSW")
    p.add_argument("--payload", type=Path, help="existing SWEETXNU payload; otherwise create an A3 build fixture")
    p.add_argument("--require-lookup", action="store_true", help="exit 3 if the native kernel cannot find the stock boot tasks")
    p.add_argument("--require-platform-policy", action="store_true",
                   help="exit 3 if the native read-only-root signature policy is unavailable")
    args = p.parse_args()
    component = args.cache.read_bytes() if args.cache else fetch_component()
    baseline = json.loads(BASELINE.read_text())
    mkpayload.a3_release_cache(component)
    changed = bytearray(component)
    changed[-1] ^= 1
    for invalid in (changed, component[:-1]):
        try:
            mkpayload.a3_release_cache(invalid)
        except ValueError:
            continue
        raise ValueError("the packer accepted a modified release component")
    if args.payload:
        payload = args.payload.read_bytes()
    else:
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            tree, ram, cache = d/"board.adt", d/"diagnostic.ram", d/"20H392.trustcache"
            tree.write_bytes(adt.serialize(mkadt_a3y17lte.build()))
            ram.write_bytes(b"A3 loader test")
            cache.write_bytes(component)
            payload, _ = mkpayload.build(args.kernel, tree, "rd=a3auto", ram, a3_static_cache=cache)
    test = TrustFixture(args.kernel, payload, component, baseline)
    spec = importlib.util.spec_from_file_location("a3_boot_regression", TOOLS / "a3-boot-regression.py")
    regression = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(regression)
    kernel = regression.Kernel(args.kernel)
    regression.startup_path(kernel)
    regression.policy_lifecycle(kernel, trust_fixture=test)
    return 3 if ((args.require_lookup and not test.lookup_ready) or
                 (args.require_platform_policy and not test.platform_ready)) else 0


if __name__ == "__main__":
    raise SystemExit(run())
