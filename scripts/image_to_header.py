from PIL import Image
import sys
import numpy
import zlib
import lzma
import subprocess


def rgb(r, g, b, a=0):
    return r << 16 | g << 8 | b


class Colours:
    BLACK = rgb(0, 0, 0, 255)
    WHITE = rgb(255, 255, 255, 255)
    RED = rgb(136, 0, 0, 255)
    CYAN = rgb(170, 255, 238, 255)
    VIOLET = rgb(204, 68, 204, 255)
    GREEN = rgb(0, 204, 85, 255)
    BLUE = rgb(0, 0, 170, 255)
    YELLOW = rgb(238, 238, 119, 255)
    ORANGE = rgb(221, 136, 85, 255)
    BROWN = rgb(102, 68, 0, 255)
    LIGHT_RED = rgb(255, 119, 119, 255)
    DARK_GREY = rgb(51, 51, 51, 255)
    MED_GREY = rgb(119, 119, 119, 255)
    LIGHT_GREEN = rgb(170, 255, 102, 255)
    LIGHT_BLUE = rgb(0, 136, 255, 255)
    LIGHT_GREY = rgb(187, 187, 187, 255)

    palette = {
        col: i
        for i, col in enumerate(
            [
                BLACK,
                WHITE,
                RED,
                CYAN,
                VIOLET,
                GREEN,
                BLUE,
                YELLOW,
                ORANGE,
                BROWN,
                LIGHT_RED,
                DARK_GREY,
                MED_GREY,
                LIGHT_GREEN,
                LIGHT_BLUE,
                LIGHT_GREY,
            ]
        )
    }


im = Image.open(sys.argv[1])
out_filename = sys.argv[2]
data = im.getdata()


width = 40
height = 30
cell_size = 8

if im.size != (width * cell_size, height * cell_size):
    raise SystemExit(f"bad size {im.size}")

palette_data = numpy.zeros(width * height, dtype=numpy.uint8)
pixel_data = numpy.zeros(width * height * cell_size * cell_size // 8, dtype=numpy.uint8)


def set_bit(x, y):

    bit = (y * width * cell_size) + x
    byte = bit >> 3
    # print(f'set {x=} {y=} {byte=} {bit=}')
    bit = bit & 7
    pixel_data[byte] |= 1 << bit


for cell_y in range(height):
    for cell_x in range(width):
        cell = im.crop(
            (cell_x * cell_size, cell_y * cell_size, (cell_x + 1) * cell_size, (cell_y + 1) * cell_size)
        )
        cell_pixels = cell.getdata()

        # Count the colours
        counts = {}
        for pixel in cell_pixels:
            try:
                counts[pixel] += 1
            except:
                counts[pixel] = 1

        if len(counts) > 2:
            raise SystemExit("Bad cell")

        counts = sorted(counts.items(), key=lambda key: key[1], reverse=True)
        # print(counts)
        # raise SystemExit()
        # The first is the most common, so it should be the background
        cell_pixels = [0 if col == counts[0][0] else 1 for col in cell_pixels]
        print(cell_x, cell_y, counts)
        colours = [Colours.palette[rgb(*col)] for col, count in counts]
        if len(counts) == 1:
            colours = (colours[0] << 4) | colours[0]
        else:
            colours = (colours[0] << 4) | colours[1]
        palette_data[cell_y * width + cell_x] = colours

        # set the pixels too
        pos_x = cell_x * cell_size
        pos_y = cell_y * cell_size
        for i, pixel in enumerate(cell_pixels):
            if pixel == 0:
                continue

            x = i % cell_size
            y = i // cell_size
            set_bit(pos_x + x, pos_y + y)

palette_data = bytes(palette_data)
pixel_data = bytes(pixel_data)

jim = palette_data + pixel_data
with open("/tmp/bin", "wb") as file:
    file.write(jim)

subprocess.check_call(["lzg", "-9", "/tmp/bin", "/tmp/jim"])

with open("/tmp/jim", "rb") as file:
    jim_compressed = file.read()

out_data = [f"size_t wolf_uncompressed_len = {len(jim)};"]
out_data.append(f"uint8_t wolf_compressed[{len(jim_compressed)}] = {{")

for pos in range(0, len(jim_compressed), 16):
    out_data.append(", ".join((f"0x{b:02x}" for b in jim_compressed[pos : pos + 16])) + ",")
out_data.append("};")

# out_data = [f'uint8_t wolf_palette_data[{len(palette_data)}] = {{']
# for pos in range(0, len(palette_data), 16):
#     out_data.append(', '.join( (f'0x{b:02x}' for b in palette_data[pos:pos+16]) ) + ',')

# out_data.append(f'}};\nuint8_t wolf_pixel_data[{len(pixel_data)}] = {{')

# for pos in range(0, len(pixel_data), 16):
#     out_data.append(', '.join( (f'0x{b:02x}' for b in pixel_data[pos:pos+16]) ) + ',')
# out_data.append('};\n')

with open(out_filename, "w") as file:
    file.write("\n".join(out_data))
