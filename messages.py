import socket
import threading
import SocketServer
import time
import select
import struct

class Error(Exception):
    pass

class Types:
    UNKNOWN     = 0
    RESUME      = 1
    STEP        = 2
    RESTART     = 3
    SETBKPT     = 4
    UNSETBKPT   = 5
    MEMDATA     = 6
    MEMWATCH    = 7
    UNWATCH     = 8
    CONNECT     = 9
    DISCONNECT  = 10
    STATE       = 11
    DISASSEMBLY = 12
    DISASSEMBLYDATA = 13

class DynamicObject(object):
    pass

class Message(object):
    type = Types.UNKNOWN

    def to_binary(self):
        return struct.pack('>I',self.type)

class Handshake(Message):
    type = Types.CONNECT

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def to_binary(self):
        first = super(Handshake,self).to_binary()
        last = struct.pack('>H',self.port) + self.host
        return first + last

    @staticmethod
    def from_binary(data):
        port = struct.unpack('>H',data[:2])[0]
        host = data[2:]
        return Handshake(host, port)

class MachineState(Message):
    type = Types.STATE

    def __init__(self, regs, mode, pc):
        self.registers = [regs[i] for i in xrange(16)]
        self.mode = mode
        self.pc = pc

    def to_binary(self):
        first = super(MachineState,self).to_binary()
        regs = ''.join(struct.pack('>I',reg) for reg in self.registers)
        mode = struct.pack('>I',self.mode)
        pc = struct.pack('>I',self.pc)
        return first + regs + mode + pc

    @staticmethod
    def from_binary(data):
        regs = [struct.unpack('>I',data[i*4:(i+1)*4])[0] for i in xrange(16)]
        mode,pc = struct.unpack('>II',data[16*4:])
        return MachineState(regs,mode,pc)


class MemView(Message):
    type = Types.MEMWATCH
    class Types:
        MEMDUMP     = 0
        DISASSEMBLY = 1

    def __init__(self, id, start, size):
        self.id = id
        self.start = start
        self.size = size

    def to_binary(self):
        first = super(MemView,self).to_binary()
        data = struct.pack('>III',self.id,self.start,self.size)
        return first + data

    @staticmethod
    def from_binary(data):
        id,start,size = struct.unpack('>III',data)
        return MemView(id, start,size)


class MemdumpView(MemView):
    id = MemView.Types.MEMDUMP
    def __init__(self, start, size):
        super(MemdumpView,self).__init__(self.id, start, size)


class MemViewReply(MemView):
    type = Types.MEMDATA
    def __init__(self, id, start, data):
        super(MemViewReply,self).__init__(id, start, len(data))
        self.data = data

    def to_binary(self):
        first = super(MemViewReply,self).to_binary()
        return first + self.data

    @staticmethod
    def from_binary(data):
        id,start,size = struct.unpack('>III',data[:12])
        data = data[12:]
        if len(data) != size:
            print 'Error mismatch lengths %d %d' % (len(data),size)
            return None
        return MemViewReply(id,start,data)


class DisassemblyView(MemView):
    type = Types.DISASSEMBLY
    id = MemView.Types.DISASSEMBLY

    def __init__(self, start, size):
        super(DisassemblyView, self).__init__(self.id, start, size)

    @staticmethod
    def from_binary(data):
        id,start,size = struct.unpack('>III',data)
        return DisassemblyView(start,size)

class DisassemblyViewReply(Message):
    type = Types.DISASSEMBLYDATA
    def __init__(self, start, memory, lines):
        self.start  = start
        self.memory = memory
        self.lines  = lines

    def to_binary(self):
        first = super(DisassemblyViewReply,self).to_binary()
        start = struct.pack('>I',self.start)
        mem   = struct.pack('>I',len(self.memory)) + self.memory
        lines = '\n'.join(self.lines)
        return first + start + mem + lines
        
    @staticmethod
    def from_binary(data):
        start,mem_length = struct.unpack('>II',data[:8])
        mem = data[8:8+mem_length]
        if mem_length != len(mem):
            raise Error('Dissasembly length mismatch %d %d' % (mem_length,len(mem)))
        lines = data[8+mem_length:].split('\n')
        if len(lines) != mem_length/4:
            raise Error('Dissasembly num_lines %d should be %d' % (len(lines),mem_length/4))
        return DisassemblyViewReply(start, mem, lines)
        

class Disconnect(Message):
    type = Types.DISCONNECT

