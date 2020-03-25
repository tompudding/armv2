import os
import sys
import struct
from elftools.elf.sections import SymbolTableSection
from elftools.elf.elffile import ELFFile

class RelTypes:
    R_ARM_ABS32 = 2
    R_ARM_JUMP_SLOT = 0x16

def load(filename):
    with open(filename,'rb') as f:
        return bytearray(f.read())

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

def get_full_symbols(elf):
    out = []
    for section in elf.iter_sections():
        if not isinstance(section, SymbolTableSection):
            continue

        if section['sh_entsize'] == 0:
            continue

        for nsym, symbol in enumerate(section.iter_symbols()):
            out.append((symbol['st_value'],symbol.name))
    return out

def pad(data, alignment):
    target = ((len(data) + (alignment - 1)) // alignment) * alignment
    if target > len(data):
        data += b'\x00'*(target-len(data))
    return data

def addr_to_offset(elf, addr):
    for segment in elf.iter_segments():
        offset = segment['p_offset']
        v_addr = segment['p_vaddr']
        filesz = segment['p_filesz']
        memsz  = segment['p_memsz']
        if segment['p_type'] != 'PT_LOAD':
            continue
        if addr >= v_addr and addr < v_addr + filesz:
            return offset + (addr - v_addr)

def process_relocation(data, elf, section, symbols, symbol_lookup, os_lookup):
    start = section['sh_offset']
    end = start + section['sh_size']
    rel_data = data[start : end]
    undefined = False

    for pos in range(0, end - start, 8):
        offset, info = struct.unpack('<II', rel_data[pos:pos+8])
        #switch for info
        sym = info >> 8
        info = info & 0xff
        offset = addr_to_offset(elf,offset)

        if info == RelTypes.R_ARM_ABS32:
            sym_val = symbols[sym][0]
            if sym_val == 0:
                sym_val = os_lookup[symbols[sym][1]]
            #print 'abs symbols %x %x %d %s val=%x' % (offset, info, sym, symbols[sym], sym_val)
            current = struct.unpack('<I',data[offset:offset+4])[0]
            sym_val += current
            data[offset:offset + 4] = list(struct.pack('<I',sym_val))

        elif info == RelTypes.R_ARM_JUMP_SLOT:
            if symbols[sym][1] in os_lookup:
                val = os_lookup[symbols[sym][1]]
            else:
                val = symbol_lookup[symbols[sym][1]]

            #print 'B %x %x %d %s %x' % (offset, info, sym, symbols[sym], val)
            if val == 0:
                print('Undefined reference to %s' % symbols[sym][1])
                undefined = True
                val = 0xffffffff
            data[offset:offset + 4] = list(struct.pack('<I', val))

    if undefined:
        raise Exception('Unresolved symbols')


def pre_link(data, elf, os_symbols):
    symbols = get_full_symbols(elf)
    os_lookup = { name : value for (value, name) in os_symbols }
    symbol_lookup = { name : value for (value, name) in symbols }
    for section in elf.iter_sections():
        if section['sh_type'] == 'SHT_REL':
            process_relocation(data, elf, section, symbols, symbol_lookup, os_lookup)


    return data, symbol_lookup['main']


def to_synapse_format(data, symbols, name, v_addr, entry_point, final):
    """
We have a very simple format for the synapse binaries:
         Offset   |   Contents
         ---------|-----------
            0     |   Length of data section
            4     |   data section
          4 + len |   Length of symbols
      4 + len + 4 |   symbols
"""
    print(f'a {len(data)}')
    data = pad(data, 4)
    symbols = pad(symbols, 4)
    #Pad the name out to 16 bytes
    name = name[:15]
    name = name + ('\x00'*(16 - len(name)))
    print('Data %d bytes, symbols %d bytes, name %s' % (len(data), len(symbols), name))
    len_flags = len(data) | (0x80000000 if final and entry_point != None else 0)
    out = struct.pack('>I', len_flags) + data + struct.pack('>I', len(symbols)) + symbols

    if entry_point != None:
        out = struct.pack('>I', entry_point) + name.encode('ascii') + struct.pack('>I', v_addr) + out

    return out

def to_tape_format(data_blocks):
    """
    This is a very simple format that wraps up data blocks that should be joined by a pilot sound when put on tape
    """
    out = bytearray()
    for block in data_blocks:
        out.extend(struct.pack('>I', len(block)) + block)
    return out

def create_binary(header, elf, tape_name, boot=False, final=True):
    elf_data = load(elf)
    with open(elf,'rb') as f:
        elffile = ELFFile(f)
        #before we grab the load segment we want to do our weird pre_linking
        symbols = [c for c in get_symbols(elffile)]
        if not boot:
            #we'll also need symbols for the os
            with open('build/os','rb') as os_f:
                os_elf = ELFFile(os_f)
                os_symbols = get_full_symbols(os_elf)

            elf_data,entry_point = pre_link(elf_data, elffile, os_symbols)
        data = []
        for segment in elffile.iter_segments():
            offset = segment['p_offset']
            v_addr = segment['p_vaddr']
            filesz = segment['p_filesz']
            memsz  = segment['p_memsz']
            flags  = segment['p_flags']
            if segment['p_type'] != 'PT_LOAD':
                continue
            print(offset,v_addr,filesz,memsz,flags)
            #Don't add zeroes for the bss section, when it's loaded there'll be zeroes in ram
            #data.append(elf_data[offset:offset + filesz] + '\x00'*(memsz-filesz))
            data.append(elf_data[offset:offset + filesz])
            if not boot:
                #we only take the first segment
                break
        data = b''.join(data)

        if boot:
            entry_point = elffile.header['e_entry']

    if boot:
        with open('build/boot.o','rb') as f:
            elf = ELFFile(f)
            boot_symbols = [c for c in get_symbols(elf)]
            symbols = boot_symbols + symbols
        v_addr = None

    symbols.sort( key=lambda data: data[0] )
    print('entry %x' % entry_point)

    #get rid of any "bx lr"s
    #for cond in xrange(16):
    #    for reg in xrange(15):
    #        data = data.replace(struct.pack('<I',(cond << 28) +  0x12fff10 + reg),struct.pack('<I',(cond << 28) + 0x1a0f000 + reg))
    print('len data',len(data))
    data = data.replace(struct.pack('<I', 0xe12fff1e), struct.pack('<I', 0xe1a0f00e))
    #We'll stick the symbols on the end
    total = 0

    symbols = b''.join(struct.pack('>I',value) + name.encode('ascii') + b'\x00' for (value, name) in symbols)
    print(f'symbols len {len(symbols)}')
    print(f'data len {len(data)}')

    if boot:
        header = load(header)
        header = header.replace(struct.pack('<I',0xcafebabe),struct.pack('<I',entry_point))
        assert len(header) < 0x1000
        header = header + b'\x00'*(0x1000 - len(header))
        print(f'header_len {len(header)}')
        entry_point = None
    else:
        header = bytearray(b'')
    return to_synapse_format(header+data, symbols, tape_name, v_addr, entry_point, final)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("header")
    parser.add_argument("binary")
    parser.add_argument("--boot", "-b", help="prepare boot rom", action="store_true")
    parser.add_argument("-o", "--output", help="output filename", required=True)
    parser.add_argument("-n", "--name", help="tape name", default=None)
    args = parser.parse_args()

    if args.name is None:
        args.name = os.path.basename(args.output)
        args.name = os.path.splitext(args.name)[0]

    args.name = args.name[:15]

    binary = create_binary(args.header, args.binary, args.name, boot=args.boot)

    if not args.boot:
        blocks = [binary]
        loading_name = os.path.splitext(args.binary)[0] + '_loading.so'
        if os.path.exists(loading_name):
            blocks.insert(0,create_binary(args.header, loading_name, args.name + ' loader', boot=args.boot, final=False))
        #If we're making a tape wrap it up in the tape format
        binary = to_tape_format(blocks)

    with open(args.output,'wb') as f:
        f.write(binary)
