#include <stdint.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include "synapse.h"
#include <terminal.h>

volatile struct tape_control  *tape_control        = (void*)0x01002000;
uint8_t                       *tape_load_area      = (void*)0x8000;
uint8_t                       *symbols_load_area   = (void*)0x40000;
volatile uint32_t             *rng                 = (void*)0x01001000 + WIDTH*HEIGHT*2;
volatile uint32_t             *clock_word          = (void*)0x01001000 + (WIDTH*HEIGHT*2) + 4;
void                         **crash_handler_word  = (void*)0x3fff8;

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

uint32_t ntohl( uint32_t in ) {
    return __builtin_bswap32( in );
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
    set_screen_data(PALETTE(BLACK,RED), PALETTE(RED,BLACK), 1);
    clear_screen_default();
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

    char *mode = NULL;
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


int _start(void) {
    crash_handler_word[0] = crash_handler;
    return main();
}

void exit(int status) {
    while(1) {
        wait_for_interrupt();
    }
}