messages_by_type = {Types.CONNECT  : Handshake,
                    Types.STATE    : MachineState,
                    Types.MEMWATCH : MemView,
                    Types.MEMDATA  : MemViewReply,
                    Types.DISASSEMBLY : DisassemblyView,
                    Types.DISASSEMBLYDATA : DisassemblyViewReply,
}

def MessageFactory(data):
    type = struct.unpack('>I',data[:4])[0]
    try:
        return messages_by_type[type].from_binary(data[4:])
    except KeyError:
        print 'Unknown message type %d' % type
    except Error as e:
        print 'Error (%s) while receiving message of type %d' % (e,type)


class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
    select_timeout = 0.5
    total_timeout = 1.0
    def read_message(self):
        ready = select.select([self.request], [], [], self.select_timeout)
        if ready[0]:
            new_data = self.request.recv(1024)
            if not new_data:
                raise socket.error()
            self.process_data(new_data)

    def set_needed(self):
        self.needed = None
        if len(self.data) > 4:
            self.needed = struct.unpack('>I',self.data[:4])[0]
            self.data = self.data[4:]
            #print 'Got needed %d' % self.needed

    def process_data(self, data):
        self.data = self.data + data
        if self.needed == None:
            self.set_needed()
        while self.needed != None and len(self.data) >= self.needed:
            message = MessageFactory(self.data[:self.needed])
            self.data = self.data[self.needed:]
            self.set_needed()
            if message:
                self.server.comms.handle(message)

    def handle(self):
        try:
            self.data = ''
            self.needed = None
            while not self.server.done:
                self.read_message()
        except socket.error as e:
            print 'Got socket error'
            self.server.comms.disconnect()


class ThreadedTCPServer(SocketServer.TCPServer):
    allow_reuse_address = True

class Comms(object):
    def __init__(self, port, callback):
        self.port = port
        self.callback = callback
        self.connected = False
        self.server = ThreadedTCPServer(('0.0.0.0',self.port),ThreadedTCPRequestHandler)
        self.server.comms = self
        self.server.done = False
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.send_socket = None

    def start(self):
        self.thread.start()
        print 'Server loop running in thread:', self.thread.name

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, tb):
        self.exit()

    def connect(self, host, port):
        self.remote_host = host
        self.remote_port = port
        if self.send_socket:
            self.send_socket.close()

        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.send_socket.connect((self.remote_host,self.remote_port))
        self.connected = True

    def disconnect(self):
        if self.send_socket:
            self.send_socket.close()
            self.send_socket = None
            self.connected = False

    def send(self, message):
        if self.connected:
            try:
                m = message.to_binary()
                self.send_socket.send(struct.pack('>I',len(m)) + m)
            except socket.error:
                self.connected = False
                print 'got disconnected'

    def handle(self, message):
        if self.callback:
            self.callback(message)

    def exit(self):
        self.disconnect()
        self.server.done = True
        self.server.shutdown()
        self.server.server_close()
        print 'joining thread'
        self.thread.join()
        print 'joined'

class Server(Comms):
    def handle(self, message):
        if message.type == Types.CONNECT:
            self.connect(message.host, message.port)
        super(Server,self).handle(message)

class Client(Comms):
    reconnect_interval = 0.1

    def __init__(self, host, port, callback):
        super(Client,self).__init__(port=0, callback=callback)
        self.host, self.port = self.server.server_address
        self.host = '127.0.0.1'
        self.remote_host = host
        self.remote_port = port
        self.connected = False
        self.done = False
        self.cv = threading.Condition()
        self.connect_thread = threading.Thread(target = self.connect_thread_main)

    def connect_thread_main(self):
        while not self.done:
            with self.cv:
                while not self.done and self.connected:
                    self.cv.wait()

            while not self.done and not self.connected:
                self.initiate_connection()
                if not self.connected:
                    time.sleep(self.reconnect_interval)

    def __enter__(self):
        super(Client,self).__enter__()
        self.connect_thread.start()
        return self

    def __exit__(self, type, value, tb):
        self.done = True
        with self.cv:
            self.cv.notify()
        self.connect_thread.join()
        super(Client,self).__exit__(type, value, tb)

    def disconnect(self):
        super(Client,self).disconnect()
        with self.cv:
            self.cv.notify()
        self.callback(Disconnect())

    def initiate_connection(self):
        try:
            self.connect(self.remote_host, self.remote_port)
            self.start_handshake()
        except socket.error as e:
            self.connected = False
            return

    def start_handshake(self):
        #Send a handshake message with our listen port
        print 'Sending a handshake message with',(self.host,self.port)
        handshake = Handshake(self.host,self.port)
        self.send(handshake)
        if self.connected:
            self.callback(handshake)



