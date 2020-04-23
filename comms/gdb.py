import socket
import threading
import socketserver
import time
import select
import struct
import bisect
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
    CONTINUE_ACTION = 'vCont'
    CONT_GET_ACTION = 'vCont;'
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



class Message(object):
    type = Types.UNKNOWN

    def to_binary(self):
        return struct.pack('>I', self.type)


messages_by_type = {}

class Factory(object):

    def message_factory(self, data):
        print('Received message',data)
        return None
        #type = struct.unpack('>I', data[:4])[0]
        #try:
        #    return messages_by_type[type].from_binary(data[4:])
        #except KeyError:
        #    print('Unknown message type %d' % type)
        #except Error as e:
        #    print('Error (%s) while receiving message of type %d' % (e, type))

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
    def handle(self, message):
        if message.type == Types.CONNECT:
            self.connect(message.host, message.port)
        super(Server, self).handle(message)
