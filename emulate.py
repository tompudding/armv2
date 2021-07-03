import sys
from . import armv2  # type: ignore
from . import debugger
from . import hardware
from . import drawing
import os
import binascii
import pygame
from . import globals
from .globals.types import Point
from pygame.locals import *
from optparse import OptionParser
from . import sounds


def new_machine(boot_rom):
    machine = hardware.Machine(cpu_size=1 << 18, cpu_rom=boot_rom)
    try:
        machine.add_hardware(hardware.Keyboard(machine), name="keyboard")
        machine.add_hardware(hardware.Display(machine, scale_factor=1), name="display")
        machine.add_hardware(hardware.Clock(machine), name="clock")
        machine.add_hardware(hardware.TapeDrive(machine), name="tape_drive")
    except:
        machine.delete()
        raise
    return machine


class Emulator(object):
    # Speeds are cycles per ms
    speeds = [0x400, 0x200, 0x100, 16, 2]
    clock_rate = None

    def __init__(self, callback=None, boot_rom="build/boot.rom", tapes=None, owner=None):
        self.last = 0
        self.boot_rom = boot_rom
        self.powered_on = True
        self.machine = new_machine(self.boot_rom)
        self.owner = owner

        try:
            self.dbg = debugger.Debugger(self.machine, tapes)
        except:
            self.machine.delete()
            raise
        self.speed_index = 0
        self.clock_rate = self.speeds[self.speed_index]

    def cycle_speed(self):
        self.speed_index = (self.speed_index + 1) % len(self.speeds)
        self.clock_rate = self.speeds[self.speed_index]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.dbg.exit()
        try:
            self.dbg.machine.delete()
        except:
            pass

    def run(self, callback=None):
        try:
            done = False
            while not done:
                done = self.mainloop(callback)

        finally:
            self.dbg.exit()
            armv2.debug_log("deleting machine")
            try:
                self.dbg.machine.delete()
            except:
                pass

    def key_up(self, key):
        if self.dbg.stopped:
            return

        if key == ord("\r"):
            key = ord("\n")
        self.dbg.machine.keyboard.key_up(key)

    def key_down(self, key):
        if self.dbg.stopped:
            return

        if key == ord("\r"):
            key = ord("\n")
        self.dbg.machine.keyboard.key_down(key)

    def step_num(self, num):
        if self.powered_on:
            self.dbg.step_num(num)

    def draw(self):
        self.machine.display.new_frame()
        self.machine.tape_drive.update()
        self.machine.display.end_frame()

    def restart(self):
        # breakpoints = self.dbg.breakpoints
        self.power_off()
        self.power_on()

    def power_off(self):
        # self.machine.delete()
        # self.machine = None
        # self.dbg.update()
        if self.machine.tape_drive:
            self.machine.tape_drive.power_down()
        if self.machine.display:
            self.machine.display.power_down()
        self.powered_on = False
        if self.owner:
            self.owner.power_off()

    def power_on(self):
        old_machine = self.machine
        self.machine = new_machine(self.boot_rom)
        # The new machine has something in common with the old; the state of its hardware. Copying the
        # hardware devices across seems to have some issues that I can't be bothered to resolve, so cheat and
        # copy the state of those things with state (like the tape drive) across manually
        self.machine.tape_drive.copy_from(old_machine.tape_drive)
        old_machine.delete()
        # FIXME: Handle taking ownership of the hardware properly
        self.dbg.new_machine(self.machine)
        self.dbg.update()
        self.dbg.load_symbols()
        self.powered_on = True
        if self.owner:
            self.owner.power_on()

    def skip_loading(self):
        self.dbg.machine.tape_drive.skip_loading()

    def is_stopped(self):
        return self.dbg.stopped

    def mainloop(self, callback):
        globals.t = pygame.time.get_ticks()
        self.dbg.step_num(self.frame_cycles)
        for event in pygame.event.get():
            if event.type == pygame.locals.QUIT:
                return True

            if event.type == pygame.USEREVENT:
                if self.dbg.wants_interrupt():
                    self.dbg.machine.clock.fired()

            if event.type == pygame.locals.KEYDOWN:
                key = event.key
                try:
                    # Try to use the unicode field instead. If it doesn't work for some reason,
                    # use the old value
                    key = ord(event.unicode)
                except (TypeError, AttributeError):
                    pass
                if key == ord("\r"):
                    key = ord("\n")
                if key < 256:
                    self.dbg.machine.keyboard.key_down(key)
            elif event.type == pygame.locals.KEYUP:
                key = event.key
                try:
                    # Try to use the unicode field instead. If it doesn't work for some reason,
                    # use the old value
                    key = ord(event.unicode)
                except (TypeError, AttributeError):
                    pass
                if key == ord("\r"):
                    key = ord("\n")
                if key < 256:
                    self.dbg.machine.keyboard.key_up(key)
        # elapsed = globals.t - self.last
        # if 1 and elapsed > 20:
        drawing.opengl.clear_screen()
        self.dbg.machine.display.new_frame()
        self.dbg.machine.tape_drive.update()
        self.dbg.machine.display.end_frame()
        self.dbg.machine.display.draw_to_screen()
        pygame.display.flip()
        # self.last = globals.t

        if callback:
            try:
                callback()
            except:
                callback = None
        return False


def init(width, height, do_screen=True):
    if hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)

    pygame.init()
    pygame.display.set_caption("Synapse")
    # pygame.mouse.set_visible(0)
    pygame.key.set_repeat(500, 50)
    globals.sounds = sounds.Sounds()
    globals.screen = Point(width, height)
    globals.dirs = globals.types.Directories(os.path.join(os.path.dirname(__file__), "resource"))
    globals.screen_quadbuffer = drawing.QuadBuffer(16)
    globals.screen.full_quad = drawing.Quad(globals.screen_quadbuffer)
    globals.screen.full_quad.set_vertices(Point(0, 0), globals.screen, 0.01)
    globals.crt_buffer = drawing.opengl.CrtBuffer(*hardware.Display.pixel_size)
    # globals.screen.full_quad.set_vertices(globals.screen*0.5, globals.screen,0.01)
    if do_screen:
        screen = pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF)
    drawing.init(width, height, hardware.Display.pixel_size)
    drawing.init_drawing()
