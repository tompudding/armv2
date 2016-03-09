import armv2
import pygame
import threading
import traceback
import signal
import time
import random
import drawing
import os
from globals.types import Point

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
    ringbuffer_size  = 128
    ringbuffer_pos   = ringbuffer_start + ringbuffer_size

    class InterruptCodes:
        KEY_DOWN = 0
        KEY_UP   = 1

    def __init__(self, cpu):
        super(Keyboard,self).__init__(cpu)
        self.ring_buffer = [0 for i in xrange(self.ringbuffer_size)]
        self.pos = 0
        self.key_state = 0
        armv2.DebugLog('keyboard keyboard keyboard!\n')

    def KeyDown(self,key):
        armv2.DebugLog('key down ' + str(key))
        self.key_state |= (1<<key)
        self.ring_buffer[self.pos] = key
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
        elif addr == self.ringbuffer_pos:
            return self.pos

        return 0

    def readByteCallback(self,addr,value):
        armv2.DebugLog('keyboard reader byte %x %x\n' % (addr,value))
        if addr < self.ringbuffer_start:
            #It's a state request
            return (self.key_state>>(8*addr)&0xff)
        elif addr < self.ringbuffer_pos:
            pos = addr - self.ringbuffer_start
            out = self.ring_buffer[pos]
            armv2.DebugLog('Read key data %d\n' % out)
            return out
        elif addr == self.ringbuffer_pos:
            return self.pos
        else:
            return 0

    def writeCallback(self,addr,value):
        armv2.DebugLog('keyboard writer %x %x\n' % (addr,value))
        return 0

    def writeByteCallback(self,addr,value):
        armv2.DebugLog('keyboard writer %x %x\n' % (addr,value))
        return 0

def SetPixels(pixels,word):
    for j in xrange(64):
        #the next line is so obvious it doesn't need a comment
        pixels[j/8][j%8] = ((word>>j)&1)

