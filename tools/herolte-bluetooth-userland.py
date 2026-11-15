#!/usr/bin/env python3
"""Stage an OWNED BCM4359 firmware and iOS Bluetooth launchd transport offline.

This tool modifies only an offline mounted iOS root directory. It never
flashes a phone. It deliberately does not distribute Broadcom firmware.
"""
import argparse
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import sys

TRANSPORT = "H4BC:POSIX:com.apple.uart.bluetooth,115200"


def validate_hcd(data):
    off = count = 0
    if not data or len(data) > 128 * 1024:
        raise ValueError("HCD must be 1..131072 bytes")
    while off < len(data) and count < 1024:
        if len(data) - off < 3:
            raise ValueError("truncated HCD command")
        op = data[off] | data[off + 1] << 8
        n = data[off + 2]
        off += 3
        if n > len(data) - off:
            raise ValueError("truncated HCD payload")
        off += n
        count += 1
        if op == 0xFC4E and n == 4 and off == len(data) and count > 1:
            return count
        if op != 0xFC4C or n < 5:
            raise ValueError(f"unsupported command 0x{op:04x} in HCD")
    raise ValueError("HCD must end with Launch_RAM (0xfc4e)")


def launchd_targets(root):
    out = []
    for directory in ("System/Library/LaunchDaemons", "Library/LaunchDaemons"):
        folder = root / directory
        if not folder.is_dir():
            continue
        for path in folder.glob("*.plist"):
            if "bluetoothd" in path.name.lower() or "bluetool" in path.name.lower():
                out.append(path)
    return sorted(set(out))


def stage_plist(path):
    original = path.read_bytes()
    try:
        obj = plistlib.loads(original)
    except (ValueError, TypeError, plistlib.InvalidFileException) as exc:
        raise ValueError(f"unreadable plist {path}: {exc}")
    if not isinstance(obj, dict):
        raise ValueError(f"not a launchd property dictionary: {path}")
    env = obj.get("EnvironmentVariables") or {}
    if not isinstance(env, dict):
        raise ValueError(f"invalid EnvironmentVariables in {path}")
    env["BT_HCI_TRANSPORT"] = TRANSPORT
    obj["EnvironmentVariables"] = env
    if obj.get("Disabled") is True:
        obj["Disabled"] = False
    fmt = plistlib.FMT_BINARY if original.startswith(b"bplist") else plistlib.FMT_XML
    updated = plistlib.dumps(obj, fmt=fmt)
    if updated != original:
        backup = path.with_suffix(path.suffix + ".before-herolte-bt")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_bytes(updated)
        print(f"updated {path}, backup {backup}")
    else:
        print(f"unchanged {path}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path, help="offline mounted iOS root path")
    p.add_argument("--firmware", type=Path,
                   help="your OWN BCM4359 Murata/Semco .hcd, from this phone")
    a = p.parse_args()
    root = a.root.resolve()
    if not root.is_dir() or not (root / "System/Library").is_dir():
        p.error("not an iOS root: System/Library missing")
    paths = launchd_targets(root)
    if not paths:
        p.error("bluetoothd/BlueTool plist not found; root unchanged")
    fwdata = None
    if a.firmware:
        fwdata = a.firmware.read_bytes()
        n = validate_hcd(fwdata)
        print(f"owner HCD: {len(fwdata)} bytes, {n} commands, "
              f"sha256={hashlib.sha256(fwdata).hexdigest()}")
    for path in paths:
        stage_plist(path)
    if fwdata is not None:
        target = root / "private/var/herolte/bt/fw.hcd"
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_bytes(fwdata)
        os.chmod(target, 0o600)
        print(f"installed owner firmware: {target}")
    else:
        print("WARNING: no --firmware provided; kernel firmware stage remains blocked")
    print("NEXT: rebuild SWEETXNU with herobt=2 and bluetoothd removed from heronoexec.")
    print("Hardware HCI Reset, HCD stage and iOS scanning/pairing still need phone logs.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
