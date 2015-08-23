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

#define INITIAL_CURSOR_POS ((WIDTH+1)*border_size)
#define FINAL_CURSOR_POS   (WIDTH*HEIGHT - border_size*(WIDTH+1))
size_t border_size = 2;
size_t cursor_pos = 0;

void newline() {
    cursor_pos = ((cursor_pos/WIDTH)+1)*WIDTH + border_size;
    if(cursor_pos >= FINAL_CURSOR_POS) {
        cursor_pos = INITIAL_CURSOR_POS;
    }
}

void process_char(uint8_t c) {
    if(isprint(c)) {
        size_t line_pos;
        letter_data[cursor_pos++] = c;
        line_pos = cursor_pos%WIDTH;
        if(line_pos >= WIDTH-border_size) {
            newline();
        }

        if(cursor_pos >= FINAL_CURSOR_POS) {
            cursor_pos = 0;
        }
    }
    else {
        if(c == '\r') {
            newline();

        }
        else if(c == 8) {
            //backspace
            if((cursor_pos%WIDTH) > border_size) {
                cursor_pos--;
                letter_data[cursor_pos] = ' ';
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
    cursor_pos = INITIAL_CURSOR_POS;
    clear_screen_with_border(BLUE, LIGHT_BLUE, border_size);
    process_text();
    return 0;
}
