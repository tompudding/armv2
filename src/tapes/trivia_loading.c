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

    void *entry_point = NULL;
    int result = load_tape(symbols_load_area, &entry_point);
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
    default:
        printf("TRIVIA LOADING ERROR!\n");
        break;
    }
    return 0;
}
