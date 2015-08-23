#include <stdint.h>
#include <string.h>
#include <ctype.h>

#define WIDTH  40
#define HEIGHT 30
#define RINGBUFFER_SIZE 128
uint8_t *palette_data = (void*)0x01001000;
uint8_t *letter_data  = (void*)0x01001000 + WIDTH*HEIGHT;
uint32_t *keyboard_bitmask = (void*)0x01000000;
uint8_t *keyboard_ringbuffer = (void*)0x01000020;
uint8_t *ringbuffer_pos      = (void*)0x010000a0;

enum colours    {
    BLACK       = 0,
    WHITE       = 1,
    RED         = 2,
    CYAN        = 3,
    VIOLET      = 4,
    GREEN       = 5,
    BLUE        = 6,
    YELLOW      = 7,
    ORANGE      = 8,
    BROWN       = 9,
    LIGHT_RED   = 10,
    DARK_GREY   = 11,
    MED_GREY    = 12,
    LIGHT_GREEN = 13,
    LIGHT_BLUE  = 14,
    LIGHT_GREY  = 15,
};

void clear_screen(enum colours background, enum colours foreground) {
    uint8_t palette_byte = background << 4 | foreground;
    memset(palette_data, palette_byte, WIDTH*HEIGHT);
    memset(letter_data, 0, WIDTH*HEIGHT);
}

size_t screen_pos = 0;

void process_char(uint8_t c) {
    if(isprint(c)) {
        letter_data[screen_pos++] = c;
        if(screen_pos >= WIDTH*HEIGHT) {
            screen_pos = 0;
        }
    }
    else {
        //only care about return
        if(c == '\n') {
            screen_pos = ((screen_pos/WIDTH)+1)*WIDTH;
            if(screen_pos >= WIDTH*HEIGHT) {
                screen_pos = 0;
            }
        }
    }
}

void wait_for_interrupt() {
    asm("mov r7,#17");
    asm("swi #0");
}

void process_text() {
    uint8_t last_pos = *ringbuffer_pos;

    while(1) {
        uint8_t new_pos;
        while(last_pos == (new_pos = *ringbuffer_pos)) {
            wait_for_interrupt();
        }
        while(last_pos != new_pos) {
            uint8_t c;
            c = keyboard_ringbuffer[last_pos];
            process_char(c);
            last_pos = ((last_pos + 1) % RINGBUFFER_SIZE);
        }
    }
}

int _start(void) {
    clear_screen(BLUE, LIGHT_BLUE);
    process_text();
    return 0;
}
