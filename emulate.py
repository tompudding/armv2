import sys
from . import armv2
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


def new_machine(boot_rom):
    machine = hardware.Machine(cpu_size=1 << 21, cpu_rom=boot_rom)
    try:
        machine.add_hardware(hardware.Keyboard(machine), name='keyboard')
        machine.add_hardware(hardware.Display(machine, scale_factor=1), name='display')
        machine.add_hardware(hardware.Clock(machine), name='clock')
        machine.add_hardware(hardware.TapeDrive(machine), name='tape_drive')
    except:
        machine.delete()
        raise
    return machine


class Emulator(object):
    def __init__(self, callback=None, boot_rom='build/boot.rom', tapes=None):
        self.last = 0
        self.boot_rom = boot_rom
        self.machine = new_machine(self.boot_rom)
        try:
            self.dbg = debugger.Debugger(self.machine, tapes)
        except:
            self.machine.delete()
            raise

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
            armv2.debug_log('deleting machine')
            try:
                self.dbg.machine.delete()
            except:
                pass

    def key_up(self, event):
        if self.dbg.stopped:
            return
        try:
            key = ord(event.char)
        except TypeError:
            return
        if key == ord('\r'):
            key = ord('\n')
        self.dbg.machine.keyboard.key_up(key)

    def key_down(self, event):
        if self.dbg.stopped:
            return
        try:
            key = ord(event.char)
        except TypeError:
            return
        if key == ord('\r'):
            key = ord('\n')
        self.dbg.machine.keyboard.key_down(key)

    def restart(self):
        breakpoints = self.dbg.breakpoints
        self.dbg.machine.delete()
        self.dbg.new_machine(new_machine(self.boot_rom))
        self.dbg.update()
        self.dbg.load_symbols()

    def skip_loading(self):
        self.dbg.machine.tape_drive.skip_loading()

    def is_stopped(self):
        return self.dbg.stopped

    def mainloop(self, callback):
        globals.t = pygame.time.get_ticks()
        self.dbg.step_num(self.dbg.FRAME_CYCLES)
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
                if key == ord('\r'):
                    key = ord('\n')
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
                if key == ord('\r'):
                    key = ord('\n')
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
    pygame.display.set_caption('Synapse')
    # pygame.mouse.set_visible(0)
    pygame.key.set_repeat(500, 50)
    globals.screen = Point(width, height)
    globals.dirs = globals.types.Directories('resource')
    globals.screen_quadbuffer     = drawing.QuadBuffer(16)
    globals.screen.full_quad      = drawing.Quad(globals.screen_quadbuffer)
    globals.screen.full_quad.set_vertices(Point(0, 0), globals.screen, 0.01)
    #globals.screen.full_quad.set_vertices(globals.screen*0.5, globals.screen,0.01)
    if do_screen:
        screen = pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF)
    drawing.init(width, height, hardware.Display.pixel_size)
    drawing.init_drawing()
