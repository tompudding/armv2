import socket
import threading
import socketserver
import time
import select
import struct
import bisect
from . import comms

class Error(Exception):
    pass


class Types(comms.Types):
    STOP            = comms.Types.MAX +  0
    RESUME          = comms.Types.MAX +  1
    STEP            = comms.Types.MAX +  2
    RESTART         = comms.Types.MAX +  3
    SETBKPT         = comms.Types.MAX +  4
    UNSETBKPT       = comms.Types.MAX +  5
    MEMDATA         = comms.Types.MAX +  6
    MEMWATCH        = comms.Types.MAX +  7
    UNWATCH         = comms.Types.MAX +  8
    STATE           = comms.Types.MAX +  9
    DISASSEMBLY     = comms.Types.MAX + 10
    DISASSEMBLYDATA = comms.Types.MAX + 11
    TAPEREQUEST     = comms.Types.MAX + 12
    TAPE_LIST       = comms.Types.MAX + 13
    TAPE_LOAD       = comms.Types.MAX + 14
    TAPE_UNLOAD     = comms.Types.MAX + 15
    SYMBOL_DATA     = comms.Types.MAX + 16
    NEXT            = comms.Types.MAX + 17


class DynamicObject(object):
    pass


class Message(object):
    type = Types.UNKNOWN

    def to_binary(self):
        return struct.pack('>I', self.type)


class Handshake(Message):
    type = Types.CONNECT

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def to_binary(self):
        first = super(Handshake, self).to_binary()
        last = struct.pack('>H', self.port) + self.host.encode('ascii')
        return first + last

    @staticmethod
    def from_binary(data):
        port = struct.unpack('>H', data[:2])[0]
        host = data[2:].decode('ascii')
        return Handshake(host, port)


class MachineState(Message):
    type = Types.STATE

    def __init__(self, regs, mode, pc, is_waiting):
        self.registers = [regs[i] for i in range(16)]
        self.mode = mode
        self.pc = pc
        self.is_waiting = is_waiting

    def to_binary(self):
        first = super(MachineState, self).to_binary()
        regs = b''.join(struct.pack('>I', reg) for reg in self.registers)
        mode = struct.pack('>I', self.mode)
        pc = struct.pack('>I', self.pc)
        is_waiting = b'1' if self.is_waiting else b'\x00'
        return first + regs + mode + pc + is_waiting

    @staticmethod
    def from_binary(data):
        regs = [struct.unpack('>I', data[i * 4:(i + 1) * 4])[0] for i in range(16)]
        mode, pc = struct.unpack('>II', data[16 * 4:16 * 4 + 8])
        is_waiting = True if data[16 * 4 + 8] == '1' else False
        return MachineState(regs, mode, pc, is_waiting)


class MemView(Message):
    type = Types.MEMWATCH

    class Types:
        MEMDUMP     = 0
        DISASSEMBLY = 1
        TAPES       = 2

    def __init__(self, id, start, size, watch_start=0, watch_size=0):
        self.id = id
        self.start = start
        self.size = size
        self.watch_start = watch_start
        self.watch_size = watch_size

    def to_binary(self):
        first = super(MemView, self).to_binary()
        data = struct.pack('>IIIII', self.id, self.start, self.size, self.watch_start, self.watch_size)
        return first + data

    @staticmethod
    def from_binary(data):
        id, start, size, watch_start, watch_size = struct.unpack('>IIIII', data)
        return MemView(id, start, size, watch_start, watch_size)


class MemdumpView(MemView):
    id = MemView.Types.MEMDUMP

    def __init__(self, start, size, watch_start=0, watch_size=0):
        super(MemdumpView, self).__init__(self.id, start, size, watch_start, watch_size)


class TapesView(MemView):
    type = Types.TAPEREQUEST
    id = MemView.Types.TAPES

    def __init__(self, start, size, watch_start=0, watch_size=0):
        super(TapesView, self).__init__(self.id, start, size, watch_start, watch_size)

    def to_binary(self):
        first = super(MemView, self).to_binary()
        data = struct.pack('>III', self.id, self.start, self.size)
        return first + data

    @staticmethod
    def from_binary(data):
        id, start, size = struct.unpack('>III', data)
        return TapesView(start, size)


