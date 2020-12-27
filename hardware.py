import armv2
import pygame
import threading
import traceback
import signal
import time
import random
from . import drawing
import os
import numpy
import wave
import struct

from . import globals
from .globals.types import Point
import armv2_emulator

def byte_reverse(x):
    out = 0
    for i in range(8):
        b = (x >> i) & 1
        out |= b << (7-i)

    return out

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
        super(Keyboard, self).__init__(cpu)
        self.ring_buffer = [0 for i in range(self.ringbuffer_size)]
        self.pos = 0
        self.key_state = 0

    def key_down(self, key):
        armv2.debug_log('key down ' + str(key))
        self.key_state |= (1 << key)
        self.ring_buffer[self.pos] = key
        self.pos += 1
        if self.pos == len(self.ring_buffer):
            self.pos = 0
        self.cpu.interrupt(self.id, self.InterruptCodes.KEY_DOWN)

    def key_up(self, key):
        armv2.debug_log('key up ' + str(key))
        self.key_state &= ~(1 << key)
        self.cpu.interrupt(self.id, self.InterruptCodes.KEY_UP)

    def read_callback(self, addr, value):
        armv2.debug_log('keyboard reader %x %x\n' % (addr, value))
        if addr < self.ringbuffer_start:
            # It's a state request
            return (self.key_state >> (8 * addr) & 0xffffffff)
        elif addr < self.ringbuffer_pos:
            pos = addr - self.ringbuffer_start
            bytes = [self.ring_buffer[pos + i % len(self.ring_buffer)] for i in range(4)]
            return (bytes[0]) | (bytes[1] << 8) | (bytes[2] << 16) | (bytes[3] << 24)
        elif addr == self.ringbuffer_pos:
            return self.pos

        return 0

    def read_byte_callback(self, addr, value):
        armv2.debug_log('keyboard reader byte %x %x\n' % (addr, value))
        if addr < self.ringbuffer_start:
            # It's a state request
            return (self.key_state >> (8 * addr) & 0xff)
        elif addr < self.ringbuffer_pos:
            pos = addr - self.ringbuffer_start
            out = self.ring_buffer[pos]
            armv2.debug_log('Read key data %d\n' % out)
            return out
        elif addr == self.ringbuffer_pos:
            return self.pos
        else:
            return 0

    def write_callback(self, addr, value):
        armv2.debug_log('keyboard writer %x %x\n' % (addr, value))
        return 0

    def write_byte_callback(self, addr, value):
        armv2.debug_log('keyboard writer %x %x\n' % (addr, value))
        return 0


