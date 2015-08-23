import disassemble
import time
import armv2
import pygame
import os
from pygame.locals import *

class WindowControl:
    SAME    = 1
    RESUME  = 2
    NEXT    = 3
    RESTART = 4
    EXIT    = 5

class View(object):
    def __init__(self,parent,tl,br):
        self.tl     = tl
        self.br     = br
        self.width  = br[0]-tl[0]
        self.height = br[1]-tl[1]
        self.parent = parent
        self.rect   = pygame.Rect(self.tl, (self.width, self.height))
        self.colour = pygame.Color(0,255,0,255)
        self.background = pygame.Color(0,0,0,255)
        self.row_height = self.parent.font.render('dummy', False, self.colour, self.background).get_rect().height
        self.rows = self.height / self.row_height

    def Centre(self,pos):
        pass

    def Select(self,pos):
        pass

    def TakeInput(self):
        return WindowControl.SAME

    def Update(self, draw_border = False):
        #Draw a rectangle around ourself, the subclasses can draw the other stuff
        if draw_border:
            pygame.draw.rect(self.parent.screen, self.colour, self.rect, 2)

    def DrawText(self, line, row, inverted=False):
        if inverted:
            fore,back = self.background, self.colour
        else:
            fore,back = self.colour, self.background
        text = self.parent.font.render(line, False, fore, back)
        rect = text.get_rect()
        rect.centery = (self.row_height*(row+0.5))+self.rect.top+1
        rect.left = self.rect.left+1
        if rect.right >= self.rect.right-1:
            rect.width = rect.width - (rect.right - (self.rect.right-1))
            area = pygame.Rect((0,0),(rect.width,rect.height))
            self.parent.screen.blit(text, rect, area)
        else:
            self.parent.screen.blit(text, rect)

class Debug(View):
    label_width = 14
    def __init__(self,debugger,tl,br):
        super(Debug,self).__init__(debugger,tl,br)
        self.selected = 0
        self.debugger = debugger

    def Centre(self,pos = None):
        if pos == None:
            pos = self.selected
        #Set our pos such that the given pos is as close to the centre as possible

        correct = None
        self.disassembly = []
        start = max(pos-((self.rows)/2)*4,0)
        end = min(pos + ((self.rows)/2)*4,len(self.debugger.machine.mem))

        dis = []
        for instruction in disassemble.Disassemble(self.debugger.machine,self.debugger.breakpoints,start,start+(self.rows)*4):
            arrow = '>' if instruction.addr == self.debugger.machine.pc else ''
            bpt   = '*' if instruction.addr in self.debugger.breakpoints else ' '
            dis.append( (instruction.addr,'%1s%s%07x %08x : %s' % (arrow,bpt,instruction.addr,instruction.word,instruction.ToString())))

        self.disassembly = dis

    def Select(self,pos):
        self.selected = pos

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
        elif key == pygame.locals.K_c:
            self.debugger.Continue()
            return WindowControl.RESUME
        elif key == pygame.locals.K_s:
            self.debugger.Step()
            return WindowControl.RESUME
        elif key == pygame.locals.K_r:
            #self.debugger.machine.Reset()
            return WindowControl.RESUME
        elif key == pygame.locals.K_q:
            return WindowControl.EXIT
        return WindowControl.SAME


    def Update(self,draw_border = False):
        super(Debug,self).Update(draw_border)
        self.selected_pos = None
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

    def Update(self,draw_border = False):
        for i in xrange(8):
            data = [(self.reglist[i*2+j],self.parent.machine.regs[i*2+j]) for j in (0,1)]
            line = ' '.join('%3s : %08x' % (r,v) for (r,v) in data)
            self.DrawText(line,i)

        #mode_text = self.window.addstr(1,18,'Mode : %s' % self.mode_names[self.debugger.machine.mode])
        # self.window.addstr(2,18,'  pc : %08x' % self.debugger.machine.pc)
        # self.window.refresh()

class Help(View):
    def Draw(self,draw_border = False):
        self.window.clear()
        if draw_border:
            self.window.border()
        for i,(key,action) in enumerate( (('c','continue'),
                                          ('q','quit'),
                                          ('s','step'),
                                          ('space','set breakpoint'),
                                          ('tab','switch window')) ):
            self.window.addstr(i+1,1,'%5s - %s' % (key,action))
        self.window.refresh()

