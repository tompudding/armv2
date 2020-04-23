import socket
import threading
import socketserver
import time
import select
import struct
import bisect
import traceback
import enum

class Types(enum.IntEnum):
    pass

class BaseHandler(object):
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
            self.needed = struct.unpack('>I', self.data[:4])[0]
            self.data = self.data[4:]
            # print 'Got needed %d' % self.needed

    def process_data(self, data):
        self.data = self.data + data
        if self.needed == None:
            self.set_needed()
        while self.needed != None and len(self.data) >= self.needed:
            message = self.message_factory(self.data[:self.needed])
            self.data = self.data[self.needed:]
            self.set_needed()
            if message:
                self.server.comms.handle(message)

    def handle(self):
        try:
            self.data = b''
            self.needed = None
            self.server.comms.set_connected(self.request)
            while not self.server.comms.done:
                self.read_message()
        except socket.error as e:
            print('Got socket error')
            self.server.comms.disconnect()


class ThreadedTCPRequestHandler(BaseHandler, socketserver.BaseRequestHandler):
    select_timeout = 0.5
    total_timeout = 1.0
    #This needs overriding
    message_factory = None
    debuf = False


def get_factory_class(inc, factory):
    class temp(inc):
        message_factory = factory
    return temp

class ThreadedTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class Comms(object):
    message_factory = None
    def __init__(self, port, callback):
        self.port = port
        self.callback = callback
        self.connected = False
        self.socket = None
        self.server = ThreadedTCPServer(('0.0.0.0', self.port), get_factory_class(ThreadedTCPRequestHandler, self.message_factory))
        self.server.comms = self
        self.done = False
        self.thread = threading.Thread(target=self.server.serve_forever)

    def start(self):
        self.thread.start()
        print('Server loop running in thread:', self.thread.name)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, tb):
        self.exit()

    def set_connected(self, socket):
        self.socket = socket
        self.connected = True

    def disconnect(self):
        if self.socket:
            self.socket.close()
            self.socket = None
            self.connected = False

    def send(self, message):
        if self.connected:
            try:
                m = message.to_binary()
                self.socket.send(struct.pack('>I', len(m)) + m)
            except socket.error:
                self.connected = False
                print('got disconnected')
        else:
            #print('lost',type(message))
            pass

    def handle(self, message):
        if self.callback:
            self.callback(message)

    def exit(self):
        self.disconnect()
        if self.server:
            self.done = True
            self.server.shutdown()
            self.server.server_close()
        print('joining thread')
        self.thread.join()
        print('joined')


class Server(Comms):
    def connect(self, host, port):
        pass

class Wrapper(object):
    def __init__(self, comms):
        self.comms = comms

class Client(Comms):
    reconnect_interval = 0.1

    def __init__(self, host, port, callback):
        #super(Client, self).__init__(port=0, callback=callback)
        # Clients still need a thread for listening to server responses and acting on them, but they don't
        # need a separate socket
        self.callback = callback
        self.server = None
        self.host = host
        self.port = port
        self.host = '127.0.0.1'
        self.remote_host = host
        self.remote_port = port
        self.socket = None
        self.connected = False
        self.done = False
        self.cv = threading.Condition()
        self.connect_thread = threading.Thread(target=self.connect_thread_main)
        if callback:
            self.thread = threading.Thread(target=self.listen_main)

    def listen_main(self):
        self.handler = get_factory_class(BaseHandler, self.message_factory)()

        while not self.done:
            with self.cv:
                while not self.done and not self.connected:
                    self.cv.wait()

            while not self.done and self.connected:
                self.handler.request = self.socket
                self.handler.server = Wrapper(self)
                self.handler.handle()

    def connect(self, host, port):
        self.remote_host = host
        self.remote_port = port
        if self.socket:
            self.socket.close()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.remote_host, self.remote_port))
        self.connected = True
        with self.cv:
            self.cv.notify()

    def set_connected(self, socket):
        print('Yo set connected',socket, self.socket)

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
        super(Client, self).__enter__()
        self.connect_thread.start()
        return self

    def __exit__(self, type, value, tb):
        self.done = True
        with self.cv:
            self.cv.notify()
        self.connect_thread.join()
        super(Client, self).__exit__(type, value, tb)

    def disconnect(self):
        super(Client, self).disconnect()
        with self.cv:
            self.cv.notify()

    def initiate_connection(self):
        try:
            self.connect(self.remote_host, self.remote_port)
        except socket.error as e:
            self.connected = False
            return


# class DummyClient(object):
#     def __init__(self, host, port, callback):
