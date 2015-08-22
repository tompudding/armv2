import armv2
import binascii
import debugger
import sys
import hardware
import pygame
import threading
from pygame.locals import *
from optparse import OptionParser

pygame.init()

class StdOutWrapper:
    text = []
    def write(self,txt):
        self.text.append(txt)
        if len(self.text) > 500:
            self.text = self.text[:500]
    def get_text(self):
        return ''.join(self.text)

def mainloop(dbg,machine):
    dbg.StepNum(dbg.FRAME_CYCLES)
    for event in pygame.event.get():
        if event.type == pygame.locals.QUIT:
            done = True
            break

        if event.type == pygame.locals.KEYDOWN:
            machine.keyboard.KeyDown(event.key)
        elif event.type == pygame.locals.KEYUP:
            if event.key == pygame.locals.K_x:
                dbg.Stop()
            machine.keyboard.KeyUp(event.key)

def main(stdscr):
    parser = OptionParser(usage="usage: %prog [options] filename",
                          version="%prog 1.0")

    (options, args) = parser.parse_args()
    pygame.display.set_caption('ARM emulator')
    pygame.mouse.set_visible(0)

    curses.use_default_colors()
    machine = hardware.Machine(cpu_size = 2**21, cpu_rom = 'boot.rom')
    try:
        machine.AddHardware(hardware.Keyboard(machine),name='keyboard')
        machine.AddHardware(hardware.Display(machine,scale_factor=3),name='display')

        dbg = debugger.Debugger(machine,stdscr)
        background = pygame.Surface((200,200))
        background = background.convert()
        background.fill((0, 0, 0))
        #machine.display.screen.blit(background, (0, 0))

        done = False
        while not done:
            mainloop(dbg,machine)

    finally:
        armv2.DebugLog('deleting machine')
        machine.Delete()

if __name__ == '__main__':
    import curses
    mystdout = StdOutWrapper()
    sys.stdout = mystdout
    sys.stderr = mystdout
    try:
        curses.wrapper(main)
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.stdout.write(mystdout.get_text())
