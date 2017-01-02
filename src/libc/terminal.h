#include <stdint.h>
#include <stddef.h>
#include <ctype.h>

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

#define WIDTH                          40
#define HEIGHT                         30
#define PALETTE(background,foreground) ((background<<4)|foreground)
#define INITIAL_CURSOR_POS             ((WIDTH+1)*os_border_size)
#define FINAL_CURSOR_POS               (WIDTH*HEIGHT - os_border_size*(WIDTH+1))

extern uint8_t *palette_data;
extern uint8_t *letter_data;
extern size_t   os_cursor_pos;

void set_screen_data(uint32_t normal, uint32_t inverted, size_t border_size);
void toggle_pos(size_t pos, uint32_t normal, uint32_t inverted);

void process_char(uint8_t c);
void process_string(char *s);
void newline(int reset_square);

void clear_screen(enum colours background, enum colours foreground);
void clear_screen_with_border(uint32_t normal, uint32_t inverted, size_t border_size);
void clear_screen_default();
