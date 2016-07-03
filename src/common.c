#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include "synapse.h"

uint8_t                       *palette_data        = (void*)0x01001000;
uint8_t                       *letter_data         = (void*)0x01001000 + WIDTH*HEIGHT;
volatile uint32_t             *keyboard_bitmask    = (void*)0x01000000;
volatile uint8_t              *keyboard_ringbuffer = (void*)0x01000020;
volatile uint8_t              *ringbuffer_pos      = (void*)0x010000a0;
volatile struct tape_control  *tape_control        = (void*)0x01002000;
uint8_t                       *tape_load_area      = (void*)0x8000;
uint8_t                       *symbols_load_area   = (void*)0x30000;
volatile uint32_t             *rng                 = (void*)0x01001000 + WIDTH*HEIGHT*2;
void                         **crash_handler_word  = (void*)0x20000;

uint64_t wait_for_interrupt() {
    asm("push {r7}");
    asm("mov r7,#0");
    asm("swi #0");
    asm("pop {r7}");
}

void set_alarm(int milliseconds) {
    asm("push {r7}");
    asm("mov r7,#3");
    asm("swi #0");
    asm("pop {r7}");
}

void toggle_pos(size_t pos, uint32_t normal, uint32_t inverted) {
     if(*(palette_data+pos) == normal) {
         *(palette_data+pos) = inverted;
     }
     else {
         *(palette_data+pos) = normal;
     }
}

void clear_screen(enum colours background, enum colours foreground) {
    uint8_t palette_byte = background << 4 | foreground;
    memset(palette_data, palette_byte, WIDTH*HEIGHT);
    memset(letter_data, 0, WIDTH*HEIGHT);
}

uint32_t ntohl( uint32_t in ) {
    return __builtin_bswap32( in );
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

size_t dump_text(char *text, size_t cursor_pos) {
    while(*text) {
        letter_data[cursor_pos++] = *text++;
    }

    return cursor_pos;
}

void crash_handler(uint32_t type, uint32_t pc, uint32_t sp, uint32_t lr) {
    char *p;
    uint32_t *registers = (void*)(crash_handler_word + 1);
    int i;
    clear_screen_with_border(BLACK, RED, 1);
    switch(type) {
    case 0:
        p = "ILLEGAL INSTRUCTION";
        break;
    case 1:
        p = "PREFETCH ERROR";
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
    cursor_pos = dump_text(p, cursor_pos);

    for(i = 0; i < 13; i++) {
        cursor_pos = WIDTH*(4+i) + 10;
        if(i < 10) {
            p = "r.  : 0x";
        }
        else {
            p = "r1. : 0x";
        }
        while(*p) {
            letter_data[cursor_pos++] = *p == '.' ? '0' + (i%10) : *p;
            p++;
        }
        dump_hex(registers[i], cursor_pos);
    }

    cursor_pos = dump_text("sp  : 0x", WIDTH*17 + 10);
    dump_hex(sp,cursor_pos);

    cursor_pos = dump_text("lr  : 0x", WIDTH*18 + 10);
    dump_hex(lr,cursor_pos);

    cursor_pos = dump_text("pc  : 0x", WIDTH*19 + 10);
    dump_hex((pc-8)&0x03fffffc,cursor_pos);

    cursor_pos = dump_text("psr : 0x", WIDTH*21 + 10);
    dump_hex((pc)&0xfc000003,cursor_pos);

    char *mode = "IMPOSSIBLE MODE";
    switch(pc&3) {
    case 0:
        mode = "USR";
        break;
    case 1:
        mode = "FIQ";
        break;
    case 2:
        mode = "IRQ";
        break;
    case 3:
        mode = "SUP";
        break;
    }

    cursor_pos = dump_text("mode: ", WIDTH*22 + 10);
    (void) dump_text(mode, cursor_pos);

    while(1) {
        wait_for_interrupt();
    }
}