class TapeDrive(armv2.Device):
    """
    A Tape Drive

    It has three bytes. The first two are control bytes and the third data
    0 : control byte containing status for the user to read
    1 : control byte for the user to write to
    2 : data byte

    The protocol is: write NEXT_BYTE to the write control and the read control will change to NOT_READY
    until there is a data byte ready, when it will change to READY. Alternatively it might change to END_OF_TAPE or DRIVE_EMPTY.
    It will generate interrupts for READY and END_OF_TAPE and DRIVE_EMPTY
    """
    id=0x2730eb6c

    class Codes:
        NEXT_BYTE   = 0
        NOT_READY   = 1
        END_OF_TAPE = 2
        DRIVE_EMPTY = 3
        READY       = 4

    def __init__(self, cpu):
        super(TapeDrive,self).__init__(cpu)
        self.status    = self.Codes.NOT_READY
        self.data_byte = 0
        self.tape_name = None
        self.tape      = None
        self.running   = True
        self.cv        = threading.Condition(threading.Lock())
        #self.thread    = threading.Thread(target = self.threadMain)
        self.byte_required = False
        #self.thread.start()
        self.loading   = False

    def loadTape(self, filename):
        self.tape = open(filename,'rb')
        self.tape_name = filename

    def unloadTape(self):
        if self.tape:
            self.tape.close()
            self.tape = None
            self.tape_name = None

    def threadMain(self):
        with self.cv:
            while self.running:
                while self.running and not self.byte_required:
                    self.cv.wait(0.01)
                if not self.running:
                    break
                self.byte_required = False
                #time.sleep(0.001)
                c = self.tape.read(1)
                if c:
                    self.data_byte = ord(c)
                    self.status = self.Codes.READY
                    self.cpu.cpu.Interrupt(self.id, self.status)
                else:
                    self.data_byte = 0
                    self.status = self.Codes.END_OF_TAPE
                    self.loading = False
                    self.cpu.cpu.Interrupt(self.id, self.status)

    def readByteCallback(self,addr,value):
        if addr == 0:
            #They want the current status
            return self.status
        elif addr == 1:
            #They really shouldn't be reading this one
            return 0
        elif addr == 2:
            return self.data_byte

    def writeByteCallback(self,addr,value):
        if addr == 0:
            #Trying to write to the read register. :(
            pass
        elif addr == 1:
            if value == self.Codes.NEXT_BYTE:
                #They want the next byte, are we ready for them?
                #self.loading = pygame.time.get_ticks()
                if self.tape:
                    # self.status = self.Codes.NOT_READY
                    # with self.cv:
                    #     self.byte_required = True
                    #     self.cv.notify()
                    c = self.tape.read(1)
                    if c:
                        self.data_byte = ord(c)
                        self.status = self.Codes.READY
                        #time.sleep(0.001)
                        self.cpu.cpu.Interrupt(self.id, self.status)
                    else:
                        self.data_byte = 0
                        self.status = self.Codes.END_OF_TAPE
                        self.loading = False
                        self.cpu.cpu.Interrupt(self.id, self.status)

                else:
                    self.data_byte = 0
                    self.status = self.Codes.DRIVE_EMPTY
                    self.cpu.cpu.Interrupt(self.id, self.status)
        elif addr == 2:
            #Can't write to the data byte
            pass
        return 0;

    def Delete(self):
        return
        with self.cv:
            self.running = False
            self.cv.notify()
        armv2.DebugLog('joining tape drivethread')
        self.thread.join()
        armv2.DebugLog('joined tape drivethread')


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
        # self.screen = screen
        # self.font_surface = pygame.Surface((self.cell_size,self.cell_size),depth=8)
        # self.font_surface.set_palette(((0, 0, 0, 255),)*256)
        # self.font_surface.set_palette(((0,0,0,255),(255, 255, 255, 255)))
        # self.font_surfaces = {}
        # self.screen.fill((0,0,0,255))
        self.atlas = drawing.texture.PetsciiAtlas(os.path.join('fonts','petscii.png'))

        self.back_quads_buffer = drawing.QuadBuffer(self.width*self.height)
        self.fore_quads_buffer = drawing.QuadBuffer(self.width*self.height)
        self.back_quads = [drawing.Quad(self.back_quads_buffer) for i in xrange(self.width*self.height)]
        self.fore_quads = [drawing.Quad(self.fore_quads_buffer) for i in xrange(self.width*self.height)]

        for z,quad_list in enumerate((self.back_quads,self.fore_quads)):
            for pos,quad in enumerate(quad_list):
                x = pos%self.width
                y = self.height - 1 - (pos/self.width)
                bl = Point(x*self.cell_size, y*self.cell_size)
                tr = bl + Point(self.cell_size, self.cell_size)
                quad.SetVertices(bl, tr, z)

        self.palette = [ (0, 0, 0, 255),
                         (255, 255, 255, 255),
                         (136, 0, 0, 255),
                         (170, 255, 238, 255),
                         (204, 68, 204, 255),
                         (0, 204, 85, 255),
                         (0, 0, 170, 255),
                         (238, 238, 119, 255),
                         (221, 136, 85, 255),
                         (102, 68, 0, 255),
                         (255, 119, 119, 255),
                         (51, 51, 51, 255),
                         (119, 119, 119, 255),
                         (170, 255, 102, 255),
                         (0, 136, 255, 255),
                         (187, 187, 187, 255), ]

        # self.pixels = pygame.PixelArray(self.font_surface)
        self.font_data = [0 for i in xrange(256)]
        self.letter_data = [0 for i in xrange(self.width*self.height)]
        self.palette_data = [0 for i in xrange(self.width*self.height)]

        #initialise the whole screen
        for pos in xrange(len(self.letter_data)):
            self.redraw(pos)

        # with open('petscii.txt','rb') as f:
        #     for line in f:
        #         i,dummy,word = line.strip().split()
        #         i,word= [int(v,16) for v in i,word]
        #         self.font_data[i] = word
        #         SetPixels(self.pixels,self.font_data[i])
        #         self.font_surfaces[i] = pygame.transform.scale(self.font_surface,(self.cell_size*self.scale_factor,self.cell_size*self.scale_factor))


    def readCallback(self,addr,value):
        #The display has a secret RNG, did you know that?
        if addr == self.letter_end:
            return int(random.getrandbits(32))
        bytes = [self.readByteCallback(addr + i, 0) for i in xrange(4)]
        return (bytes[0]) | (bytes[1]<<8) | (bytes[2]<<16) | (bytes[3]<<24)

    def pixel_width(self):
        return self.width*self.cell_size*self.scale_factor

    def writeCallback(self,addr,value):
        armv2.DebugLog('display write word %x %x\n' % (addr,value))
        for i in xrange(4):
            byte = value&0xff
            self.writeByteCallback(addr,byte)
            addr += 1
            value >>= 8
        return 0

    def readByteCallback(self,addr,value):
        if addr < self.letter_start:
            #It's the palette
            return self.palette_data[addr]
        elif addr < self.letter_end:
            pos = addr - self.letter_start
            return self.letter_data[pos]

    def writeByteCallback(self,addr,value):
        #armv2.DebugLog('display write byte %x %x\n' % (addr,value))
        if addr < self.letter_start:
            #It's the palette
            pos = addr
            if value == self.palette_data[pos]:
                #no change, ignore
                return 0
            self.palette_data[pos] = value
            self.redraw(pos)
        elif addr < self.letter_end:
            pos = addr - self.letter_start
            if value == self.letter_data[pos]:
                #no change, ignore
                return 0
            self.letter_data[pos] = value
            self.redraw(pos)
        return 0

    def redraw(self,pos):
        #armv2.DebugLog('redraw %d' % pos)
        letter = self.letter_data[pos]
        palette = self.palette_data[pos]
        back_colour = self.palette[(palette>>4)&0xf]
        fore_colour = self.palette[(palette)&0xf]
        self.back_quads[pos].SetColour(back_colour)
        self.fore_quads[pos].SetColour(fore_colour)
        tc = self.atlas.TextureCoords(chr(letter))
        self.fore_quads[pos].SetTextureCoordinates(tc)
        # tile = self.font_surfaces[letter]
        # tile.set_palette((back_colour,fore_colour))
        # dirty = (x*self.cell_size*self.scale_factor,
        #          y*self.cell_size*self.scale_factor,
        #          (x+1)*self.cell_size*self.scale_factor,
        #          (y+1)*self.cell_size*self.scale_factor)
        # self.screen.blit(tile,(dirty[0],dirty[1]))
        # self.dirty_rects[dirty] = True

    def Update(self):
        drawing.DrawNoTexture(self.back_quads_buffer)
        drawing.DrawAll(self.fore_quads_buffer, self.atlas.texture)

