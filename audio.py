"""
Plays the sound chips' samples.

pygame's mixer can only play one whole sound after another, which leaves a small gap between them, so the
chips share an SDL audio stream of their own instead. SDL calls us back from its audio thread whenever it wants
more samples, and we give it the sum of whatever each chip has queued up.
"""

import atexit
import collections
import ctypes
import glob
import os
import threading

import numpy
import pygame
from pygame._sdl2 import audio as sdl_audio


# Set this to part of a device's name to play through that one rather than the default
DEVICE_VARIABLE = "ARMV2_AUDIO_DEVICE"


def sdl_library():
    """The copy of SDL that pygame is using, which has functions that pygame doesn't pass on"""
    try:
        with open("/proc/self/maps") as f:
            # The dash keeps out the likes of libSDL2_mixer
            paths = {line.split()[-1] for line in f if "/libSDL2-" in line}
    except OSError:
        # Not Linux, so look for the one that comes in pygame's package
        folder = os.path.dirname(pygame.__file__)
        paths = set(glob.glob(os.path.join(folder, "SDL2.dll")))
        paths.update(glob.glob(os.path.join(folder, ".dylibs", "libSDL2-*.dylib")))
    if len(paths) != 1:
        return None
    return ctypes.CDLL(paths.pop())


def default_device_name():
    """The name of the system's default output, or None if SDL can't tell us"""
    try:
        sdl = sdl_library()
        get_info = sdl.SDL_GetDefaultAudioInfo
        get_info.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_int]
        sdl.SDL_free.argtypes = [ctypes.c_void_p]
        name = ctypes.c_void_p()
        # It also fills in an SDL_AudioSpec, which we don't want but have to give it room for
        spec = ctypes.create_string_buffer(64)
        if get_info(ctypes.byref(name), spec, 0) != 0:
            return None
        try:
            return ctypes.cast(name, ctypes.c_char_p).value.decode("utf-8")
        finally:
            sdl.SDL_free(name)
    except (AttributeError, OSError, UnicodeDecodeError):
        # We didn't find SDL, or it's older than 2.24 and doesn't have the function
        return None


def choose_device():
    """The name of the output device to open

    pygame insists on being given a name rather than letting SDL use the default, and the first one in the
    list is often not the one that the speakers are plugged in to."""
    names = sdl_audio.get_audio_device_names(False)
    wanted = os.environ.get(DEVICE_VARIABLE)
    if wanted:
        matches = [name for name in names if wanted.lower() in name.lower()]
        if matches:
            return matches[0]
        print(f"No audio device matches {DEVICE_VARIABLE}={wanted}. The devices are {names}")
    default = default_device_name()
    if default in names:
        return default
    return names[0]


class Source:
    """The samples from one sound chip that are waiting to be played"""

    # How much has to be queued before we start playing, which is what covers for frames that arrive late,
    # and the most we let build up before dropping some. The delay between a guest writing to a register
    # and it being heard is somewhere between the two
    start_ms = 60
    max_ms = 200

    def __init__(self, output):
        self.output = output
        self.volume = 1.0
        self.chunks = collections.deque()
        self.queued = 0
        # How much of the first chunk has already been played
        self.offset = 0
        self.waiting = True
        # How many times we ran out of samples, for checking that the buffer sizes are sensible
        self.underruns = 0
        self.start_samples = self.start_ms * output.sample_rate // 1000
        self.max_samples = self.max_ms * output.sample_rate // 1000

    def write(self, samples):
        with self.output.lock:
            self.chunks.append(samples)
            self.queued += len(samples)
            if self.queued > self.max_samples:
                # We're making samples faster than they're being played, so skip ahead
                self.discard(self.queued - self.start_samples)

    def discard(self, count):
        self.read_into(None, count)

    def read(self, count):
        """Take the next count samples, or None if there's nothing to play. Called with the lock held"""
        if self.waiting:
            if self.queued < self.start_samples:
                return None
            self.waiting = False

        out = numpy.zeros(count, dtype=numpy.int16)
        if self.read_into(out, count) < count:
            # We ran out, so wait until there's a reasonable amount again rather than stuttering
            self.waiting = True
            self.underruns += 1
        return out

    def read_into(self, out, count):
        pos = 0
        while pos < count and self.chunks:
            chunk = self.chunks[0]
            num = min(count - pos, len(chunk) - self.offset)
            if out is not None:
                out[pos : pos + num] = chunk[self.offset : self.offset + num]
            pos += num
            self.offset += num
            if self.offset >= len(chunk):
                self.chunks.popleft()
                self.offset = 0
        self.queued -= pos
        return pos

    def close(self):
        self.output.remove(self)


class Output:
    """The audio stream that all the sources are mixed into"""

    chunk_size = 512
    instance = None
    failed = False

    @classmethod
    def get(cls):
        """The shared output, or None if we couldn't open one"""
        if cls.instance is None and not cls.failed:
            try:
                cls.instance = cls()
            except (RuntimeError, IndexError) as e:
                # pygame's errors are RuntimeErrors, and there might be no devices at all. This happens with
                # SDL's dummy driver, for example, which only allows the one device that the mixer has
                print(f"The sound chips will be silent as the audio device didn't open: {e}")
                cls.failed = True
        return cls.instance

    def __init__(self):
        self.sample_rate = pygame.mixer.get_init()[0]
        self.lock = threading.Lock()
        self.sources = []
        self.device = sdl_audio.AudioDevice(
            devicename=choose_device(),
            iscapture=0,
            frequency=self.sample_rate,
            audioformat=sdl_audio.AUDIO_S16,
            numchannels=1,
            chunksize=self.chunk_size,
            allowed_changes=0,
            callback=self.callback,
        )
        print(f"The sound chips are playing through {self.device.devicename}")
        atexit.register(self.close)
        self.device.pause(0)

    def close(self):
        if self.device is not None:
            self.device.pause(1)
            self.device.close()
            self.device = None

    def add(self):
        source = Source(self)
        with self.lock:
            self.sources.append(source)
        return source

    def remove(self, source):
        with self.lock:
            if source in self.sources:
                self.sources.remove(source)

    def callback(self, device, memory):
        # This is on SDL's audio thread. The buffer isn't cleared for us, so it must always be filled
        out = numpy.frombuffer(memory, dtype=numpy.int16)
        mixed = numpy.zeros(len(out))
        with self.lock:
            for source in self.sources:
                samples = source.read(len(out))
                if samples is not None:
                    mixed += samples * source.volume
        out[:] = numpy.clip(mixed, -32768, 32767)
