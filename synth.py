r"""
A synthesiser chip modelled on the SID, the sound chip in the Commodore 64 (the "Sound Interface Device").

It doesn't play recorded audio. Instead a program controls it by writing numbers to its registers, each of
which is a single byte at a fixed address that changes one setting, such as how high a note is. This module
only turns those register values into samples; hardware.SoundChip maps it into a machine's memory and plays
the result.

Voices
------
A voice is one independent sound generator, like one singer in a choir. It plays one note at a time, and the
chip has three of them, so a tune might use one for the bass, one for the melody and one for drums. For each
voice a program chooses:

    The frequency, which is how high or low the note is.
    The waveform, which is the shape of the wave and gives the note its character. A triangle is soft, a
    sawtooth is buzzy, a pulse is hollow and noise is a hiss that's used for drums.
    The envelope, which is how the loudness changes over the life of the note.

A note starts when the program sets the voice's gate bit, like pressing a piano key, and ends when it clears
it, like letting go. The envelope has four settings that shape the loudness between those:

    loudness
      |     /\
      |    /  \________
      |   /            \
      |  /              \
      +--------------------> time
         A   D    S     R
       gate set      gate cleared

    Attack is how long the note takes to rise from silence to full loudness after the gate is set. A short
    one gives a sharp pluck and a long one a slow swell.
    Decay is how long it then takes to fall from full loudness to the sustain level.
    Sustain is the loudness that it holds for as long as the gate stays set. It's the only one of the four
    that is a level rather than a time.
    Release is how long it takes to fade to silence once the gate is cleared.

A drum hit, for example, is an instant attack, a quick decay and no sustain, so it's a burst that dies away
at once. An organ is an instant attack, full sustain and a short release, so it's steady while held.

Registers
---------
These are at the same addresses as on the SID, so its programming guides mostly apply. Every voice has the
same seven registers, so the three voices are three blocks of seven, starting at 0x00, 0x07 and 0x0e. The
table gives each register's offset from the start of its voice's block. A nibble is half a byte, so two
settings from 0 to 15 fit in one register.

    +0    frequency, low byte
    +1    frequency, high byte. The note's frequency is this 16 bit value * 0.0587 Hz, as on a European C64
    +2    pulse width, low byte
    +3    pulse width, high nibble. This 12 bit value is how much of each cycle of the pulse waveform is
          spent low, which changes its tone. 0x800 is half, which makes a square wave
    +4    control, where each bit is a switch:
              bit 0  gate, which starts and ends the note
              bit 1  sync, which restarts this voice's waveform whenever the previous voice's one restarts.
                     The note heard is then the previous voice's, and this one's frequency changes the tone
              bit 2  ring modulate, which combines the triangle with the previous voice for a bell-like tone
              bit 3  test, which holds the waveform at its start
              bit 4  triangle waveform
              bit 5  sawtooth waveform
              bit 6  pulse waveform
              bit 7  noise waveform
    +5    attack in the high nibble and decay in the low. 0 is the fastest and 15 the slowest: attack goes
          from 2ms to 8 seconds, and decay and release take three times as long as the same attack setting
    +6    sustain level in the high nibble, where 15 is full loudness, and release in the low

For sync and ring modulation, the voice before voice 1 is voice 3.

The rest belong to the chip as a whole. The filter removes part of the sound of the voices sent through it:
a low pass filter removes what's above its cutoff frequency, which makes the sound duller, a high pass
removes what's below it, and a band pass keeps only what's near it. Resonance emphasises the sound around the
cutoff.

    0x15  filter cutoff, low 3 bits
    0x16  filter cutoff, high 8 bits. The 11 bit value runs from 30Hz to 12kHz
    0x17  resonance in the high nibble, and bits 0 to 2 send voices 1 to 3 through the filter
    0x18  volume of the whole chip in the low nibble, then bit 4 turns on the low pass filter, 5 the band
          pass and 6 the high pass. Bit 7 silences voice 3, for when it's only there to modulate voice 1
    0x19  unused. On the SID this and the next one read the positions of the two paddle controllers
    0x1a  unused
    0x1b  the top 8 bits of voice 3's waveform, read only
    0x1c  voice 3's envelope, read only

The chip takes up 0x20 addresses, as the SID does, but the last three aren't used for anything either. The
unused ones just hold whatever was last written to them.

Differences from the real chip
------------------------------
Registers can be read back, selecting several waveforms at once simply ANDs them together, the noise repeats
after 0x10000 values, and the filter is a clean digital one.
"""

