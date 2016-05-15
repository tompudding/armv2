import os
import sys
import struct
from elftools.elf.elffile import ELFFile

def load(filename):
    with open(filename,'rb') as f:
        return f.read()

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
    #get rid of any "bx lr"s
    data = data.replace(struct.pack('<I',0xe12fff1e),struct.pack('<I',0xe1a0f00e))
    header = header.replace(struct.pack('<I',0xcafebabe),struct.pack('<I',entry_point))

    if boot:
        assert len(header) < 0x8000
        header = header + '\x00'*(0x8000 - len(header))
    else:
        header = header.replace(struct.pack('<I',0x41414141),struct.pack('<I',len(data)))
    return header + data

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
