#include <stdint.h>
#include <string.h>

#define WIDTH  40
#define HEIGHT 30
uint8_t *palette_data = (void*)0x01001000;
uint8_t *letter_data  = (void*)0x01001000 + WIDTH*HEIGHT;

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

int _start(void) {
    clear_screen(BLUE, LIGHT_BLUE);
    strcpy(letter_data, "Monkey Monkey");
    return 0;
}