class TapeReply(TapesView):
    type = Types.TAPE_LIST

    def __init__(self, id, start, tape_list, num_tapes):
        super(TapeReply, self).__init__(start, len(tape_list))
        self.tape_list = tape_list
        self.max = num_tapes

    def to_binary(self):
        first = super(TapeReply, self).to_binary()
        return first + struct.pack('>I', self.max) + b'\x00'.join((tape.name.encode('ascii') for tape in self.tape_list))

    @staticmethod
    def from_binary(data):
        id, start, size, num_tapes = struct.unpack('>IIII', data[:16])
        data = data[16:]
        tape_list = [tape.decode('ascii') for tape in data.split(b'\x00')]
        if len(tape_list) != size:
            print('Error tape_list mismatch lengths %d %d' % (len(tape_list), size))
            return None
        return TapeReply(id, start, tape_list, num_tapes)


class MemViewReply(MemView):
    type = Types.MEMDATA

    def __init__(self, id, start, data):
        super(MemViewReply, self).__init__(id, start, len(data))
        self.data = data

    def to_binary(self):
        first = super(MemView, self).to_binary()
        data = struct.pack('>III', self.id, self.start, self.size)
        return first + data + self.data

    @staticmethod
    def from_binary(data):
        id, start, size = struct.unpack('>III', data[:12])
        data = data[12:]
        if len(data) != size:
            print('Error mismatch lengths %d %d' % (len(data), size))
            return None
        return MemViewReply(id, start, data)


class DisassemblyView(MemView):
    type = Types.DISASSEMBLY
    id = MemView.Types.DISASSEMBLY

    def __init__(self, start, size, watch_start=0, watch_size=0):
        # ignore the watch params for this for now
        super(DisassemblyView, self).__init__(self.id, start, size)

    @staticmethod
    def from_binary(data):
        id, start, size, watch_start, watch_size = struct.unpack('>IIIII', data)
        return DisassemblyView(start, size, watch_start, watch_size)


