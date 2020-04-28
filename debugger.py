from . import disassemble
import time
import armv2
import pygame
import os
import string
import glob
from .comms import gdb as messages
#from .comms import custom as messages
import struct
import random
import signal
from pygame.locals import *
from . import tapes

class Debugger(object):
    BKPT         = 0xef000000 | armv2.SWI_BREAKPOINT
    FRAME_CYCLES = 66666
    SYMBOLS_ADDR = 0x30000

    def __init__(self, machine, tape_list=None):
        self.machine          = machine
        self.breakpoints      = {}
        self.next_breakpoint  = None
        self.handlers = {messages.Types.STOP            : self.handle_stop,
                         messages.Types.READ_REGISTERS  : self.handle_get_regs,
                         messages.Types.READ_REGISTER   : self.handle_get_reg,
                         messages.Types.WRITE_REGISTERS : self.handle_set_regs,
                         messages.Types.WRITE_REGISTER  : self.handle_set_reg,
                         messages.Types.READ_MEM        : self.handle_read_mem,
                         messages.Types.STEP            : self.handle_step,
                         messages.Types.CONTINUE        : self.handle_continue,
                         messages.Types.CONTINUE_SIGNAL : self.handle_continue,
                         messages.Types.WRITE_MEM       : self.handle_write_mem,
                         messages.Types.ADD_HARD_BP     : self.handle_set_breakpoint,
                         messages.Types.DEL_HARD_BP     : self.handle_unset_breakpoint,
                         messages.Types.ADD_READ_WP     : self.handle_set_watchpoint,
                         messages.Types.ADD_WRITE_WP    : self.handle_set_watchpoint,
                         messages.Types.ADD_ACCESS_WP   : self.handle_set_watchpoint,
                         messages.Types.DEL_READ_WP     : self.handle_unset_watchpoint,
                         messages.Types.DEL_WRITE_WP    : self.handle_unset_watchpoint,
                         messages.Types.DEL_ACCESS_WP   : self.handle_unset_watchpoint,
        }
        self.wp_types = {messages.Types.ADD_READ_WP   : armv2.WatchpointType.READ,
                         messages.Types.ADD_WRITE_WP  : armv2.WatchpointType.WRITE,
                         messages.Types.ADD_ACCESS_WP : armv2.WatchpointType.ACCESS,
                         messages.Types.DEL_READ_WP   : armv2.WatchpointType.READ,
                         messages.Types.DEL_WRITE_WP  : armv2.WatchpointType.WRITE,
                         messages.Types.DEL_ACCESS_WP : armv2.WatchpointType.ACCESS
        }
        self.need_symbols = False
        self.machine.tape_drive.register_callback(self.set_need_symbols)
        self.connection = None
        try:
            self.load_symbols()
            self.mem_watches = {}
            self.num_to_step    = 0
            # stopped means that the debugger has halted execution and is waiting for input
            self.stopped        = False
            # self.help_window.draw()
            self.update()
        except:
            self.exit()
            raise

    def start_listening(self):
        for port_trial in range(10):
            self.port = 4141#random.randint(0x400, 0x10000)
            print(f'Trying port {self.port}')
            try:
                self.connection = messages.Server(port=self.port, callback=self.handle_message)
                print(f'Success with port {self.port}')
                break
            except OSError:
                continue
        else:
            raise

        self.connection.start()

    def stop_listening(self):
        self.connection.exit()
        self.connection = None

    def handle_message(self, message):
        try:
            handler = self.handlers[message.type]
        except KeyError:
            print('Ooops got unknown message type', message.type)
            return
        return handler(message)

    def handle_continue(self, message):
        self.resume(explicit=True)

    def handle_stop(self, message):
        self.stop(send_message=False)
        self.connection.send(messages.StopReply(signal.SIGINT))

    def handle_step(self, message):
        self.step(explicit=True)
        self.connection.send(messages.StopReply(signal.SIGTRAP))

    def handle_next(self, message):
        self.next(explicit=True)

    def handle_restart(self, message):
        print('Got restart')

    def handle_set_breakpoint(self, message):
        print('Got set breakpoint')
        self.add_breakpoint(message.addr)
        self.connection.send(messages.OK())

    def handle_unset_breakpoint(self, message):
        print('Got unset breakpoint')
        self.remove_breakpoint(message.addr)
        self.connection.send(messages.OK())

    def handle_set_watchpoint(self, message):
        print('Got set watchpoint')
        self.machine.set_watchpoint(self.wp_types[message.type], message.addr)
        self.connection.send(messages.OK())

    def handle_unset_watchpoint(self, message):
        print('Got unset watchpoint')
        self.machine.unset_watchpoint(self.wp_types[message.type], message.addr)
        self.connection.send(messages.OK())

    def handle_request_symbols(self, message):
        if self.connection:
            self.connection.send(self.symbols)

    def handle_memory_watch(self, message):
        self.mem_watches[message.id] = message
        if message.size:
            # They want something now too
            data = self.machine.mem[message.start:message.start + message.size]
            #self.connection.send(messages.MemViewReply(message.id, message.start, data))

    def handle_memory_unwatch(self, message):
        del self.mem_watches[message.id]

    def handle_connect(self, message):
        # On connect we send an initial update
        self.send_register_update()

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
        #self.connection.send(messages.DisassemblyViewReply(start, mem, lines))

    def handle_get_regs(self, message):
        if not self.connection:
            return
        self.connection.send(messages.RegisterValues(self.machine.regs,
                                                     self.machine.cpsr,
                                                     self.machine.pc_value
        ))

    def handle_set_regs(self, message):
        for i,reg in message.regs:
            self.machine.regs[i] = reg

        self.machine.regs[15] = message.pc | message.cpsr
        self.connection.send(messages.OK())

    def handle_set_reg(self, message):
        if message.register < 15:
            self.machine.regs[message.register] = message.value

        elif message.register == 15:
            self.machine.regs[message.register] = message.value | (self.machine.regs[15] & 0xfc000003)

        elif message.register == 25:
            self.machine.regs[message.register] = message.value | (self.machine.regs[15] & 0x03ffffff)
        self.connection.send(messages.OK())

    def handle_get_reg(self, message):
        if not self.connection:
            return
        if message.register < 15:
            register = self.machine.regs[message.register]
        elif message.register == 15:
            #They want the pc
            register = self.machine.pc_value
        elif message.register == 24:
            #This is fps. wtf is fps?
            register = 0
        elif message.register == 25:
            register = self.machine.cpsr
        else:
            register = 0

        self.connection.send(messages.RegisterValue(register))

    def handle_read_mem(self, message):
        if not self.connection:
            return
        self.connection.send(messages.Memory(self.machine.mem[message.start:message.end]))

    def handle_write_mem(self, message):
        print(f'JOJO {message.start=:x} {message.end=:x} {len(message.data)=:x}')
        self.machine.mem[message.start:message.end] = message.data
        if not self.connection:
            return
        self.connection.send(messages.OK())

    def send_mem_update(self):
        for message in self.mem_watches.values():
            if not self.connection:
                return
            data = self.machine.mem[message.watch_start:message.watch_start + message.watch_size]
            #self.connection.send(messages.MemViewReply(message.id, message.watch_start, data))

    def set_need_symbols(self):
        self.need_symbols = True

    def load_symbols(self):
        # reloading all symbols
        self.need_symbols = False
        symbols = []
        pos     = self.SYMBOLS_ADDR
        value   = None

        while value != 0:
            value = struct.unpack('>I', self.machine.mem[pos:pos + 4])[0]
            if 0 == value:
                break
            name = []
            pos += 4
            b = self.machine.mem[pos]
            while b != 0:
                name.append(chr(b))
                pos += 1
                b = self.machine.mem[pos]
            pos += 1
            name = ''.join(name)
            symbols.append((value, name))

        #self.symbols = messages.Symbols(symbols)
        # pretend they just requested the symbols
        #self.handle_request_symbols(self.symbols)

    def add_breakpoint(self, addr):
        print(f'Add breakpoint {addr=:x}')
        if addr & 3:
            raise ValueError()
        if addr in self.breakpoints:
            return
        #self.breakpoints[addr] = True
        addr_word = addr
        self.machine.set_breakpoint(addr)

    def new_machine(self, machine):
        self.machine = machine
        self.machine.tape_drive.register_callback(self.set_need_symbols)
        self.next_instruction = None
        #for bkpt in self.breakpoints:
        #    self.breakpoints[bkpt] = self.machine.memw[bkpt]
        #    self.machine.memw[bkpt] = self.BKPT

    def remove_breakpoint(self, addr):
        #self.machine.memw[addr] = self.breakpoints[addr]
        #del self.breakpoints[addr]
        self.machine.unset_breakpoint(addr)

    def step_num_internal(self, num, skip_breakpoint):
        # If we're at a breakpoint and we've been asked to continue, we step it once and then replace the breakpoint
        if num == 0:
            return None
        self.num_to_step -= num
        #armv2.DebugLog('stepping %s %s %s' % (self.machine.pc,num, self.machine.pc in self.breakpoints))
        #if skip_breakpoint and self.machine.pc in self.breakpoints:
        #    old_pos = self.machine.pc
        #    print('boom doing replacement')
        #    #self.machine.memw[self.machine.pc] = self.breakpoints[self.machine.pc]
        #    status = self.machine.step_and_wait(1)
        #    #self.machine.memw[old_pos] = self.BKPT
        #    if num > 0:
        #        num -= 1
        if num > 0:
            status = self.machine.step_and_wait(num)

        # self.state_window.update()
        if self.need_symbols:
            self.load_symbols()
        #self.send_register_update()
        self.send_mem_update()
        return status

    def step(self, explicit=False):
        return self.step_num_internal(1, skip_breakpoint=explicit)

    def next(self, explicit=True):
        # Continue until we reach the next instruction. We implement this by adding a secret breakpoint
        # at the next instruction, then removing it the next time the machine stops
        if self.machine.pc in self.breakpoints:
            word = self.breakpoints[self.machine.pc]
        else:
            word = self.machine.memw[self.machine.pc]
        print(hex(self.machine.pc), hex(word), disassemble.sets_lr(word))
        if not disassemble.sets_lr(word):
            # We can just step 1 instruction in this case
            return self.step(explicit)

        next_instruction = self.machine.pc + 4
        if next_instruction in self.breakpoints:
            # In this case we just allow a continue since it'll stop anyway
            print('blarg')
            return self.resume(explicit)

        # OK so we're going to actually put the breakpoint in
        self.next_breakpoint = (next_instruction, self.machine.memw[next_instruction])
        self.machine.memw[next_instruction] = self.BKPT
        return self.resume(explicit)

    def resume(self, explicit=False):
        result = None
        self.stopped = False
        status = self.step_num_internal(self.num_to_step, skip_breakpoint=explicit)
        if armv2.Status.BREAKPOINT == status:
            print('**************** GOT BREAKPOINT **************')
            self.stop()
            #Can we send the message to GDB here or do we have threading issues? Let's try here
            if self.connection:
                self.connection.send(messages.SWBreakReply())
        #raise SystemExit('bob %d' % self.num_to_step)

    def wants_interrupt(self):
        return not self.stopped or self.machine.is_waiting()

    def step_num(self, num):
        self.num_to_step = num
        if not self.stopped:
            if self.machine.stepping:
                return
            else:
                return self.resume()

        #disassembly = disassemble.Disassemble(cpu.mem)
        # We're stopped, so display and wait for a keypress
        self.update()

    def update(self):
        #self.send_register_update()
        #self.send_mem_update()
        pass

    def exit(self):
        if self.connection:
            self.connection.exit()

    def stop(self, send_message=True):
        self.stopped = True
        if self.next_breakpoint is not None:
            next_instruction, word = self.next_breakpoint
            print('replace at %08x with %08x pc=%08x' % (next_instruction, word, self.machine.pc))
            # We always clear the next breakpoint when we stop
            self.machine.memw[next_instruction] = word
            self.next_breakpoint = None
        if send_message:
            #self.connection.send(messages.Stop())
            pass
