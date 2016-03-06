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

class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        data = self.request.recv(1024)
        print 'Handle message'

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

class Server(object):
    def __init__(self, port, callback):
        self.port = port
        self.callback = callback
        self.server = ThreadedTCPServer(('0.0.0.0',self.port),ThreadedTCPRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        print "Server loop running in thread:", self.thread.name

    def exit(self):
        self.server.shutdown()
        self.server.server_close()
        print 'joining thread'
        self.thread.join()
        print 'joined'
        
