"""Replay the actual named MAC syscall; user-memory copy and audit context are modeled."""
from pathlib import Path
import sys,importlib.util,json,argparse
w=Path(__file__).resolve().parent
def module(name,file):
 s=importlib.util.spec_from_file_location(name,file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
trust=module('trust',w/'a3-boot-trust-test.py');reg=module('reg',w/'a3-boot-regression.py')
p=argparse.ArgumentParser(description=__doc__);p.add_argument('kernel',type=Path);p.add_argument('payload',type=Path);p.add_argument('--cache',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
from unicorn import UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_PC,UC_ARM64_REG_LR
import struct
class Fixture(trust.TrustFixture):
 def query_boot_files(self,cpu,call):
  super().query_boot_files(cpu,call)
  def finish(value):
   cpu.reg_write(UC_ARM64_REG_X0,value);cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
  def copy_string(cpu,pc,size,data):
   address,target,limit,length=[cpu.reg_read(r) for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3)]
   value=bytes(cpu.mem_read(address,limit));value=value[:value.index(b'\0')+1];cpu.mem_write(target,value)
   if length:cpu.mem_write(length,struct.pack('<Q',len(value)))
   finish(0)
  handles=[cpu.hook_add(UC_HOOK_CODE,copy_string,begin=call.symbols['_copyinstr'],end=call.symbols['_copyinstr'])]
  for name in ('_audit_arg_value32','_audit_arg_mac_string'):
   if name in call.symbols: handles.append(cpu.hook_add(UC_HOOK_CODE,lambda *_:finish(0),begin=call.symbols[name],end=call.symbols[name]))
  results=[]
  try:
   for name,want in ((b'Sandbox',1),(b'A3UnknownPolicy',103)):
    cpu.mem_write(self.buffer+768,name+b'\0');cpu.mem_write(self.buffer+512,struct.pack('<QI4xQ',self.buffer+768,2,0))
    rc=call('___mac_syscall',0,self.buffer+512,0)
    print('NAMED MAC DISPATCH',name.decode(),'return',rc,'expected',want,flush=True)
    assert rc==want,(name,rc,want)
    results.append({'policy':name.decode(),'null_process_errno':rc,'passed':True})
  finally:
   for handle in handles:cpu.hook_del(handle)
  a.report.write_text(json.dumps(results,indent=2)+'\n')
k=reg.Kernel(a.kernel);component=a.cache.read_bytes();baseline=json.loads((w.parent/'tests/a3-20h392-startup.json').read_text());f=Fixture(a.kernel,a.payload.read_bytes(),component,baseline);f.kernel=k;reg.startup_path(k);reg.policy_lifecycle(k,f)
