import socket
import threading
import socketserver
import time
import select
import struct
import bisect
import signal
import enum
from . import comms

class Error(Exception):
    pass


class Types(enum.Enum):
    ENABLE_EXTENDED = '!'
    HALTED_REASON   = '?'
    ARGV            = 'A'
    BACK_CONTINUE   = 'bc'
    BACK_SINGLESTEP = 'bs'
    CONTINUE        = 'c'
    CONTINUE_SIGNAL = 'C'
    DETACH          = 'D'
    FILE            = 'F'
    READ_REGISTERS  = 'g'
    WRITE_REGISTERS = 'G'
    SET_THREAD      = 'H'
    STEP_CYCLE      = 'i'
    SIGNAL_CYCLE    = 'I'
    KILL            = 'k'
    READ_MEM        = 'm'
    WRITE_MEM       = 'M'
    READ_REGISTER   = 'p'
    WRITE_REGISTER  = 'P'
    QUERY           = 'q'
    SET             = 'Q'
    RESTART_SYSTEM  = 'r'
    RESTART         = 'R'
    STEP            = 's'
    STEP_SIGNAL     = 'S'
    BACK_SEARCH     = 't'
    THREAD_QUERY    = 'T'
    ATTACH          = 'vAttach'
    CONTINUE_ACTION = 'vCont?'
    CTRL_C          = 'vCtrlC'
    FILE_OPERATION  = 'vFile'
    FLASH_ERASE     = 'vFlashErase'
    FLASH_WRITE     = 'vFlashWrite'
    FLASH_DONE      = 'vFlashDone'
    VKILL           = 'vKill'
    RUN             = 'vRun'
    STOP_NOTIF      = 'vStopped'
    WRITE_MEM_BIN   = 'X'
    ADD_BREAKPOINT  = 'z'
    DEL_BREAKPOINT  = 'Z'
    ADD_SOFT_BP     = 'z0'
    DEL_SOFT_BP     = 'Z0'
    ADD_HARD_BP     = 'z1'
    DEL_HARD_BP     = 'Z1'
    ADD_WRITE_WP    = 'z2'
    DEL_WRITE_WP    = 'Z2'
    ADD_READ_WP     = 'z3'
    DEL_READ_WP     = 'Z3'
    ADD_ACCESS_WP   = 'z4'
    DEL_ACCESS_WP   = 'Z4'
    UNKNOWN         = '\x00'
    STOP            = '\x03'



def checksum(bytes):
    checksum = 0

    for byte in bytes:
        checksum = (checksum + byte) & 0xff

    return checksum

def format_gdb_message(bytes):
    return b'$' + bytes + b'#' + f'{checksum(bytes):02x}'.encode('ascii')

def byte_swap(n):
    return ((n & 0xff) << 24) | ((n & 0xff00) << 8) | ((n & 0xff0000) >> 8) | ((n & 0xff000000) >> 24)

class Message(object):
    type = Types.UNKNOWN

    def __init__(self, data):
        self.data = data

    def to_binary(self):
        return struct.pack('>I', self.type)

class EmptyMessage(Message):
    def __init__(self):
        pass

class Stop(EmptyMessage):
    type = Types.STOP

class OK(Message):
    def to_binary(self):
        return format_gdb_message(b'OK')


class StopReply(Message):
    def __init__(self, data=None):
        if data is None:
            data = signal.SIGINT

        self.signal = int(data)

    def to_binary(self):
        return format_gdb_message(b'S%02x' % self.signal)


class GetRegisters(Message):
    type = Types.READ_REGISTERS
    def to_binary(self):
        return format_gdb_message(b'g')


class SetRegisters(Message):
    type = Types.WRITE_REGISTERS

    def __init__(self, data):
        words = [byte_swap(int(data[i:i+8],16)) for i in range(1, len(data), 8)]
        self.regs = words[:15]
        self.pc = words[15]
        self.fps = words[24]
        self.cpsr = words[25]

    def to_binary(self):
        return format_gdb_message(b'g')


class OK(EmptyMessage):

    def to_binary(self):
        return format_gdb_message(b'OK')


class GetRegister(Message):
    type = Types.READ_REGISTER

    def __init__(self, data):
        self.register = int(data[1:],16)

    def to_binary(self):
        return format_gdb_message(b'g')

class Continue(Message):
    type = Types.CONTINUE

    def __init__(self, data):
        try:
            self.addr = int(data[1:],16)
        except ValueError:
            self.addr = None

class ContinueSignal(Message):
    type = Types.CONTINUE_SIGNAL

    def __init__(self, data):
        data = data[1:]
        if b';' in data:
            signal, addr = data.split(b';')
        else:
            addr = None

        self.signal = int(signal,16)
        self.addr = None if addr is None else int(addr,16)


class SetRegister(Message):
    type = Types.WRITE_REGISTER

    def __init__(self, data):
        data = data[1:]
        reg, value = data.split(b'=')
        self.register = int(reg,16)
        self.value = byte_swap(int(value, 16))

    def to_binary(self):
        return format_gdb_message(b'g')


class Step(Message):
    type = Types.STEP

    def __init__(self, data):
        try:
            self.addr = int(data[1:],16)
        except ValueError:
            self.addr = None

    def to_binary(self):
        return format_gdb_message(b'g')


class ReadMemory(Message):

    type = Types.READ_MEM
    def __init__(self, data):
        self.start, self.length = (int(v,16) for v in data[1:].split(b','))
        self.end = self.start + self.length

    def to_binary(self):
        return format_gdb_message(b'g')

