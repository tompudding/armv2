import disassemble
import time
import armv2
import pygame
import os
import string
import glob
from pygame.locals import *

class WindowControl:
    SAME    = 1
    RESUME  = 2
    NEXT    = 3
    RESTART = 4
    EXIT    = 5
    POPUP_GOTO = 6

class View(object):
    def __init__(self,parent):
        self.parent = parent

    def Update(self):
        self.parent.send_message()

class Debug(View):
    label_width = 14
    def __init__(self,debugger,tl,br):
        super(Debug,self).__init__(debugger,tl,br)
        self.debugger = debugger
        self.disassembly = None

    def Centre(self,pos = None):
        if pos == None:
            pos = self.selected
        #Set our pos such that the given pos is as close to the centre as possible

        correct = None
        self.disassembly = []
        start = max(pos-((self.rows)/2)*4,pos&3)

        dis = []
        for instruction in disassemble.Disassemble(self.debugger.machine,self.debugger.breakpoints,start,start+(self.rows)*4):
            arrow = '>' if instruction.addr == self.debugger.machine.pc else ''
            bpt   = '*' if instruction.addr in self.debugger.breakpoints else ' '
            dis.append( (instruction.addr,'%1s%s%07x %08x : %s' % (arrow,bpt,instruction.addr,instruction.word,instruction.ToString())))

        self.disassembly = dis
        self.Update()

    def Select(self,pos):
        self.selected = pos
        self.Update()

    def KeyPress(self, key):
        if key == pygame.locals.K_DOWN:
            try:
                self.selected = self.disassembly[self.selected_pos+1][0]
                self.Centre(self.selected)
            except IndexError:
                pass
        elif key == pygame.locals.K_UP:
            if self.selected_pos > 0:
                self.selected = self.disassembly[self.selected_pos-1][0]
                self.Centre(self.selected)
        elif key == pygame.locals.K_PAGEDOWN:
            #We can't jump to any arbitrary point because we don't know the instruction boundaries
            #instead jump to the end of the screen twice, which should push us down by a whole page
            for i in xrange(2):
                p = self.disassembly[-1][0]
                self.Centre(p)

            self.Select(p)
        elif key == pygame.locals.K_PAGEUP:
            for i in xrange(2):
                p = self.disassembly[0][0]
                self.Centre(p)

            self.Select(p)
        elif key == pygame.locals.K_TAB:
            return WindowControl.NEXT
        elif key == pygame.locals.K_SPACE:
            if self.selected in self.debugger.breakpoints:
                self.debugger.RemoveBreakpoint(self.selected)
            else:
                self.debugger.AddBreakpoint(self.selected)
            self.Centre(self.selected)
        return WindowControl.SAME


    def Update(self):
        super(Debug,self).Update()
        self.selected_pos = None
        if not self.disassembly:
            return
        for i,(pos,line) in enumerate(self.disassembly):
            line = line + ' '*30
            if pos == self.selected:
                self.DrawText(line,i,inverted = True)
                self.selected_pos = i
            else:
                text = self.parent.font.render(line, False, self.colour, self.background)
                self.DrawText(line,i)

class State(View):
    reglist = [('r%d' % i) for i in xrange(12)] + ['fp','sp','lr','pc']
    mode_names = ['USR','FIQ','IRQ','SUP']
    def __init__(self,parent,tl,br):
        super(State,self).__init__(parent,tl,br)
        self.parent = parent

    def Update(self):
        super(State,self).Update()
        for i in xrange(8):
            data = [(self.reglist[i*2+j],self.parent.machine.regs[i*2+j]) for j in (0,1)]
            line = ' '.join('%3s : %08x' % (r,v) for (r,v) in data)
            self.DrawText(line,i)

        self.DrawText('Mode : %s' % self.mode_names[self.parent.machine.mode], 0, self.rect.width*0.6)
        self.DrawText('  pc : %08x' % self.parent.machine.pc, 1, self.rect.width*0.6)

