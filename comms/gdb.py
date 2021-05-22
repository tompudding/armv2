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
    ENABLE_EXTENDED = "!"
    HALTED_REASON = "?"
    ARGV = "A"
    BACK_CONTINUE = "bc"
    BACK_SINGLESTEP = "bs"
    CONTINUE = "c"
    CONTINUE_SIGNAL = "C"
    DETACH = "D"
    FILE = "F"
    READ_REGISTERS = "g"
    WRITE_REGISTERS = "G"
    SET_THREAD = "H"
    STEP_CYCLE = "i"
    SIGNAL_CYCLE = "I"
    KILL = "k"
    READ_MEM = "m"
    WRITE_MEM = "M"
    READ_REGISTER = "p"
    WRITE_REGISTER = "P"
    QUERY = "q"
    SET = "Q"
    RESTART_SYSTEM = "r"
    RESTART = "R"
    STEP = "s"
    STEP_SIGNAL = "S"
    BACK_SEARCH = "t"
    THREAD_QUERY = "T"
    ATTACH = "vAttach"
    CONTINUE_ACTION = "vCont?"
    CTRL_C = "vCtrlC"
    FILE_OPERATION = "vFile"
    FILE_OPEN = "vFile:open"
    FILE_CLOSE = "vFile:close"
    FILE_FSTAT = "vFile:fstat"
    FILE_PREAD = "vFile:pread"
    FLASH_ERASE = "vFlashErase"
    FLASH_WRITE = "vFlashWrite"
    FLASH_DONE = "vFlashDone"
    VKILL = "vKill"
    RUN = "vRun"
    STOP_NOTIF = "vStopped"
    WRITE_MEM_BIN = "X"
    ADD_BREAKPOINT = "z"
    DEL_BREAKPOINT = "Z"
    ADD_SOFT_BP = "z0"
    DEL_SOFT_BP = "Z0"
    ADD_HARD_BP = "z1"
    DEL_HARD_BP = "Z1"
    ADD_WRITE_WP = "z2"
    DEL_WRITE_WP = "Z2"
    ADD_READ_WP = "z3"
    DEL_READ_WP = "Z3"
    ADD_ACCESS_WP = "z4"
    DEL_ACCESS_WP = "Z4"
    UNKNOWN = "\x00"
    STOP = "\x03"
    # Special internal types
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNTED"


def checksum(bytes):
    checksum = 0

    for byte in bytes:
        checksum = (checksum + byte) & 0xFF

    return checksum


def format_gdb_message(bytes):
    return b"$" + bytes + b"#" + f"{checksum(bytes):02x}".encode("ascii")


def byte_swap(n):
    return ((n & 0xFF) << 24) | ((n & 0xFF00) << 8) | ((n & 0xFF0000) >> 8) | ((n & 0xFF000000) >> 24)


escaped = bytearray([c ^ 0x20 for c in b"#$}"])


def unescape(data):
    out = bytearray()
    pos = 0
    while pos < len(data):
        if data[pos] == BaseHandler.escape and pos + 1 < len(data) and (data[pos + 1] ^ 0x20) in b"#$}":
            out.append(data[pos + 1] ^ 0x20)
            pos += 2
        else:
            out.append(data[pos])
            pos += 1
    return bytes(out)


def escape(data):
    out = bytearray()
    pos = 0
    for byte in data:
        if byte in b"#$}*":
            out.append(BaseHandler.escape)
            byte ^= 0x20
        out.append(byte)

    return bytes(out)


class Message(object):
    type = Types.UNKNOWN

    def __init__(self, data):
        self.data = data

    def to_binary(self):
        return struct.pack(">I", self.type)


class EmptyMessage(Message):
    def __init__(self):
        pass

    def to_binary(self):
        return format_gdb_message(b"")


class Stop(Message):
    type = Types.STOP


class Detach(Message):
    type = Types.DETACH


class Connect(EmptyMessage):
    type = Types.CONNECTED


class Disconnect(EmptyMessage):
    type = Types.DISCONNECTED


