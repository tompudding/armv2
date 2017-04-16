#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include "synapse.h"
#include <terminal.h>
#include "loading.h"

#define BACKGROUND WHITE
#define FOREGROUND BLACK
uint32_t normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted = PALETTE(FOREGROUND,BACKGROUND);

#define TITLE "Buffy the Vampire Slayer Trivia"

int main(void) {
    int border_size = 2;
    set_screen_data(normal, inverted, border_size);
    clear_screen_default();

    load_with_progress_bar(TITLE, sizeof(TITLE)-1);

    //Returning at all is an error

    printf("Error loading trivia\n");
inf_loop:
    while(1) {
        wait_for_interrupt();
    }
}
