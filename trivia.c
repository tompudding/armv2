#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include "synapse.h"

//Loads of copy pasta here due to a severe lack of time, got to write 5 games in the next 5 hours :(

#define INITIAL_CURSOR_POS ((WIDTH+1)*border_size)
#define FINAL_CURSOR_POS   (WIDTH*HEIGHT - border_size*(WIDTH+1))
size_t border_size = 0;
size_t cursor_pos = 0;
size_t processing = 0;

char *banner_lines[] = {
    "      Buffy Trivia\r",
    "\r",
    "  Do you have what it takes?\r",
    "\r",
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

char input[WIDTH+1] = {0};
size_t input_size = 0;

void wait_for_interrupt() {
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
    uint8_t obfs[] = {191, 165, 190, 229, 165, 161, 241, 190, 166, 176, 241, 170, 184, 162, 179, 231, 225, 162, 227, 224, 220, 186, 177, 241, 186, 190, 234, 185, 164, 243, 169, 164, 165, 162, 166, 227, 182, 187, 171, 165, 165, 181, 219, 219, 233, 140, 171, 160, 165, 165, 190, 179, 169, 237, 190, 241, 231, 185, 171, 187, 198, 214};
    char *password = "You're not friends. You'll never be friends. Love isn't brains, children, it's blood. Blood screaming inside you to work its will. I may be love's bitch, but at least I'm man enough to admit it.";
    int i;

    for(i=0; i < sizeof(obfs)/sizeof(obfs[0]); i++) {
        obfs[i] ^= (password[i]^0xa5);
    }

    process_string(obfs);
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

int _start(void) {
    int max = 1000;
    cursor_pos = INITIAL_CURSOR_POS;
    clear_screen_with_border(WHITE, BLACK, border_size);
    banner();
    uint32_t number = (getrand()%max)+1;
    int remaining = 1;
    char question[] = "What is the title of episode 00 of season 0 of Buffy the Vampire Slayer?\r\r>";
    while(1) {
        char buffer[64] = {0};
        char *episode_name = NULL;
        int season = getrand()%7;;
        int episode_number;
        if(season == 0) {
            episode_number = getrand()%13;
        }
        else {
            episode_number = getrand()%22;
        }
        episode_name = episodes[season][episode_number];
        episode_number++;
        season++;
        //format the question
        question[29] = (episode_number >= 10) ? ('0' + (episode_number/10)) : ' ';
        question[30] = '0' + (episode_number%10);
        question[42] = '0' + season;

        //ask the question
        process_string(question);

        process_text(buffer);
        if(0 == strcasecmp(buffer,episode_name)) {
            if(--remaining == 0) {
                print_secret();
                break;
            }
            else {
                process_string("Correct! get ");
                print_number(remaining);
                process_string(" more correct to learn the password\r\r");
            }
        }
        else {
            process_string("Wrong! The answer is \"");
            process_string(episode_name);
            process_string("\"\r\r");
        }
    }
    //infinite loop
    while(1) {
        wait_for_interrupt();
    }
}
