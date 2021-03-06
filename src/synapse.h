#include <stdio.h>
#undef putc
#undef getc
#include <stdint.h>

struct tape_control {
    volatile uint8_t read;
    volatile uint8_t write;
    volatile uint8_t data;
};

struct region {
    void *start;
    void *end;
};

enum tape_codes {
    NEXT_BYTE   = 0,
    NOT_READY   = 1,
    END_OF_TAPE = 2,
    DRIVE_EMPTY = 3,
    READY       = 4,
    ERROR       = 5,
};

enum letter_codes {
    KEY_LEFT  = 250,
    KEY_RIGHT = 251,
    KEY_UP    = 252,
    KEY_DOWN  = 253
};

#define RINGBUFFER_SIZE  128
#define MAX_SYMBOLS_SIZE 0x10000
#define INT_ID(info)     ((info)&0xffffffff)
#define CLOCK_ID         0x92d177b0
#define TAPE_NAME_LEN    16
#define TAPE_FLAG_FINAL  0x80000000
#define MAX_TAPE_REGIONS 16
#define SCREEN_WIDTH 320
#define SCREEN_HEIGHT 240
#define ARRAY_SIZE(x) (sizeof((x))/sizeof((x)[0]))

extern volatile struct tape_control  *tape_control;
extern uint8_t                       *tape_load_area;
struct region                        *tape_regions;
extern uint32_t                       num_tape_regions;
extern uint8_t                       *symbols_load_area;
extern volatile uint32_t             *rng;
extern volatile uint32_t             *clock_word;
extern void                         **crash_handler_word;
extern uint8_t                       *palette_data;
extern uint8_t                       *letter_data;
extern uint64_t                      *font_data;
extern uint32_t                      *framebuffer;

uint64_t wait_for_interrupt();
void set_alarm(int milliseconds);

void crash_handler(uint32_t type, uint32_t pc, uint32_t sp, uint32_t lr);
uint32_t ntohl( uint32_t );
extern int libc_init(void);
int tape_next_byte(uint8_t *out);
int tape_next_word(uint32_t *out);
enum tape_codes load_tape(uint8_t *symbols_area, void **entry_point_out);
enum tape_codes load_tape_symbols( uint8_t *tape_area, uint8_t *symbols_area );
void write_to_screen(char *text, int x, int y, uint8_t colour);

#include <xprintf.h>
#define printf xprintf
#define __assert_func __dessert_func
