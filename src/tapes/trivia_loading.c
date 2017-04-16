#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include "synapse.h"
#include <terminal.h>


#define BACKGROUND WHITE
#define FOREGROUND BLACK
uint32_t normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted = PALETTE(FOREGROUND,BACKGROUND);

int main(void) {
    int border_size = 2;
    set_screen_data(normal, inverted, border_size);
    clear_screen_default();
    uint32_t entry_point = 0;
    enum tape_codes result = tape_next_word( &entry_point );

    if( READY != result ) {
        goto error;
    }

    for(int i = 0; i < TAPE_NAME_LEN; i++) {
        char dummy;
        result = tape_next_byte( &dummy );
        if( READY != result ) {
            goto error;
        }
    }

    uint32_t load_addr = 0;
    result = tape_next_word( &load_addr );
    if( READY != result ) {
        goto error;
    }
    uint8_t *load_area = (void*)(load_addr);

    uint32_t section_length = 0;
    result = tape_next_word( &section_length );
    section_length &= (~TAPE_FLAG_FINAL);
    while(result == READY && section_length != 0) {
        uint8_t byte;
        result = tape_next_byte( &byte );
        if(READY == result) {
            section_length--;
            *load_area++ = byte;
        }
    }
    if( READY != result ) {
        goto error;
    }

    result = load_tape_symbols( (void*)load_addr, symbols_load_area );
    if( READY != result ) {
        goto error;
    }
    tape_control->write = READY;
    switch(result) {
    case READY:
    case END_OF_TAPE:
    {
        //The tape is loaded so let's clear the screen and jump to the tape
        void (*fn)(void) = (void*)entry_point;
        clear_screen(BLACK,BLACK);
        fn();
        break;
    }
    default:
        break;
    }

error:
    printf("Error loading trivia\n");
inf_loop:
    while(1) {
        wait_for_interrupt();
    }
}