class Clock(armv2.Device):
    """
    A clock device
    """
    id = 0x92d177b0
    def operationCallback(self, arg0, arg1):
        pygame.time.set_timer(pygame.USEREVENT, arg0)
        return 0

    def fired(self):
        self.cpu.Interrupt(self.id, 0)


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
        self.rom_filename = cpu_rom
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
        self.tape_drive   = None
        self.status       = armv2.Status.Ok
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
        try:
            with self.cv:
                while self.running:
                    while self.running and \
                            ((self.steps_to_run == 0) or\
                                 (self.status == armv2.Status.WaitForInterrupt and not (self.cpu.pins & armv2.Pins.Interrupt))):
                        armv2.DebugLog('%d %d %x' % (self.steps_to_run,self.status,self.cpu.pins))
                        self.cv.wait(5)
                    self.status = self.cpu.Step(self.steps_to_run)
                    self.steps_to_run = 0
                    self.cv.notify()
        finally:
            #in case we exit this and leave running on (due to an exception say)
            self.running = False

    def Step(self,num):
        with self.cv:
            self.steps_to_run = num
            self.cv.notify()

    def StepAndWait(self,num):
        self.Step(num)
        with self.cv:
            while self.running:
                while self.running and (self.steps_to_run and self.status != armv2.Status.WaitForInterrupt):
                    self.cv.wait(0.1)
                    #Keep interrupts pumping every now and again
                    #self.cpu.Interrupt(6, 0)
                if not self.running:
                    break
                return self.status
            #if we get here it's not running
            raise RuntimeError('Thread is not running!')

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
        if self.tape_drive:
            self.tape_drive.Delete()

    def Interrupt(self, hw_id, code):
        armv2.DebugLog('Interrupting1')
        with self.cv:
            self.cpu.Interrupt(hw_id, code)
            armv2.DebugLog('Interrupting2')
            self.cv.notify()

    def Update(self):

        return
        # if self.tape_drive and self.tape_drive.loading:
        #     #We should do some kind of animation
        #     elapsed = pygame.time.get_ticks() - self.tape_drive.loading
        #     #draw lines of alternate background and foreground of 5 times the current data bytes length,
        #     #and then every 2 seconds change the background and foreground colours randomly
        #     if not self.loading_background or elapsed > 2000:
        #         self.loading_background = random.choice(self.display.palette)
        #         self.loading_foreground = random.choice(self.display.palette)
        #         while self.loading_foreground == self.loading_background:
        #             self.loading_foreground = random.choice(self.display.palette)
        #     data = self.tape_drive.data_byte
        #     colour_one,colour_two = self.loading_background, self.loading_foreground
        #     width,height = self.display.pixel_width(),self.display.pixel_height()
        #     pos = 0
        #     while pos < self.display.pixels():
        #         length = width*4 + data*10
        #         while length >= width:
        #             self.display.screen.fill(colour_one, pygame.Rect((pos%width,pos/width),((pos+length)
