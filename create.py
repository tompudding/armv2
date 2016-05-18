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
            if symbol['st_size'] == 0 or symbol['st_value'] == 0:
                continue
            yield symbol['st_value'],symbol.name

        #     version_info = ''
        #     # readelf doesn't display version info for Solaris versioning
        #     if (section['sh_type'] == 'SHT_DYNSYM' and
        #             self._versioninfo['type'] == 'GNU'):
        #         version = self._symbol_version(nsym)
        #         if (version['name'] != symbol.name and

def create_binary(header, elf, boot=False):
    header = load(header)
    elf_data = load(elf)
    with open(elf,'rb') as f:
        elffile = ELFFile(f)
        for segment in elffile.iter_segments():
            offset = segment['p_offset']
            v_addr = segment['p_vaddr']
            filesz = segment['p_filesz']
            memsz  = segment['p_memsz']
            print offset,v_addr,filesz,memsz
            data = elf_data[offset:offset + filesz]
            data += '\x00'*(memsz-filesz)

        entry_point = elffile.header['e_entry']
        symbols = [c for c in get_symbols(elffile)]
    #get rid of any "bx lr"s
    data = data.replace(struct.pack('<I',0xe12fff1e),struct.pack('<I',0xe1a0f00e))
    header = header.replace(struct.pack('<I',0xcafebabe),struct.pack('<I',entry_point))
    #We'll stick the symbols on the end
    symbols = ''.join(struct.pack('<I',value) + name + '\00' for (value,name) in symbols)

    if boot:
        assert len(header) < 0x8000
        header = header + '\x00'*(0x8000 - len(header))
    else:
        header = header.replace(struct.pack('<I',0x41414141),struct.pack('<I',len(data)))
    return header + data + symbols + struct.pack('<I',len(symbols))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("header")
    parser.add_argument("binary")
    parser.add_argument("--boot", "-b", help="prepare boot rom", action="store_true")
    parser.add_argument("-o", "--output", help="output filename", required=True)
    args = parser.parse_args()
    binary = create_binary(args.header, args.binary, boot=args.boot)

    with open(args.output,'wb') as f:
        f.write(binary)
