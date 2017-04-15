#include <stdio.h>
#undef putc
#undef getc
#include <stdint.h>

struct tape_control {
    volatile uint8_t read;
    volatile uint8_t write;
    volatile uint8_t data;
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
    LEFT  = 250,
    RIGHT = 251,
    UP    = 252,
    DOWN  = 253
};

#define RINGBUFFER_SIZE  128
#define MAX_SYMBOLS_SIZE 0x10000
#define INT_ID(info)     ((info)&0xffffffff)
#define CLOCK_ID         0x92d177b0
#define TAPE_NAME_LEN    16

extern volatile struct tape_control  *tape_control;
extern uint8_t                       *tape_load_area;
extern uint8_t                       *symbols_load_area;
extern volatile uint32_t             *rng;
extern volatile uint32_t             *clock_word;
extern void                         **crash_handler_word;

uint64_t wait_for_interrupt();
void set_alarm(int milliseconds);

void crash_handler(uint32_t type, uint32_t pc, uint32_t sp, uint32_t lr);
uint32_t ntohl( uint32_t );
extern int libc_init(void);
enum tape_codes load_tape(uint8_t *symbols_area, void **entry_point_out);

#include <xprintf.h>
#define printf xprintf