class Memdump(View):
    display_width = 16
    key_time = 1
    max = 0x4000000
    def __init__(self,debugger,h,w,y,x):
        super(Memdump,self).__init__(h,w,y,x)
        self.debugger = debugger
        self.pos      = 0
        self.selected = 0
        self.lastkey  = 0
        self.keypos   = 0
        self.masks = (0x3fffff0,0x3ffff00,0x3fff000,0x3ff0000,0x3f00000,0x3000000,0)
        self.newnum   = 0

    def Draw(self,draw_border = False):
        self.window.clear()
        if draw_border:
            self.window.border()
        for i in xrange(self.height-2):
            addr = self.pos + i*self.display_width
            data = self.debugger.machine.mem[addr:addr+self.display_width]
            if len(data) < self.display_width:
                data += '??'*(self.display_width-len(data))
            data_string = ' '.join((('%02x' % ord(data[i])) if i < len(data) else '??') for i in xrange(self.display_width))
            line = '%07x : %s' % (addr,data_string)
            if addr == self.selected:
                self.window.addstr(i+1,1,line,curses.A_REVERSE)
            else:
                self.window.addstr(i+1,1,line)

        type_string = ('%07x' % self.pos)[:self.keypos]
        extra = 7 - len(type_string)
        if extra > 0:
            type_string += '.'*extra
        self.window.addstr(1,60,type_string)
        self.window.refresh()

    def SetSelected(self,pos):
        if pos > self.max:
            pos = self.max
        if pos < 0:
            pos = 0
        self.selected = pos
        if ((self.selected - self.pos)/self.display_width) >= (self.height - 2):
            self.pos = self.selected - (self.height-3)*self.display_width
        elif self.selected < self.pos:
            self.pos = self.selected

    def TakeInput(self):
        ch = self.window.getch()
        if key == curses.KEY_DOWN:
            self.SetSelected(self.selected + self.display_width)
        elif key == curses.KEY_NPAGE:
            self.SetSelected(self.selected + self.display_width*(self.height-2))
        elif key == curses.KEY_PPAGE:
            self.SetSelected(self.selected - self.display_width*(self.height-2))
        elif key == curses.KEY_UP:
            self.SetSelected(self.selected - self.display_width)
        elif key == ord('q'):
            return WindowControl.EXIT
        elif ch in [ord(c) for c in '0123456789abcdef']:
            newnum = int(chr(ch),16)
            self.keypos %= 7
            now = time.time()
            if now - self.lastkey > self.key_time:
                self.keypos = 0
                self.newnum = 0
            self.newnum <<= 4
            self.newnum |= newnum
            self.newnum &= 0x3ffffff
            self.pos &= self.masks[self.keypos]
            self.pos |= self.newnum
            self.keypos += 1
            self.lastkey = now
            self.selected = self.pos

        elif key == ord('\t'):
            return WindowControl.NEXT
        return WindowControl.SAME


class Debugger(object):
    BKPT = 0xef000000 | armv2.SWI_BREAKPOINT
    FRAME_CYCLES = 66666
    def __init__(self,machine,screen):
        self.machine          = machine
        self.screen           = screen
        self.breakpoints      = {}
        self.selected         = 0
        self.font             = pygame.font.Font(os.path.join('fonts','TerminusTTF-4.39.ttf'),12)
        #self.labels           = Labels(labels)

        self.h,self.w       = self.screen.get_height(),self.screen.get_width()
        padding = 20
        pos = 0
        self.code_window    = Debug(self,(self.w*3/4,pos),(self.w,self.h/3))
        pos = self.code_window.rect.height + padding
        self.state_window   = State(self,(self.w*3/4,pos),(self.w,self.h*2/3))
        pos += self.state_window.rect.height + padding
        # self.help_window    = Help(self.h/2,self.w/4,0,3*(self.w/4))
        # self.memdump_window = Memdump(self,self.h/2,self.w/2,self.h/2,self.w/2)
        # self.window_choices = [self.code_window,self.memdump_window]
        # self.draw_windows = self.state_window,self.memdump_window,self.code_window
        self.draw_windows = [self.code_window,self.state_window]
        self.window_choices = [self.code_window]
        self.current_view   = self.code_window
        self.current_view.Select(self.machine.pc)
        self.current_view.Centre(self.machine.pc)
        self.num_to_step    = 0
        #stopped means that the debugger has halted execution and is waiting for input
        self.stopped        = True
        # self.help_window.Draw()

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

    def StepNumInternal(self,num):
        #If we're at a breakpoint and we've been asked to continue, we step it once and then replace the breakpoint
        if num == 0:
            return None
        self.num_to_step -= num
        #armv2.DebugLog('stepping %s %s %s' % (self.machine.pc,num, self.machine.pc in self.breakpoints))
        if self.machine.pc in self.breakpoints:
            old_pos = self.machine.pc
            self.machine.memw[self.machine.pc] = self.breakpoints[self.machine.pc]
            self.machine.StepAndWait(1)
            self.machine.memw[old_pos] = self.BKPT
            if num > 0:
                num -= 1
        return self.machine.StepAndWait(num)

    def Step(self):
        return self.StepNumInternal(1)

    def Continue(self):
        result = None
        self.stopped = False
        try:
            if armv2.Status.Breakpoint == self.StepNumInternal(self.num_to_step):
                raise KeyboardInterrupt()
        except KeyboardInterrupt:
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
        for window in self.draw_windows:
            window.Update(self.current_view is window)

    def KeyPress(self,key):
        result = self.current_view.KeyPress(key)

        if result == WindowControl.RESUME:
            self.current_view.Select(self.machine.pc)
            self.current_view.Centre(self.machine.pc)
        elif result == WindowControl.RESTART:
            return False
        elif result == WindowControl.NEXT:
            pos = self.window_choices.index(self.current_view)
            pos = (pos + 1)%len(self.window_choices)
            self.current_view = self.window_choices[pos]
        elif result == WindowControl.EXIT:
            raise SystemExit

    def Stop(self):
        armv2.DebugLog("Stopped called")
        self.stopped = True
        self.current_view.Select(self.machine.pc)
        self.current_view.Centre(self.machine.pc)
