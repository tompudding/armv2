import socket
import threading
import SocketServer

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
        if not self.send_socket:
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
    def __init__(self, host, port, callback):
        super(Client,self).__init__(port=0, callback=callback)
        self.host, self.port = self.server.server_address
        self.connect(host, port)
        self.start_handshake()

    def start_handshake(self):
        #Send a handshake message with our listen port
        print 'Sending a handshake message with',(self.host,self.port)
        self.send_socket.send('jim')


