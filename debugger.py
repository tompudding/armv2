import disassemble
import time
import armv2
import pygame
import os
import string
import glob
import messages
import disassemble
import struct
from pygame.locals import *

class Debugger(object):
    BKPT         = 0xef000000 | armv2.SWI_BREAKPOINT
    FRAME_CYCLES = 66666
    PORT         = 16705
    SYMBOLS_ADDR = 0x30000

    def __init__(self,machine):
        self.machine          = machine
        self.breakpoints      = {}
        self.handlers = {messages.Types.RESUME      : self.handle_resume,
                         messages.Types.STOP        : self.handle_stop,
                         messages.Types.STEP        : self.handle_step,
                         messages.Types.RESTART     : self.handle_restart,
                         messages.Types.SETBKPT     : self.handle_set_breakpoint,
                         messages.Types.UNSETBKPT   : self.handle_unset_breakpoint,
                         messages.Types.MEMWATCH    : self.handle_memory_watch,
                         messages.Types.UNWATCH     : self.handle_memory_unwatch,
                         messages.Types.CONNECT     : self.handle_connect,
                         messages.Types.DISASSEMBLY : self.handle_disassembly,
                         messages.Types.TAPEREQUEST : self.handle_taperequest,
                         messages.Types.TAPE_LOAD   : self.handle_load_tape,
                         messages.Types.TAPE_UNLOAD : self.handle_unload_tape,
                         messages.Types.SYMBOL_DATA : self.handle_request_symbols,
        }
        self.tapes = glob.glob(os.path.join('tapes','*.tape'))
        self.loaded_tape = None
        self.need_symbols = False
        self.machine.tape_drive.registerCallback(self.set_need_symbols)
        self.connection = messages.Server(port = self.PORT, callback = self.handle_message)
        self.connection.start()
        try:
            self.load_symbols()
            self.mem_watches = {}
            self.num_to_step    = 0
            #stopped means that the debugger has halted execution and is waiting for input
            self.stopped        = False
            # self.help_window.Draw()
            self.Update()
        except:
            self.exit()
            raise

    def handle_message(self,message):
        try:
            handler = self.handlers[message.type]
        except KeyError:
            print 'Ooops got unknown message type',message.type
            return
        return handler(message)

    def handle_resume(self,message):
        self.Continue(explicit=True)

    def handle_stop(self,message):
        self.Stop(send_message=False)

    def handle_step(self,message):
        self.Step(explicit=True)

    def handle_restart(self,message):
        print 'Got restart'

    def handle_set_breakpoint(self,message):
        print 'Got set breakpoint'
        self.AddBreakpoint(message.addr)

    def handle_unset_breakpoint(self,message):
        print 'Got unset breakpoint'
        self.RemoveBreakpoint(message.addr)

    def handle_taperequest(self,message):
        if message.size:
            tape_list = self.tapes[message.start : message.start + message.size]
            if tape_list:
                self.connection.send(messages.TapeReply(message.id, message.start, tape_list, len(self.tapes)))

    def handle_load_tape(self, message):
        if message.num < len(self.tapes):
            self.machine.tape_drive.loadTape(self.tapes[message.num])
            self.loaded_tape = message.num

    def handle_unload_tape(self, message):
        self.machine.tape_drive.unloadTape()
        self.loaded_tape = None

    def handle_request_symbols(self, message):
        self.connection.send( self.symbols )

    def handle_memory_watch(self, message):
        self.mem_watches[message.id] = message
        if message.size:
            #They want something now too
            data = self.machine.mem[message.start:message.start + message.size]
            self.connection.send(messages.MemViewReply(message.id,message.start,data))

    def handle_memory_unwatch(self, message):
        del self.mem_watches[message.id]

    def handle_connect(self, message):
        #On connect we send an initial update
        self.send_register_update()
        #self.send_tapes()

    def handle_disassembly(self, message):
        start = message.start
        end   = message.start + message.size
        dis   = list(disassemble.Disassemble(self.machine,
                                             self.breakpoints,
                                             message.start,
                                             message.start + message.size,
                                             self.symbols))
        lines = [ins.ToString() for ins in dis]
        mem   = self.machine.mem[start:end]
        self.connection.send(messages.DisassemblyViewReply(start, mem, lines))

    def send_register_update(self):
        self.connection.send(messages.MachineState(self.machine.regs,
                                                   self.machine.mode,
                                                   self.machine.pc,
                                                   self.machine.is_waiting(),
                                               ))

    def send_mem_update(self):
        for message in self.mem_watches.itervalues():
            data = self.machine.mem[message.watch_start:message.watch_start + message.watch_size]
            self.connection.send(messages.MemViewReply(message.id,message.watch_start,data))

    def set_need_symbols(self):
        self.need_symbols = True

    def load_symbols(self):
        #reloading all symbols
        self.need_symbols = False
        symbols = []
        pos     = self.SYMBOLS_ADDR
        value   = None

        while value != 0:
            value = struct.unpack('>I',self.machine.mem[pos:pos+4])[0]
            if 0 == value:
                break
            name = []
            pos += 4
            while self.machine.mem[pos] != '\x00':
                name.append(self.machine.mem[pos])
                pos += 1
            pos += 1
            name = ''.join(name)
            symbols.append( ( value, name ) )

        self.symbols = messages.Symbols(symbols)
        #pretend they just requested the symbols
        self.handle_request_symbols(self.symbols)

    def AddBreakpoint(self,addr):
        if addr&3:
            raise ValueError()
        if addr in self.breakpoints:
            return
        addr_word = addr
        self.breakpoints[addr]   = self.machine.memw[addr_word]
        self.machine.memw[addr_word] = self.BKPT

    def new_machine(self, machine):
        self.machine = machine
        for bkpt in self.breakpoints:
            self.breakpoints[bkpt] = self.machine.memw[bkpt]
            self.machine.memw[bkpt] = self.BKPT
        if self.loaded_tape is not None:
            self.machine.tape_drive.loadTape(self.tapes[self.loaded_tape])

    def RemoveBreakpoint(self,addr):
        self.machine.memw[addr] = self.breakpoints[addr]
        del self.breakpoints[addr]

    def StepNumInternal(self,num,skip_breakpoint):
        #If we're at a breakpoint and we've been asked to continue, we step it once and then replace the breakpoint
        if num == 0:
            return None
        self.num_to_step -= num
        #armv2.DebugLog('stepping %s %s %s' % (self.machine.pc,num, self.machine.pc in self.breakpoints))
        if skip_breakpoint and self.machine.pc in self.breakpoints:
            old_pos = self.machine.pc
            print 'boom doing replacement'
            self.machine.memw[self.machine.pc] = self.breakpoints[self.machine.pc]
            status = self.machine.StepAndWait(1)
            self.machine.memw[old_pos] = self.BKPT
            if num > 0:
                num -= 1
        if num > 0:
            status = self.machine.StepAndWait(num)

        #self.state_window.Update()
        if self.need_symbols:
            self.load_symbols()
        self.send_register_update()
        self.send_mem_update()
        return status

    def Step(self, explicit=False):
        return self.StepNumInternal(1, skip_breakpoint=explicit)

    def Continue(self, explicit=False):
        result = None
        self.stopped = False
        status = self.StepNumInternal(self.num_to_step, skip_breakpoint=explicit)
        if armv2.Status.Breakpoint == status:
            print '**************** GOT BREAKPOINT **************'
            self.Stop()
        #raise SystemExit('bob %d' % self.num_to_step)

    def wants_interrupt(self):
        return not self.stopped or self.machine.is_waiting()

    def StepNum(self,num):
        self.num_to_step = num
        if not self.stopped:
            if self.machine.stepping:
                return
            else:
                return self.Continue()

        #disassembly = disassemble.Disassemble(cpu.mem)
        #We're stopped, so display and wait for a keypress
        self.Update()

    def Update(self):
        self.send_register_update()
        self.send_mem_update()

    def exit(self):
        self.connection.exit()

    def Stop(self, send_message=True):
        self.stopped = True
        if send_message:
            self.connection.send(messages.Stop())
