import socket
import threading
import SocketServer
import time
import select
import struct

end_tag = '\r\nEND\r\n'

class Types:
    UNKNOWN    = 0
    RESUME     = 1
    STEP       = 2
    RESTART    = 3
    SETBKPT    = 4
    UNSETBKPT  = 5
    MEMGET     = 6
    MEMWATCH   = 7
    UNWATCH    = 8
    CONNECT    = 9
    DISCONNECT = 10

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
        last = struct.pack('>H',self.port) + self.host + end_tag
        return first + last

    @staticmethod
    def from_binary(data):
        port = struct.unpack('>H',data[:2])[0]
        host = data[2:]
        return Handshake(host, port)

class Disconnect(Message):
    type = Types.DISCONNECT

messages_by_type = {Types.CONNECT : Handshake}

def MessageFactory(data):
    type = struct.unpack('>I',data[:4])[0]
    try:
        return messages_by_type[type].from_binary(data[4:])
    except KeyError:
        print 'Unknown message type %d' % type


class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
    select_timeout = 0.5
    total_timeout = 1.0
    def dispatch_message(self):
        data = []
        ready = select.select([self.request], [], [], self.select_timeout)
        if ready[0]:
            new_data = self.request.recv(1024)
            if not new_data:
                raise socket.error()
            data.append(new_data)
            if end_tag in new_data:
                print 'Got message'
                message = MessageFactory(''.join(data).split(end_tag)[0])
                data = []
                if message:
                    return self.server.comms.handle(message)

    def handle(self):
        try:
            while not self.server.done:
                self.dispatch_message()
        except socket.error as e:
            print 'Got socket error'
            self.server.comms.disconnect()


class ThreadedTCPServer(SocketServer.TCPServer):
    allow_reuse_address = True

class Comms(object):
    def __init__(self, port, callback):
        self.port = port
        self.callback = callback
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
        self.send_socket.close()
        self.send_socket = None
        self.connected = False

    def send(self, message):
        if self.connected:
            try:
                self.send_socket.send(message.to_binary())
            except socket.error:
                self.connected = False
                print 'got disconnected'

    def handle(self, message):
        print 'Got message',message

    def exit(self):
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
        else:
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
        self.callback(handshake)



