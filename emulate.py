import armv2
import binascii
import debugger
import os
import sys
import hardware
import pygame
import threading
from pygame.locals import *
from optparse import OptionParser

width,height = (1280, 720)

pygame.init()

def new_machine(screen):
    machine = hardware.Machine(cpu_size = 2**21, cpu_rom = 'boot.rom')
    machine.AddHardware(hardware.Keyboard(machine),name='keyboard')
    machine.AddHardware(hardware.Display(machine,screen,scale_factor=3),name='display')
    machine.AddHardware(hardware.TapeDrive(machine),name='tape_drive')
    return machine

def mainloop(dbg):
    dbg.StepNum(dbg.FRAME_CYCLES)
    for event in pygame.event.get():

        if event.type == pygame.locals.QUIT:
            return True

        if event.type == pygame.locals.KEYDOWN:
            key = event.key
            # try:
            #     #Try to use the unicode field instead. If it doesn't work for some reason,
            #     #use the old value
            #     key = ord(event.unicode)
            # except (TypeError,AttributeError):
            #     pass
            if key == pygame.locals.K_ESCAPE and not dbg.stopped:
                dbg.Stop()
                return
            if dbg.stopped:
                if False == dbg.KeyPress(key):
                    screen = dbg.machine.display.screen
                    dbg.machine.Delete()

                    dbg.machine = new_machine(screen)
                    dbg.Reset()
            else:
                if key < 256:
                    dbg.machine.keyboard.KeyDown(key)
        elif event.type == pygame.locals.KEYUP:
            key = event.key
            # try:
            #     #Try to use the unicode field instead. If it doesn't work for some reason,
            #     #use the old value
            #     key = ord(event.unicode)
            # except (TypeError,AttributeError):
            #     pass
            if not dbg.stopped and key < 256:
                dbg.machine.keyboard.KeyUp(key)
    dbg.machine.display.Update()
    pygame.display.flip()
    return False

def main():
    parser = OptionParser(usage="usage: %prog [options] filename",
                          version="%prog 1.0")

    if hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)

    (options, args) = parser.parse_args()
    pygame.display.set_caption('Synapse')
    pygame.mouse.set_visible(0)
    pygame.key.set_repeat(500,50)

    screen = pygame.display.set_mode((width, height))
    machine = new_machine(screen)
    try:
        dbg = debugger.Debugger(machine, screen)
    except:
        machine.Delete()
        raise

    try:
        done = False
        while not done:
            done = mainloop(dbg)

    finally:
        armv2.DebugLog('deleting machine')
        try:
            dbg.machine.Delete()
        except:
            pass

if __name__ == '__main__':
    main()
