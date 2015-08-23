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
uint32_t *rng = (void*)0x01001000 + WIDTH*HEIGHT*2;
uint32_t *crash_handler_word = (void*)0x20000;

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
    for(i=border_size; i<HEIGHT-border_size; i++) {
        //start of border
        memset(palette_data + WIDTH*i, border_palette, border_size);
        //middle part
        memset(palette_data + WIDTH*i + border_size, palette_byte, WIDTH-(border_size*2));
        //final border
        memset(palette_data + WIDTH*(i+1) - border_size, border_palette, border_size);
    }

    //memset(palette_data, palette_byte, WIDTH*HEIGHT);
    memset(letter_data, 0, WIDTH*HEIGHT);
}

void dump_hex(uint32_t value, size_t cursor_pos) {
    int i;
    for(i=0; i<8; i++) {
        int val = (value>>((7-i)*4))&0xf;
        val = val < 10 ? '0' + val : 'a' + (val-10);
        letter_data[cursor_pos++] = val;
    }
}

void crash_handler(uint32_t type, uint32_t pc, uint32_t sp, uint32_t lr) {
    char *p;
    clear_screen_with_border(BLACK, RED, 1);
    switch(type) {
    case 0:
        p = "ILLEGAL INSTRUCTION";
        break;
    case 1:
        p = "PREFECT ERROR";
        break;
    case 2:
        p = "DATA ABORT";
        break;
    case 3:
        p = "ADDRESS EXCEPTION";
        break;
    default:
        p = "UNKNOWN ERROR";
        break;
    }
    size_t cursor_pos = WIDTH*2 + 15;
    while(*p) {
        letter_data[cursor_pos++] = *p++;
    }

    p = "sp : 0x";
    cursor_pos = WIDTH*4 + 10;
    while(*p) {
        letter_data[cursor_pos++] = *p++;
    }
    dump_hex(sp,cursor_pos);

    p = "lr : 0x";
    cursor_pos = WIDTH*5 + 10;
    while(*p) {
        letter_data[cursor_pos++] = *p++;
    }
    dump_hex(lr,cursor_pos);

    p = "pc : 0x";
    cursor_pos = WIDTH*6 + 10;
    while(*p) {
        letter_data[cursor_pos++] = *p++;
    }
    dump_hex(pc-8,cursor_pos);

    while(1) {
    }
}