class RegisterValues(Message):
    type = Types.UNKNOWN

    def __init__(self, regs, mode, pc):
        #There are 8 floating point registers gdb expects, and they're 12 bytes! Then an "fps" register
        self.registers = [regs[i] for i in range(15)] + [pc,0,mode]

    def to_binary(self):
        regs = ''.join((f'{byte_swap(reg):08x}' for reg in self.registers)).encode('ascii')
        return format_gdb_message(regs)

class RegisterValue(RegisterValues):
    def __init__(self, register):
        self.registers = [register]

class Memory(Message):
    type = Types.UNKNOWN

    def to_binary(self):
        data = ''.join((f'{byte:02x}' for byte in self.data)).encode('ascii')
        return format_gdb_message(data)

messages_by_type = {}

def format_type(t):
    return t.value.encode('ascii')[0]

def instantiate(cls):
    def do_instantiate(data):
        return cls(data)

    return do_instantiate

class BaseHandler(object):
    select_timeout = 0.5
    total_timeout = 1.0
    escape = ord('}')
    acks = set(v for v in b'+-')
    ack = b'+'
    bad_ack = b'-'
    ignored_but_ok = set(v for v in b'H?')

    def __init__(self, *args, **kwargs):
        self.handlers = {
            format_type(Types.QUERY)           : self.handle_query,
            format_type(Types.READ_REGISTERS)  : instantiate(GetRegisters),
            format_type(Types.WRITE_REGISTERS) : instantiate(SetRegisters),
            format_type(Types.READ_MEM)        : instantiate(ReadMemory),
            format_type(Types.READ_REGISTER)   : instantiate(GetRegister),
            format_type(Types.WRITE_REGISTER)  : instantiate(SetRegister),
            ord('v')                           : self.handle_extended,
            format_type(Types.STEP)            : instantiate(Step),
            format_type(Types.DETACH)          : self.detach,
            format_type(Types.CONTINUE)        : instantiate(Continue),
            format_type(Types.CONTINUE_SIGNAL) : instantiate(ContinueSignal),
        }
        for byte in self.ignored_but_ok:
            self.handlers[byte] = self.handle_ignored
        self.done = False
        super().__init__(*args, **kwargs)

    def read_message(self):
        ready = select.select([self.request], [], [], self.select_timeout)
        if ready[0]:
            new_data = self.request.recv(1024)
            if not new_data:
                raise socket.error()
            self.process_data(new_data)

    def process_data(self, data):
        self.data = self.data + data
        #GDB packets start with a dollar and end with a hash followed by two bytes of checksum
        #We can split based on un-escaped dollars
        messages = []
        message = bytearray()
        pos = 0
        print('data',self.data)
        while pos < len(self.data):
            byte = self.data[pos]
            #+ and - bytes are allowed between messages, they are acknowledgements that we can ignore
            if byte in self.acks and len(message) == 0:
                #ignore!
                pos += 1
                continue
            if byte == ord('$') and len(message) > 0 and self.data[pos - 1] != self.escape:
                messages.append(message)
                message = bytearray()
                pos += 1
                continue
            #It wasn't the first byte, maybe it's a hash at the end?
            if byte == ord('#') and pos > 0 and self.data[pos-1] != self.escape and pos < len(self.data) - 2:
                messages.append(message + self.data[pos:pos+3])
                message = []
                pos += 3
            else:
                message.append(byte)

            pos += 1

        if message == b'\x03':
            #They asked for an interruption. It doesn't have the same format as anything else of course
            messages.append(message)
        print(message)
        print(messages)
        self.data = self.data[pos:]

        for message in messages:
            print(f'{message=}')
            self.request.send(self.ack)
            if message:
                m = self.message_factory(message)
                if m:
                    self.server.comms.handle(m)

    def handle(self):
        try:
            print('Handling message!')
            self.data = b''
            self.needed = None
            self.server.comms.set_connected(self.request)
            while not self.server.comms.done and not self.done:
                self.read_message()
            print('done')
            self.request.close()
        except socket.error as e:
            print('Got socket error')
            self.server.comms.disconnect()

    def detach(self, data):
        self.request.send(format_gdb_message(b'OK'))
        print('Detach!')
        self.done = True

    def handle_query(self, data):
        print('handle query')
        if data.startswith(b'qSupported'):
            #It wants to know what we support
            m = format_gdb_message(b'qSupported:swbreak+;hwbreak+;PacketSize=1024')
            print('clonk',m)
            #self.request.send(b'+')
            self.request.send(m)
        elif data == b'qC':
            self.request.send(format_gdb_message(b''))
        else:
            print('Unknown message',data)

    def handle_extended(self, data):
        if data.startswith(b'vCont?'):
            self.request.send(format_gdb_message(b''))


    def handle_get_reg(self, data):
        return GetRegisters()

    def handle_ignored(self, data):
        print('Handle ignored')
        self.request.send(format_gdb_message(b'OK'))

    def message_factory(self, data):
        #First we need to check the checksum
        if data == b'\x03':
            #Special interrupt message
            return Stop()
        csum = checksum(data[1:-3])
        message_csum = int(data[-2:],16)
        if data[0] != ord('$') or csum != message_csum:
            print('Checksum mismatch {csum=} {message_csum=}')
            self.request.send(self.bad_ack)
            return

        data = data[1:-3]

        try:
            handler = self.handlers[data[0]]
        except KeyError:
            #send some sort of error?
            print('No jim',self.handlers,data[0])
            return

        return handler(data)


        #type = struct.unpack('>I', data[:4])[0]
        #try:
        #    return messages_by_type[type].from_binary(data[4:])
        #except KeyError:
        #    print('Unknown message type %d' % type)
        #except Error as e:
        #    print('Error (%s) while receiving message of type %d' % (e, type))
        return None


class Client(comms.Client):
    factory_class = BaseHandler
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


class Server(comms.Server):
    factory_class = BaseHandler
    def handle(self, message):
        super(Server, self).handle(message)
