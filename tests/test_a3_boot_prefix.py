"""Exercise the PowerShell check's TWRP shell command with regular-file fixtures."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
CHECK = HERE / 'tools/windows-a3-diagnose/Diagnose/A3-Bootvergleich.ps1'
PWSH = os.environ.get('A3_TEST_PWSH') or shutil.which('pwsh')
HARNESS = r"""
param([string]$Check, [string]$Directory)
$ErrorActionPreference = 'Stop'
. $Check
function Confirm-BackupSource($Path, $Size) {
    if ($Path -ne '/dev/block/mmcblk0p10' -or $Size -ne 33554432) { throw 'unexpected BOOT' }
}
function Invoke-Adb($AdbArguments, $TimeoutSeconds) {
    if ($AdbArguments[0] -ne 'shell') { throw 'unexpected ADB command' }
    $cmd = $AdbArguments[1].Replace('/dev/block/mmcblk0p10', '"$A3_PREFIX_FIXTURE/partition"')
    $cmd = $cmd.Replace('/tmp/a3-bootcheck.XXXXXX', '"$A3_PREFIX_FIXTURE/a3-bootcheck.XXXXXX"')
    $env:A3_PREFIX_FIXTURE = $Directory
    $output = $cmd | /bin/sh
    if ($LASTEXITCODE -ne 0) { throw 'read failed' }
    [pscustomobject]@{ Bytes = [Text.Encoding]::UTF8.GetBytes([string]$output) }
}
try { Write-Output (Get-InstalledA3BootHash 19) } catch { Write-Output 'unverified'; exit 1 }
"""


@unittest.skipUnless(PWSH and os.name == 'posix', 'requires PowerShell and a POSIX shell')
class BootPrefix(unittest.TestCase):
    def test_padding_and_short_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            script = directory / 'probe.ps1'
            script.write_text(HARNESS)
            image = bytes(range(19))
            for partition, success in ((image+b'previous partition tail', True), (image[:-1], False)):
                with self.subTest(success=success):
                    (directory/'partition').write_bytes(partition)
                    result = subprocess.run([PWSH, '-NoProfile', '-File', str(script), str(CHECK), tmp],
                                            capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
                    expected = hashlib.sha256(image).hexdigest() if success else 'unverified'
                    self.assertIn(expected, result.stdout.splitlines())
                    self.assertEqual((directory/'partition').read_bytes(), partition)
                    self.assertFalse(list(directory.glob('a3-bootcheck.*')))