import functools
import math
from typing import NamedTuple

import numpy
import numpy.typing as npt
from scipy.signal import lfilter

# The arrays here all have an entry per sample, and these say what the entries are
FloatArray = npt.NDArray[numpy.float64]
IntArray = npt.NDArray[numpy.int64]
BoolArray = npt.NDArray[numpy.bool_]
# The finished audio, as signed 16 bit samples
Samples = npt.NDArray[numpy.int16]

# The SID's oscillators count up at the C64's clock rate, which is what sets the pitch of a frequency value
CLOCK_HZ = 985248
NUM_VOICES = 3
VOICE_SIZE = 7
# How many addresses the chip takes up, which is more than the number that do anything
NUM_REGISTERS = 0x20
# The frequency register is 16 bits, which makes the highest note about 3.8kHz
MAX_FREQUENCY = 0xFFFF

ACC_BITS = 24
ACC_SIZE = 1 << ACC_BITS
ACC_MASK = ACC_SIZE - 1
# The noise generator steps every time bit 19 of the oscillator goes high
NOISE_SHIFT = 20

# How long each attack setting takes to reach full volume, in ms. Decay and release take three times as long
ATTACK_MS = (2, 8, 16, 24, 38, 56, 68, 80, 100, 250, 500, 800, 1000, 3000, 5000, 8000)
DECAY_SCALE = 3
# The decay and release times are how long it takes to fall to this fraction of the starting level
DECAY_FLOOR = 1 / 256

MAX_CUTOFF = 0x7FF
MIN_CUTOFF_HZ = 30
MAX_CUTOFF_HZ = 12000
MIN_Q = 0.707
MAX_Q = 4.0
# Leave some room for several voices and filter resonance before the output clips
OUTPUT_SCALE = 0.6


class Control:
    GATE = 0x01
    SYNC = 0x02
    RING = 0x04
    TEST = 0x08
    TRIANGLE = 0x10
    SAWTOOTH = 0x20
    PULSE = 0x40
    NOISE = 0x80
    WAVEFORMS = TRIANGLE | SAWTOOTH | PULSE | NOISE


class Registers:
    FREQ_LO = 0
    FREQ_HI = 1
    PULSE_LO = 2
    PULSE_HI = 3
    CONTROL = 4
    ATTACK_DECAY = 5
    SUSTAIN_RELEASE = 6

    CUTOFF_LO = 0x15
    CUTOFF_HI = 0x16
    RESONANCE_ROUTING = 0x17
    MODE_VOLUME = 0x18
    OSC3 = 0x1B
    ENV3 = 0x1C


class Mode:
    LOW_PASS = 0x10
    BAND_PASS = 0x20
    HIGH_PASS = 0x40
    VOICE3_OFF = 0x80


def clamp(value: int, low: int, high: int) -> int:
    """The nearest value to this one that is from low to high"""
    return max(low, min(high, value))


def frequency_register(hz: float) -> int:
    """The value to put in a voice's frequency register to play a note at this frequency"""
    # The oscillator goes up by the register's value on every tick of the chip's clock, and has to count
    # through ACC_SIZE to complete one cycle of the waveform
    value = round(hz * ACC_SIZE / CLOCK_HZ)
    return clamp(value, 0, MAX_FREQUENCY)


@functools.cache
def build_noise_table(size: int = 1 << 16) -> IntArray:
    """The output of the SID's 23 bit shift register, as 12 bit values

    It's the same for every chip, so it is only worked out once."""
    table = numpy.zeros(size, dtype=numpy.int64)
    register = 0x7FFFF8
    taps = (20, 18, 14, 11, 9, 5, 2, 0)
    for i in range(size):
        bit = ((register >> 22) ^ (register >> 17)) & 1
        register = ((register << 1) | bit) & 0x7FFFFF
        value = 0
        for tap in taps:
            value = (value << 1) | ((register >> tap) & 1)
        table[i] = value << 4
    return table


