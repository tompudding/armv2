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
import argparse
from . import sounds
from . import tapes


def new_machine(boot_rom):
    machine = hardware.Machine(cpu_size=1 << 18, cpu_rom=boot_rom)
    try:
        machine.add_hardware(hardware.Keyboard(machine), name="keyboard")
        machine.add_hardware(hardware.Display(machine, scale_factor=1), name="display")
        machine.add_hardware(hardware.Clock(machine), name="clock")
        machine.add_hardware(hardware.TapeDrive(machine), name="tape_drive")
        machine.add_hardware(hardware.SoundChip(machine), name="sound")
    except:
        machine.delete()
        raise
    return machine


class Emulator:
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
            clock = pygame.time.Clock()
            while not done:
                clock.tick(60)
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
        self.machine.sound.update()

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
        if self.machine.sound:
            self.machine.sound.power_down()
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

    def load_tape(self, filename):
        self.machine.tape_drive.load_tape(tapes.ProgramTape(filename))

    def play_tape(self):
        self.machine.tape_drive.start_playing()

    # Keys that control the harness rather than going to the guest, used by the standalone runner
    function_keys = {
        pygame.K_F5: play_tape,
        pygame.K_F6: skip_loading,
        pygame.K_F7: restart,
        pygame.K_F8: cycle_speed,
    }

    def mainloop(self, callback):
        globals.t = pygame.time.get_ticks()
        # Run 16ms worth of cycles per frame, as the game does
        self.dbg.step_num(16 * self.clock_rate)
        for event in pygame.event.get():
            if event.type == pygame.locals.QUIT:
                return True

            if event.type == pygame.locals.KEYDOWN and event.key in self.function_keys:
                self.function_keys[event.key](self)
                continue

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
        drawing.new_crt_frame(globals.crt_buffer)
        self.draw()
        globals.crt_buffer.unbind()
        drawing.opengl.clear_screen()
        self.dbg.machine.display.draw_to_screen()
        pygame.display.flip()
        # self.last = globals.t

        if callback:
            try:
                callback()
            except:
                callback = None
        return False


def init(width, height, do_screen=True, hidden=False):
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
    globals.screen.full_quad = drawing.Quad(globals.screen_quadbuffer, tc=drawing.constants.full_tc)
    globals.screen.full_quad.set_vertices(Point(0, 0), globals.screen, 0.01)
    # globals.screen.full_quad.set_vertices(globals.screen*0.5, globals.screen,0.01)
    if do_screen:
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
        flags = pygame.OPENGL | pygame.DOUBLEBUF
        if hidden:
            flags |= pygame.HIDDEN
        screen = pygame.display.set_mode((width, height), flags)
    globals.crt_buffer = drawing.opengl.CrtBuffer(*hardware.Display.pixel_size)
    drawing.init(width, height, hardware.Display.pixel_size)
    drawing.init_drawing()


def main():
    """Run a single machine in its own window. Run from the repo root with python -m armv2_emulator.emulate"""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--rom", default="armv2_emulator/build/boot.rom", help="the boot rom")
    parser.add_argument("--tape", help="a tape to put in the drive. Type load, then press F5 to play it")
    parser.add_argument("--scale", type=int, default=3, help="window size as a multiple of 320x240")
    args = parser.parse_args()

    print("F5 plays the tape, F6 skips the loading, F7 restarts the machine, F8 changes speed")
    width, height = hardware.Display.pixel_size
    init(width * args.scale, height * args.scale)
    emulator = Emulator(boot_rom=args.rom)
    if args.tape:
        emulator.load_tape(args.tape)
    emulator.run()


if __name__ == "__main__":
    main()
