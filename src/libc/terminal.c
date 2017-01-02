#include "terminal.h"

uint8_t *palette_data = (void*)0x01001000;
uint8_t *letter_data  = (void*)0x01001000 + WIDTH*HEIGHT;

#define BACKGROUND BLACK
#define FOREGROUND GREEN
uint32_t os_normal      = PALETTE(BACKGROUND,FOREGROUND);
uint32_t os_inverted    = PALETTE(FOREGROUND,BACKGROUND);
size_t   os_border_size = 2;
size_t   os_cursor_pos  = 0;

void set_screen_data(uint32_t normal, uint32_t inverted, size_t border_size) 
{
    os_normal   = normal;
    os_inverted = inverted;
    os_border_size = border_size;
    os_cursor_pos = INITIAL_CURSOR_POS;
}

void toggle_pos(size_t pos, uint32_t normal, uint32_t inverted)
{
     if(*(palette_data+pos) == normal) {
         *(palette_data+pos) = inverted;
     }
     else {
         *(palette_data+pos) = normal;
     }
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
    }
}

void process_string(char *s) 
{
    while(*s) {
        process_char(*s++);
    }
}

void process_char(uint8_t c) 
{
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
        if(c == '\n') {
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

int tty_write(const char *s, size_t cnt) 
{
    for(size_t i = 0; i < cnt; i++) {
        process_char(s[i]);
    }

    return (int)cnt;
}