class StopReply(Message):
    def __init__(self, data=None):
        if data is None:
            data = signal.SIGINT

        self.signal = int(data)

    def to_binary(self):
        return format_gdb_message(b"S%02x" % self.signal)


class SWBreakReply(Message):
    def __init__(self):
        self.signal = int(signal.SIGTRAP)

    def to_binary(self):
        return format_gdb_message(b"T%02x swbreak:;" % self.signal)


class OpenFile(Message):
    type = Types.FILE_OPEN

    def to_binary(self):
        return format_gdb_message(b"g")


class CloseFile(Message):
    type = Types.FILE_CLOSE

    def __init__(self, message):
        self.fd = int(message)


class FstatFile(Message):
    type = Types.FILE_FSTAT

    def __init__(self, message):
        self.fd = int(message)


class PreadFile(Message):
    type = Types.FILE_PREAD

    def __init__(self, message):
        fd, count, offset = (int(v, 16) for v in message.split(b","))
        self.fd = fd
        self.count = count
        self.offset = offset


class FileResponse(Message):
    type = Types.FILE_OPEN

    def __init__(self, result):
        self.result = result

    def to_binary(self):
        return format_gdb_message(b"F%d" % self.result)


class FstatResponse(Message):
    # Something about this doesn't actually work; it's requested 3 times and then ignored, perhaps I'll come
    # back to it
    type = Types.FILE_FSTAT

    def __init__(self, length):
        self.length = length

    def stat_format(self):
        out = bytearray()

        # unsigned int  st_dev;      /* device */
        # unsigned int  st_ino;      /* inode */
        out.extend(struct.pack(">II", 0, 0))

        # mode_t        st_mode;     /* protection */
        out.extend(struct.pack(">I", 0xE0))

        # unsigned int  st_nlink;    /* number of hard links */
        # unsigned int  st_uid;      /* user ID of owner */
        # unsigned int  st_gid;      /* group ID of owner */
        # unsigned int  st_rdev;     /* device type (if inode device) */
        out.extend(struct.pack(">IIII", 0, 0, 0, 0))

        # unsigned long st_size;     /* total size, in bytes */
        out.extend(struct.pack(">Q", self.length))

        # unsigned long st_blksize;  /* blocksize for filesystem I/O */
        # unsigned long st_blocks;   /* number of blocks allocated */
        out.extend(struct.pack(">QQ", 1, self.length))
        # time_t        st_atime;    /* time of last access */
        # time_t        st_mtime;    /* time of last modification */
        # time_t        st_ctime;    /* time of last change */
        out.extend(struct.pack(">III", 0, 0, 0))
        return bytes(out)

    def to_binary(self):
        data = self.stat_format()
        message = b"F%x;" % len(data)

        return format_gdb_message(message + escape(data))


class PreadResponse(Message):
    type = Types.FILE_PREAD

    def __init__(self, chunk):
        self.chunk = chunk

    def to_binary(self):
        message = b"F%x;" % len(self.chunk)

        return format_gdb_message(message + escape(self.chunk))


class GetRegisters(Message):
    type = Types.READ_REGISTERS

    def to_binary(self):
        return format_gdb_message(b"g")


class SetRegisters(Message):
    type = Types.WRITE_REGISTERS

    def __init__(self, data):
        words = [byte_swap(int(data[i : i + 8], 16)) for i in range(1, len(data), 8)]
        self.regs = words[:15]
        self.pc = words[15]
        self.fps = words[24]
        self.cpsr = words[25]

    def to_binary(self):
        return format_gdb_message(b"g")


class OK(EmptyMessage):
    def to_binary(self):
        return format_gdb_message(b"OK")


class GetRegister(Message):
    type = Types.READ_REGISTER

    def __init__(self, data):
        self.register = int(data[1:], 16)

    def to_binary(self):
        return format_gdb_message(b"g")


class Continue(Message):
    type = Types.CONTINUE

    def __init__(self, data):
        try:
            self.addr = int(data[1:], 16)
        except ValueError:
            self.addr = None


class ContinueSignal(Message):
    type = Types.CONTINUE_SIGNAL

    def __init__(self, data):
        data = data[1:]
        if b";" in data:
            signal, addr = data.split(b";")
        else:
            addr = None

        self.signal = int(signal, 16)
        self.addr = None if addr is None else int(addr, 16)