class Envelope:
    ATTACK = 0
    DECAY = 1
    RELEASE = 2

    def __init__(self) -> None:
        self.state: int = self.RELEASE
        # The loudness, from 0 to 1
        self.level: float = 0.0

    def gate(self, on: bool) -> None:
        self.state = self.ATTACK if on else self.RELEASE

    def render(self, count: int, attack_decay: int, sustain_release: int, sample_rate: int) -> FloatArray:
        """The envelope's level for each of the next count samples"""
        out = numpy.empty(count)
        samples_per_ms = sample_rate / 1000
        attack_samples = ATTACK_MS[attack_decay >> 4] * samples_per_ms
        decay = self.decay_factor(ATTACK_MS[attack_decay & 0xF] * samples_per_ms)
        release = self.decay_factor(ATTACK_MS[sustain_release & 0xF] * samples_per_ms)
        sustain = (sustain_release >> 4) / 15

        pos = 0
        while pos < count:
            remaining = count - pos
            if self.state == self.ATTACK:
                # The level rises by the same amount each sample until it gets to 1
                step = 1 / attack_samples
                samples_to_peak = math.ceil((1 - self.level) / step)
                # We can only fill in as many as are left in this render, and always do at least one so
                # that an attack that has already reached the top still moves on to the decay
                num = clamp(samples_to_peak, 1, remaining)
                out[pos : pos + num] = self.level + step * numpy.arange(1, num + 1)
                self.level = min(1.0, float(out[pos + num - 1]))
                if self.level >= 1.0:
                    out[pos + num - 1] = 1.0
                    self.state = self.DECAY
                pos += num
                continue

            if self.state == self.DECAY:
                # It falls to the sustain level and stays there. If the sustain level has been raised above
                # where we are then the level just holds, as it does on the real chip
                factor, floor = decay, min(sustain, self.level)
            else:
                factor, floor = release, 0.0
            levels = self.level * factor ** numpy.arange(1, remaining + 1)
            if self.state == self.RELEASE:
                levels[levels < DECAY_FLOOR / 4] = 0
            out[pos:] = numpy.maximum(levels, floor)
            self.level = float(out[-1])
            pos = count
        return out

    @staticmethod
    def decay_factor(samples: float) -> float:
        """What to multiply the level by each sample so that it reaches DECAY_FLOOR after this many"""
        return DECAY_FLOOR ** (1 / (samples * DECAY_SCALE))


