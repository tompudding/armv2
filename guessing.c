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

char input[WIDTH+1] = {0};
size_t input_size = 0;

int _start(void) {
    cursor_pos = INITIAL_CURSOR_POS;
    clear_screen_with_border(BLACK, RED, border_size);
    while(1) {
    }
}
