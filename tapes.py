from scipy.signal import butter, lfilter
import zipfile
import tempfile
import configparser
import pygame
import pygame.image
import numpy
import io
import struct
import traceback
import globals

try:
    from . import popcnt  # type: ignore
except ImportError:
    # We also need to import this from create.py as a top-level package
    import popcnt


def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype="band")
    return b, a


def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y


def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff // nyq
    b, a = butter(order, normal_cutoff, btype="low", analog=True)
    return b, a


def butter_lowpass_filter(data, cutoff, fs, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = lfilter(b, a, data)
    return y


class Tape(object):
    """Instances of this class represent tapes that can be loaded into computers, including their binary data,
    sound file, name, and tape image (if one is provided)"""

    data_filename = "data.bin"
    info_filename = "info.cfg"
    image_filename = "image.png"

    metadata_section = "metadata"

    pilot_length = 2

    def __init__(self, filename, data=None, info=None, image=None):
        # Tapes are represented by zip files with the following structure
        # /-+           #  root dir
        #   |
        #   - data.bin  # Binary representation of the data on the tape
        #   - info.cfg  # metatdata about the tape
        #   - image.png # tape image
        self._sound = None
        self.pause_bits = [0 for i in range(1024)]

        if filename is None:
            assert data is not None
            self.data = data
            self.info = info
            self.image = image
        else:
            with open(filename, "rb") as file:
                self.from_binary(file.read())

    def from_binary(self, data):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            config_bytes = io.StringIO(zf.read(self.info_filename).decode("ascii"))
            self.data = zf.read(self.data_filename)
            self.info = configparser.ConfigParser()
            self.info.read_file(config_bytes)
            # self.image = pygame.image.load(zf.read(self.image_filename))
            # TODO: Worry about the image later as we'll need to bake them into the computer atlas at runtime
            # if we want them to be definable here
            self.image = None

    def to_binary(self):
        config_bytes = io.StringIO()
        self.info.write(config_bytes)
        config_bytes.seek(0)
        with tempfile.SpooledTemporaryFile() as tmp:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(self.data_filename, self.data)
                archive.writestr(self.info_filename, config_bytes.read())

            # Reset file pointer
            tmp.seek(0)
            return tmp.read()

    @property
    def name(self):
        return self.info[self.metadata_section]["name"]

    def play_sound(self):
        self.sound.play()

    def stop_sound(self):
        self.sound.stop()
        # As we might want to resume playing, we rebuild the sound from the current position
        self.build_sound()


class ProgramTape(Tape):
    cache_seconds = 1

    def __init__(self, filename):

        # Position in the tape in milliseconds
        self.position = 0
        self.current_block = 0
        self.current_bit = 0
        self.block_pos = 0

        super(ProgramTape, self).__init__(filename)
        self.data_blocks = []
        pos = 0
        while pos < len(self.data):
            word = self.data[pos : pos + 4]
            if len(word) != 4:
                # We're done
                break
            size = struct.unpack(">I", word)[0]
            self.data_blocks.append(self.data[pos + 4 : pos + 4 + size])
            pos += size + 4

        self.build_samples()
        self.build_sound()
        self.block_start = self.preamble_len

    def rewind(self):
        self.position = 0
        self.current_block = 0
        self.current_bit = 0
        self.block_pos = 0
        self.block_start = self.preamble_len
        self.build_sound()

    def fast_forward(self):
        self.position = self.end_time
        self.current_block = len(self.data_blocks) - 1
        self.current_bit = len(self.bit_times[self.current_block]) - 1
        self.block_pos = len(self.data_blocks[self.current_block]) - 1
        self.block_start = self.end_time
        self.build_sound()

    def build_samples(self):
        freq, sample_size, num_channels = pygame.mixer.get_init()
        tone_length = 4 * float(freq) / 22050
        clr_length = int(tone_length)
        set_length = int(tone_length * 2)

        # We'll want a pilot signal first as it will go before all data segments
        num_pilot_samples = freq * self.pilot_length
        pilot_samples = numpy.zeros(shape=num_pilot_samples, dtype="float64")
        popcnt.create_tone(pilot_samples, set_length)

        # And before the first pilot segment, we want some tape noise to sell the illusion
        raw_samples = globals.sounds.noise.get_raw()
        # That's a bytes object

        self.byte_samples = []
        self.bit_times = []
        self.bits = []

        all_samples = [numpy.frombuffer(raw_samples, dtype="int16")]
        total_samples = len(all_samples[0])

        self.noise_len = (1000 * total_samples) / freq
        self.preamble_len = self.noise_len + self.pilot_length * 1000

        for block in self.data_blocks:
            data = numpy.fromstring(block, dtype="uint32")
            set_bits = popcnt.count_array(data)
            clr_bits = (len(data) * 32) - set_bits
            # The sigmals we're using are either 8 (4 on 4 off) or 16 samples at 22050 Hz, which is
            # either 1378 or 2756 Hz

            block_samples = 2 * (set_bits * set_length + clr_bits * clr_length)
            total_samples += block_samples
            total_samples += num_pilot_samples

            samples = numpy.zeros(shape=block_samples, dtype="float64")
            # print 'ones={ones} zeros={zeros} length={l}'.format(ones=set_bits, zeros=clr_bits, l=float(block_samples) // freq)
            # The position in samples that each byte starts
            byte_samples = numpy.zeros(shape=len(data) * 4, dtype="uint32")
            # The number of milliseconds that each bit should
            bit_times = numpy.zeros(shape=len(data) * 4 * 8, dtype="uint32")
            bits = numpy.zeros(shape=len(data) * 4 * 9, dtype="uint8")
            popcnt.create_samples(
                data, samples, byte_samples, bit_times, bits, clr_length, set_length, float(1000) / freq
            )
            all_samples.append(pilot_samples)
            all_samples.append(samples)
            self.byte_samples.append(byte_samples)
            self.bit_times.append(bit_times)
            self.bits.append(bits)

        samples = numpy.concatenate(all_samples)
        # bandpass filter it to make it less harsh
        self.samples = butter_bandpass_filter(samples, 500, 2700, freq).astype("int16")

        if num_channels != 1:
            # Duplicate it into the required number of channels
            self.samples = self.samples.repeat(num_channels).reshape(total_samples, num_channels)
        self.sample_rate = float(freq) / 1000
        self.cache_samples = self.cache_seconds * freq

        # start time for each block...
        self.start_time = []
        last_end = self.preamble_len
        for i, times in enumerate(self.bit_times):
            self.start_time.append(last_end)
            last_end += times[-1] + (self.pilot_length * 1000)
        self.end_time = last_end

    def build_sound(self):
        offset = int(self.position * self.sample_rate)
        self.sound = pygame.sndarray.make_sound(self.samples[offset:])
        self.sound.set_volume(0.2)

    def byte_ready(self):
        if self.current_block >= len(self.data_blocks):
            return True

        if self.position < self.start_time[self.current_block]:
            return False

        pos = self.position - self.block_start
        pos_sample = pos * self.sample_rate
        target_sample = self.byte_samples[self.current_block][self.block_pos]
        if pos_sample > target_sample + self.cache_samples:
            self.trim_cache(pos)
        ready = pos_sample > target_sample

        return ready

    def trim_cache(self, pos):
        print("Trim cache")
        pos_sample = pos * self.sample_rate

        while pos_sample > self.byte_samples[self.current_block][self.block_pos] + self.cache_samples:
            self.block_pos += 1
            if self.block_pos >= len(self.byte_samples[self.current_block]):
                self.advance_block()
                return

    def get_byte(self):
        try:
            c = self.data_blocks[self.current_block][self.block_pos]
            self.block_pos += 1
            if self.block_pos >= len(self.data_blocks[self.current_block]):
                self.advance_block()
        except IndexError:
            c = None
        return c

    def advance_block(self):
        self.current_block += 1
        self.block_pos = 0
        self.current_bit = 0
        if self.current_block < len(self.start_time):
            self.block_start = self.start_time[self.current_block]
        else:
            self.block_start = self.position

    def update(self, elapsed, paused, num_required):
        if not paused:
            self.position += elapsed

        # The update function is mainly to return to the display a set of bits it should use to draw its
        # coloured bars. If we don't have any bits we also tell it if we're playing a tone so it can draw cool
        # red and grey bars.
        #
        # Actual delivery of data is handled by byte_ready() and get_byte(). If you call get_byte() without
        # calling byte_ready it will just return all the bytes for you as fast as you want them (to facilitate
        # skipping the loading), but one thing we need to do is to handle the other case; when a caller is not
        # calling get_byte() while we're playing. If after we've been playing for a minute and the cpu asks
        # what our byte is we shouldn't give them the whole thing, we need to cut off ones that are too

        if self.current_block >= len(self.data_blocks):
            return None, TapeStage.no_data

        if self.current_bit >= len(self.bit_times[self.current_block]):
            diff = self.position - self.block_start - self.bit_times[self.current_block][-1]
            if diff > 100:
                self.advance_block()
            else:
                return None, TapeStage.no_data

        if self.position < self.noise_len:
            return None, TapeStage.no_tone

        if self.position < self.start_time[self.current_block]:
            return None, TapeStage.tone

        if paused:
            return self.pause_bits[:num_required], TapeStage.data

        # We've got some to show, how many
        pos = self.position - self.block_start
        try:
            while self.bit_times[self.current_block][self.current_bit] <= pos:
                self.current_bit += 1
        except IndexError:
            self.current_bit = len(self.bit_times[self.current_block])
        return (
            self.bits[self.current_block][self.current_bit : self.current_bit + num_required],
            TapeStage.data,
        )


class TapeStage:
    no_data = 0
    no_tone = 1
    tone = 2
    data = 3