class Voice:
    """One of the chip's sound generators

    At its heart is an oscillator, which is just a 24 bit counter that goes up by the voice's frequency
    setting on every tick of the chip's clock. When it reaches the top it wraps around to the bottom and
    carries on, and each trip from bottom to top is one cycle of the waveform, so the more it goes up by, the
    more cycles there are per second and the higher the note. The waveforms are all made from the counter's
    value: a sawtooth is simply the value itself, for example, which climbs steadily and then drops back."""

    def __init__(self) -> None:
        self.envelope = Envelope()
        # The counter's value at the start of the next render
        self.phase: float = 0.0
        # How many steps the noise generator has taken
        self.noise_pos: int = 0
        # Whether the oscillator wrapped between the last sample of the previous render and the next one
        self.wrap_pending: bool = False
        # The 12 bit value of the waveform at the last sample
        self.last_output: int = 0

        # These are filled in during each render and have an entry per sample. raw is the counter's value
        # without wrapping it, wraps is whether it wrapped on the way to that sample, noise_index is how
        # many steps the noise generator has taken, and accumulator is the counter's wrapped 24 bit value
        self.raw: FloatArray = numpy.zeros(0)
        self.wraps: BoolArray = numpy.zeros(0, dtype=bool)
        self.noise_index: IntArray = numpy.zeros(0, dtype=numpy.int64)
        self.accumulator: IntArray = numpy.zeros(0, dtype=numpy.int64)

    def oscillate(self, count: int, frequency: float, test: bool) -> None:
        """Move the oscillator on by count samples, where frequency is how far it moves in each one

        This sets raw to the counter's value at each sample, which is left to run past the top rather than
        being wrapped, and wraps to whether it wrapped on the way to each sample, meaning that a new cycle of
        the waveform started there."""
        if test:
            # The test bit holds the oscillator at zero
            self.phase = 0.0
            self.wrap_pending = False
            self.raw = numpy.zeros(count)
            self.wraps = numpy.zeros(count, dtype=bool)
            return

        # numpy.arange(count) is 0, 1, 2 and so on, so this is every sample's value in one go
        self.raw = self.phase + frequency * numpy.arange(count, dtype=numpy.float64)
        # How many times the counter has been all the way round by each sample. It wrapped wherever that
        # goes up
        laps = numpy.floor(self.raw / ACC_SIZE)
        self.wraps = numpy.diff(laps, prepend=0) > 0
        self.wraps[0] |= self.wrap_pending

        end = self.phase + frequency * count
        end_laps = math.floor(end / ACC_SIZE)
        self.wrap_pending = bool(end_laps > laps[-1])
        self.phase = end - end_laps * ACC_SIZE
        # Wrapping loses 16 steps of the noise generator each time, so account for them
        self.noise_index = self.noise_pos + numpy.floor(self.raw / (1 << NOISE_SHIFT)).astype(numpy.int64)
        self.noise_pos += end_laps * (ACC_SIZE >> NOISE_SHIFT)

    def sync(self, source: "Voice", frequency: float) -> None:
        """Restart this oscillator's cycle every time the source one starts a new cycle

        This makes our waveform repeat at the source's frequency, so that is the note that's heard. Our own
        frequency no longer sets the note. Instead it sets how far through its cycle our waveform gets before
        it's cut short and restarted, which changes the shape of the wave and so the tone. It's a way to get
        harsher, more complex sounds than the four plain waveforms, and sweeping our frequency while the
        source holds the note gives the tearing sound of a classic "sync lead"."""
        count = len(self.raw)
        indices = numpy.arange(count)
        # For each sample we need to know which sample we last restarted at. If the source wrapped at
        # samples 2 and 5 of a chunk of 7, then
        #
        #     indices                           0   1   2   3   4   5   6
        #     source.wraps                      F   F   T   F   F   T   F
        #     where(wraps, indices, -1)        -1  -1   2  -1  -1   5  -1
        #     maximum.accumulate of that       -1  -1   2   2   2   5   5
        #
        # The where keeps the sample number of each wrap, and maximum.accumulate makes each entry the
        # largest so far, which is the most recent wrap as sample numbers only go up. It stays at -1 until
        # the first wrap in this chunk.
        last_wrap = numpy.maximum.accumulate(numpy.where(source.wraps, indices, -1))
        synced = last_wrap >= 0
        # The samples since the last restart are then . . 0 1 2 0 1, and our counter is that many steps up
        # from zero. Before the first restart it's left as it was
        self.raw = numpy.where(synced, frequency * (indices - last_wrap), self.raw)
        if synced[-1]:
            self.phase = float(frequency * (count - last_wrap[-1])) % ACC_SIZE

    def waveform(self, control: int, pulse_width: int, source: "Voice", noise_table: IntArray) -> FloatArray:
        """The selected waveform as values from -1 to 1"""
        count = len(self.raw)
        if not control & Control.WAVEFORMS:
            self.last_output = 0
            return numpy.zeros(count)

        value = numpy.full(count, 0xFFF, dtype=numpy.int64)
        if control & Control.TRIANGLE:
            msb = self.accumulator >> (ACC_BITS - 1)
            if control & Control.RING:
                msb = msb ^ (source.accumulator >> (ACC_BITS - 1))
            value &= ((self.accumulator ^ (-msb & ACC_MASK)) >> (ACC_BITS - 13)) & 0xFFF
        if control & Control.SAWTOOTH:
            value &= self.accumulator >> (ACC_BITS - 12)
        if control & Control.PULSE:
            value &= numpy.where((self.accumulator >> (ACC_BITS - 12)) >= pulse_width, 0xFFF, 0)
        if control & Control.NOISE:
            if control & Control.TEST:
                value &= noise_table[self.noise_pos % len(noise_table)]
            else:
                value &= noise_table[self.noise_index % len(noise_table)]

        self.last_output = int(value[-1])
        return (value - 0x800) / 0x800


class Filter:
    def __init__(self) -> None:
        # The filter state for each of the low, band and high pass outputs
        self.state: FloatArray = numpy.zeros((3, 2))

    @staticmethod
    def coefficients(cutoff_hz: float, q: float, sample_rate: int) -> tuple[list[FloatArray], FloatArray]:
        """Biquad coefficients for low, band and high pass filters sharing a cutoff"""
        omega = 2 * math.pi * cutoff_hz / sample_rate
        cos = math.cos(omega)
        alpha = math.sin(omega) / (2 * q)
        a = numpy.array([1 + alpha, -2 * cos, 1 - alpha])
        low = numpy.array([(1 - cos) / 2, 1 - cos, (1 - cos) / 2])
        band = numpy.array([alpha, 0, -alpha])
        high = numpy.array([(1 + cos) / 2, -(1 + cos), (1 + cos) / 2])
        return [b / a[0] for b in (low, band, high)], a / a[0]

    def render(
        self, samples: FloatArray, cutoff: int, resonance: int, mode: int, sample_rate: int
    ) -> FloatArray:
        cutoff_hz = MIN_CUTOFF_HZ + (MAX_CUTOFF_HZ - MIN_CUTOFF_HZ) * cutoff / MAX_CUTOFF
        cutoff_hz = min(cutoff_hz, sample_rate * 0.45)
        q = MIN_Q + (MAX_Q - MIN_Q) * resonance / 15
        numerators, denominator = self.coefficients(cutoff_hz, q, sample_rate)

        out = numpy.zeros(len(samples))
        # Every output is run even if it isn't selected, so that switching one on doesn't click
        for i, bit in enumerate((Mode.LOW_PASS, Mode.BAND_PASS, Mode.HIGH_PASS)):
            filtered, self.state[i] = lfilter(numerators[i], denominator, samples, zi=self.state[i])
            if mode & bit:
                out += filtered
        return out


