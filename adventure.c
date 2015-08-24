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
    " Welcome to Adventure!! Would you like instructions?\r",
    "\r",
};


char input[512] = {0};
size_t input_size = 0;

void wait_for_interrupt() {
    asm("push {r7}");
    asm("mov r7,#17");
    asm("swi #0");
    asm("pop {r7}");
}

char *get_secret_syscall() {
    asm("push {r7}");
    asm("mov r7,#18");
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
    if(isprint(c) || 0 == c) {
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

void process_text(char *in_buffer) {
    uint8_t last_pos = *ringbuffer_pos;
    char buffer[64] = {0};

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
                process_char('\r',0);
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

void print_secret() {
    char *secret = get_secret_syscall();

    process_string("The final secret is ");
    process_string(secret);
    process_string("\r Congratulations, you win!\r");
    while(1) {
        wait_for_interrupt();
    }
}

void print_number(int n) {
    char buffer[10];
    int size=0,i;
    while(n > 0) {
        buffer[size++] = n%10;
        n/=10;
    }
    for(i=size-1;i>=0;i--) {
        process_char('0' + buffer[i],0);
    }
}

void start() {
    char buffer[32] = {0};
    while(1) {
        process_string(" Welcome to Adventure!! Would you like instructions?\r");
        process_text(buffer);
        if(0 == strcasecmp(buffer,"yes")) {
            process_string("Somewhere nearby is Colossal Cave, where others have found fortunes in treasure and gold, though it is rumored that some who enter are never seen again. Magic is said to work in the cave. I will be your eyes and hands. Direct me with commands of 1 or 2 words.\r>");
            break;
        }
        else if(0 == strcasecmp(buffer,"no")) {
            process_string("\r>");
            break;
        }
        else {
            process_string("I did not understand :");
            process_string(buffer);
            process_string("\r\r>");
            memset(buffer,0,sizeof(buffer));
        }
    }
}

char *adventure(char *out) {
    char buffer[32] = {0};

    process_text(buffer);
    //get the first word
    char *p = buffer;
    while(*p && p < (buffer + sizeof(buffer))) {
        *out = *p;
        if(*p == ' ') {
            *out = 0;
        }
        if(!*p) {
            break;
        }
        p++;
        out++;
    }
    if(input_size == 0x414243 && input[3] == 0x94) {
        print_secret();
    }
}

int _start(void) {
    crash_handler_word[0] = crash_handler;
    int max = 1000;
    cursor_pos = INITIAL_CURSOR_POS;
    clear_screen_with_border(DARK_GREY, WHITE, border_size);
    char word[64] = {0};
    start();
    while(1) {
        adventure(word);
        process_string("I don't know how to ");
        process_string(word);
        process_string(".\r\r>");
        memset(word,0,sizeof(word));
    }

    //infinite loop
    while(1) {
        wait_for_interrupt();
    }
}