class SetRegister(Message):
    type = Types.WRITE_REGISTER

    def __init__(self, data):
        data = data[1:]
        reg, value = data.split(b"=")
        self.register = int(reg, 16)
        self.value = byte_swap(int(value, 16))

    def to_binary(self):
        return format_gdb_message(b"g")


class Step(Message):
    type = Types.STEP

    def __init__(self, data):
        try:
            self.addr = int(data[1:], 16)
        except ValueError:
            self.addr = None

    def to_binary(self):
        return format_gdb_message(b"g")


class ReadMemory(Message):

    type = Types.READ_MEM

    def __init__(self, data):
        self.start, self.length = (int(v, 16) for v in data[1:].split(b","))
        self.end = self.start + self.length

    def to_binary(self):
        return format_gdb_message(b"g")


class WriteMemory(Message):
    type = Types.WRITE_MEM

    def __init__(self, data):
        data = data[1:]
        params, data = data.split(b":")
        self.start, self.length = (int(v, 16) for v in params.split(b","))
        self.end = self.start + self.length
        self.data = [int(data[i : i + 2], 16) for i in range(0, len(data), 2)]
        print(f"YOYO {self.start=:x} {self.end=:x} {len(self.data)=:x}")


class WriteMemoryBinary(Message):
    type = Types.WRITE_MEM

    def __init__(self, data):
        data = data[1:]
        params, data = data.split(b":")
        self.start, self.length = (int(v, 16) for v in params.split(b","))
        self.end = self.start + self.length
        self.data = unescape(data)
        print(f"POGO {self.start=:x} {self.end=:x} {len(self.data)=:x}")


class RegisterValues(Message):
    type = Types.UNKNOWN

    def __init__(self, regs, mode, pc):
        # There are 8 floating point registers gdb expects, and they're 12 bytes! Then an "fps" register
        self.regs = [regs[i] for i in range(15)] + [pc]
        self.fp_regs = [0 for i in range(8)]
        self.final_regs = [0, mode]

    def to_binary(self):
        regs = "".join((f"{byte_swap(reg):08x}" for reg in self.regs))
        fp_regs = "".join((f"{byte_swap(reg):024x}" for reg in self.fp_regs))
        final_regs = "".join((f"{byte_swap(reg):08x}" for reg in self.final_regs))
        return format_gdb_message((regs + fp_regs + final_regs).encode("ascii"))


class RegisterValue(RegisterValues):
    def __init__(self, register):
        self.registers = [register]


class Memory(Message):
    type = Types.UNKNOWN

    def to_binary(self):
        data = "".join((f"{byte:02x}" for byte in self.data)).encode("ascii")
        return format_gdb_message(data)


class SetBreakpoint(Message):
    type = Types.ADD_HARD_BP

    def __init__(self, data):
        data = data[3:]
        addr, kind = data.split(b";")[0].split(b",")
        self.addr = int(addr, 16)
        # ignore kind, we only have one type


class UnsetBreakpoint(Message):
    type = Types.DEL_HARD_BP

    def __init__(self, data):
        data = data[3:]
        addr, kind = data.split(b";")[0].split(b",")
        self.addr = int(addr, 16)
        # ignore kind, we only have one type


class SetWriteWatchpoint(SetBreakpoint):
    type = Types.ADD_WRITE_WP


class SetReadWatchpoint(SetBreakpoint):
    type = Types.ADD_READ_WP


class SetAccessWatchpoint(SetBreakpoint):
    type = Types.ADD_ACCESS_WP


class UnsetWriteWatchpoint(SetBreakpoint):
    type = Types.DEL_WRITE_WP


class UnsetReadWatchpoint(SetBreakpoint):
    type = Types.DEL_READ_WP


class UnsetAccessWatchpoint(SetBreakpoint):
    type = Types.DEL_ACCESS_WP


def format_type(t):
    return t.value.encode("ascii")[0]


def instantiate(cls):
    def do_instantiate(data):
        return cls(data)

    return do_instantiate


