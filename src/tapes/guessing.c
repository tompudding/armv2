#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include "synapse.h"
#include <terminal.h>

size_t border_size = 1;

char *banner_lines[] = {
    "\n",
    "      The Infernal Guessing Game!     ",
    "\n",
    "  I'm thinking of a number...         ",
    "\n",
    "Guess it to learn the secret word...\n",
    "\n"
};

#define BACKGROUND BLACK
#define FOREGROUND RED
#define PROMPT ">"
uint32_t normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted = PALETTE(FOREGROUND,BACKGROUND);

static void banner() {
    size_t i;
    for(i=0; i< sizeof(banner_lines)/sizeof(banner_lines[0]); i++) {
        process_string(banner_lines[i]);
    }
}

int main(void) {
    int max = 1000;

    set_screen_data(normal, inverted, border_size);
    clear_screen_default();
    banner();

    uint32_t number = (rand() % max) + 1;
    int remaining = 10;

    while(1) {
        char buffer[64] = {0};
        printf("You have %d guesses remaining\n" PROMPT, remaining);
        gets(buffer);

        int guess = atoi(buffer);
        if(guess <= 0 || guess > max) {
            printf("That is not a valid guess\n");
            continue;
        }
        else if(guess == number) {
            printf("Correct! The first word to the passphrase is \"sulphuric\"\n");
            printf("Please reset now\n");
            break;
        }
        else if(guess < number) {
            process_string("Your guess is too low\n");
        }
        else {
            process_string("Your guess is too high\n");
        }

        remaining -= 1;

        if(remaining <= 0) {
            number = (rand() % max) + 1;
            remaining = 10;
            printf("You ran out, I picked a new number\n");
        }
    }
    //infinite loop
    while(1) {
        wait_for_interrupt();
    }
}
