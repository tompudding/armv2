import os
import sys
import struct
from elftools.elf.elffile import ELFFile

def load(filename):
    with open(filename,'rb') as f:
        return f.read()

boot,data = (load(filename) for filename in sys.argv[1:3])
with open(sys.argv[2],'rb') as f:
    elffile = ELFFile(f)
    for segment in elffile.iter_segments():
        offset = segment['p_offset']
        v_addr = segment['p_vaddr']
        filesz = segment['p_filesz']
        memsz  = segment['p_memsz']
        print offset,v_addr,filesz,memsz
        data = data[offset:offset + filesz]
        data += '\x00'*(memsz-filesz)

#Get rid of any bx lrs from the gcc stdlib

entry_point = elffile.header['e_entry']
data = data.replace(struct.pack('<I',0xe12fff1e),struct.pack('<I',0xe1a0f00e))
boot = boot.replace(struct.pack('<I',0xcafebabe),struct.pack('<I',entry_point))

assert len(boot) < 0x8000
boot = boot + '\x00'*(0x8000 - len(boot))
with open(sys.argv[3],'wb') as f:
    f.write(boot)
    f.write(data)
