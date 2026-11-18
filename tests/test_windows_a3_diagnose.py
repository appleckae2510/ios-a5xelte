"""Integration checks with an ADB simulator; no phone or Windows USB driver used."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import textwrap
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/windows-a3-diagnose/Diagnose/A3-Diagnose.ps1'
PWSH = os.environ.get('A3_TEST_PWSH') or shutil.which('pwsh')


def boot_fixture(unknown=False):
    # Several chunks plus a non-MiB-aligned tail exercise skip/count and assembly.
    b = bytearray(bytes(range(256)) * (3 * 4096 + 2))
    b[:8] = b'OTHERIMG' if unknown else b'ANDROID!'
    struct.pack_into('<I', b, 36, 2048)
    return bytes(b)


FAKE_ADB = r'''#!/usr/bin/env python3
import hashlib, json, os, pathlib, re, shlex, struct, sys
a = sys.argv[1:]
with open(os.environ['A3_MOCK_LOG'],'a',encoding='utf-8') as f: f.write(json.dumps(a)+'\n')
state_path = pathlib.Path(os.environ['A3_MOCK_LOG']).with_suffix('.state')
state = json.loads(state_path.read_text()) if state_path.exists() else {}
def save_state(): state_path.write_text(json.dumps(state))
mode = os.environ.get('A3_MOCK_MODE','ok')
def emit(s): sys.stdout.buffer.write(s.encode() if isinstance(s,str) else s)
b=bytearray(bytes(range(256))*(3*4096+2)); b[:8]=b'OTHERIMG' if mode=='unknown-boot' else b'ANDROID!'; struct.pack_into('<I',b,36,2048)
if a == ['devices','-l']:
 emit('List of devices attached\nFAKE_A3\trecovery product:a3y17lte\n')
 if mode == 'multiple': emit('OTHER_PHONE\tdevice product:herolte\n')
 sys.exit(0)
if a[:2] != ['-s','FAKE_A3']:
 sys.stderr.write('Explicit device selection missing'); sys.exit(7)
a = a[2:]
props = {'ro.product.device':'a3y17lte','ro.build.product':'a3y17lte',
 'ro.product.model':'SM-A320F','ro.board.platform':'exynos5','ro.product.cpu.abi':'arm64-v8a',
 'ro.bootloader':'TEST-A320F','ro.twrp.version':'3.7.0'}
if mode == 'wrong-device': props.update({'ro.product.device':'herolte','ro.build.product':'herolte','ro.product.model':'SM-G930F'})
if mode == 'identity-change' and state.get('failed'): props['ro.product.device']='herolte'
if a == ['shell','id','-u']: emit('2000' if mode=='not-root' else '0')
elif a == ['get-state']: emit('recovery')
elif a[:2] == ['shell','getprop']: emit(props.get(a[2],''))
elif a == ['shell','find /dev/block -type d -name by-name 2>/dev/null']: emit('/dev/block/platform/13540000.dwmmc0/by-name\n')
elif a[:3] == ['shell','readlink','-f']: emit('/dev/block/mmcblk0p10\n')
elif a == ['shell','blockdev','--getsize64','/dev/block/mmcblk0p10']: emit(str(len(b)))
elif a[0]=='shell' and len(a)==2 and a[1].startswith('stat -c %s '):
 path=shlex.split(a[1])[3]
 if path!='/system/vendor/etc/firmware/nvm_tlv_tf_1.1.bin': sys.exit(1)
 emit('32768')
elif a[0]=='exec-out' and (a[1].startswith('dd ') or a[1]=='dd'):
 command=' '.join(a[1:]); opts=dict(re.findall(r'\b(if|bs|skip|count)=([^ ]+)',command))
 if opts.get('if')!='/dev/block/mmcblk0p10': sys.exit(10)
 bs=int(opts.get('bs','512')); start=int(opts.get('skip','0'))*bs
 count=int(opts.get('count',str(len(b)//bs+1))); data=bytearray(b[start:start+bs*count])
 key='offset-'+str(start); number=state.get(key,0)+1; state[key]=number; save_state()
 if mode=='no-dd': sys.stderr.write('dd: not found'); sys.exit(127)
 if mode=='transfer-fail': emit(bytes(data[:121])); sys.stderr.write('USB disconnected'); sys.exit(1)
 if start==1048576 and number==1 and mode in {'transient-short','transient-disconnect','identity-change'}:
  state['failed']=True; save_state(); emit(bytes(data[:121]))
  if mode!='transient-short': sys.stderr.write('error: device offline'); sys.exit(1)
  sys.exit(0)
 if start==1048576 and (mode=='corrupt-always' or (mode=='corrupt-once' and number==1)): data[17]^=0xff
 if start==1048576 and mode=='no-hash-inconsistent' and number%2: data[17]^=0xff
 emit(bytes(data))
 # Old adbd exec-out really merges REMOTE stderr into stdout, including dd counters.
 if '2>/dev/null' not in command or mode=='oversized': emit('\n16+0 records in\n16+0 records out\n')
elif a[0]=='shell' and len(a)==2 and any(a[1].startswith(x+' ') for x in ('sha256sum','busybox sha256sum','toybox sha256sum')):
 if mode in {'no-hash','no-hash-inconsistent'}: sys.exit(127)
 source=next(x for x in shlex.split(a[1]) if x.startswith('/'))
 if '/vendor/' in source:
  if mode=='firmware-no-hash': sys.exit(127)
  emit(hashlib.sha256(bytes(range(256))*128).hexdigest()+'  '+source+'\n')
 else: emit(hashlib.sha256(b).hexdigest()+'  /dev/block/mmcblk0p10\n')
elif a[0]=='exec-out' and (a[1].startswith('cat ') or a[1]=='cat'):
 if mode=='no-optional': sys.exit(1)
 path=shlex.split(' '.join(a[1:]))[1]
 if path=='/system/vendor/etc/firmware/nvm_tlv_tf_1.1.bin':
  data=bytearray(bytes(range(256))*128)
  state['firmware-reads']=state.get('firmware-reads',0)+1; save_state()
  if mode=='firmware-corrupt' or (mode=='firmware-transient' and state['firmware-reads']==1): data[15]^=255
  emit(bytes(data))
 elif path=='/sys/firmware/fdt': emit(b'\xd0\x0d\xfe\xedMOCK-DTB\x00\xff')
 elif path=='/proc/cmdline': emit('androidboot.hardware=samsungexynos7870')
 elif path=='/sys/class/graphics/fb0/virtual_size': emit('720,1280')
 elif path=='/sys/class/graphics/fb0/bits_per_pixel': emit('32')
 else: sys.exit(1)
elif a in (['exec-out','dmesg'],['exec-out','dmesg 2>/dev/null']): emit('Mock Exynos7870 TWRP log')
elif len(a)==2 and a[0]=='shell' and a[1].startswith('ls -l /dev/block/'): emit('BOOT -> /dev/block/mmcblk0p10')
else:
 sys.stderr.write('Unapproved command: '+repr(a)); sys.exit(9)
'''


@unittest.skipUnless(PWSH, 'PowerShell runtime required; set A3_TEST_PWSH')
class WindowsDiagnostic(unittest.TestCase):
    def run_case(self, mode, hardware=False):
        temp = tempfile.TemporaryDirectory(prefix='A3 Diagnose Test ')
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        fake = base / 'ADB with spaces' / 'adb.exe'
        fake.parent.mkdir()
        fake.write_text(textwrap.dedent(FAKE_ADB)); fake.chmod(0o755)
        out = base / 'Ergebnisse mit Leerzeichen'
        log = base / 'adb-calls.jsonl'
        env = dict(os.environ, A3_MOCK_MODE=mode, A3_MOCK_LOG=str(log))
        args = [PWSH,'-NoLogo','-NoProfile','-File',str(SCRIPT),
                '-AdbPath',str(fake),'-OutputDirectory',str(out)]
        if hardware: args.append('-Hardware')
        result = subprocess.run(args,
                                env=env,capture_output=True,text=True,timeout=45)
        calls = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
        self.assertTrue(calls, result.stdout + result.stderr)
        for call in calls:
            tokens = ' '.join(call).split()
            self.assertFalse(any(x.startswith('of=') or x in {'push','flash','reboot','root','install','erase','format'} for x in tokens), call)
            if call[0] != 'devices': self.assertEqual(call[:2], ['-s','FAKE_A3'])
        return result, out, calls

    def test_hardware_firmware_integrity_and_retries(self):
        for mode in ('firmware', 'firmware-transient', 'firmware-corrupt', 'firmware-no-hash'):
            with self.subTest(mode=mode):
                result, out, calls = self.run_case(mode, hardware=True)
                self.assert_valid_backup(result, out)
                with zipfile.ZipFile(next(out.rglob('A3-Diagnose.zip'))) as archive:
                    manifest = json.loads(archive.read('manifest.json'))
                    self.assertTrue(manifest['hardware_firmware_requested'])
                    entries = json.loads(archive.read('hardware-firmware.json'))
                    entry = next(x for x in entries if x['file'] == 'firmware/nvm_tlv_tf_1.1.bin')
                    if mode == 'firmware-corrupt':
                        self.assertEqual(entry['status'], 'missing-or-unverified')
                        self.assertNotIn(entry['file'], archive.namelist())
                    else:
                        data = bytes(range(256))*128
                        self.assertEqual(archive.read(entry['file']), data)
                        self.assertEqual(manifest['files'][entry['file']]['sha256'], hashlib.sha256(data).hexdigest())
                        method = 'matching-independent-reads' if mode == 'firmware-no-hash' else 'device-sha256'
                        self.assertEqual(entry['integrity'], method)

    def assert_valid_backup(self, result, out, method='device-sha256'):
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        archives=list(out.rglob('A3-Diagnose.zip'))
        self.assertEqual(len(archives),1)
        with zipfile.ZipFile(archives[0]) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.read('boot.img'),boot_fixture())
            manifest=json.loads(z.read('manifest.json'))
            self.assertEqual(manifest['boot_integrity'],method)
            self.assertEqual(manifest['files']['boot.img']['sha256'],hashlib.sha256(boot_fixture()).hexdigest())
        self.assertFalse(list(out.rglob('*.part')))

    @staticmethod
    def boot_commands(calls):
        return [' '.join(c[3:]) for c in calls if c[2:3]==['exec-out'] and c[3].startswith('dd')]

    def assert_failed_cleanly(self, result, out):
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse(list(out.rglob('*.zip')))
        self.assertFalse(list(out.rglob('*.part')))
        self.assertFalse(list(out.rglob('boot.img')))
        self.assertEqual(len(list(out.rglob('FEHLER.txt'))),1)

    def test_binary_backup_and_compatible_manifest(self):
        result, out, calls = self.run_case('ok')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        archives = list(out.rglob('A3-Diagnose.zip'))
        self.assertEqual(len(archives), 1)
        with zipfile.ZipFile(archives[0]) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.read('boot.img'), boot_fixture())
            manifest = json.loads(z.read('manifest.json'))
            self.assertEqual(manifest['target'], 'a3y17lte')
            self.assertFalse(manifest['phone_writes'])
            self.assertEqual(manifest['files']['boot.img']['sha256'], hashlib.sha256(boot_fixture()).hexdigest())
            self.assertEqual(manifest['files']['boot.img']['size'], len(boot_fixture()))
            self.assertEqual(manifest['boot_integrity'], 'device-sha256')
            self.assertEqual(manifest['boot_format'], 'android-samsung-legacy-2048')
            self.assertEqual(json.loads(z.read('device.json'))['ro.product.model'], 'SM-A320F')

    def test_multiple_devices_stop_before_reading_phone(self):
        result, out, calls = self.run_case('multiple')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [['devices','-l']])
        self.assertFalse(list(out.rglob('*.zip')))

    def test_foreign_phone_cannot_be_backed_up_as_a3(self):
        result, out, calls = self.run_case('wrong-device')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('dd' in call for call in calls))
        self.assertIn('a3y17lte', result.stdout)
        self.assertTrue(any(call[2:4] == ['shell','getprop'] for call in calls))
        self.assertFalse(list(out.rglob('*.zip')))

    def test_no_twrp_root_stops_before_partition_access(self):
        result, out, calls = self.run_case('not-root')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('dd' in call for call in calls))
        self.assertIn('TWRP-Root-Zugriff', result.stdout)

    def test_interrupted_copy_is_not_reported_as_success(self):
        result, out, calls = self.run_case('transfer-fail')
        self.assert_failed_cleanly(result,out)
        self.assertEqual(len(self.boot_commands(calls)),3)
        self.assertIn('Exitcode 1', result.stdout)

    def test_remote_dd_status_is_suppressed_before_binary_transport(self):
        result,out,calls=self.run_case('legacy-stderr')
        self.assert_valid_backup(result,out)
        self.assertTrue(all(c.endswith('2>/dev/null') for c in self.boot_commands(calls)))

    def test_short_transfer_retries_only_failed_chunk(self):
        result,out,calls=self.run_case('transient-short')
        self.assert_valid_backup(result,out)
        commands=self.boot_commands(calls)
        self.assertEqual(sum('skip=16 ' in c for c in commands),2)
        self.assertEqual(sum('skip=0 ' in c for c in commands),1)
        self.assertIn('empfangen 121',result.stdout)

    def test_disconnected_adb_can_recover_without_restarting_entire_backup(self):
        result,out,calls=self.run_case('transient-disconnect')
        self.assert_valid_backup(result,out)
        self.assertEqual(sum('skip=16 ' in c for c in self.boot_commands(calls)),2)
        self.assertGreaterEqual(sum(c[2:]==['get-state'] for c in calls),2)

    def test_same_size_corruption_is_detected_and_full_copy_retried(self):
        result,out,calls=self.run_case('corrupt-once')
        self.assert_valid_backup(result,out)
        self.assertEqual(sum('skip=0 ' in c for c in self.boot_commands(calls)),2)

    def test_persistent_corruption_never_creates_success_archive(self):
        result,out,calls=self.run_case('corrupt-always')
        self.assert_failed_cleanly(result,out)
        self.assertEqual(sum('skip=0 ' in c for c in self.boot_commands(calls)),2)
        self.assertIn('BOOT-Pruefsummen',result.stdout)

    def test_no_remote_hash_uses_two_complete_independent_reads(self):
        result,out,calls=self.run_case('no-hash')
        self.assert_valid_backup(result,out,'two-independent-reads-sha256')
        self.assertEqual(sum('skip=0 ' in c for c in self.boot_commands(calls)),2)

    def test_inconsistent_double_reads_are_rejected(self):
        result,out,calls=self.run_case('no-hash-inconsistent')
        self.assert_failed_cleanly(result,out)
        self.assertIn('BOOT-Pruefsummen',result.stdout)

    def test_oversized_binary_result_is_not_silently_truncated(self):
        result,out,calls=self.run_case('oversized')
        self.assert_failed_cleanly(result,out)
        self.assertEqual(len(self.boot_commands(calls)),3)
        self.assertIn('erwartet 1048576 Bytes',result.stdout)
        self.assertNotIn('Bitte USB-Kabel pruefen',result.stdout)

    def test_source_identity_is_rechecked_before_retry(self):
        result,out,calls=self.run_case('identity-change')
        self.assert_failed_cleanly(result,out)
        self.assertIn('Geraetekennung hat sich geaendert',result.stdout)
        self.assertEqual(sum('skip=16 ' in c for c in self.boot_commands(calls)),1)

    def test_missing_dd_has_accurate_error_and_bounded_retry(self):
        result,out,calls=self.run_case('no-dd')
        self.assert_failed_cleanly(result,out)
        self.assertEqual(len(self.boot_commands(calls)),3)
        self.assertIn('Exitcode 127',result.stdout)

    def test_missing_optional_files_do_not_block_boot_backup(self):
        result, out, calls = self.run_case('no-optional')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        with zipfile.ZipFile(next(out.rglob('A3-Diagnose.zip'))) as z:
            manifest=json.loads(z.read('manifest.json'))
            self.assertIn('live.dtb',manifest['missing_optional'])
            self.assertEqual(z.read('boot.img'),boot_fixture())

    def test_unknown_boot_format_is_preserved_for_diagnosis(self):
        result, out, calls = self.run_case('unknown-boot')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        with zipfile.ZipFile(next(out.rglob('A3-Diagnose.zip'))) as z:
            self.assertEqual(json.loads(z.read('manifest.json'))['boot_format'], 'unknown')
            self.assertEqual(z.read('boot.img'),boot_fixture(True))


if __name__ == '__main__': unittest.main()
