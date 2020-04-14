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
try:
    from . import popcnt
except ImportError:
    #We also need to import this from create.py as a top-level package
    import popcnt

def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq  = 0.5 * fs
    low  = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a


def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y


def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff // nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=True)
    return b, a


def butter_lowpass_filter(data, cutoff, fs, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = lfilter(b, a, data)
    return y


class Tape(object):
    """Instances of this class represent tapes that can be loaded into computers, including their binary data,
       sound file, name, and tape image (if one is provided)"""
    data_filename  = 'data.bin'
    info_filename  = 'info.cfg'
    image_filename = 'image.png'

    metadata_section = 'metadata'

    pilot_length = 2

    def __init__(self, filename, data=None, info=None, image=None):
        # Tapes are represented by zip files with the following structure
        # /-+           #  root dir
        #   |
        #   - data.bin  # Binary representation of the data on the tape
        #   - info.cfg  # metatdata about the tape
        #   - image.png # tape image
        self._sound = None

        if filename is None:
            assert(data is not None)
            self.data = data
            self.info = info
            self.image = image
        else:
            with zipfile.ZipFile(filename) as zf:
                config_bytes = io.StringIO(zf.read(self.info_filename).decode('ascii'))
                self.data = zf.read(self.data_filename)
                self.info = configparser.ConfigParser()
                self.info.read_file(config_bytes)
                #self.image = pygame.image.load(zf.read(self.image_filename))
                # TODO: Worry about the image later as we'll need to bake them into the computer atlas at runtime
                # if we want them to be definable here
                self.image = None

    def to_binary(self):
        config_bytes = io.StringIO()
        self.info.write(config_bytes)
        config_bytes.seek(0)
        with tempfile.SpooledTemporaryFile() as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(self.data_filename, self.data)
                archive.writestr(self.info_filename, config_bytes.read())

            # Reset file pointer
            tmp.seek(0)
            return tmp.read()

    @property
    def name(self):
        return self.info[self.metadata_section]['name']

    def play_sound(self):
        self.sound.play()
        print('sound play!')

    def stop_sound(self):
        print('sound stop!')
        self.sound.stop()
        #As we might want to resume playing, we rebuild the sound from the current position
        self.build_sound()


class ProgramTape(Tape):
    def __init__(self, filename):

        #Position in the tape in milliseconds
        self.position = 0
        self.current_block = 0
        self.current_bit = 0
        self.block_pos = 0
        self.block_start = 0

        super(ProgramTape, self).__init__(filename)
        self.data_blocks = []
        pos = 0
        while pos < len(self.data):
            word = self.data[pos:pos+4]
            if len(word) != 4:
                # We're done
                break
            size = struct.unpack('>I', word)[0]
            self.data_blocks.append(self.data[pos+4:pos+4+size])
            pos += size+4

        self.build_samples()
        self.build_sound()

    def build_samples(self):
        freq, sample_size, num_channels = pygame.mixer.get_init()
        tone_length = 4 * float(freq) / 22050
        clr_length = int(tone_length)
        set_length = int(tone_length * 2)

        # We'll want a pilot signal first as it will go before all data segments
        num_pilot_samples = 22050 * self.pilot_length
        pilot_samples = numpy.zeros(shape=num_pilot_samples, dtype='float64')
        popcnt.create_tone(pilot_samples, set_length)

        self.byte_samples = []
        self.bit_times    = []
        self.bits         = []

        all_samples = []
        total_samples = 0

        for block in self.data_blocks:
            data = numpy.fromstring(block, dtype='uint32')
            set_bits = popcnt.count_array(data)
            clr_bits = (len(data) * 32) - set_bits
            # The sigmals we're using are either 8 (4 on 4 off) or 16 samples at 22050 Hz, which is
            # either 1378 or 2756 Hz

            block_samples = 2 * (set_bits * set_length + clr_bits * clr_length)
            total_samples += block_samples
            total_samples += num_pilot_samples

            samples = numpy.zeros(shape=block_samples, dtype='float64')
            # print 'ones={ones} zeros={zeros} length={l}'.format(ones=set_bits, zeros=clr_bits, l=float(block_samples) // freq)
            # The position in samples that each byte starts
            byte_samples = numpy.zeros(shape=len(data) * 4, dtype='uint32')
            # The number of milliseconds that each bit should
            bit_times = numpy.zeros(shape=len(data) * 4 * 8, dtype='uint32')
            bits = numpy.zeros(shape=len(data) * 4 * 9, dtype='uint8')
            popcnt.create_samples(data, samples, byte_samples, bit_times, bits,
                                  clr_length, set_length, float(1000) / 22050)
            all_samples.append(pilot_samples)
            all_samples.append(samples)
            self.byte_samples.append(byte_samples)
            self.bit_times.append(bit_times)
            self.bits.append(bits)

        samples = numpy.concatenate(all_samples)
        # bandpass filter it to make it less harsh
        self.samples = butter_bandpass_filter(samples, 500, 2700, freq).astype('int16')

        if num_channels != 1:
            # Duplicate it into the required number of channels
            self.samples = self.samples.repeat(num_channels).reshape(total_samples, num_channels)
        self.sample_rate = float(freq) / 1000

        # start time for each block...
        self.start_time = []
        last_end = 0
        for i, times in enumerate(self.bit_times):
            self.start_time.append(last_end + (i + 1) * self.pilot_length * 1000)
            last_end += times[-1]

    def build_sound(self):
        offset = int(self.position * self.sample_rate)
        print(f'{self.position=} {len(self.samples)=} {offset=}')
        self.sound = pygame.sndarray.make_sound(self.samples[offset:])

    def byte_ready(self):
        if self.current_block >= len(self.data_blocks):
            return True

        pos = self.position - self.block_start - self.pilot_length*1000
        pos_sample = pos * self.sample_rate
        target_sample = self.byte_samples[self.current_block][self.block_pos]
        ready = pos_sample > target_sample
        if ready:
            print(f'Byte ready, {pos=} {pos_sample=} {target_sample=}')
        return ready

    def get_byte(self):
        c = self.data_blocks[self.current_block][self.block_pos]
        self.block_pos += 1
        if self.block_pos >= len(self.data_blocks[self.current_block]):
            self.current_block += 1
            self.block_pos = 0
            self.current_bit = 0
            self.block_start = self.position

        return c

    def update(self, elapsed, paused, num_required):
        if paused:
            self.pause_time += elapsed
            return

        self.position += elapsed
        print(f'Update! {self.position=} {self.start_time[self.current_block]=}')

        if self.current_block >= len(self.data_blocks) or \
           self.current_bit >= len(self.bit_times[self.current_block]):
            return []

        if self.position < self.start_time[self.current_block]:
            return None

        # We've got some to show, how many
        pos = self.position - self.block_start - self.pilot_length*1000
        try:
            while self.bit_times[self.current_block][self.current_bit] <= pos:
                self.current_bit += 1
        except IndexError:
            self.current_bit = len(self.bit_times[self.current_block])
        return self.bits[self.current_block][self.current_bit:self.current_bit + num_required]
