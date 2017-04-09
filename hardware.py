import armv2
import pygame
import threading
import traceback
import signal
import time
import random
import drawing
import os
import numpy
import popcnt
import wave
import globals
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

from scipy.signal import butter, lfilter


def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq  = 0.5 * fs
    low  = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y


def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=True)
    return b, a

def butter_lowpass_filter(data, cutoff, fs, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = lfilter(b, a, data)
    return y

class TapeDrive(armv2.Device):
    """A Tape Drive

    It has three bytes. The first two are control bytes and the third data
    0 : control byte containing status for the user to read
    1 : control byte for the user to write to
    2 : data byte

    The protocol is: write NEXT_BYTE to the write control and the read control will change to NOT_READY until
    there is a data byte ready, when it will change to READY. Alternatively it might change to END_OF_TAPE or
    DRIVE_EMPTY.  It will generate interrupts for READY and END_OF_TAPE and DRIVE_EMPTY

    Optionally the user can write READY to the control byte signifying that the tape drive can remain at the
    current position and power down, the user is done with it for now.

    """
    id=0x2730eb6c

    stripe_height = 2
    border_pixels = 16

    class Codes:
        NEXT_BYTE   = 0
        NOT_READY   = 1
        END_OF_TAPE = 2
        DRIVE_EMPTY = 3
        READY       = 4

    def __init__(self, cpu):
        super(TapeDrive,self).__init__(cpu)
        self.status     = self.Codes.NOT_READY
        self.data_byte  = 0
        self.tape_name  = None
        self.tape       = None
        self.tape_sound = None
        self.running    = True
        self.playing    = False
        self.loading   = False
        self.end_callback = None
        self.lock = threading.Lock()
        self.current_bit = 0

        screen_width = self.cpu.display.pixel_width()
        screen_height = self.cpu.display.pixel_height()

        num_t_stripes = self.border_pixels / self.stripe_height
        num_l_stripes = (screen_height - (self.border_pixels * 2)) / self.stripe_height
        num_stripes = 2*(num_t_stripes + num_l_stripes)

        print num_stripes
        self.quad_buffer = drawing.QuadBuffer( num_stripes )
        #Add the stripes as a tuple for each row. The first few will have just one in (for the top rows that
        #go all the way across), then the middle lot will have 2, then the final sets will be one again
        self.stripes = []
        #First the bottom
        for i in xrange(num_t_stripes):
            q = drawing.Quad(self.quad_buffer)
            bl = Point(0, i*self.stripe_height)
            tr = Point(screen_width, (i+1) * self.stripe_height)
            q.SetVertices(bl, tr, 5)
            self.stripes.append([q])

        for i in xrange(num_t_stripes, num_t_stripes + num_l_stripes):
            row = []
            for j in xrange(2):
                q = drawing.Quad(self.quad_buffer)
                bl = Point(j*(screen_width - self.border_pixels), i*self.stripe_height)
                tr = Point(bl.x + self.border_pixels, (i+1) * self.stripe_height)
                q.SetVertices(bl, tr, 5)
                row.append(q)
            self.stripes.append(row)

        for i in xrange(num_t_stripes):
            row = num_t_stripes + num_l_stripes + i
            q = drawing.Quad(self.quad_buffer)
            bl = Point(0, row*self.stripe_height)
            tr = Point(screen_width, (row+1) * self.stripe_height)
            q.SetVertices(bl, tr, 5)
            self.stripes.append([q])

        for i,row in enumerate(self.stripes):
            for stripe in row:
                stripe.SetColour(Display.Colours.YELLOW if i&1 else Display.Colours.BLUE)

    def start_playing(self):
        if not self.tape_sound:
            return
        self.tape_sound.play()
        self.playing = True
        self.start_time = globals.t

    def stop_playing(self):
        if not self.tape_sound:
            return
        self.tape_sound.stop()
        self.playing = False

    def loadTape(self, filename):
        self.unloadTape()
        self.tape = open(filename, 'rb')
        self.tape_name = filename
        self.make_sound()

    def make_sound(self):
        freq, sample_size, num_channels = pygame.mixer.get_init()
        data = numpy.fromfile(self.tape, dtype='uint32')
        set_bits = popcnt.count_array(data)
        clr_bits = (len(data) * 32) - set_bits
        #The sigmals we're using are either 8 (4 on 4 off) or 16 samples at 22050 Hz, which is 
        #either 1378 or 2756 Hz
        tone_length = 4*float(freq)/22050
        clr_length = int(tone_length)
        set_length = int(tone_length*2)
        total_samples = 2*(set_bits*set_length + clr_bits*clr_length)
        samples = numpy.zeros(shape=total_samples, dtype='float64')
        #print 'ones={ones} zeros={zeros} length={l}'.format(ones=set_bits, zeros=clr_bits, l=float(total_samples)/freq)
        #The position in samples that each byte starts
        self.byte_samples = numpy.zeros(shape=len(data)*4, dtype='uint32')
        #The number of milliseconds that each bit should
        self.bit_times = numpy.zeros(shape=len(data)*4*8, dtype='uint32')
        self.bits = numpy.zeros(shape=len(data)*4*9, dtype='uint8')
        popcnt.create_samples(data, samples, self.byte_samples, self.bit_times, self.bits, clr_length, set_length, float(1000)/22050)
        #bandpass filter it to make it less harsh
        samples = butter_bandpass_filter(samples, 500, 2700, freq).astype('int16')

        if num_channels != 1:
            #Duplicate it into the required number of channels
            samples = samples.repeat(num_channels).reshape(total_samples, num_channels)

        self.tape_sound = pygame.sndarray.make_sound(samples)
        #rewind the tape so we can load from it correctly
        self.tape.seek(0)
        self.sample_rate = float(freq)/1000

    def registerCallback(self, callback):
        self.end_callback = callback

    def unloadTape(self):
        if self.tape:
            self.tape.close()
            self.tape = None
            self.tape_name = None
        if self.tape_sound:
            self.stop_playing()
            self.tape_sound = None

    def power_down(self):
        #We don't actually need to do any powering down, but alert any potential debugger that they can update
        #their symbols
        self.stop_playing()
        self.end_callback()

    def readByteCallback(self,addr,value):
        if addr == 0:
            #They want the current status
            return self.status
        elif addr == 1:
            #They really shouldn't be reading this one
            return 0
        elif addr == 2:
            return self.data_byte

    def is_byte_ready(self):
        elapsed = globals.t - self.start_time
        current_byte = self.tape.tell()
        if current_byte >= len(self.byte_samples):
            return True

        #return True
        return elapsed * self.sample_rate > self.byte_samples[current_byte]

    def feed_byte(self):
        c = self.tape.read(1)
        if c:
            self.data_byte = ord(c)
            #self.tape_data = self.tape_data[-((len(self.stripes)/8)):] + [self.data_byte]
            #self.tape_data.extend( [((self.data_byte >> i) & 1) for i in xrange(8)] )
            # #How quickly should we show those bytes? Pretend that they arrived in even intervals
            # if self.last_byte_time is None:
            #     self.last_byte_time = globals.t
            #     #Just put these on straight away
            #     self.tape_times.extend( [globals.t]*8 )
            # else:
            #     elapsed = globals.t - self.last_byte_time
            #     print 'elapsed',elapsed
            #     self.tape_times.extend( [globals.t + int(i*float(elapsed)/8) for i in xrange(8)] )
            #     self.last_byte_time = globals.t
            self.status = self.Codes.READY
            #time.sleep(0.001)
            self.cpu.cpu.Interrupt(self.id, self.status)

        else:
            self.data_byte = 0
            self.status = self.Codes.END_OF_TAPE
            self.loading = False
            self.stop_playing()
            self.cpu.cpu.Interrupt(self.id, self.status)

    def update(self):
        
        if not self.playing:
            return

        if self.status == self.Codes.NOT_READY:
            #We're waiting, so check if it's time for the next byte
            if self.is_byte_ready():
                self.feed_byte()

        elapsed = globals.t - self.start_time

        #The stripes should be all the ones up to that position. If we don't have anything
        #Use zeroes
        
        if self.current_bit >= len(self.bit_times) or self.bit_times[self.current_bit] > elapsed:
            return

        #We've got some to show, how many
        try:
            while self.bit_times[self.current_bit] <= elapsed:
                self.current_bit += 1
        except IndexError:
            self.current_bit = len(self.bit_times)

        stripe_pos = 0
        bit_pos = 0
        while stripe_pos < len(self.stripes):
            try:
                bit = self.bits[self.current_bit + bit_pos]
            except IndexError:
                bit = 0

            #steps = 2 if bit else 1
            colour = [Display.Colours.BLUE, Display.Colours.YELLOW][bit]
            steps = 1

            for q in self.stripes[stripe_pos]:
                q.SetColour(colour)

            # try:
            #     for i in xrange(steps):
            #         for q in self.stripes[stripe_pos + i]:
            #             q.SetColour(Display.Colours.BLUE)
            #         for q in self.stripes[stripe_pos + steps + i]:
            #             q.SetColour(Display.Colours.YELLOW)
            # except IndexError:
            #     #print 'ie',stripe_pos
            #     break

            bit_pos += 1
            #stripe_pos += steps*2
            stripe_pos += 1

        drawing.DrawNoTexture(self.quad_buffer)
        

    def writeByteCallback(self,addr,value):
        if addr == 0:
            #Trying to write to the read register. :(
            pass
        elif addr == 1:
            if 1:
                if value == self.Codes.NEXT_BYTE:
                    #They want the next byte, are we ready for them?
                    #self.loading = pygame.time.get_ticks()

                    if self.tape:
                        #Have we progressed enough to give the next byte?
                        if not self.playing:
                            self.start_playing()

                        if self.is_byte_ready():
                            #Great you can have a byte
                            self.feed_byte()
                        else:
                            #Not ready for one yet
                            self.data_byte = 0
                            self.status = self.Codes.NOT_READY

                    else:
                        self.data_byte = 0
                        self.status = self.Codes.DRIVE_EMPTY
                        self.cpu.cpu.Interrupt(self.id, self.status)
                elif value == self.Codes.READY:
                    #power down
                    self.power_down()
        elif addr == 2:
            #Can't write to the data byte
            pass
        return 0;

    def Delete(self):
        return

class Display(armv2.Device):
    """
    A Display

    Mapped memory looks like this:

    0x000 - 0x4b0 : Letter array, 1 byte for every pixel starting at the bottom left, where the high nibble
                    represents the background colour and the low nibble the foreground colour
    0x4b0 - 0x960 : Same as above, but each byte represents the ascii code for the character displayed

    """
                    
    class Colours:
        BLACK       = (0, 0, 0, 255)
        WHITE       = (255, 255, 255, 255)
        RED         = (136, 0, 0, 255)
        CYAN        = (170, 255, 238, 255)
        VIOLET      = (204, 68, 204, 255)
        GREEN       = (0, 204, 85, 255)
        BLUE        = (0, 0, 170, 255)
        YELLOW      = (238, 238, 119, 255)
        ORANGE      = (221, 136, 85, 255)
        BROWN       = (102, 68, 0, 255)
        LIGHT_RED   = (255, 119, 119, 255)
        DARK_GREY   = (51, 51, 51, 255)
        MED_GREY    = (119, 119, 119, 255)
        LIGHT_GREEN = (170, 255, 102, 255)
        LIGHT_BLUE  = (0, 136, 255, 255)
        LIGHT_GREY  = (187, 187, 187, 255)

        palette = [ BLACK   , WHITE      , RED       , CYAN, 
                    VIOLET  , GREEN      , BLUE      , YELLOW, 
                    ORANGE  , BROWN      , LIGHT_RED , DARK_GREY,
                    MED_GREY, LIGHT_GREEN, LIGHT_BLUE, LIGHT_GREY ]


    id = 0x9d99389e
    width  = 40
    height = 30
    cell_size = 8
    pixel_size = (width*cell_size, height*cell_size)
    palette_start = 0
    letter_start  = width*height
    letter_end    = width*height*2
    def __init__(self, cpu, scale_factor):
        super(Display,self).__init__(cpu)
        self.dirty_rects = {}
        self.scale_factor = scale_factor
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

        self.font_data = [0 for i in xrange(256)]
        self.letter_data = [0 for i in xrange(self.width*self.height)]
        self.palette_data = [0 for i in xrange(self.width*self.height)]

        #initialise the whole screen
        for pos in xrange(len(self.letter_data)):
            self.redraw(pos)

    def readCallback(self,addr,value):
        #The display has a secret RNG, did you know that?
        if addr == self.letter_end:
            return int(random.getrandbits(32))
        if addr == self.letter_end + 4:
            return int(time.time())
        bytes = [self.readByteCallback(addr + i, 0) for i in xrange(4)]
        return (bytes[0]) | (bytes[1]<<8) | (bytes[2]<<16) | (bytes[3]<<24)

    def pixel_width(self):
        return self.width * self.cell_size * self.scale_factor

    def pixel_height(self):
        return self.height * self.cell_size * self.scale_factor

    def writeCallback(self,addr,value):
        armv2.DebugLog('display write word %x %x\n' % (addr,value))
        if addr == self.letter_end:
            random.seed(value)
            return 0
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
        letter = self.letter_data[pos]
        palette = self.palette_data[pos]
        back_colour = self.Colours.palette[(palette>>4)&0xf]
        fore_colour = self.Colours.palette[(palette)&0xf]
        self.back_quads[pos].SetColour(back_colour)
        self.fore_quads[pos].SetColour(fore_colour)
        tc = self.atlas.TextureCoords(chr(letter))
        self.fore_quads[pos].SetTextureCoordinates(tc)

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

    def threadMainLoop(self):
        while self.running and \
              ((self.steps_to_run == 0) or\
               (self.status == armv2.Status.WaitForInterrupt and not (self.cpu.pins & armv2.Pins.Interrupt))):
            armv2.DebugLog('%d %d %x' % (self.steps_to_run,self.status,self.cpu.pins))
            self.cv.wait(5)
            if self.steps_to_run > 0:
                self.status = self.cpu.Step(self.steps_to_run)
            self.steps_to_run = 0
            self.cv.notify()

    def threadMain(self):
        try:
            with self.cv:
                while self.running:
                    self.threadMainLoop()
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
        #print 'Interrupting1'
        with self.cv:
            self.cpu.Interrupt(hw_id, code)
            #If the CPU is presently paused, it won't ever know it's received an interrupt, it needs to take one step
            #to take the exception
            if self.steps_to_run == 0:
                self.steps_to_run = 1
            self.cv.notify()

    def is_waiting(self):
        return self.status == armv2.Status.WaitForInterrupt

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
