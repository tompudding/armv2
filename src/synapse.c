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

#define BACKGROUND BLACK
#define FOREGROUND GREEN
uint32_t os_normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t os_inverted = PALETTE(FOREGROUND,BACKGROUND);
size_t os_border_size = 2;
size_t os_cursor_pos = 0;

int main(void);

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

void set_screen_data(uint32_t normal, uint32_t inverted, size_t border_size) {
    os_normal   = normal;
    os_inverted = inverted;
    os_border_size = border_size;
    os_cursor_pos = INITIAL_CURSOR_POS;
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

void clear_screen_default() {
    clear_screen_with_border(os_normal, os_inverted, os_border_size);
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

void newline(int reset_square) {
    if(reset_square) {
        *(palette_data + os_cursor_pos) = os_normal;
    }
    os_cursor_pos = ((os_cursor_pos / WIDTH) + 1) * WIDTH + os_border_size;
    if(os_cursor_pos >= FINAL_CURSOR_POS) {
        //move all rows up one
        memmove(letter_data+os_border_size*WIDTH, letter_data + (os_border_size+1)*WIDTH, (WIDTH*(HEIGHT-os_border_size*2-1)));
        memset(letter_data + (WIDTH*(HEIGHT-os_border_size-1)), 0, WIDTH);
        os_cursor_pos = ((os_cursor_pos/WIDTH)*WIDTH) + os_border_size - WIDTH;
        //os_cursor_pos = INITIAL_OS_CURSOR_POS;
    }
}

void process_string(char *s) {
    while(*s) {
        process_char(*s++);
    }
}

void process_char(uint8_t c) {
    if(isprint(c)) {
        size_t line_pos;
        *(palette_data+os_cursor_pos) = os_normal;
        letter_data[os_cursor_pos++] = c;
        line_pos = os_cursor_pos%WIDTH;
        if(line_pos >= WIDTH-os_border_size) {
            newline(0);
        }
    }
    else {
        if(c == '\r') {
            newline(1);
        }
        else if(c == 8) {
            //backspace
            *(palette_data+os_cursor_pos) = os_normal;
            if((os_cursor_pos%WIDTH) > os_border_size) {
                os_cursor_pos--;
                letter_data[os_cursor_pos] = ' ';
            }
        }
    }
}


int _start(void) {
    crash_handler_word[0] = crash_handler;
    return main();
}

void _exit(int status) {
    while(1) {
        wait_for_interrupt();
    }
}
