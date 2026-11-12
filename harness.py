"""
A scriptable harness for a single machine, for testing guest programs without the game.

Time is virtual: every frame advances the clock by FRAME_MS whatever the wall clock says, the guest's clock
interrupt is fired from that time, and tape loading is skipped, so runs are fast and repeatable. The screen is
read straight from the display's memory and the sound chip's output is recorded, so no window needs to be
shown and nothing is played unless one is.

From Python, with the repo root as the working directory:

    from armv2_emulator.harness import Harness

    with Harness() as h:
        h.wait_for_text("READY")
        h.load_tape("tapes/guessing.tape")
        h.wait_for_text("guess")
        h.type("50\\n")
        print(h.text())
        h.screenshot("guess.png")
        h.save_audio("guess.wav")

From the command line, where each action runs in order:

    python -m armv2_emulator.harness --tape tapes/guessing.tape --wait guess --type '50\\n' \\
        --run 500 --print --screenshot guess.png
"""

import argparse
import os
import sys
import wave

import numpy

if "--show" not in sys.argv:
    # The machine needs a window for its OpenGL context, but it stays hidden and makes no sound
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from . import emulate, globals, hardware
from .emulate import Emulator

Display = hardware.Display


class Timeout(Exception):
    pass


class Harness:
    FRAME_MS = 16
    # How long a typed key is held down for, and the gap after it before the next one
    KEY_MS = 32

    def __init__(self, boot_rom="armv2_emulator/build/boot.rom", show=False, scale=3):
        self.show = show
        width, height = Display.pixel_size
        emulate.init(width * scale, height * scale, hidden=not show)
        hardware.Clock.use_pygame_timer = False
        hardware.Machine.daemon_thread = True
        self.emulator = Emulator(boot_rom=boot_rom)
        self.captured = []
        self.capture_sound()
        self.t = 0
        self.next_tick = None
        self.set_time()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self.emulator is not None:
            self.emulator.__exit__()
            self.emulator = None

    @property
    def machine(self):
        return self.emulator.machine

    def capture_sound(self):
        # Restarting the machine makes a new sound chip, so this needs doing again after that
        sound = self.machine.sound
        sound.capture = self.captured
        # Virtual time runs faster than the speakers can keep up with, so only play it when it's being watched
        sound.playback = self.show

    def set_time(self):
        globals.t = self.t

    def frame(self):
        """Advance the machine by one frame"""
        self.t += self.FRAME_MS
        self.set_time()

        clock = self.machine.clock
        if clock.period <= 0:
            self.next_tick = None
        else:
            if self.next_tick is None:
                self.next_tick = self.t + clock.period
            while self.t >= self.next_tick:
                if self.emulator.dbg.wants_interrupt():
                    clock.fired()
                self.next_tick += clock.period

        # Interrupts from the clock or from keys make the cpu thread take a step, and the frame's cycles
        # would be dropped if we asked for them while that was still going on
        self.machine.wait_until_idle()
        self.emulator.step_num(self.FRAME_MS * self.emulator.clock_rate)

        # The tape drive's update moves the tape on, so it has to happen even if nothing is shown
        emulate.drawing.new_crt_frame(globals.crt_buffer)
        self.emulator.draw()

        if self.show:
            globals.crt_buffer.unbind()
            emulate.drawing.opengl.clear_screen()
            self.machine.display.draw_to_screen()
            pygame.display.flip()
        # Keep the window responsive, but the input comes from the script
        pygame.event.pump()

    def run(self, ms):
        """Run for at least this many milliseconds of virtual time"""
        end = self.t + ms
        while self.t < end:
            self.frame()

    def run_until(self, condition, timeout=10000):
        """Run until condition() is true, raising Timeout after timeout milliseconds of virtual time"""
        end = self.t + timeout
        while not condition():
            if self.t >= end:
                raise Timeout(f"Condition not met after {timeout}ms. The screen is:\n{self.text()}")
            self.frame()

    def wait_for_text(self, text, timeout=10000):
        """Run until text appears somewhere on the screen. Rows are joined with newlines"""
        self.run_until(lambda: text in self.text(), timeout)

    # Input

    @staticmethod
    def key_code(key):
        if isinstance(key, str):
            if len(key) != 1:
                raise ValueError(f"Expected a single character, not {key!r}")
            key = ord(key)
        if key == ord("\r"):
            key = ord("\n")
        return key

    def key_down(self, key):
        self.emulator.key_down(self.key_code(key))

    def key_up(self, key):
        self.emulator.key_up(self.key_code(key))

    def press(self, key, hold=KEY_MS, after=KEY_MS):
        """Press and release a key, given as a character or an ascii code"""
        self.key_down(key)
        self.run(hold)
        self.key_up(key)
        self.run(after)

    def type(self, text, hold=KEY_MS, after=KEY_MS):
        for c in text:
            self.press(c, hold, after)

    # Tapes

    def load_tape(self, filename, command="load\n", fast=True):
        """Put a tape in the drive, type the command that loads it, and press play"""
        self.emulator.load_tape(filename)
        if command:
            self.type(command)
        self.emulator.play_tape()
        if fast:
            self.emulator.skip_loading()

    # Reading the screen. Rows are top to bottom and columns left to right, as the guest sees them

    def letters(self):
        """The character code in each cell, as a (30, 40) array"""
        return numpy.array(self.machine.display.letter_data, dtype=numpy.uint8).reshape(
            Display.height, Display.width
        )

    def text(self):
        """The screen's text, with a line per row. Codes outside printable ascii become spaces"""
        rows = []
        for row in self.letters():
            rows.append("".join(chr(c) if 32 <= c < 127 else " " for c in row).rstrip())
        return "\n".join(rows)

    def char_at(self, x, y):
        return chr(self.machine.display.letter_data[y * Display.width + x])

    def cell_colours(self):
        """The (foreground, background) palette index of each cell, as two (30, 40) arrays"""
        palette = numpy.array(self.machine.display.palette_data, dtype=numpy.uint8).reshape(
            Display.height, Display.width
        )
        return palette & 0xF, palette >> 4

    def pixel_bits(self):
        """Whether each pixel is set to the foreground colour, as a (240, 320) bool array"""
        data = self.machine.display.pixel_data_words.view(numpy.uint8)
        bits = numpy.unpackbits(data, bitorder="little").reshape(Display.pixel_size[1], Display.pixel_size[0])
        # The display stores rows from the bottom up
        return bits[::-1].astype(bool)

    def pixels(self):
        """The palette index of each pixel, as a (240, 320) array"""
        fore, back = self.cell_colours()
        size = Display.cell_size
        fore = fore.repeat(size, axis=0).repeat(size, axis=1)
        back = back.repeat(size, axis=0).repeat(size, axis=1)
        return numpy.where(self.pixel_bits(), fore, back)

    def rgb(self):
        """The screen as a (240, 320, 3) array of colours"""
        palette = numpy.array([colour[:3] for colour in Display.Colours.palette], dtype=numpy.uint8)
        return palette[self.pixels()]

    def screenshot(self, filename, scale=2):
        from PIL import Image

        image = Image.fromarray(self.rgb())
        if scale != 1:
            image = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
        image.save(filename)

    # Sound. This is everything the sound chip has produced, whether or not it was played

    @property
    def sample_rate(self):
        return self.machine.sound.sample_rate

    def audio(self):
        """The mono samples produced so far, as an int16 array at sample_rate"""
        if not self.captured:
            return numpy.zeros(0, dtype=numpy.int16)
        return numpy.concatenate(self.captured)

    def clear_audio(self):
        self.captured.clear()

    def save_audio(self, filename):
        with wave.open(filename, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(self.sample_rate)
            f.writeframes(self.audio().tobytes())

    def restart(self):
        self.emulator.restart()
        self.capture_sound()


def unescape(text):
    return text.encode("utf-8").decode("unicode_escape")


class Action(argparse.Action):
    """Collect the actions in the order they were given"""

    def __call__(self, parser, namespace, values, option_string=None):
        namespace.actions.append((self.dest, values))


def main():
    parser = argparse.ArgumentParser(
        description="Run a machine from a script of actions, which run in the order given",
        epilog="Run from the repo root. Text arguments understand escapes such as \\n",
    )
    parser.add_argument("--rom", default="armv2_emulator/build/boot.rom", help="the boot rom")
    parser.add_argument("--show", action="store_true", help="show the window, at normal speed or faster")
    parser.add_argument("--timeout", type=int, default=10000, help="ms of virtual time for each --wait")
    parser.set_defaults(actions=[])
    actions = parser.add_argument_group("actions")
    actions.add_argument("--tape", action=Action, help="load a tape and run it, skipping the loading")
    actions.add_argument("--wait", action=Action, metavar="TEXT", help="run until TEXT is on screen")
    actions.add_argument("--type", action=Action, metavar="TEXT", help="type TEXT")
    actions.add_argument("--press", action=Action, metavar="CODE", help="press the key with this ascii code")
    actions.add_argument("--run", action=Action, metavar="MS", help="run for MS ms of virtual time")
    actions.add_argument("--print", action=Action, nargs=0, help="print the screen's text")
    actions.add_argument("--screenshot", action=Action, metavar="FILE", help="save the screen as an image")
    actions.add_argument("--audio", action=Action, metavar="FILE", help="save the sound so far as a wav file")
    args = parser.parse_args()

    with Harness(boot_rom=args.rom, show=args.show) as harness:
        harness.wait_for_text("READY", args.timeout)
        for name, value in args.actions:
            if name == "tape":
                harness.load_tape(value)
            elif name == "wait":
                harness.wait_for_text(unescape(value), args.timeout)
            elif name == "type":
                harness.type(unescape(value))
            elif name == "press":
                harness.press(int(value, 0))
            elif name == "run":
                harness.run(int(value))
            elif name == "print":
                print("-" * Display.width)
                print(harness.text())
                print("-" * Display.width)
            elif name == "screenshot":
                harness.screenshot(value)
            elif name == "audio":
                harness.save_audio(value)
        if args.show:
            # Leave it running until the window is closed
            harness.emulator.run()


if __name__ == "__main__":
    main()
