#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include "synapse.h"

//Loads of copy pasta here due to a severe lack of time, got to write 5 games in the next 5 hours :(

#define INITIAL_CURSOR_POS ((WIDTH+1)*border_size)
#define FINAL_CURSOR_POS   (WIDTH*HEIGHT - border_size*(WIDTH+1))
size_t border_size = 1;
size_t cursor_pos = 0;
size_t processing = 0;

char *banner_lines[] = {
    "\r",
    "      The Infernal Guessing Game!     ",
    "\r",
    "  I'm thinking of a number...         ",
    "\r",
    "Guess it to learn the secret word...\r",
    "\r"
};

char input[WIDTH+1] = {0};
size_t input_size = 0;

void wait_for_interrupt() {
    //hack, got some kind of weird bug with not returning from SWI, for now just don't break the registers
    asm("push {r7}");
    asm("mov r7,#17");
    asm("swi #0");
    asm("pop {r7}");
}

void set_input() {
    size_t row_start = (cursor_pos/WIDTH)*WIDTH + border_size + 1;
    input_size = (cursor_pos - row_start);
    memcpy(input,letter_data + row_start, input_size);
    //should be null terminated due to size
}

void newline() {
    cursor_pos = ((cursor_pos/WIDTH)+1)*WIDTH + border_size;
    if(cursor_pos >= FINAL_CURSOR_POS) {
        //move all rows up one
        memmove(letter_data+border_size*WIDTH, letter_data + (border_size+1)*WIDTH, (WIDTH*(HEIGHT-border_size*2-1)));
        memset(letter_data + (WIDTH*(HEIGHT-border_size-1)), 0, WIDTH);
        cursor_pos = ((cursor_pos/WIDTH)*WIDTH) + border_size - WIDTH;
        //cursor_pos = INITIAL_CURSOR_POS;
    }
}

void process_char(uint8_t c, int is_input) {
    if(isprint(c)) {
        size_t line_pos;
        letter_data[cursor_pos++] = c;
        if(is_input) {
            input[input_size++] = c;
        }
        line_pos = cursor_pos%WIDTH;
        if(line_pos >= WIDTH-border_size) {
            newline();
        }
    }
    else {
        if(c == '\r') {
            newline();
        }
        else if(c == 8) {
            //backspace
            if((cursor_pos%WIDTH) > border_size+1) { //1 for the prompt
                cursor_pos--;
                letter_data[cursor_pos] = ' ';
            }
            if(is_input && input_size > 0) {
                input_size--;
                input[input_size] = 0;
            }
        }
    }
}

void process_string(char *s) {
    while(*s) {
        process_char(*s++,0);
    }
}

void process_text(char *in_buffer, int remaining) {
    uint8_t last_pos = *ringbuffer_pos;
    char buffer[64] = {0};
    if(remaining > 0) {
        //Dammit there's no standard library so I can't use sprintf :(
        strcpy(buffer,"You have    guesses remaining\r>");
        if(remaining >= 10) {
            buffer[9] = '0' + (remaining/10);
        }
        buffer[10] = '0' + (remaining%10);
        process_string(buffer);
    }
    else {
        process_string("You ran out, I picked a new number\r>");
    }

    while(1) {
        uint8_t new_pos;
        while(last_pos == (new_pos = *ringbuffer_pos)) {
            wait_for_interrupt();
        }
        while(last_pos != new_pos) {
            uint8_t c;
            c = keyboard_ringbuffer[last_pos];
            process_char(c,1);
            last_pos = ((last_pos + 1) % RINGBUFFER_SIZE);
            if(c == '\r') {
                memcpy(in_buffer, input, input_size);
                input_size = 0;
                memset(input,0,sizeof(input));
                goto done;
            }
        }
    }
done:
    return;
}

void banner() {
    size_t i;
    for(i=0; i< sizeof(banner_lines)/sizeof(banner_lines[0]); i++) {
        process_string(banner_lines[i]);
    }
}

uint32_t getrand() {
    //The display has a secret RNG
    return rng[0];
}

int _start(void) {
    int max = 1000;
    cursor_pos = INITIAL_CURSOR_POS;
    clear_screen_with_border(BLACK, RED, border_size);
    banner();
    uint32_t number = (getrand()%max)+1;
    int remaining = 10;
    while(1) {

        char buffer[64] = {0};
        process_text(buffer,remaining);
        if(remaining <= 0) {
            number = (getrand()%max)+1;
            remaining = 10;
        }
        int guess = atoi(buffer);
        if(guess <= 0 || guess > max) {
            process_string("That is not a valid guess\r");
        }
        else if(guess == number) {
            process_string("Correct! The first word to the passphrase is \"sulphuric\"\r");
            break;
        }
        else if(guess < number) {
            process_string("Your guess is too low\r");
        }
        else {
            process_string("Your guess is too high\r");
        }
        remaining -= 1;
    }
}