class VoiceSettings(NamedTuple):
    """What a voice's registers currently ask for"""

    frequency: int
    pulse_width: int
    control: int
    attack_decay: int
    sustain_release: int


class Synth:
    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = sample_rate
        self.noise_table = build_noise_table()
        self.reset()

    def reset(self) -> None:
        self.registers = bytearray(NUM_REGISTERS)
        self.voices = [Voice() for i in range(NUM_VOICES)]
        self.filter = Filter()

    def read(self, addr: int) -> int:
        if addr >= NUM_REGISTERS:
            return 0
        if addr == Registers.OSC3:
            return self.voices[2].last_output >> 4
        if addr == Registers.ENV3:
            return int(self.voices[2].envelope.level * 255)
        return self.registers[addr]

    def write(self, addr: int, value: int) -> None:
        if addr >= NUM_REGISTERS:
            return
        value &= 0xFF
        voice, offset = divmod(addr, VOICE_SIZE)
        if voice < NUM_VOICES and offset == Registers.CONTROL:
            # The envelope follows the gate bit as it changes rather than when we next render, so that a note
            # can be restarted by turning it off and on again in one go
            changed = (self.registers[addr] ^ value) & Control.GATE
            if changed:
                self.voices[voice].envelope.gate(bool(value & Control.GATE))
        self.registers[addr] = value

    def voice_settings(self, voice: int) -> VoiceSettings:
        base = voice * VOICE_SIZE
        regs = self.registers
        return VoiceSettings(
            frequency=regs[base + Registers.FREQ_LO] | (regs[base + Registers.FREQ_HI] << 8),
            pulse_width=regs[base + Registers.PULSE_LO] | ((regs[base + Registers.PULSE_HI] & 0xF) << 8),
            control=regs[base + Registers.CONTROL],
            attack_decay=regs[base + Registers.ATTACK_DECAY],
            sustain_release=regs[base + Registers.SUSTAIN_RELEASE],
        )

    def render(self, count: int) -> Samples:
        """Produce the next count samples"""
        all_settings = [self.voice_settings(i) for i in range(NUM_VOICES)]
        # How far each oscillator moves in one of our samples
        steps = [settings.frequency * CLOCK_HZ / self.sample_rate for settings in all_settings]

        for voice, step, settings in zip(self.voices, steps, all_settings):
            voice.oscillate(count, step, bool(settings.control & Control.TEST))

        # Sync needs every oscillator's wraps, and ring modulation needs every final position, so these are
        # separate passes over the voices
        for i, voice in enumerate(self.voices):
            control = all_settings[i].control
            if control & Control.SYNC and not control & Control.TEST:
                voice.sync(self.voices[i - 1], steps[i])
        for voice in self.voices:
            voice.accumulator = voice.raw.astype(numpy.int64) & ACC_MASK

        routing = self.registers[Registers.RESONANCE_ROUTING]
        mode = self.registers[Registers.MODE_VOLUME]
        direct = numpy.zeros(count)
        filtered = numpy.zeros(count)
        for i, voice in enumerate(self.voices):
            settings = all_settings[i]
            wave = voice.waveform(
                settings.control, settings.pulse_width, self.voices[i - 1], self.noise_table
            )
            wave *= voice.envelope.render(
                count, settings.attack_decay, settings.sustain_release, self.sample_rate
            )
            if routing & (1 << i):
                filtered += wave
            elif not (i == 2 and mode & Mode.VOICE3_OFF):
                direct += wave

        cutoff = (self.registers[Registers.CUTOFF_LO] & 7) | (self.registers[Registers.CUTOFF_HI] << 3)
        direct += self.filter.render(filtered, cutoff, routing >> 4, mode, self.sample_rate)

        volume = (mode & 0xF) / 15
        out = direct * (volume * OUTPUT_SCALE * 32767 / NUM_VOICES)
        return numpy.clip(numpy.round(out), -32768, 32767).astype(numpy.int16)
