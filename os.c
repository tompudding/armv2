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

#define INITIAL_CURSOR_POS ((WIDTH+1)*border_size)
#define FINAL_CURSOR_POS   (WIDTH*HEIGHT - border_size*(WIDTH+1))
size_t border_size = 2;
size_t cursor_pos = 0;
size_t processing = 0;
char command[WIDTH+1] = {0};
size_t command_size = 0;

#define BACKGROUND BLUE
#define FOREGROUND LIGHT_BLUE
uint32_t normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted = PALETTE(FOREGROUND,BACKGROUND);

void set_command() {
    size_t row_start = (cursor_pos/WIDTH)*WIDTH + border_size + 1;
    command_size = (cursor_pos - row_start);
    memcpy(command,letter_data + row_start, command_size);
    //should be null terminated due to size
}

void newline(int reset_square) {
    if(processing) {
        //handle the command
        set_command();
    }
    if(reset_square) {
        *(palette_data+cursor_pos) = normal;
    }
    cursor_pos = ((cursor_pos/WIDTH)+1)*WIDTH + border_size;
    if(cursor_pos >= FINAL_CURSOR_POS) {
        //move all rows up one
        memmove(letter_data+border_size*WIDTH, letter_data + (border_size+1)*WIDTH, (WIDTH*(HEIGHT-border_size*2-1)));
        memset(letter_data + (WIDTH*(HEIGHT-border_size-1)), 0, WIDTH);
        cursor_pos = ((cursor_pos/WIDTH)*WIDTH) + border_size - WIDTH;
        //cursor_pos = INITIAL_CURSOR_POS;
    }
    if(processing && command_size == 0) {
        process_char('>');
    }
}

void process_char(uint8_t c) {
    if(isprint(c)) {
        size_t line_pos;
        *(palette_data+cursor_pos) = normal;
        letter_data[cursor_pos++] = c;
        line_pos = cursor_pos%WIDTH;
        if(line_pos >= WIDTH-border_size) {
            newline(0);
        }
    }
    else {
        if(c == '\r') {
            newline(1);
        }
        else if(c == 8) {
            //backspace
            *(palette_data+cursor_pos) = normal;
            if((cursor_pos%WIDTH) > border_size+1) { //1 for the prompt
                cursor_pos--;
                letter_data[cursor_pos] = ' ';
            }
        }
    }
}

void process_string(char *s) {
    while(*s) {
        process_char(*s++);
    }
}

int load_tape(uint8_t *tape_area) {
    //We need to read all the bytes from the tape until we get an end of tape, without getting any errors
    int result = READY;
    while(result == READY) {
        tape_control->write = NEXT_BYTE;
        while(tape_control->read == NOT_READY) {
            //wait_for_interrupt();
        }
        if(tape_control->read == READY) {
            *tape_area++ = tape_control->data;
            if((((uint32_t)tape_area)&7) == 0) {
                processing = 0;
                process_char('.');
                processing = 1;
            }

        }
        result = tape_control->read;
    }
    return tape_control->read == END_OF_TAPE ? 0 : tape_control->read + 1;
}

void handle_command() {
    if(command_size) {
        if(0 == strcasecmp(command,"load")) {
            process_string("Loading...\r");
            int result = load_tape(tape_load_area);
            switch(result) {
            case 0:
            {
                //The tape is loaded so let's clear the screen and jump to the tape
                void (*fn)(void) = (void*)tape_load_area;
                clear_screen(BLACK,BLACK);
                fn();
                break;
            }
            case DRIVE_EMPTY+1:
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
                toggle_pos(cursor_pos, normal, inverted);
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

int _start(void) {
    crash_handler_word[0] = crash_handler;
    cursor_pos = INITIAL_CURSOR_POS;
    clear_screen_with_border(BLUE, LIGHT_BLUE, border_size);
    *((int*)0) = 4;
    banner();
    processing = 1;
    process_text();
    return 0;
}