def set_pixels(pixels, word):
    for j in range(64):
        # the next line is so obvious it doesn't need a comment
        pixels[j // 8][j % 8] = ((word >> j) & 1)


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
    id = 0x2730eb6c

    stripe_height = 2
    border_pixels = 16

    class Codes:
        NEXT_BYTE   = 0
        NOT_READY   = 1
        END_OF_TAPE = 2
        DRIVE_EMPTY = 3
        READY       = 4

    def __init__(self, cpu):
        super(TapeDrive, self).__init__(cpu)
        self.status        = self.Codes.NOT_READY
        self.data_byte     = 0
        self.tape          = None
        self.entered_pilot = False
        self.entered_first_pilot = False
        self.running       = True
        self.playing       = False
        self.loading       = False
        self.end_callback  = None
        self.skipped       = False
        self.open          = False
        self.lock          = threading.Lock()
        self.paused        = False
        self.rewinding     = None
        self.fast_forwarding = None
        self.loading       = False
        freq, sample_size, num_channels = pygame.mixer.get_init()
        self.sample_rate = float(freq) / 1000
        self.start_time  = None
        self.last_time   = None
        self.wind_time   = None
        self.pause_start = None


        screen_width  = self.cpu.display.pixel_width()
        screen_height = self.cpu.display.pixel_height()

        num_t_stripes = self.border_pixels // self.stripe_height
        num_l_stripes = (screen_height - (self.border_pixels * 2)) // self.stripe_height
        num_stripes   = 2 * (num_t_stripes + num_l_stripes)

        self.quad_buffer = drawing.QuadBuffer(num_stripes)
        # Add the stripes as a tuple for each row. The first few will have just one in (for the top rows that
        # go all the way across), then the middle lot will have 2, then the final sets will be one again
        self.stripes = []
        # First the bottom
        for i in range(num_t_stripes):
            q = drawing.Quad(self.quad_buffer)
            bl = Point(0, i * self.stripe_height)
            tr = Point(screen_width, (i + 1) * self.stripe_height)
            q.set_vertices(bl, tr, 5)
            self.stripes.append([q])

        for i in range(num_t_stripes, num_t_stripes + num_l_stripes):
            row = []
            for j in range(2):
                q = drawing.Quad(self.quad_buffer)
                bl = Point(j * (screen_width - self.border_pixels), i * self.stripe_height)
                tr = Point(bl.x + self.border_pixels, (i + 1) * self.stripe_height)
                q.set_vertices(bl, tr, 5)
                row.append(q)
            self.stripes.append(row)

        for i in range(num_t_stripes):
            row = num_t_stripes + num_l_stripes + i
            q = drawing.Quad(self.quad_buffer)
            bl = Point(0, row * self.stripe_height)
            tr = Point(screen_width, (row + 1) * self.stripe_height)
            q.set_vertices(bl, tr, 5)
            self.stripes.append([q])

        for i, row in enumerate(self.stripes):
            for stripe in row:
                stripe.set_colour(Display.Colours.YELLOW if i & 1 else Display.Colours.BLUE)

    def copy_from(self, other):
        self.status = other.status
        self.tape          = other.tape
        self.entered_pilot = other.entered_pilot
        self.entered_first_pilot = other.entered_first_pilot
        self.running       = other.running
        self.playing       = other.playing
        self.loading       = other.loading
        self.end_callback  = other.end_callback
        self.skipped       = other.skipped
        self.open          = other.open
        self.paused        = other.paused
        self.rewinding     = other.rewinding
        self.fast_forwarding = other.fast_forwarding
        self.loading       = other.loading
        self.pause_start    = other.pause_start

        self.start_time  = other.start_time
        self.last_time   = other.last_time
        self.wind_time   = other.wind_time


    def start_playing(self):
        if not self.tape:
            return
        if not self.paused:
            self.tape.play_sound()
        self.skipped = False
        self.playing = True
        self.start_time = globals.t
        self.last_time = self.start_time

    def stop_playing(self):
        if not self.tape:
            return
        if not self.paused:
            self.tape.stop_sound()
        self.playing = False
        self.start_time  = None
        self.last_time = None


    def pause(self):
        self.paused = True
        self.pause_start = globals.t
        if self.playing:
            self.tape.stop_sound()

    def unpause(self):

        if self.rewinding or self.fast_forwarding:
            self.wind_time += self.pause_time
        self.paused = False
        self.pause_start = None

        if self.playing:
            self.tape.play_sound()

    @property
    def pause_time(self):
        if not self.paused:
            return 0
        return globals.t - self.pause_start

    def rewind(self, callback):
        #TODO: Base this on the current position and the tape length
        if not self.tape:
            callback()
            return
        duration = 1000
        self.wind_time = globals.t + duration
        self.rewinding = callback
        self.fast_forwarding = None

    def fast_forward(self, callback):
        if not self.tape:
            callback()
            return
        duration = 1000
        self.wind_time = globals.t + duration
        self.fast_forwarding = callback
        self.rewinding = None

    def stop_winding(self):
        self.rewinding = self.fast_forwarding = self.wind_time = None

    def load_tape(self, tape):
        self.unload_tape()
        self.tape = tape

        #self.tape.block_pos = 0
        #self.tape.current_block = 0
        #self.tape = open(filename, 'rb')
        #self.tape_name = filename

    def register_callback(self, callback):
        self.end_callback = callback

    def unload_tape(self):
        if self.tape:
            #self.tape.current_block = 0
            #self.tape.current_bit = 0
            #self.block_pos = 0
            self.tape = None
            self.stop_playing()

    def power_down(self):
        # We don't actually need to do any powering down, but alert any potential debugger that they can update
        # their symbols
        self.stop_playing()
        self.loading = False
        self.entered_pilot = False
        self.entered_first_pilot = False
        if self.end_callback is not None:
            self.end_callback()

    def read_byte_callback(self, addr, value):
        if addr == 0:
            # They want the current status
            return self.status
        elif addr == 1:
            # They really shouldn't be reading this one
            return 0
        elif addr == 2:
            return self.data_byte

    def skip_loading(self):
        if self.playing:
            self.tape.sound.stop()
            self.skipped = True

    def is_byte_ready(self):
        if not self.tape or not self.playing:
            return False

        return self.tape.byte_ready() or self.skipped

    def feed_byte(self):
        try:
            if not self.tape or self.open:
                raise IndexError

            c = self.tape.get_byte()
        except IndexError:
            c = None

        if c is not None:
            self.data_byte = c
            #self.tape_data = self.tape_data[-((len(self.stripes)//8)):] + [self.data_byte]
            #self.tape_data.extend( [((self.data_byte >> i) & 1) for i in xrange(8)] )
            # #How quickly should we show those bytes? Pretend that they arrived in even intervals
            # if self.last_byte_time is None:
            #     self.last_byte_time = globals.t
            #     #Just put these on straight away
            #     self.tape_times.extend( [globals.t]*8 )
            # else:
            #     elapsed = globals.t - self.last_byte_time
            #     print 'elapsed',elapsed
            #     self.tape_times.extend( [globals.t + int(i*float(elapsed)//8) for i in xrange(8)] )
            #     self.last_byte_time = globals.t
            self.status = self.Codes.READY
            # time.sleep(0.001)
            self.cpu.cpu.interrupt(self.id, self.status)

        else:
            self.data_byte = 0
            self.status = self.Codes.NOT_READY if self.paused else self.Codes.END_OF_TAPE
            self.loading = False
            self.stop_playing()
            self.cpu.cpu.interrupt(self.id, self.status)

    def update(self):

        if self.rewinding:
            if globals.t >= self.wind_time + self.pause_time:
                self.rewinding()
                self.rewinding = None
                self.wind_time = None
                if self.tape:
                    self.tape.rewind()
            return

        if self.fast_forwarding:
            if globals.t >= self.wind_time + self.pause_time:
                self.fast_forwarding()
                self.fast_forwarding = None
                if self.tape:
                    self.tape.fast_forward()
            return

        try:
            if self.playing:
                wall_elapsed = globals.t - self.last_time
                self.last_time = globals.t
                bits, stage = self.tape.update(wall_elapsed, self.paused, len(self.stripes))
                #elapsed = globals.t - self.start_time[self.tape.current_block]
            else:
                bits = None
                stage = armv2_emulator.tapes.TapeStage.no_data
        except IndexError:
            # We reached the end of the tape
            self.power_down()
            return

        if not self.loading:
            return

        if self.entered_first_pilot and self.status == self.Codes.NOT_READY:
            # We're waiting, so check if it's time for the next byte
            if self.is_byte_ready():
                self.feed_byte()

        if bits is None or not self.entered_first_pilot:
            # In this phase we do rolling bars of grey and red
            if bits is None and not self.entered_pilot:
                if stage == armv2_emulator.tapes.TapeStage.tone:
                    if self.end_callback:
                        self.end_callback()
                    self.entered_pilot = True
                    self.entered_first_pilot = True

            if self.playing and not self.paused and stage is armv2_emulator.tapes.TapeStage.tone:
                pos = float(globals.t - self.start_time) / 20
                colours = (Display.Colours.MED_GREY, Display.Colours.RED)
            else:
                pos = 0
                colours = (Display.Colours.RED, Display.Colours.RED)

            for i, stripes in enumerate(self.stripes):
                if ((i + 8 - pos) % 12) >= 4:
                    colour = colours[0]
                else:
                    colour = colours[1]
                for q in stripes:
                    q.set_colour(colour)

        else:
            # The stripes should be all the ones up to that position. If we don't have anything
            # Use zeroes
            self.entered_pilot = False

            if len(bits) == 0:
                #The tape returns a set of empty bits when it's done
                return

            stripe_pos = 0
            bit_pos = 0
            while stripe_pos < len(self.stripes):
                try:
                    bit = bits[bit_pos]
                except IndexError:
                    bit = 0

                #steps = 2 if bit else 1
                colour = [Display.Colours.BLUE, Display.Colours.YELLOW][bit]
                steps = 1

                for q in self.stripes[stripe_pos]:
                    q.set_colour(colour)

                # try:
                #     for i in xrange(steps):
                #         for q in self.stripes[stripe_pos + i]:
                #             q.set_colour(Display.Colours.BLUE)
                #         for q in self.stripes[stripe_pos + steps + i]:
                #             q.set_colour(Display.Colours.YELLOW)
                # except IndexError:
                #     #print 'ie',stripe_pos
                #     break

                bit_pos += 1
                #stripe_pos += steps*2
                stripe_pos += 1

        drawing.draw_no_texture(self.quad_buffer)

    def write_byte_callback(self, addr, value):
        if addr == 0:
            # Trying to write to the read register. :(
            pass
        elif addr == 1:
            if value == self.Codes.NEXT_BYTE:
                # They want the next byte, are we ready for them?
                #self.loading = pygame.time.get_ticks()

                if self.tape:
                    # Have we progressed enough to give the next byte?
                    #if not self.playing:
                    #    self.start_playing()
                    self.loading = True

                    if self.is_byte_ready():
                        # Great you can have a byte
                        self.feed_byte()
                    else:
                        # Not ready for one yet
                        self.data_byte = 0
                        self.status = self.Codes.NOT_READY

                else:
                    self.data_byte = 0
                    self.status = self.Codes.DRIVE_EMPTY
                    self.cpu.cpu.interrupt(self.id, self.status)
            elif value == self.Codes.READY:
                # power down
                self.power_down()
        elif addr == 2:
            # Can't write to the data byte
            pass
        return 0

    def delete(self):
        self.power_down()


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

        palette = [BLACK, WHITE, RED, CYAN,
                   VIOLET, GREEN, BLUE, YELLOW,
                   ORANGE, BROWN, LIGHT_RED, DARK_GREY,
                   MED_GREY, LIGHT_GREEN, LIGHT_BLUE, LIGHT_GREY]

    id = 0x9d99389e
    width  = 40
    height = 30
    cell_size = 8
    pixel_size = (width * cell_size, height * cell_size)
    # The palette data is a byte for each 8x8 "cell" that gives the background and foreground colour in each
    # of its nibbles
    palette_start = 0
    # The letter data is a byte for each cell which gives which character is drawn at that cell
    letter_start  = width * height
    letter_end    = width * height * 2
    # The font data is 256 8 byte words, each of which is bitmask for that character. The first half is fixed
    # (writes to it are rejected without error), but the second half can be customized
    font_start    = letter_end
    font_end      = font_start + 0x100*8
    # The framebuffer is a bitmask for all (width*cellsize) * (height*cellsize) pixels on the screen. If the
    # bit is set then it has the foreground colour, otherwise it has the background colour. Software running
    # on the device can either write to the letter data to draw a character to a cell, or write directly to
    # the framebuffer
    frame_buffer_start = font_end
    frame_buffer_end = frame_buffer_start + ((width * cell_size * height * cell_size)//8)

    def __init__(self, cpu, scale_factor):
        super(Display, self).__init__(cpu)
        self.dirty_rects = {}
        self.scale_factor = scale_factor
        #self.atlas = drawing.texture.PetsciiAtlas(os.path.join('fonts', 'petscii.png'))

        self.cell_quads_buffer = drawing.QuadBuffer(self.width * self.height)
        self.fore_vertex_buffer = drawing.VertexBuffer(self.pixel_size[0] * self.pixel_size[1])
        self.cell_quads = [drawing.Quad(self.cell_quads_buffer) for i in range(self.width * self.height)]

        # The shape of this pixel data is an unfortunate side effect of trying to cram it all in in one large
        # uniform; 2400 uint32s is too many, so we're using 600 uvec4s. We could instead do 4 draw calls with
        # the screen partitioned and change the uniform portion each time, but this is what we're doing for
        # now.
        #
        # Each element of the pixel data has 4x32 = 128 bits. The screen is 320 pixels across, so it doesn't
        # really line up nicely. Note that the pixel data is stored from the bottom of the screen up (as
        # that's how we draw it to the screen in our opengl), but we want the CPU to see it from the top down,
        # so we do that translation in the memory accesses
        self.pixel_data_words = numpy.zeros((self.pixel_size[0] * self.pixel_size[1] // (32*4), 4), numpy.uint32)
        self.pixel_data = self.pixel_data_words.view(dtype = numpy.uint8).reshape( (self.pixel_size[1], (self.pixel_size[0] // 8)) )
        self.crt_buffer = drawing.opengl.CrtBuffer(*self.pixel_size)
        self.powered_on = True

        for pos, quad in enumerate(self.cell_quads):
            x = pos % self.width
            y = self.height - 1 - (pos // self.width)
            bl = Point(x * self.cell_size, y * self.cell_size)
            tr = bl + Point(self.cell_size, self.cell_size)
            quad.set_vertices(bl, tr, 0)

        self.font_data = [0 for i in range(256)]
        self.letter_data = [0 for i in range(self.width * self.height)]
        self.palette_data = [0 for i in range(self.width * self.height)]

        with open(os.path.join(globals.dirs.fonts,'petscii.txt'),'r') as f:
            for line in f:
                i, word = line.strip().split(' : ')
                i, word = [int(v,16) for v in (i,word)]
                #Each 64 bit word reprents all the bits of an 8x8 cell, but it's easier to store them as 8
                #rows of a byte each as that's how they'll get written to memory
                self.font_data[i] = numpy.array([ byte_reverse(((word >> (i*8)) & 0xff)) for i in range(8) ], dtype = numpy.uint8)

        # initialise the whole screen
        for pos in range(len(self.letter_data)):
            self.redraw_colours(pos)
            self.redraw(pos)

        self.dirty = set()
        self.dirty_colours = set()

    def power_down(self):
        self.powered_on = False

    def read_callback(self, addr, value):
        # The display has a secret RNG, did you know that?
        if addr == self.frame_buffer_end:
            return int(random.getrandbits(32))
        if addr == self.frame_buffer_end + 4:
            return int(time.time())

        # If it's an aligned read from the frame buffer then it's easier for us to do it directly
        if 0 == (addr & 3) and addr >= self.frame_buffer_start and addr < self.frame_buffer_end:
            word = self.cpu_to_screen(addr - self.frame_buffer_start) // 4
            return self.pixel_data_words[word // 4][word & 3]

        # Otherwise we handle it byte-wise

        bytes = [self.read_byte_callback(addr + i, 0) for i in range(4)]
        return (bytes[0]) | (bytes[1] << 8) | (bytes[2] << 16) | (bytes[3] << 24)

    def pixel_width(self):
        return self.width * self.cell_size * self.scale_factor

    def pixel_height(self):
        return self.height * self.cell_size * self.scale_factor

    def cpu_to_screen(self, offset):
        offset *= 8
        x, y = offset % self.pixel_size[0], offset // self.pixel_size[0]
        y = self.pixel_size[1] - 1 - y
        out = ((y * self.pixel_size[0]) + x) // 8
        return out


    def write_callback(self, addr, value):
        if addr == self.letter_end:
            random.seed(value)
            return 0

        # If it's an aligned read from the frame buffer then it's easier for us to do it directly
        if 0 == (addr & 3) and addr >= self.frame_buffer_start and addr < self.frame_buffer_end:
            word = self.cpu_to_screen(addr - self.frame_buffer_start) // 4
            self.pixel_data_words[word // 4][word & 3] = value
            return 0

        for i in range(4):
            byte = value & 0xff
            self.write_byte_callback(addr, byte)
            addr += 1
            value >>= 8
        return 0

    def read_byte_callback(self, addr, value):
        if addr < self.letter_start:
            # It's the palette
            return self.palette_data[addr]
        elif addr < self.letter_end:
            pos = addr - self.letter_start
            return self.letter_data[pos]
        elif addr < self.font_end:
            pos = addr - self.font_start
            return self.font_data[pos // 8][pos & 7]
        elif addr < self.frame_buffer_end:
            pos = self.cpu_to_screen(addr - self.frame_buffer_start)
            word = pos // 4
            word = self.pixel_data_words[word // 4][word & 3]
            byte = pos & 3
            return (word >> (byte * 8)) & 0xff

    def write_byte_callback(self, addr, value):
        if addr < self.letter_start:
            # It's the palette
            pos = addr
            if value == self.palette_data[pos]:
                # no change, ignore
                return 0
            self.palette_data[pos] = value
            #self.redraw_colours(pos)
            self.dirty_colours.add(pos)
        elif addr < self.letter_end:
            pos = addr - self.letter_start
            if value == self.letter_data[pos]:
                # no change, ignore
                return 0
            self.letter_data[pos] = value
            #self.redraw(pos)
            self.dirty.add(pos)
        elif addr < self.font_end:
            pos = addr - self.font_start
            if pos // 8 >= 0x80:
                self.font_data[pos // 8][7-(pos & 7)] = value
        elif addr < self.frame_buffer_end:
            pos = self.cpu_to_screen(addr - self.frame_buffer_start)
            word = pos // 4
            old_word = self.pixel_data_words[word // 4][word & 3]
            shift = (pos & 3) * 8
            mask = 0xffffffff ^ (0xff << shift)
            self.pixel_data_words[word // 4][word & 3] = (old_word & mask) | (value << shift)
        return 0

    def redraw_colours(self, pos):
        palette = self.palette_data[pos]
        back_colour = self.Colours.palette[(palette >> 4) & 0xf]
        fore_colour = self.Colours.palette[(palette) & 0xf]
        self.cell_quads[pos].set_colour(fore_colour)
        self.cell_quads[pos].set_back_colour(back_colour)

    def redraw(self, pos):
        letter = self.letter_data[pos]
        letter_bits = self.font_data[letter]

        x = pos % self.width
        y = self.height - 1 - (pos // self.width)

        self.pixel_data[y*8:(y+1)*8, x] = letter_bits

    def new_frame(self):
        drawing.new_crt_frame(self.crt_buffer)
        # self.crt_buffer.bind_for_writing()
        redraw = self.dirty
        redraw_colours = self.dirty_colours
        self.dirty = set()
        self.dirty_colours = set()
        for pos in redraw:
            self.redraw(pos)
        for pos in redraw_colours:
            self.redraw_colours(pos)

        #self.dirty = set()
        if self.powered_on:
            drawing.draw_pixels(self.cell_quads_buffer, self.pixel_data_words)
            #drawing.draw_no_texture(self.fore_vertex_buffer)

    def end_frame(self):
        drawing.end_crt_frame(self.crt_buffer)

    def draw_to_screen(self):
        drawing.draw_crt_to_screen(self.crt_buffer)


class Clock(armv2.Device):
    """
    A clock device
    """
    id = 0x92d177b0

    def operation_callback(self, arg0, arg1):
        pygame.time.set_timer(pygame.USEREVENT, arg0)
        return 0

    def fired(self):
        self.cpu.interrupt(self.id, 0)


class MemPassthrough(object):
    def __init__(self, cv, accessor):
        self.cv = cv
        self.accessor = accessor

    def __getitem__(self, index):
        with self.cv:
            return self.accessor.__getitem__(index)

    def __setitem__(self, index, values):
        with self.cv:
            return self.accessor.__setitem__(index, values)

    def __len__(self):
        with self.cv:
            return self.accessor.__len__()


class Machine:
    def __init__(self, cpu_size, cpu_rom):
        self.rom_filename = cpu_rom
        self.cpu          = armv2.Armv2(size=cpu_size, filename=cpu_rom)
        self.hardware     = []
        self.running      = True
        self.steps_to_run = 0
        # I'm not sure why I need a regular lock here rather than the default (A RLock), but with the default
        # I get weird deadlocks on KeyboardInterrupt
        self.cv           = threading.Condition(threading.Lock())
        self.mem          = MemPassthrough(self.cv, self.cpu.mem)
        self.memw         = MemPassthrough(self.cv, self.cpu.memw)
        self.thread       = threading.Thread(target=self.thread_main)
        self.tape_drive   = None
        self.status       = armv2.Status.OK
        self.thread.start()

    @property
    def regs(self):
        with self.cv:
            return self.cpu.regs

    @regs.setter
    def regs(self, value):
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

    @property
    def pc_value(self):
        with self.cv:
            return self.cpu.pc & 0x03fffffc

    @property
    def cpsr(self):
        mode = self.mode
        cpsr = self.regs[15] & 0xfc000000
        return mode | cpsr

    def thread_main_loop(self):
        while self.running and \
            ((self.steps_to_run == 0) or
             (self.status == armv2.Status.WAIT_FOR_INTERRUPT and not (self.cpu.pins & armv2.Pins.INTERRUPT))):
            self.cv.wait(5)
            num_left = self.steps_to_run
            if self.steps_to_run > 0:
                #self.cv.release()
                #self.cv.notify()
                self.status, num_left = self.cpu.step(self.steps_to_run)
                #self.cv.acquire()
            if num_left != self.steps_to_run:
                armv2.debug_log(f'{self.steps_to_run=:d} {self.status=:x} {num_left=} {self.cpu.pins=:x}')
            self.steps_to_run = 0
            self.cv.notify()

    def thread_main(self):
        try:
            with self.cv:
                while self.running:
                    self.thread_main_loop()
        finally:
            # in case we exit this and leave running on (due to an exception say)
            self.running = False

    def step(self, num):
        with self.cv:
            self.steps_to_run = int(num)
            self.cv.notify()

    def step_and_wait(self, num):
        self.step(num)

        with self.cv:
            while self.running:
                while self.running and (self.steps_to_run and self.status != armv2.Status.WAIT_FOR_INTERRUPT):
                    self.cv.wait(0.1)

                if not self.running:
                    break
                return self.status
            # if we get here it's not running
            raise RuntimeError('Thread is not running!')

    def add_hardware(self, device, name=None):
        with self.cv:
            self.cpu.add_hardware(device)
        self.hardware.append(device)
        if name is not None:
            setattr(self, name, device)
            setattr(device, 'name', name)

    def set_breakpoint(self, addr):
        self.cpu.set_breakpoint(addr)

    def unset_breakpoint(self, addr):
        self.cpu.unset_breakpoint(addr)

    def set_watchpoint(self, type, addr):
        self.cpu.set_watchpoint(type, addr)

    def unset_watchpoint(self, type, addr):
        self.cpu.unset_watchpoint(type, addr)

    def reset_breakpoints(self):
        self.cpu.reset_breakpoints()

    def reset_watchpoints(self):
        self.cpu.reset_watchpoints()

    def delete(self):
        with self.cv:
            self.running = False
            self.cv.notify()
        armv2.debug_log('joining thread')
        self.thread.join()
        armv2.debug_log('Killed')
        if self.tape_drive:
            self.tape_drive.delete()

    def interrupt(self, hw_id, code):
        with self.cv:
            self.cpu.interrupt(hw_id, code)
            # If the CPU is presently paused, it won't ever know it's received an interrupt, it needs to take
            # one step to take the exception
            if self.steps_to_run == 0:
                self.steps_to_run = 1
            self.cv.notify()

    def is_waiting(self):
        return self.status == armv2.Status.WAIT_FOR_INTERRUPT

    def update(self):

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
        #             self.display.screen.fill(colour_one, pygame.Rect((pos%width,pos // width),((pos+length)
