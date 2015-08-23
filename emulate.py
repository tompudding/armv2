import armv2
import binascii
import debugger
import sys
import hardware
import pygame
import threading
from pygame.locals import *
from optparse import OptionParser

width,height = (1280, 720)

pygame.init()

def mainloop(dbg,machine):
    dbg.StepNum(dbg.FRAME_CYCLES)
    for event in pygame.event.get():

        if event.type == pygame.locals.QUIT:
            done = True
            break

        if event.type == pygame.locals.KEYDOWN:
            key = event.key
            try:
                #Try to use the unicode field instead. If it doesn't work for some reason,
                #use the old value
                key = ord(event.unicode)
            except (TypeError,AttributeError):
                pass
            if key == pygame.locals.K_ESCAPE:
                dbg.Stop()
            if dbg.stopped:
                dbg.KeyPress(key)
            else:
                if key < 256:
                    machine.keyboard.KeyDown(key)
        elif event.type == pygame.locals.KEYUP:
            key = event.key
            try:
                #Try to use the unicode field instead. If it doesn't work for some reason,
                #use the old value
                key = ord(event.unicode)
            except (TypeError,AttributeError):
                pass
            if not dbg.stopped and key < 256:
                machine.keyboard.KeyUp(key)
    machine.display.Update()
    pygame.display.flip()

def main():
    parser = OptionParser(usage="usage: %prog [options] filename",
                          version="%prog 1.0")

    (options, args) = parser.parse_args()
    pygame.display.set_caption('ARM emulator')
    pygame.mouse.set_visible(0)
    pygame.key.set_repeat(500,50)

    screen = pygame.display.set_mode((width, height))
    machine = hardware.Machine(cpu_size = 2**21, cpu_rom = 'boot.rom')
    try:
        machine.AddHardware(hardware.Keyboard(machine),name='keyboard')
        machine.AddHardware(hardware.Display(machine,screen,scale_factor=3),name='display')

        dbg = debugger.Debugger(machine, screen)

        done = False
        while not done:
            mainloop(dbg,machine)

    finally:
        armv2.DebugLog('deleting machine')
        machine.Delete()

if __name__ == '__main__':
    main()