class BaseHandler(object):
    select_timeout = 0.5
    total_timeout = 1.0
    escape = ord("}")
    acks = set(v for v in b"+-")
    ack = b"+"
    bad_ack = b"-"
    ignored_but_ok = set(v for v in b"H")

    def __init__(self, *args, **kwargs):
        self.handlers = {
            format_type(Types.QUERY): self.handle_query,
            format_type(Types.READ_REGISTERS): instantiate(GetRegisters),
            format_type(Types.WRITE_REGISTERS): instantiate(SetRegisters),
            format_type(Types.READ_MEM): instantiate(ReadMemory),
            format_type(Types.WRITE_MEM): instantiate(WriteMemory),
            format_type(Types.WRITE_MEM_BIN): instantiate(WriteMemoryBinary),
            format_type(Types.READ_REGISTER): instantiate(GetRegister),
            format_type(Types.WRITE_REGISTER): instantiate(SetRegister),
            ord("v"): self.handle_extended,
            format_type(Types.STEP): instantiate(Step),
            format_type(Types.DETACH): self.detach,
            format_type(Types.CONTINUE): instantiate(Continue),
            format_type(Types.CONTINUE_SIGNAL): instantiate(ContinueSignal),
            ord("z"): self.handle_unset_breakpoints,
            ord("Z"): self.handle_set_breakpoints,
            format_type(Types.HALTED_REASON): instantiate(Stop),
        }
        self.files = {}
        for byte in self.ignored_but_ok:
            self.handlers[byte] = self.handle_ignored

        self.bp_messages = {
            ord("0"): (SetBreakpoint, UnsetBreakpoint),
            ord("1"): (SetBreakpoint, UnsetBreakpoint),
            ord("2"): (SetWriteWatchpoint, UnsetWriteWatchpoint),
            ord("3"): (SetReadWatchpoint, UnsetReadWatchpoint),
            ord("4"): (SetAccessWatchpoint, UnsetAccessWatchpoint),
        }
        self.done = False
        super().__init__(*args, **kwargs)

    def read_message(self):
        try:
            ready = select.select([self.request], [], [], self.select_timeout)
        except ValueError:
            # We get this if the request has been closed and self.request is set to -1
            self.done = True
            return
        if ready[0]:
            new_data = self.request.recv(1024)
            if not new_data:
                raise socket.error()
            self.process_data(new_data)

    def process_data(self, data):
        self.data = self.data + data
        # GDB packets start with a dollar and end with a hash followed by two bytes of checksum
        # We can split based on un-escaped dollars
        messages = []
        message = bytearray()
        pos = 0
        print("data", self.data)
        while pos < len(self.data):
            byte = self.data[pos]
            # + and - bytes are allowed between messages, they are acknowledgements that we can ignore
            if byte in self.acks and len(message) == 0:
                # ignore!
                pos += 1
                continue
            if byte == ord("$") and len(message) > 0 and self.data[pos - 1] != self.escape:
                messages.append(message)
                message = bytearray()
                pos += 1
                continue
            # It wasn't the first byte, maybe it's a hash at the end?
            if (
                byte == ord("#")
                and pos > 0
                and self.data[pos - 1] != self.escape
                and pos < len(self.data) - 2
            ):
                messages.append(message + self.data[pos : pos + 3])
                message = []
                pos += 3
            else:
                message.append(byte)

            pos += 1

        if message == b"\x03":
            # They asked for an interruption. It doesn't have the same format as anything else of course
            messages.append(message)
        print(message)
        print(messages)
        self.data = self.data[pos:]

        for message in messages:
            print(f"{message=}")
            self.reply(self.ack)
            if message:
                m = self.message_factory(message)
                if m:
                    self.server.comms.handle(m)

    def handle(self):
        try:
            print("Handling message!")
            self.data = b""
            self.needed = None
            self.server.comms.set_connected(self.request)
            self.server.comms.handle(Connect())
            while not self.server.comms.done and not self.done:
                self.read_message()
            self.request.close()
        except socket.error as e:
            print("Got socket error")
            # self.server.comms.disconnect()

        # Whatever happens, if the machine is stopped when we disconnect, we need to resume it and clear any
        # breakpoints and stuff

        self.done = True
        self.server.comms.handle(Disconnect())
        self.server.comms.disconnect()

    def reply(self, message):
        print("Sending reply", message)
        self.request.send(message)

    def detach(self, data):
        self.done = True
        return Detach(data)

    def handle_query(self, data):
        print("handle query")
        if data.startswith(b"qSupported:"):
            features = [f.rstrip(b"+") for f in data.split(b"qSupported:")[1].split(b";")]
            reply_features = []
            for feature in features:
                supported = feature in [b"swbreak", b"hwbreak", b"vContSupported"]
                reply_features.append(feature + (b"+" if supported else b"-"))

            message = b";".join(reply_features) + b";PacketSize=1000"
            # It wants to know what we support
            m = format_gdb_message(b"qSupported:" + message)
            self.reply(m)
        elif data == b"qC":
            self.reply(format_gdb_message(b"QC1"))
        elif data == b"qfThreadInfo":
            self.reply(format_gdb_message(b"m1"))
        elif data == b"qsThreadInfo":
            self.reply(format_gdb_message(b"l"))
        elif data == b"qAttached":
            self.reply(format_gdb_message(b"1"))
        elif data == b"qSymbol::":
            self.reply(format_gdb_message(b"OK"))
        # elif data == b'qTStatus':
        #    self.reply(format_gdb_message(b'T0'))
        else:
            print("Unknown message", data)
            self.reply(format_gdb_message(b""))

    def handle_file(self, data):
        # This is used to give gdb a copy of the symbols: If they put "file target:/whatever" then gdb will
        # request "whatever" from us, and we can reply with a constructed elf with all the symbols in. There's
        # no such thing as multiple programs so it suffices to just give everything for any requested fil

        if data.startswith(b"setfs"):
            # Whatever
            self.reply(format_gdb_message(b"F0"))

        elif data.startswith(b"open:"):
            # TODO: We do probably need to keep track of file descriptors and positions and things in order to
            # handle GDB reading from multiple files at once
            # self.reply(format_gdb_message(b'F7'))
            return OpenFile(data)
        elif data.startswith(b"close:"):
            return CloseFile(data[6:])
        elif data.startswith(b"fstat:"):
            return FstatFile(data[6:])
        elif data.startswith(b"pread:"):
            return PreadFile(data[6:])
        else:
            self.reply(format_gdb_message(b""))

    def handle_extended(self, data):
        if data.startswith(b"vCont?"):
            self.reply(format_gdb_message(b""))
        elif data.startswith(b"vFile:"):
            return self.handle_file(data[6:])
        else:
            self.reply(format_gdb_message(b""))

    def handle_set_breakpoints(self, data):
        try:
            return self.bp_messages[data[1]][0](data)
        except KeyError:
            self.reply(format_gdb_message(b""))
            return

    def handle_unset_breakpoints(self, data):
        try:
            return self.bp_messages[data[1]][1](data)
        except KeyError:
            self.reply(format_gdb_message(b""))
            return

    def handle_get_reg(self, data):
        return GetRegisters()

    def handle_ignored(self, data):
        print("Handle ignored")
        self.reply(format_gdb_message(b"OK"))

    def message_factory(self, data):
        # First we need to check the checksum
        if data == b"\x03":
            # Special interrupt message
            return Stop(b"")
        csum = checksum(data[1:-3])
        message_csum = int(data[-2:], 16)
        if data[0] != ord("$") or csum != message_csum:
            print("Checksum mismatch {csum=} {message_csum=}")
            self.reply(self.bad_ack)
            return

        data = data[1:-3]

        try:
            handler = self.handlers[data[0]]
        except KeyError:
            # send some sort of error?
            print("No jim", self.handlers, data[0])
            return

        return handler(data)

        # type = struct.unpack('>I', data[:4])[0]
        # try:
        #    return messages_by_type[type].from_binary(data[4:])
        # except KeyError:
        #    print('Unknown message type %d' % type)
        # except Error as e:
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
        print("Sending a handshake message with", (self.host, self.port))
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
