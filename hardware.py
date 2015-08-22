import armv2
import pygame
import threading
import traceback
import signal

class Keyboard(armv2.Device):
    """
    A Keyboard device. The memory map looks like

    0x00 - 0x20 : bitmask of currently pressed ascii keys
    0x20 - 0xa0 : 128 byte ring buffer
    0xa0 - 0xa1 : byte indicating ringbuffer position
    """
    id = 0x41414141
    bitmask_start    = 0
    ringbuffer_start = 0x20
    ringbuffer_pos   = 0xa0

    class InterruptCodes:
        KEY_DOWN = 0
        KEY_UP   = 1

    def __init__(self, cpu):
        super(Keyboard,self).__init__(cpu)
        self.ring_buffer = [0 for i in xrange(128)]
        self.pos = 0
        self.key_state = 0
        armv2.DebugLog('keyboard keyboard keyboard!\n')

    def KeyDown(self,key):
        armv2.DebugLog('key down ' + str(key))
        self.key_state |= (1<<key)
        self.ring_buffer[self.ring_buffer[self.pos]] = key
        self.pos += 1
        if self.pos == len(self.ring_buffer):
            self.pos = 0
        self.cpu.Interrupt(self.id, self.InterruptCodes.KEY_DOWN)

    def KeyUp(self,key):
        armv2.DebugLog('key up ' + str(key))
        self.key_state &= ~(1<<key)
        self.cpu.Interrupt(self.id, self.InterruptCodes.KEY_UP)

    def readCallback(self,addr,value):
        armv2.DebugLog('keyboard reader %x %x\n' % (addr,value))
        if addr < self.ringbuffer_start:
            #It's a state request
            return (self.key_state>>(8*addr)&0xffffffff)
        elif addr < self.ringbuffer_pos:
            pos = addr - self.ringbuffer_start
            bytes = [self.ring_buffer[pos + i % len(self.ring_buffer)] for i in xrange(4)]
            return (bytes[0]) | (bytes[1]<<8) | (bytes[2]<<16) | (bytes[3]<<24)
        elif addr == ringbuffer_pos:
            return self.pos

        return 0

    def readByteCallback(self,addr,value):
        armv2.DebugLog('keyboard reader byte %x %x\n' % (addr,value))
        if addr < self.ringbuffer_start:
            #It's a state request
            return (self.key_state>>(8*addr)&0xff)
        elif addr < self.ringbuffer_pos:
            pos = addr - self.ringbuffer_start
            return self.ring_buffer[pos]
        elif addr == ringbuffer_pos:
            return self.pos

    def writeCallback(self,addr,value):
        armv2.DebugLog('keyboard writer %x %x\n' % (addr,value))
        return 0

    def writeByteCallback(self,addr,value):
        armv2.DebugLog('keyboard writer %x %x\n' % (addr,value))
        return 0

def SetPixels(pixels,word):
    for j in xrange(64):
        #the next line is so obvious it doesn't need a comment
        pixels[7-(j/8)][j%8] = ((word>>j)&1)

