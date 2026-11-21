"""Execute the native corpse tunable and query on the exact packed boot command."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('kernel',type=Path);p.add_argument('image',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
w=Path(__file__).resolve().parent

spec=importlib.util.spec_from_file_location('boot',w/'a3-boot-regression.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
k=r.Kernel(a.kernel)
from mkpayload import apply_chained_fixups,parse_macho
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM
from unicorn.arm64_const import UC_CPU_ARM64_A53,UC_ARM64_REG_PSTATE,UC_ARM64_REG_X0,UC_ARM64_REG_SP,UC_ARM64_REG_LR,UC_ARM64_REG_PC
image=a.image.read_bytes();ks=struct.unpack_from('<I',image,8)[0];payload=image[2048+0x4010:2048+ks];command=payload[0x48:0x2a8].split(b'\0')[0]
assert command.split().count(b'-no_corpses')==1
kernel=bytearray(k.data);apply_chained_fixups(kernel,parse_macho(kernel))
cpu=Uc(UC_ARCH_ARM64,UC_MODE_ARM);cpu.ctl_set_cpu_model(UC_CPU_ARM64_A53);cpu.reg_write(UC_ARM64_REG_PSTATE,0x3c5);cpu.cpr_write(3,0,1,0,2,3<<20)
for name,va,length,off,size,prot in k.segments:
 cpu.mem_map(va,length,prot|2);cpu.mem_write(va,bytes(kernel[off:off+size]))
area,stop=0x50000000,0x51000000;cpu.mem_map(area,0x40000);cpu.mem_map(stop,4096)
bootargs=area+0x20000;cpu.mem_write(k.symbols['_PE_state']+160,struct.pack('<Q',bootargs))
entry=next(v for n,v in k.symbols.items() if 'spec_corpses_disabled' in n)
def call(name,arg=0):
 cpu.reg_write(UC_ARM64_REG_SP,area+0x1f000);cpu.reg_write(UC_ARM64_REG_LR,stop);cpu.reg_write(UC_ARM64_REG_X0,arg)
 cpu.emu_start(k.symbols[name],stop,count=1000000)
 assert cpu.reg_read(UC_ARM64_REG_PC)==stop
 return cpu.reg_read(UC_ARM64_REG_X0)&0xffffffff
results=[]
for title,cmd,want in [('without flag',b' '.join(x for x in command.split() if x!=b'-no_corpses'),1),('packed v0.13 command',command,0)]:
 cpu.mem_write(k.symbols['_corpses_disabled'],b'\0');cpu.mem_write(bootargs+108,cmd.ljust(608,b'\0'))
 assert call('_corpses_enabled')==1
 call('_kernel_startup_tunable_init',entry)
 enabled=call('_corpses_enabled');assert enabled==want,(title,enabled)
 print(title,'PASS','corpses_enabled',enabled)
 results.append({'case':title,'corpses_enabled':enabled,'passed':True})
a.report.write_text(json.dumps(results,indent=2)+'\n')
