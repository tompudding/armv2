import os
import sys
import struct
from elftools.elf.sections import SymbolTableSection
from elftools.elf.elffile import ELFFile

def load(filename):
    with open(filename,'rb') as f:
        return f.read()

def get_symbols(elf):
    for section in elf.iter_sections():
        if not isinstance(section, SymbolTableSection):
            continue

        if section['sh_entsize'] == 0:
            continue

        # if self.elffile.elfclass == 32:
        #     self._emitline('   Num:    Value  Size Type    Bind   Vis      Ndx Name')
        # else: # 64
        #     self._emitline('   Num:    Value          Size Type    Bind   Vis      Ndx Name')

        for nsym, symbol in enumerate(section.iter_symbols()):
            if symbol['st_shndx'] == 'SHN_ABS' or symbol['st_value'] == 0:
                continue
            if not symbol.name.strip() or symbol.name.startswith('$'):
                continue
            yield symbol['st_value'],symbol.name

        #     version_info = ''
        #     # readelf doesn't display version info for Solaris versioning
        #     if (section['sh_type'] == 'SHT_DYNSYM' and
        #             self._versioninfo['type'] == 'GNU'):
        #         version = self._symbol_version(nsym)
        #         if (version['name'] != symbol.name and

def pad(data, alignment):
    target = ((len(data) + (alignment - 1)) / alignment) * alignment
    if target > len(data):
        data += '\00'*(target-len(data))
    return data

def to_synapse_format(data, symbols, entry_point):
    """
We have a very simple format for the synapse binaries:
         Offset   |   Contents
         ---------|-----------
            0     |   Length of data section
            4     |   data section
          4 + len |   Length of symbols
      4 + len + 4 |   symbols
"""
    data = pad(data, 4)
    out = struct.pack('>I', len(data)) + data + struct.pack('>I', len(symbols)) + symbols
    if entry_point != None:
        out = struct.pack('>I', entry_point) + out
    return out

def create_binary(header, elf, boot=False):
    elf_data = load(elf)
    with open(elf,'rb') as f:
        elffile = ELFFile(f)
        data = []
        for segment in elffile.iter_segments():
            offset = segment['p_offset']
            v_addr = segment['p_vaddr']
            filesz = segment['p_filesz']
            memsz  = segment['p_memsz']
            flags  = segment['p_flags']
            if segment['p_type'] != 'PT_LOAD':
                continue
            print offset,v_addr,filesz,memsz,flags
            data.append(elf_data[offset:offset + filesz] + '\x00'*(memsz-filesz))
        data = ''.join(data)

        entry_point = elffile.header['e_entry']
        symbols = [c for c in get_symbols(elffile)]
    if boot:
        with open('build/boot.o','rb') as f:
            elf = ELFFile(f)
            boot_symbols = [c for c in get_symbols(elf)]
            symbols = boot_symbols + symbols

    symbols.sort( lambda x,y: cmp(x[0], y[0]) )
            
    #get rid of any "bx lr"s
    #for cond in xrange(16):
    #    for reg in xrange(15):
    #        data = data.replace(struct.pack('<I',(cond << 28) +  0x12fff10 + reg),struct.pack('<I',(cond << 28) + 0x1a0f000 + reg))
    data = data.replace(struct.pack('<I', 0xe12fff1e), struct.pack('<I', 0xe1a0f00e))
    #We'll stick the symbols on the end
    symbols = ''.join(struct.pack('>I',value) + name + '\00' for (value,name) in symbols)

    if boot:
        header = load(header)
        header = header.replace(struct.pack('<I',0xcafebabe),struct.pack('<I',entry_point))
        assert len(header) < 0x1000
        header = header + '\x00'*(0x1000 - len(header))
        entry_point = None
    else:
        header = ''
    return to_synapse_format(header+data, symbols, entry_point)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("header")
    parser.add_argument("binary")
    parser.add_argument("--boot", "-b", help="prepare boot rom", action="store_true")
    parser.add_argument("-o", "--output", help="output filename", required=True)
    args = parser.parse_args()
    binary = create_binary(args.header, args.binary, boot=args.boot)
    left = len(binary)&3
    if left:
        binary += (4 - left)*'\x00'

    with open(args.output,'wb') as f:
        f.write(binary)
