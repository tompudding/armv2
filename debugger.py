import disassemble
import time
import armv2
import pygame
import os
import string
import glob
import messages
from pygame.locals import *


class Debugger(object):
    BKPT = 0xef000000 | armv2.SWI_BREAKPOINT
    FRAME_CYCLES = 66666
    PORT = 16705

    def __init__(self,machine,screen):
        self.machine          = machine
        self.screen           = screen
        self.breakpoints      = {}
        self.handlers = {messages.Types.RESUME    : self.handle_resume,
                         messages.Types.STEP      : self.handle_step,
                         messages.Types.RESTART   : self.handle_restart,
                         messages.Types.SETBKPT   : self.handle_set_breakpoint,
                         messages.Types.UNSETBKPT : self.handle_unset_breakpoint,
                         messages.Types.MEMGET    : self.handle_memory_get,
                         messages.Types.MEMWATCH  : self.handle_memory_watch,
                         messages.Types.UNWATCH   : self.handle_memory_unwatch,
                         messages.Types.CONNECT   : self.handle_connect}

        self.connection       = messages.Server(port = self.PORT, callback = self.handle_message)
        self.connection.start()

        try:
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
            return self.handlers[message.type](message)
        except KeyError:
            print 'Ooops got unknown message type',message.type

    def handle_resume(self,message):
        print 'Got resume'

    def handle_step(self,message):
        print 'Got step'

    def handle_restart(self,message):
        print 'Got restart'

    def handle_set_breakpoint(self,message):
        print 'Got set breakpoint'

    def handle_unset_breakpoint(self,message):
        print 'Got unset breakpoint'

    def handle_memory_get(self, message):
        print 'Got memory get'

    def handle_memory_watch(self, message):
        print 'Got memory watch'

    def handle_memory_unwatch(self, message):
        print 'Got memory unwatch'

    def handle_connect(self, message):
        print 'Got connect in debugger'
        #On connect we send an initial update
        self.send_register_update()

    def send_register_update(self):
        self.connection.send(messages.MachineState(self.machine.regs))

    def AddBreakpoint(self,addr):
        if addr&3:
            raise ValueError()
        if addr in self.breakpoints:
            return
        addr_word = addr
        self.breakpoints[addr]   = self.machine.memw[addr_word]
        self.machine.memw[addr_word] = self.BKPT

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
        self.send_register_update()
        #self.memdump_window.Update()
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

    def exit(self):
        self.connection.exit()

    def Stop(self):
        self.stopped = True
