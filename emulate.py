import armv2
import binascii
import debugger
import os
import sys
import hardware
import pygame
import drawing
import globals
from globals.types import Point
from pygame.locals import *
from optparse import OptionParser

width,height = (960, 720)
globals.screen = Point(width,height)

def new_machine():
    machine = hardware.Machine(cpu_size = 1<<21, cpu_rom = 'build/boot.rom')
    try:
        machine.AddHardware(hardware.Keyboard(machine), name='keyboard')
        machine.AddHardware(hardware.Display(machine,scale_factor=1),name='display')
        machine.AddHardware(hardware.Clock(machine), name='clock')
        machine.AddHardware(hardware.TapeDrive(machine), name='tape_drive')
    except:
        machine.Delete()
        raise
    return machine

class Emulator(object):
    def __init__(self,callback=None):

        self.machine = new_machine()

        try:
            self.dbg = debugger.Debugger(self.machine)
        except:
            self.machine.Delete()
            raise

    def run(self, callback=None):
        try:
            done = False
            while not done:
                done = self.mainloop(callback)

        finally:
            self.dbg.exit()
            armv2.DebugLog('deleting machine')
            try:
                self.dbg.machine.Delete()
            except:
                pass

    def key_up(self, event):
        if self.dbg.stopped:
            return
        try:
            key = ord(event.char)
        except TypeError:
            return
        self.dbg.machine.keyboard.KeyDown(key)

    def key_down(self, event):
        if self.dbg.stopped:
            return
        try:
            key = ord(event.char)
        except TypeError:
            return
        self.dbg.machine.keyboard.KeyUp(key)

    def restart(self):
        breakpoints = self.dbg.breakpoints
        self.dbg.machine.Delete()
        self.dbg.new_machine(new_machine())
        self.dbg.Update()

    def mainloop(self, callback):
        globals.t = pygame.time.get_ticks()
        self.dbg.StepNum(self.dbg.FRAME_CYCLES)
        for event in pygame.event.get():
            if event.type == pygame.locals.QUIT:
                return True

            if event.type == pygame.USEREVENT:
                if self.dbg.wants_interrupt():
                    self.dbg.machine.clock.fired()

            if event.type == pygame.locals.KEYDOWN:
                key = event.key
                try:
                    #Try to use the unicode field instead. If it doesn't work for some reason,
                    #use the old value
                    key = ord(event.unicode)
                except (TypeError,AttributeError):
                    pass
                if key < 256:
                    self.dbg.machine.keyboard.KeyDown(key)
            elif event.type == pygame.locals.KEYUP:
                key = event.key
                try:
                    #Try to use the unicode field instead. If it doesn't work for some reason,
                    #use the old value
                    key = ord(event.unicode)
                except (TypeError,AttributeError):
                    pass
                if key < 256:
                    self.dbg.machine.keyboard.KeyUp(key)
        drawing.NewFrame()
        self.dbg.machine.display.Update()
        drawing.EndFrame()
        pygame.display.flip()
        if callback:
            try:
                callback()
            except:
                callback = None
        return False

def init():
    if hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)

    pygame.init()
    pygame.display.set_caption('Synapse')
    #pygame.mouse.set_visible(0)
    pygame.key.set_repeat(500,50)
    globals.dirs = globals.types.Directories('resource')
    globals.screen_quadbuffer     = drawing.QuadBuffer(16)
    globals.screen.full_quad      = drawing.Quad(globals.screen_quadbuffer)
    globals.screen.full_quad.SetVertices(Point(0,0),globals.screen,0.01)

    screen = pygame.display.set_mode((width, height), pygame.OPENGL|pygame.DOUBLEBUF)
    drawing.Init(width, height, hardware.Display.pixel_size)
    drawing.InitDrawing()

if __name__ == '__main__':
    from multiprocessing import Process
    import peripherals,time

    p = Process(target=peripherals.run)
    p.start()
    init()
    emulator = Emulator()
    emulator.run()
    pygame.display.quit()
    p.join()