class DisassemblyViewReply(Message):
    type = Types.DISASSEMBLYDATA

    def __init__(self, start, memory, lines):
        self.start  = start
        self.memory = memory
        self.lines  = lines

    def to_binary(self):
        first = super(DisassemblyViewReply, self).to_binary()
        start = struct.pack('>I', self.start)
        mem   = struct.pack('>I', len(self.memory)) + self.memory
        lines = b'\n'.join((line.encode('ascii') for line in self.lines))
        return first + start + mem + lines

    @staticmethod
    def from_binary(data):
        start, mem_length = struct.unpack('>II', data[:8])
        mem = data[8:8 + mem_length]
        if mem_length != len(mem):
            raise Error('Dissasembly length mismatch %d %d' % (mem_length, len(mem)))
        lines = [line.decode('ascii') for line in data[8 + mem_length:].split(b'\n')]
        if len(lines) != mem_length // 4:
            raise Error('Dissasembly num_lines %d should be %d' % (len(lines), mem_length // 4))
        return DisassemblyViewReply(start, mem, lines)


class Symbols(Message):
    type = Types.SYMBOL_DATA

    def __init__(self, symbols_list):
        self.symbols_list = symbols_list
        self.addrs   = [addr for (addr, name) in symbols_list]
        self.lookup  = dict(self.symbols_list)
        self.names = dict(((name, addr) for (addr, name) in symbols_list))

    def to_binary(self):
        first = super(Symbols, self).to_binary()
        data = []
        for addr, name in self.symbols_list:
            data.append(struct.pack('>I', addr) + name.encode('ascii') + b'\x00')
        return first + b''.join(data)

    def get_symbol_and_offset(self, addr):
        index = bisect.bisect_left(self.addrs, addr)
        try:
            sym_addr, sym_name = self.symbols_list[index]
        except IndexError:
            sym_addr, sym_name = self.symbols_list[-1]
            return sym_name, addr - sym_addr

        if addr == sym_addr:
            return sym_name, 0
        elif index > 0:
            # We're pointing at the first symbol after the address we gave, and we want to say the one before that
            sym_addr, sym_name = self.symbols_list[index - 1]
            return sym_name, addr - sym_addr
        else:
            # We're before all the symbols
            return None, addr

    def by_name(self, name):
        return self.names[name]

    def by_index(self, index):
        return self.symbols_list[index]

    def __iter__(self):
        return self.lookup.__iter__()

    def __next__(self):
        return self.lookup.__next__()

    def iteritems(self):
        for item in self.lookup.items():
            yield item

    def items(self):
        return list(self.iteritems())

    def __contains__(self, addr):
        return addr in self.lookup

    def __getitem__(self, addr):
        return self.lookup[addr]

    @staticmethod
    def from_binary(data):
        symbols = []
        while data:
            addr = struct.unpack('>I', data[:4])[0]
            name, data = data[4:].split(b'\x00', 1)
            symbols.append((addr, name.decode('ascii')))
        return Symbols(symbols)


class SetBreakpoint(Message):
    type = Types.SETBKPT

    def __init__(self, addr):
        self.addr = addr

    def to_binary(self):
        first = super(SetBreakpoint, self).to_binary()
        last = struct.pack('>I', self.addr)
        return first + last

    @staticmethod
    def from_binary(data):
        addr = struct.unpack('>I', data[:4])[0]
        return SetBreakpoint(addr)


class UnsetBreakpoint(SetBreakpoint):
    type = Types.UNSETBKPT

    @staticmethod
    def from_binary(data):
        addr = struct.unpack('>I', data[:4])[0]
        return UnsetBreakpoint(addr)


class Disconnect(Message):
    type = Types.DISCONNECT


class Stop(Message):
    type = Types.STOP

    @staticmethod
    def from_binary(data):
        return Stop()


class Resume(Message):
    type = Types.RESUME

    @staticmethod
    def from_binary(data):
        return Resume()


class Restart(Message):
    type = Types.RESTART

    @staticmethod
    def from_binary(data):
        return Restart()


class Step(Message):
    type = Types.STEP

    @staticmethod
    def from_binary(data):
        return Step()


class Next(Message):
    type = Types.NEXT

    @staticmethod
    def from_binary(data):
        return Next()


class TapeLoad(SetBreakpoint):
    type = Types.TAPE_LOAD

    def __init__(self, num):
        self.num = num

    def to_binary(self):
        first = super(SetBreakpoint, self).to_binary()
        last = struct.pack('>I', self.num)
        return first + last

    @staticmethod
    def from_binary(data):
        num = struct.unpack('>I', data[:4])[0]
        return TapeLoad(num)


class TapeUnload(Message):
    type = Types.TAPE_UNLOAD

    @staticmethod
    def from_binary(data):
        return TapeUnload()


messages_by_type = {Types.CONNECT: Handshake,
                    Types.STATE: MachineState,
                    Types.MEMWATCH: MemView,
                    Types.MEMDATA: MemViewReply,
                    Types.SETBKPT: SetBreakpoint,
                    Types.UNSETBKPT: UnsetBreakpoint,
                    Types.DISASSEMBLY: DisassemblyView,
                    Types.DISASSEMBLYDATA: DisassemblyViewReply,
                    Types.STOP: Stop,
                    Types.RESUME: Resume,
                    Types.RESTART: Restart,
                    Types.STEP: Step,
                    Types.TAPEREQUEST: TapesView,
                    Types.TAPE_LIST: TapeReply,
                    Types.TAPE_LOAD: TapeLoad,
                    Types.TAPE_UNLOAD: TapeUnload,
                    Types.SYMBOL_DATA: Symbols,
                    Types.NEXT: Next,
                    }

class Factory(object):

    def message_factory(self, data):
        type = struct.unpack('>I', data[:4])[0]
        try:
            return messages_by_type[type].from_binary(data[4:])
        except KeyError:
            print('Unknown message type %d' % type)
        except Error as e:
            print('Error (%s) while receiving message of type %d' % (e, type))

class Client(Factory, comms.Client):
    def initiate_connection(self):
        try:
            self.connect(self.remote_host, self.remote_port)
            self.start_handshake()
        except socket.error as e:
            self.connected = False
            return

    def start_handshake(self):
        # Send a handshake message with our listen port
        print('Sending a handshake message with', (self.host, self.port))
        handshake = Handshake(self.host, self.port)
        self.send(handshake)
        if self.connected:
            self.callback(handshake)

    def disconnect(self):
        super(Client, self).disconnect()
        self.callback(Disconnect())


class Server(Factory, comms.Server):
    pass
