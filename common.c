#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include "synapse.h"

uint8_t *palette_data = (void*)0x01001000;
uint8_t *letter_data  = (void*)0x01001000 + WIDTH*HEIGHT;
uint32_t *keyboard_bitmask = (void*)0x01000000;
uint8_t *keyboard_ringbuffer = (void*)0x01000020;
uint8_t *ringbuffer_pos      = (void*)0x010000a0;
struct tape_control *tape_control = (void*)0x01002000;
uint8_t *tape_load_area = (void*)0xf0000;


void clear_screen(enum colours background, enum colours foreground) {
    uint8_t palette_byte = background << 4 | foreground;
    memset(palette_data, palette_byte, WIDTH*HEIGHT);
    memset(letter_data, 0, WIDTH*HEIGHT);
}

void clear_screen_with_border(enum colours background, enum colours foreground, size_t border_size) {
    uint8_t palette_byte = background << 4 | foreground;
    uint8_t border_palette = foreground << 4 | background;
    int i;
    //set the top border

    memset(palette_data, border_palette, WIDTH*border_size);
    memset(palette_data + WIDTH*(HEIGHT-border_size), border_palette, WIDTH*border_size);
    for(i=2; i<HEIGHT-border_size; i++) {
        //start of border
        memset(palette_data + WIDTH*i, border_palette, border_size);
        //middle part
        memset(palette_data + WIDTH*i + border_size, palette_byte, WIDTH-(border_size*2));
        //final border
        memset(palette_data + WIDTH*(i+1) - border_size, border_palette, border_size);
    }

    //memset(palette_data, palette_byte, WIDTH*HEIGHT);
    //memset(letter_data, 0, WIDTH*HEIGHT);
}
