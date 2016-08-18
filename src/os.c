#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include "synapse.h"

char *banner_lines[] = {
    "\r",
    "** TETRALIMBIC SYSTEMS Synapse V2 **",
    "\r",
    "    2048K RAM SYSTEM 2021K FREE     ",
    "\r",
    "READY. Type load to access the tape\r",
    "\r"
};


size_t border_size = 2;
size_t processing = 0;
char command[WIDTH+1] = {0};
size_t command_size = 0;

#define BACKGROUND BLUE
#define FOREGROUND LIGHT_BLUE
uint32_t normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted = PALETTE(FOREGROUND,BACKGROUND);

void set_command() {
    size_t row_start = (os_cursor_pos/WIDTH)*WIDTH + border_size + 1;
    command_size = (os_cursor_pos - row_start);
    memcpy(command,letter_data + row_start, command_size);
    //should be null terminated due to size
}

int tape_next_byte(uint8_t *out) {
    int tape_status = tape_control->read;

    tape_control->write = NEXT_BYTE;

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

int load_tape_data( uint8_t *tape_area ) {
    uint32_t section_length = 0;
    int result = tape_next_word( &section_length );

    while(result == READY && section_length != 0) {
        uint8_t byte;
        result = tape_next_byte( &byte );
        if(READY == result) {
            section_length--;
            *tape_area++ = byte;
            if((((uint32_t)tape_area)&7) == 0) {
                processing = 0;
                process_char('.');
                processing = 1;
            }
        }
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
    return load_tape_data( symbol_entry_pos );
}

enum tape_codes load_tape(uint8_t *tape_area, uint8_t *symbols_area, void **entry_point_out) {
    //Tapes are comprised of 2 sections, the data and (optionally) the symbols. Just load the first for now
    uint32_t entry_point = 0;
    enum tape_codes result = tape_next_word( &entry_point );

    if( READY != result ) {
        return result;
    }

    result = load_tape_data( tape_area );
    if( READY != result ) {
        return result;
    }

    result = load_tape_symbols( tape_area, symbols_area );
    if( READY != result ) {
        return result;
    }

    //Now we're done, but let the tape drive know that we won't be needing it for a while
    tape_control->write = READY;

    *entry_point_out = (void *)entry_point;
    return READY;
}

void handle_command() {
    if(command_size) {
        if(0 == strcasecmp(command,"load")) {
            void *entry_point = NULL;
            process_string("Loading...\r");
            int result = load_tape(tape_load_area, symbols_load_area, &entry_point);
            switch(result) {
            case READY:
            case END_OF_TAPE:
            {
                //The tape is loaded so let's clear the screen and jump to the tape
                void (*fn)(void) = entry_point;
                clear_screen(BLACK,BLACK);
                fn();
                break;
            }
            case DRIVE_EMPTY:
                process_string("Tape drive empty\r>");
                break;
            default:
                process_string("Tape drive error\r>");
                break;
            }

        }
        else {
            process_string("Unknown command\r>");
        }
        command_size = 0;
        memset(command,0,sizeof(command));
    }
}

void process_text() {
    uint8_t last_pos = *ringbuffer_pos;
    process_char('>');
    while(1) {
        uint8_t new_pos;
        while(last_pos == (new_pos = *ringbuffer_pos)) {
            uint64_t int_info = wait_for_interrupt();
            if(INT_ID(int_info) == CLOCK_ID) {
                toggle_pos(os_cursor_pos, normal, inverted);
            }
        }
        while(last_pos != new_pos) {
            uint8_t c;
            c = keyboard_ringbuffer[last_pos];
            process_char(c);
            last_pos = ((last_pos + 1) % RINGBUFFER_SIZE);
        }
        handle_command();
    }
}

void banner() {
    size_t i;
    for(i=0; i< sizeof(banner_lines)/sizeof(banner_lines[0]); i++) {
        process_string(banner_lines[i]);
    }
}

int main(void) {
    set_screen_data(BLUE, LIGHT_BLUE, border_size);
    clear_screen_default();
    banner();
    processing = 1;
    process_text();
}
