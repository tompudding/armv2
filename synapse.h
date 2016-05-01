
struct tape_control {
    uint8_t read;
    uint8_t write;
    uint8_t data;
};

enum tape_codes {
    NEXT_BYTE   = 0,
    NOT_READY   = 1,
    END_OF_TAPE = 2,
    DRIVE_EMPTY = 3,
    READY       = 4,
};

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

enum letter_codes {
    LEFT  = 250,
    RIGHT = 251,
    UP    = 252,
    DOWN  = 253
};


#define WIDTH  40
#define HEIGHT 30
#define RINGBUFFER_SIZE 128
#define PALETTE(background,foreground) ((background<<4)|foreground)
#define INT_ID(info) ((info)&0xffffffff)
#define CLOCK_ID 0x92d177b0

extern uint8_t *palette_data;
extern uint8_t *letter_data;
extern uint32_t *keyboard_bitmask;
extern uint8_t *keyboard_ringbuffer;
extern uint8_t *ringbuffer_pos;
extern struct tape_control *tape_control;
extern uint8_t *tape_load_area;
extern uint32_t *rng;
extern void **crash_handler_word;

uint64_t wait_for_interrupt();
void set_alarm(int milliseconds);
void toggle_pos(size_t pos, uint32_t normal, uint32_t inverted);

void clear_screen(enum colours background, enum colours foreground);
void clear_screen_with_border(enum colours background, enum colours foreground, size_t border_size);
void crash_handler(uint32_t type, uint32_t pc, uint32_t sp, uint32_t lr);