class Display(armv2.Device):
    """
    A Display

    Mapped memory looks like this:

    0x000 - 0x4b0 : Letter array, 1 byte for every pixel starting at the bottom left, where the high nibble
                    represents the background colour and the low nibble the foreground colour
    0x4b0 - 0x960 : Same as above, but each byte represents the ascii code for the character displayed

    """
    id = 0x9d99389e
    width  = 40
    height = 30
    cell_size = 8
    palette_start = 0
    letter_start  = width*height
    letter_end    = width*height*2
    def __init__(self, cpu, scale_factor):
        super(Display,self).__init__(cpu)
        self.dirty_rects = {}
        self.scale_factor = scale_factor
        self.screen = pygame.display.set_mode((self.width*self.cell_size*self.scale_factor, self.height*self.cell_size*self.scale_factor))
        self.font_surface = pygame.Surface((self.cell_size,self.cell_size),depth=8)
        self.font_surface.set_palette(((0, 0, 0, 255),)*256)
        self.font_surface.set_palette(((0,0,0,255),(255, 255, 255, 255)))
        self.font_surfaces = {}
        self.palette = [ (0x00,0x00,0x00,0xff),
                         (0x00,0x00,0xaa,0xff),
                         (0x00,0xaa,0x00,0xff),
                         (0x00,0xaa,0xaa,0xff),
                         (0xaa,0x00,0x00,0xff),
                         (0xaa,0x00,0xaa,0xff),
                         (0xaa,0xaa,0x00,0xff),
                         (0xaa,0xaa,0xaa,0xff),
                         (0x55,0x55,0x55,0xff),
                         (0x55,0x55,0xff,0xff),
                         (0x55,0xff,0x55,0xff),
                         (0x55,0xff,0xff,0xff),
                         (0xff,0x55,0x55,0xff),
                         (0xff,0x55,0xff,0xff),
                         (0xff,0xff,0x55,0xff),
                         (0xff,0xff,0xff,0xff) ]

        self.pixels = pygame.PixelArray(self.font_surface)
        self.font_data = [0 for i in xrange(256)]
        self.letter_data = [0 for i in xrange(self.width*self.height)]
        self.palette_data = [0 for i in xrange(self.width*self.height)]

        with open('petscii.txt','rb') as f:
            for line in f:
                i,dummy,word = line.strip().split()
                i,word= [int(v,16) for v in i,word]
                self.font_data[i] = word
                SetPixels(self.pixels,self.font_data[i])
                self.font_surfaces[i] = pygame.transform.scale(self.font_surface,(self.cell_size*self.scale_factor,self.cell_size*self.scale_factor))


    def readCallback(self,addr,value):
        pass

    def writeCallback(self,addr,value):
        pass

    def readByteCallback(self,addr,value):
        pass

    def writeByteCallback(self,addr,value):
        if addr < self.letter_start:
            #It's the palette
            pos = addr
            if value == self.palette_data[pos]:
                #no change, ignore
                return
            self.palette_data[pos] = value
            self.redraw(pos)
        elif addr < self.letter_end:
            pos = addr - self.letter_start
            if value == self.letter_data[pos]:
                #no change, ignore
                return
            self.letter_data[pos] = value
            self.redraw(pos)

    def redraw(self,pos):
        x = pos%self.width
        y = pos/self.width
        letter = self.letter_data[pos]
        palette = self.palette_data[pos]
        back_colour = self.palette[(palette>>4)&0xf]
        fore_colour = self.palette[(palette)&0xf]

        tile = self.font_surfaces[letter]
        tile.set_palette((back_colour,text_colour))

        dirty = (x*self.cell_size*scale_factor,
                 y*self.cell_size*scale_factor,
                 (x+1)*self.cell_size*scale_factor,
                 (y+1)*self.cell_size*scale_factor)
        self.screen.blit(tile,(dirty[0],dirty[1]))
        self.dirty_rects[dirty] = True

    def Update(self):
        if self.dirty_rects:
            pygame.display.update(self.dirty_rects.keys())
            self.dirty_rects = {}


class MemPassthrough(object):
    def __init__(self,cv,accessor):
        self.cv = cv
        self.accessor = accessor

    def __getitem__(self,index):
        with self.cv:
            return self.accessor.__getitem__(index)

    def __setitem__(self,index,values):
        with self.cv:
            return self.accessor.__setitem__(index,values)

    def __len__(self):
        with self.cv:
            return self.accessor.__len__()

class Machine:
    def __init__(self,cpu_size,cpu_rom):
        self.cpu          = armv2.Armv2(size = cpu_size,filename = cpu_rom)
        self.hardware     = []
        self.running      = True
        self.steps_to_run = 0
        #I'm not sure why I need a regular lock here rather than the default (A RLock), but with the default
        #I get weird deadlocks on KeyboardInterrupt
        self.cv           = threading.Condition(threading.Lock())
        self.mem          = MemPassthrough(self.cv,self.cpu.mem)
        self.memw         = MemPassthrough(self.cv,self.cpu.memw)
        self.thread       = threading.Thread(target = self.threadMain)
        self.status       = None
        self.thread.start()

    @property
    def regs(self):
        with self.cv:
            return self.cpu.regs

    @regs.setter
    def regs(self,value):
        with self.cv:
            self.cpu.regs = value

    @property
    def stepping(self):
        with self.cv:
            return self.steps_to_run != 0

    @property
    def mode(self):
        with self.cv:
            return self.cpu.mode

    @property
    def pc(self):
        with self.cv:
            return self.cpu.pc

    def threadMain(self):
        with self.cv:
            while self.running:
                while self.running and self.steps_to_run == 0:
                    self.cv.wait(1)
                if not self.running:
                    break
                self.status = self.cpu.Step(self.steps_to_run)
                self.steps_to_run = 0
                self.cv.notify()

    def Step(self,num):
        with self.cv:
            self.steps_to_run = num
            self.cv.notify()

    def StepAndWait(self,num):
        self.Step(num)
        with self.cv:
            while self.running:
                while self.running and self.steps_to_run != 0:
                    self.cv.wait(1)
                if not self.running:
                    break
                return self.status

    def AddHardware(self,device,name = None):
        with self.cv:
            self.cpu.AddHardware(device)
        self.hardware.append(device)
        if name != None:
            setattr(self,name,device)

    def Delete(self):
        with self.cv:
            self.running = False
            self.cv.notify()
        armv2.DebugLog('joining thread')
        self.thread.join()
        armv2.DebugLog('Killed')

    def Interrupt(self, hw_id, code):
        armv2.DebugLog('Interrupt from device %s with code %s' % (hw_id, code))
        self.cpu.Interrupt(hw_id, code)
