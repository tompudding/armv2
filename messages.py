import socket
import threading
import SocketServer
import time

class Types:
    RESUME    = 0
    STEP      = 1
    RESTART   = 2
    SETBKPT   = 3
    UNSETBKPT = 4
    MEMGET    = 5
    MEMWATCH  = 6
    UNWATCH   = 7
    CONNECT   = 8

class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        data = self.request.recv(1024)
        print 'Handle message'

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = True

class Comms(object):
    def __init__(self, port, callback):
        self.port = port
        self.callback = callback
        self.server = ThreadedTCPServer(('0.0.0.0',self.port),ThreadedTCPRequestHandler)
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


    def exit(self):
        self.server.shutdown()
        self.server.server_close()
        print 'joining thread'
        self.thread.join()
        print 'joined'

class Server(Comms):
    pass

class Client(Comms):
    reconnect_interval = 0.1

    def __init__(self, host, port, callback):
        super(Client,self).__init__(port=0, callback=callback)
        self.host, self.port = self.server.server_address
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

    def initiate_connection(self):
        try:
            self.connect(self.remote_host, self.remote_port)
            self.connected = True
            self.start_handshake()
        except socket.error as e:
            return


    def start_handshake(self):
        #Send a handshake message with our listen port
        print 'Sending a handshake message with',(self.host,self.port)
        self.send_socket.send('jim')



