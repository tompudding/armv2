#include "terminal.h"
#include <string.h>
#include <synapse.h>

volatile uint32_t *keyboard_bitmask    = (void*)0x01000000;
volatile uint8_t  *keyboard_ringbuffer = (void*)0x01000020;
volatile uint8_t  *ringbuffer_pos      = (void*)0x010000a0;


#define BACKGROUND BLACK
#define FOREGROUND GREEN
#define OS_CURSOR_MIN_DEFAULT (os_border_size * (WIDTH + 1))

uint32_t os_normal      = PALETTE(BACKGROUND,FOREGROUND);
uint32_t os_inverted    = PALETTE(FOREGROUND,BACKGROUND);
size_t   os_border_size = 2;
size_t   os_cursor_pos  = 0;
size_t   os_cursor_min  = 0;
bool word_wrap = true;
bool in_word = false;
int word_start = 0;

void set_screen_data(uint32_t normal, uint32_t inverted, size_t border_size)
{
    os_normal   = normal;
    os_inverted = inverted;
    os_border_size = border_size;
    os_cursor_pos = INITIAL_CURSOR_POS;
}

void toggle_pos(size_t pos)
{
    uint8_t *p = palette_data + pos;
    *p = ((*p & 0xf0) >> 4) | ((*p & 0x0f) << 4);
}

void clear_screen(enum colours background, enum colours foreground)
{
    uint8_t palette_byte = background << 4 | foreground;
    memset(palette_data, palette_byte, WIDTH*HEIGHT);
    memset(letter_data, 0, WIDTH*HEIGHT);
}

void clear_screen_with_border(uint32_t normal, uint32_t inverted, size_t border_size)
{
    int i;
    //set the top border

    memset(palette_data, inverted, WIDTH*border_size);
    memset(palette_data + WIDTH*(HEIGHT-border_size), inverted, WIDTH*border_size);
    for(i=border_size; i<HEIGHT-border_size; i++) {
        //start of border
        memset(palette_data + WIDTH*i, inverted, border_size);
        //middle part
        memset(palette_data + WIDTH*i + border_size, normal, WIDTH-(border_size*2));
        //final border
        memset(palette_data + WIDTH*(i+1) - border_size, inverted, border_size);
    }

    //memset(palette_data, normal, WIDTH*HEIGHT);
    memset(letter_data, 0, WIDTH*HEIGHT);
}

void clear_screen_default()
{
    clear_screen_with_border(os_normal, os_inverted, os_border_size);
}

void newline(int reset_square)
 {
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
        if(in_word) {
            word_start -= WIDTH;
        }
        if( os_cursor_min > OS_CURSOR_MIN_DEFAULT + WIDTH ) {
            os_cursor_min -= WIDTH;
        }
        else {
            os_cursor_min = OS_CURSOR_MIN_DEFAULT;
        }
    }
}

void process_string(char *s)
{
    while(*s) {
        process_char(*s++);
    }
}

size_t prev_pos(size_t pos) {
    if((pos%WIDTH) > os_border_size) {
        return pos - 1;
    }
    else if( (pos / WIDTH) > os_border_size ) {
        //This hopefully means it exactly equal to border size and not on the top row
        return pos - (os_border_size * 2 + 1);
    }
    return pos;
}

void recreate_word_start() {
    //From the current position we have to step backwards to see how big the word we've gone back into is
    if( os_cursor_pos == os_cursor_min ) {
        in_word = false;
        return;
    }

    size_t last = prev_pos(os_cursor_pos);
    if( last == os_cursor_pos || isspace(letter_data[last]) ) {
        in_word = false;
        return;
    }

    //This means we are in a word
    in_word = true;
    while( last > os_cursor_min && !isspace(letter_data[last]) ) {
        word_start = last;
        size_t new_last = prev_pos(last);
        if( new_last == last ) {
            break;
        }
        last = new_last;
    }
}

void process_char(uint8_t c)
{
    if(isprint(c)) {
        if(isspace(c)) {
            in_word = false;
        }
        else if(!in_word) {
            //we're starting a new word
            word_start = os_cursor_pos;
            in_word = true;
        }
        else if(word_wrap &&
                (os_cursor_pos % WIDTH) == os_border_size &&
                (word_start % WIDTH) != os_border_size) {
            //We're already in a word and we're continuing it, and we're about to type the first
            //letter on a new line, we need to move the last part down

            int width = (WIDTH - os_border_size) - (word_start % WIDTH);
            memcpy(letter_data + os_cursor_pos, letter_data + word_start, width);
            //then set the original word to nothings
            memset(letter_data + word_start, ' ', width);
            word_start = os_cursor_pos;
            *(palette_data + os_cursor_pos) = os_normal;
            os_cursor_pos += width;
        }

        //We're not word wrapping for some reason.
        size_t line_pos;
        *(palette_data+os_cursor_pos) = os_normal;
        letter_data[os_cursor_pos++] = c;
        line_pos = os_cursor_pos%WIDTH;
        if(line_pos >= WIDTH-os_border_size) {
            newline(0);
        }

    }
    else {
        if(c == '\n') {
            newline(1);
            in_word = false;
        }
        else if(c == 8 && os_cursor_pos > os_cursor_min) {
            //backspace
            size_t old_pos = os_cursor_pos;
            os_cursor_pos = prev_pos(os_cursor_pos);

            if(old_pos != os_cursor_pos) {
                palette_data[old_pos] = os_normal;
                letter_data[os_cursor_pos] = ' ';
                recreate_word_start();
            }
        }
    }
}

int tty_write(const char *s, size_t cnt)
{
    for(size_t i = 0; i < cnt; i++) {
        process_char(s[i]);
    }

    return (int)cnt;
}

int tty_read(char *s, size_t cnt)
{
    size_t num_read = 0;
    static bool init = false;
    static uint8_t last_pos = 0;

    if(!init) {
        last_pos = *ringbuffer_pos;
        init = true;
    }

    while(num_read < cnt) {
        uint8_t new_pos;
        while(last_pos == (new_pos = *ringbuffer_pos)) {
            uint64_t int_info = wait_for_interrupt();
            if(INT_ID(int_info) == CLOCK_ID) {
                toggle_pos(os_cursor_pos);
            }
        }
        while(last_pos != new_pos) {
            uint8_t c;
            c = keyboard_ringbuffer[last_pos];
            last_pos = ((last_pos + 1) % RINGBUFFER_SIZE);
            s[num_read++] = c;
            if(num_read >= cnt) {
                break;
            }
        }
    }

    return num_read;
}

void set_word_wrap(bool val) {
    word_wrap = val;
}

void set_cursor_min() {
    os_cursor_min = os_cursor_pos;
}

void terminal_init() {
    uint32_t normal   = PALETTE(BLACK,GREEN);
    uint32_t inverted = PALETTE(GREEN,BLACK);
    word_wrap = true;
    os_cursor_min = OS_CURSOR_MIN_DEFAULT;

    set_screen_data(normal, inverted, 1);
    clear_screen_default();
}
