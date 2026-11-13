#ifndef __HW_MANAGER_H__
#define __HW_MANAGER_H__

#include "common.h"
#define HW_MANAGER_NUMREGS 4
#define MAP_MEMORY_ERROR_OK 0
#define MAP_MEMORY_ERROR_NO_SUCH_DEVICE 1

/* How many interrupts can be waiting for the cpu to take them. The boot rom's ring buffer holds 32, so a
   longer queue than that would only overwrite it */
#define INTERRUPT_QUEUE_SIZE 32

struct queued_interrupt {
    uint32_t id;
    uint32_t code;
};

typedef struct {
    uint32_t regs[HW_MANAGER_NUMREGS];
    /* The interrupt that the cpu took most recently, which is what INTERRUPT_DATA reads */
    uint32_t last_interrupt_id;
    uint32_t last_interrupt_code;
    /* The interrupts that haven't been taken yet, oldest first, as a ring. The I pin is on whenever there
       are any */
    struct queued_interrupt queue[INTERRUPT_QUEUE_SIZE];
    uint32_t queue_start;
    uint32_t queue_length;
} hw_manager_t;

typedef enum {
    NUM_DEVICES   = 0,
    MAP_MEMORY    = 1,
    GET_DEVICE_ID = 2,
    INTERRUPT_DATA = 3,
    WAIT_FOR_INTERRUPT = 4,
    GETTIME = 5,
    DEVICE_OPERATION = 6,
} hw_manager_opcode_t;

typedef enum {
    MOV_REGISTER = 0,
} hw_register_opcode_t;

#endif