class Help(View):
    def Update(self):
        super(Help,self).Update()
        actions = (('c','continue'),
                   ('q','quit'),
                   ('s','step'),
                   ('r','reset'),
                   ('g','goto'),
                   ('p','play tape as input'),
                   ('ESC','stop/continue'),
                   ('space','set breakpoint'),
                   ('tab','switch window'),
                   ('',''),
        )
        for i in xrange(len(actions)/2):
            self.DrawText('%5s - %s' % actions[i*2],i)
            try:
                action = actions[i*2+1]
            except IndexError:
                continue
            self.DrawText('%5s - %s' % action,i,xoffset=self.rect.width*0.5)

        self.DrawText('                 ***** %6s *****                 ' % ('STOPPED' if self.parent.stopped else 'RUNNING'),
                      self.rows-1,
                      inverted = False if self.parent.stopped else True)

class TapeSelector(View):
    def __init__(self,parent,tl,br):
        super(TapeSelector,self).__init__(parent,tl,br)
        self.parent   = parent
        self.Reset()

    def Reset(self):
        self.tapes    = sorted(glob.glob(os.path.join('tapes','*')))
        self.pos      = 0
        self.selected = 0
        self.loaded   = -1
        self.Update()

    def SetSelected(self,pos):
        if pos > len(self.tapes)-1:
            pos = len(self.tapes)-1
        if pos < 0:
            pos = 0
        self.selected = pos

        if self.selected - self.pos >= self.rows-1:
            self.pos = self.selected - (self.rows-2)
        elif self.selected < self.pos:
            self.pos = self.selected
        self.Update()

    def KeyPress(self,key):
        if key == pygame.locals.K_DOWN:
            self.SetSelected(self.selected + 1)
        elif key == pygame.locals.K_PAGEDOWN:
            self.SetSelected(self.selected + self.rows)
        elif key == pygame.locals.K_PAGEUP:
            self.SetSelected(self.selected - self.rows)
        elif key == pygame.locals.K_UP:
            self.SetSelected(self.selected - 1)
        elif key == pygame.locals.K_p:
            #Hack to allow arbitrary input through the keyboard
            name = self.tapes[self.selected]
            with open(name,'rb') as f:
                for byte in f.read():
                    self.parent.machine.keyboard.KeyDown(ord(byte))
                    self.parent.machine.keyboard.KeyUp(ord(byte))

        elif key in (pygame.locals.K_RETURN,pygame.locals.K_SPACE):
            self.loaded = self.selected
            self.parent.machine.tape_drive.loadTape(self.tapes[self.loaded])
            self.Update()
            #TODO: do something with the tape drive here

        elif key == pygame.locals.K_TAB:
            return WindowControl.NEXT
        return WindowControl.SAME

    def Select(self,pos):
        return self.SetSelected(pos)

    def Centre(self,pos):
        self.Select(pos)
        if pos > len(self.tapes)-1:
            pos = len(self.tapes)-1
        self.pos = pos

    def Update(self):
        pygame.draw.rect(self.parent.screen, self.background, self.rect, 0)
        super(TapeSelector,self).Update()
        for i in xrange(0,min(self.rows-1,len(self.tapes)-self.pos)):
            item = self.pos + i
            name = os.path.basename(self.tapes[item])
            if item == self.selected:
                self.DrawText(name,i+1,inverted=True,xoffset=20)
            else:
                self.DrawText(name,i+1,xoffset=20)
            if item == self.loaded:
                self.DrawText('*LOADED*',i+1,inverted=True,xoffset=self.rect.width*0.8)
        self.DrawText('Tape Selector:',0)


