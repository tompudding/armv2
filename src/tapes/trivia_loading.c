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

#define TITLE "Buffy the Vampire Slayer Trivia"

int main(void) {
    int border_size = 2;
    int bar_x = 4;
    int bar_y = HEIGHT-14;
    int bar_end = (WIDTH - bar_x);
    int bar_width = bar_end - bar_x;
    int title_x = (WIDTH - (sizeof(TITLE)-1)) / 2;
    int title_y = 12;
    uint8_t *bar_pos = letter_data + (bar_y * WIDTH) + bar_x;

    set_screen_data(normal, inverted, border_size);
    clear_screen_default();

    bar_pos[-1] = '\x87';
    bar_pos[bar_width] = '\x85';
    memcpy( letter_data + (title_y * WIDTH) + title_x, TITLE, sizeof(TITLE) - 1 );

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
    uint32_t num_read = 0;
    result = tape_next_word( &section_length );
    section_length &= (~TAPE_FLAG_FINAL);

    //Now we know the length we know how many bytes we need for each blip along the progress bar
    uint32_t bytes_per_blip = section_length / bar_width;
    uint32_t next_blip = bytes_per_blip;

    while(result == READY && section_length != num_read) {
        uint8_t byte;
        result = tape_next_byte( &byte );
        if(READY == result) {
            num_read++;
            *load_area++ = byte;
            next_blip--;

            if(next_blip == 1) {
                *bar_pos++ = '\x60';
            }
            else if(next_blip == 0) {
                //*bar_pos++ = '\x60';
                //*bar_pos = '\x60';
                next_blip = bytes_per_blip;
            }
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
