#include "synapse.h"

#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include <stdio.h>
#include <terminal.h>
#include <stdbool.h>

char *banner_lines[] = {
    "\n",
    "** TETRALIMBIC SYSTEMS Synapse V2 **",
    "\n",
    "    2048K RAM SYSTEM 2021K FREE     ",
    "\n",
    "READY. Type load to access the tape\n",
    "\n"
};


size_t border_size = 2;
size_t processing = 0;

#define BACKGROUND BLUE
#define FOREGROUND LIGHT_BLUE
#define PROMPT ">"
uint32_t normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted = PALETTE(FOREGROUND,BACKGROUND);

int tape_next_byte(uint8_t *out) {
    tape_control->write = NEXT_BYTE;

    int tape_status = tape_control->read;

    while(tape_status == NOT_READY) {
        wait_for_interrupt();
        tape_status = tape_control->read;
    }

    if(tape_status == READY) {
        *out = tape_control->data;
    }

    return tape_status;
}

int tape_next_word(uint32_t *out) {
    uint32_t working = 0;
    int result = NOT_READY;

    for(size_t i = 0; i < sizeof(working); i++) {
        uint8_t working_byte = 0;
        result = tape_next_byte( &working_byte );
        if(READY != result) {
            break;
        }
        working <<= 8;
        working |= working_byte;
    }

    if( READY == result ) {
        *out = working;
    }

    return result;
}

int load_tape_data( uint8_t *tape_area, bool *final, size_t *written_out ) {
    uint32_t section_length = 0;
    int result = tape_next_word( &section_length );
    size_t written = 0;
    if( final ) {
        *final = section_length & TAPE_FLAG_FINAL;
    }

    section_length &= (~TAPE_FLAG_FINAL);

    while(result == READY && section_length != 0) {
        uint8_t byte;
        result = tape_next_byte( &byte );
        if(READY == result) {
            section_length--;
            *tape_area++ = byte;
            written++;
        }
    }
    if( written_out ) {
        *written_out = written;
    }
    return result;
}

//We can't do a 32 bit read from an unaligned address, so just read it bytewise
uint32_t load_network_uint32( uint8_t *in ) {
    return (in[0] << 24) | (in[1] << 16) | (in[2] << 8) | (in[3]);
}

enum tape_codes load_tape_symbols( uint8_t *tape_area, uint8_t *symbols_area ) {
    //First find our entry position in the symbols area
    uint32_t  symbol_value     = 0;
    uint8_t  *symbol_entry_pos = symbols_area;
    uint8_t *symbols_end       = symbols_area + MAX_SYMBOLS_SIZE;

    while( (uint8_t*)symbol_value < tape_area && symbol_entry_pos < symbols_end ) {
        uint8_t *current_symbol = symbol_entry_pos;
        symbol_value = load_network_uint32( current_symbol );
        if( 0 == symbol_value || (uint8_t*)symbol_value >= tape_area ) {
            //This is the end
            break;
        }
        current_symbol += sizeof(uint32_t);

        while(*current_symbol && current_symbol < symbols_end) {
            current_symbol++;
        }
        symbol_entry_pos = current_symbol + 1;
    }

    if( symbol_entry_pos >= symbols_end ) {
        //We ran off the end
        return ERROR;
    }

    //Now we've just read the

    //Now we can load symbols from the tape in
    return load_tape_data( symbol_entry_pos, NULL, NULL );
}

void add_loaded_tape( void *addr, size_t len )
{
    //printf("\n    Data going at %08x\n", (uint32_t)(tape_regions + num_tape_regions));
    if( num_tape_regions >= MAX_TAPE_REGIONS ) {
        //we ignore everything after the max
        return;
    }

    tape_regions[num_tape_regions].start = addr;
    tape_regions[num_tape_regions].end = addr + len;
    num_tape_regions++;
}

enum tape_codes load_tape(uint8_t *symbols_area, void **entry_point_out)
{
    //Tapes are comprised of 2 sections, the data and (optionally) the symbols. Just load the first for now
    uint32_t entry_point = 0;
    char tape_name[TAPE_NAME_LEN];

    printf("\n\n\n   Press PLAY on tape ");

    enum tape_codes result = tape_next_word( &entry_point );

    if( READY != result ) {
        return result;
    }

    for(int i = 0; i < sizeof(tape_name); i++) {
        result = tape_next_byte( tape_name + i );
        if( READY != result ) {
            return result;
        }
    }

    uint32_t load_addr = 0;

    result = tape_next_word( &load_addr );

    if( READY != result ) {
        return result;
    }

    printf("\n    Loading at %08x\n", load_addr);
    bool final = false;
    size_t written = 0;

    result = load_tape_data( (void*)load_addr, &final, &written );
    if( READY != result ) {
        return result;
    }

    (void) add_loaded_tape(load_addr, written);

    result = load_tape_symbols( load_addr, symbols_area );
    if( READY != result ) {
        return result;
    }

    // Now we're done, but let the tape drive know that we won't be needing it for a while, but only if this is
    // the final data block
    if( final ) {
        tape_control->write = READY;
    }

    *entry_point_out = (void *)entry_point;
    return READY;
}

void handle_command(char *command) {
    if(0 == strcasecmp(command,"load")) {
        void *entry_point = NULL;
        set_screen_data(normal, inverted, border_size);
        clear_screen_default();
        puts("Loading...");
        int result = load_tape(symbols_load_area, &entry_point);
        switch(result) {
        case READY:
            //case END_OF_TAPE:
        {
            //The tape is loaded so let's clear the screen and jump to the tape
            void (*fn)(void) = entry_point;
            clear_screen(BLACK,BLACK);
            fn();
            break;
        }
        case DRIVE_EMPTY:
            printf("Tape drive empty\n");
            break;
        default:
            printf("Tape drive error %d\n", result);
            break;
        }

    }
    else {
        printf("Unknown command : [%s]\n", command);
    }
}

void banner() {
    size_t i;
    for(i=0; i< sizeof(banner_lines)/sizeof(banner_lines[0]); i++) {
        printf("%s", banner_lines[i]);
    }
}

extern int libc_init(void);

int main(void) {
    char command[WIDTH+1] = {0};

    libc_init();
    set_screen_data(normal, inverted, border_size);
    clear_screen_default();
    banner();
    processing = 1;

    //Quick hack for demonstrating the loaded font
    /* for(int i = 4; i < 4+16; i++) { */
    /*     for(int j = 4; j < 4+16; j++) { */
    /*         letter_data[j*WIDTH+i] = ((j-4)<<4) | (i-4); */
    /*     } */
    /* } */
    /* while(1) { */
    /*     wait_for_interrupt(); */
    /* } */

    //Quick hack to test that the framebuffer works
    /* for(int i = 0; i < WIDTH*HEIGHT*8*8/32; i++) { */
    /*    framebuffer[i] = 0xa5a5a5a5; */
    /* } */

    while(1) {
        printf(PROMPT);
        handle_command(gets(command));
    }
}