class Memdump(View):
    display_width = 8
    key_time = 1
    max = 0x4000000
    def __init__(self,parent,tl,br):
        super(Memdump,self).__init__(parent,tl,br)
        self.parent   = parent
        self.pos      = 0
        self.selected = 0
        self.lastkey  = 0
        self.keypos   = 0
        self.masks = (0x3fffff0,0x3ffff00,0x3fff000,0x3ff0000,0x3f00000,0x3000000,0)
        self.newnum   = 0

    def Update(self):
        pygame.draw.rect(self.parent.screen, self.background, self.rect, 0)
        super(Memdump,self).Update()
        for i in xrange(self.rows):
            addr = self.pos + i*self.display_width
            data = self.parent.machine.mem[addr:addr+self.display_width]
            if len(data) < self.display_width:
                data += '??'*(self.display_width-len(data))
            data_string = ' '.join((('%02x' % ord(data[i])) if i < len(data) else '??') for i in xrange(self.display_width))
            ascii_string = ''.join( ('%c' % (data[i] if i < len(data) and data[i] in string.printable else '.') for i in xrange(self.display_width)))
            line = '%07x : %s   %s' % (addr,data_string,ascii_string)
            if addr == self.selected:
                self.DrawText(line,i,inverted=True)
            else:
                self.DrawText(line,i)

        # type_string = ('%07x' % self.pos)[:self.keypos]
        # extra = 7 - len(type_string)
        # if extra > 0:
        #     type_string += '.'*extra
        # self.DrawText(type_string,0,xoffset=self.rect.width*0.7)

    def SetSelected(self,pos):
        if pos > self.max:
            pos = self.max
        if pos < 0:
            pos = 0
        self.selected = pos
        if ((self.selected - self.pos)/self.display_width) >= (self.rows):
            self.pos = self.selected - (self.rows-1)*self.display_width
        elif self.selected < self.pos:
            self.pos = self.selected
        self.Update()

    def Select(self,pos):
        return self.SetSelected(pos)

    def Centre(self,pos):
        self.Select(pos)
        self.pos = pos
        self.Update()

    def KeyPress(self,key):
        if key == pygame.locals.K_DOWN:
            self.SetSelected(self.selected + self.display_width)
        elif key == pygame.locals.K_PAGEDOWN:
            self.SetSelected(self.selected + self.display_width*(self.rows))
        elif key == pygame.locals.K_PAGEUP:
            self.SetSelected(self.selected - self.display_width*(self.rows))
        elif key == pygame.locals.K_UP:
            self.SetSelected(self.selected - self.display_width)

        elif key == pygame.locals.K_TAB:
            return WindowControl.NEXT
        return WindowControl.SAME


class Debugger(object):
    BKPT = 0xef000000 | armv2.SWI_BREAKPOINT
    FRAME_CYCLES = 66666
    PORT = 16705
    def __init__(self,machine,screen):
        self.machine          = machine
        self.screen           = screen
        self.breakpoints      = {}
        self.connection       = messages.Server(port = self.PORT)

        self.code_window    = Debug(self, self.connection)
        self.state_window   = State(self, self.connection)
        self.memdump_window = Memdump(self, self.connection)
        self.tape_window    = TapeSelector(self, self.connection)

        self.draw_windows = [self.code_window,self.state_window,self.memdump_window,self.tape_window]

        self.num_to_step    = 0
        #stopped means that the debugger has halted execution and is waiting for input
        self.stopped        = False
        # self.help_window.Draw()
        self.Update()

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
        self.state_window.Update()
        self.memdump_window.Update()
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
        #self.Update()

    def Update(self):
        for window in self.draw_windows:
            window.Update()

    def OuterKeyPress(self,key):
        try:
            key = ord(chr(key).lower())
        except ValueError:
            pass
        if key == pygame.locals.K_c or key == pygame.locals.K_ESCAPE:
            self.Continue(explicit=True)
            return WindowControl.RESUME
        elif key == pygame.locals.K_s:
            self.Step(explicit=True)
            return WindowControl.RESUME
        elif key == pygame.locals.K_r:
            #self.debugger.machine.Reset()
            return WindowControl.RESTART
        elif key == pygame.locals.K_g:
            return WindowControl.POPUP_GOTO
        elif key == pygame.locals.K_q:
            return WindowControl.EXIT

    def KeyPress(self,key):
        if self.current_view is self.goto_window:
            return self.goto_window.KeyPress(key)

        result = self.OuterKeyPress(key)
        if not result:
            result = self.current_view.KeyPress(key)

        if result == WindowControl.POPUP_GOTO:
            h = self.current_view.rect.centery
            self.current_view = self.goto_window = Goto(self,self.current_view,(self.machine.display.pixel_width()+20,h),(self.w-20,h+32))
            #we've changed who should be selected, so update those two windows
            self.goto_window.view.Update()
            self.goto_window.Update()

        elif result == WindowControl.RESUME:
            self.code_window.Select(self.machine.pc)
            self.code_window.Centre(self.machine.pc)
        elif result == WindowControl.RESTART:
            return False
        elif result == WindowControl.NEXT:
            pos = self.window_choices.index(self.current_view)
            pos = (pos + 1)%len(self.window_choices)
            old = self.current_view
            self.current_view = self.window_choices[pos]
            for view in old,self.current_view:
                view.Update()
        elif result == WindowControl.EXIT:
            raise SystemExit

    def Stop(self):
        self.stopped = True
