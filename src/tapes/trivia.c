#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include "synapse.h"
#include <terminal.h>

size_t border_size = 1;

#define BACKGROUND WHITE
#define FOREGROUND BLACK
uint32_t normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted = PALETTE(FOREGROUND,BACKGROUND);

char *banner_lines[] = {
    "      Buffy Trivia\n",
    "      ------------\n",
    "\n",
    "  Do you have what it takes?\n",
    "\n",
};

char *episodes[7][22] = { {"Welcome to the Hellmouth",
                           "The Harvest",
                           "Witch",
                           "Teacher's Pet",
                           "Never Kill a Boy on the First Date",
                           "The Pack",
                           "Angel",
                           "I, Robot... You, Jane",
                           "The Puppet Show",
                           "Nightmares",
                           "Out of Mind, Out of Sight",
                           "Prophecy Girl",
                           NULL,
                           NULL,
                           NULL,
                           NULL,
                           NULL,
                           NULL,
                           NULL,
                           NULL,
                           NULL,
                           NULL},
                          {"When She Was Bad",
                           "Some Assembly Required",
                           "School Hard",
                           "Inca Mummy Girl",
                           "Reptile Boy",
                           "Halloween",
                           "Lie to Me",
                           "The Dark Age",
                           "What's My Line (Part 1)",
                           "What's My Line (Part 2)",
                           "Ted",
                           "Bad Eggs",
                           "Surprise",
                           "Innocence",
                           "Phases",
                           "Bewitched, Bothered and Bewildered",
                           "Passion",
                           "Killed by Death",
                           "I Only Have Eyes for You",
                           "Go Fish",
                           "Becoming (Part 1)",
                           "Becoming (Part 2)"},
                          {"Anne",
                           "Dead Man's Party",
                           "Faith, Hope & Trick",
                           "Beauty and the Beasts",
                           "Homecoming",
                           "Band Candy",
                           "Revelations",
                           "Lovers Walk",
                           "The Wish",
                           "Amends",
                           "Gingerbread",
                           "Helpless",
                           "The Zeppo",
                           "Bad Girls",
                           "Consequences",
                           "Doppelgangland",
                           "Enemies",
                           "Earshot",
                           "Choices",
                           "The Prom",
                           "Graduation Day (Part 1)",
                           "Graduation Day (Part 2)"},
                          {"The Freshman",
                           "Living Conditions",
                           "The Harsh Light of Day",
                           "Fear, Itself",
                           "Beer Bad",
                           "Wild at Heart",
                           "The Initiative",
                           "Pangs",
                           "Something Blue",
                           "Hush",
                           "Doomed",
                           "A New Man",
                           "The I in Team",
                           "Goodbye Iowa",
                           "This Year's Girl",
                           "Who Are You",
                           "Superstar",
                           "Where the Wild Things Are",
                           "New Moon Rising",
                           "The Yoko Factor",
                           "Primeval",
                           "Restless"},
                          {"Buffy vs. Dracula",
                           "Real Me",
                           "The Replacement",
                           "Out of My Mind",
                           "No Place Like Home",
                           "Family",
                           "Fool for Love",
                           "Shadow",
                           "Listening to Fear",
                           "Into the Woods",
                           "Triangle",
                           "Checkpoint",
                           "Blood Ties",
                           "Crush",
                           "I Was Made to Love You",
                           "The Body",
                           "Forever",
                           "Intervention",
                           "Tough Love",
                           "Spiral",
                           "The Weight of the World",
                           "The Gift"},
                          {"Bargaining (Part 1)",
                           "Bargaining (Part 2)",
                           "After Life",
                           "Flooded",
                           "Life Serial",
                           "All the Way",
                           "Once More, with Feeling",
                           "Tabula Rasa",
                           "Smashed",
                           "Wrecked",
                           "Gone",
                           "Doublemeat Palace",
                           "Dead Things",
                           "Older and Far Away",
                           "As You Were",
                           "Hell's Bells",
                           "Normal Again",
                           "Entropy",
                           "Seeing Red",
                           "Villains",
                           "Two to Go",
                           "Grave"},
                          {"Lessons",
                           "Beneath You",
                           "Same Time, Same Place",
                           "Help",
                           "Selfless",
                           "Him",
                           "Conversations with Dead People",
                           "Sleeper",
                           "Never Leave Me",
                           "Bring on the Night",
                           "Showtime",
                           "Potential",
                           "The Killer in Me",
                           "First Date",
                           "Get It Done",
                           "Storyteller",
                           "Lies My Parents Told Me",
                           "Dirty Girls",
                           "Empty Places",
                           "Touched",
                           "End of Days",
                           "Chosen"} };

static void banner() {
    size_t i;
    for(i=0; i< sizeof(banner_lines)/sizeof(banner_lines[0]); i++) {
        printf(banner_lines[i]);
    }
}

static void print_secret() {
    uint8_t obfs[] = {191, 165, 190, 229, 165, 161, 241, 190, 166, 176, 241, 170, 184, 162, 179, 231, 225, 162, 227, 224, 220, 186, 177, 241, 186, 190, 234, 185, 164, 243, 169, 164, 165, 162, 166, 227, 182, 187, 171, 165, 165, 181, 219, 219, 233, 140, 171, 160, 165, 165, 190, 179, 169, 237, 190, 241, 231, 185, 171, 187, 198, 214};
    char *password = "You're not friends. You'll never be friends. Love isn't brains, children, it's blood. Blood screaming inside you to work its will. I may be love's bitch, but at least I'm man enough to admit it.";
    int i;

    for(i=0; i < sizeof(obfs)/sizeof(obfs[0]); i++) {
        obfs[i] ^= (password[i]^0xa5);
    }

    process_string(obfs);
}

char question[] = "What is the title of episode 00 of season 0 of Buffy the Vampire Slayer?\r\r>";

int main(void) {
    int max = 1000;

    set_screen_data(normal, inverted, border_size);
    clear_screen_default();
    banner();

    uint32_t number = (rand() % max) + 1;
    int remaining = 1337;

    while(1) {
        char buffer[32]      = {0};
        char *episode_name   = NULL;
        int   season         = rand() % 7;
        int   episode_number = rand() % ( season == 0 ? 12 : 22 );

        episode_name = episodes[season][episode_number];

        //ask the question
        printf("What is the title of episode %d of season %d of Buffy the Vampire Slayer?\n\n",
               episode_number + 1,
               season + 1);

        gets(buffer);

        if(0 == strcasecmp(buffer,episode_name)) {
            if(remaining == 0) {
                print_secret();
                break;
            }
            else {
                printf("Correct! get %d more correct to learn the password\n\n", remaining--);
            }
        }
        else {
            printf("Wrong! The answer is \"%s\"\n\n", episode_name);
        }
    }

    //infinite loop
    while(1) {
        wait_for_interrupt();
    }
}
