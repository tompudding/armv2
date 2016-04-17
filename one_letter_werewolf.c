#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include <stdbool.h>
#include "synapse.h"

//Loads of copy pasta here due to a severe lack of time, got to write 5 games in the next 5 hours :(

#define INITIAL_CURSOR_POS ((WIDTH+1)*border_size)
#define FINAL_CURSOR_POS   (WIDTH*HEIGHT - border_size*(WIDTH+1))
size_t border_size = 1;
size_t cursor_pos = 0;
size_t processing = 0;

#define BACKGROUND BLUE
#define FOREGROUND LIGHT_BLUE
uint32_t normal   = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted = PALETTE(FOREGROUND,BACKGROUND);
bool is_day = true;
int current_blips = 0;

#define MAX_HEIGHT (HEIGHT-2)
#define MIN_HEIGHT 1
#define DAY_TICKS 0x40
#define BAR_CHAR '='
#define VILLAGER_CHAR 'p'
#define PLAYER_CHAR 'x'
#define MAX(a,b) ((a) < (b) ? (b) : (a))

int colours[] = {PALETTE(BLUE, LIGHT_BLUE),
                 PALETTE(BLACK, RED)};
int current_palette = -1;
bool transforming = false;


#define BANNER_OFFSET ((HEIGHT-MIN_HEIGHT)*WIDTH)
#define banner_row (letter_data + BANNER_OFFSET)

#define CHAR_TO_HEX(c) ((c) > 9 ? ('a' + (c) - 10) : ('0' + (c)))

char *map = 
    "   Health                               "
    "   ==========                           "
    "                                        "
    "                                        "
    "                                        "
    "    \x90`````\x8e                             "
    "    }     }                             "
    "    }     }                             "
    "    }     }                             "
    "    }     }                             "
    "    \x8d``-``\x9d                             "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        "
    "                                        ";



struct position {
    int x;
    int y;
};

struct character {
    struct position pos;
    uint8_t symbol;
    uint8_t old_symbol;
    int size;
    int old_size;
    int transform_done;
    int palette;
};
#define NUM_VILLAGERS 10
struct character player = {.pos = {.x = 20, .y = 15}, .symbol=PLAYER_CHAR, .palette = -1, .size=1};
struct character villagers[NUM_VILLAGERS];
int time_of_day = 0x38; //0 - 10

volatile uint32_t getrand() {
    //The display has a secret RNG
    return rng[0];
}

int set_letter(char c, int x, int y) {
    letter_data[WIDTH*(HEIGHT-1-y) + x] = c;
}

int set_palette(int c, int x, int y) {
    if(c == -1) {
        c = current_palette;
    }
    palette_data[WIDTH*(HEIGHT-1-y) + x] = c;
}

uint8_t get_item(int x, int y) {
    return letter_data[WIDTH*(HEIGHT-1-y) + x];
}

void update_werewolf_pos(struct position *new_pos, struct character *character) {
}

void update_char_pos(struct position *new_pos, struct character *character) {
    uint8_t current = get_item(new_pos->x, new_pos->y);
    if(current != ' ') {
        return;
    }
    set_letter(' ', character->pos.x, character->pos.y);
    character->pos = *new_pos;
    set_letter(character->symbol, character->pos.x, character->pos.y);
}

void update_player_pos(struct position *new_pos, struct character *character) {
    int i,j;
    int num_villagers = 0;

    for(i = 0; i < character->size; i++) {
        for(j = 0; j < character->size; j++) {
            int x = new_pos->x + i;
            int y = new_pos->y + j;

            uint8_t current = get_item(x, y);
            if(current == VILLAGER_CHAR) {
                num_villagers++;
            }
            else if(current != ' ' && current != character->symbol) {
                //this is a wall of some kind
                return;
            }
        }
    }
    //proceeding
    for(i = 0; i < character->size; i++) {
        for(j = 0; j < character->size; j++) {
            int x = character->pos.x + i;
            int y = character->pos.y + j;
            set_letter(' ', x, y);
            set_palette(character->palette, x, y);
        }
    }
    character->pos = *new_pos;
    for(i = 0; i < character->size; i++) {
        for(j = 0; j < character->size; j++) {
            int x = character->pos.x + i;
            int y = character->pos.y + j;
            set_letter(character->symbol, x, y);
        }
    }
}


bool update_player_form(struct character *character, bool new_form) {
    //firstly lets get the things where we're going into
    int i,j;
    int num_villagers = 0;
    int num_others = 0;
    int size = new_form ? character->size : character->old_size;
    int old_size = new_form ? character->old_size : character->size;
    for(i = 0; i < MAX(size,old_size); i++) {
        for(j = 0; j < MAX(size,old_size); j++) {
            int x = character->pos.x + i;
            int y = character->pos.y + j;
            if(i == 0 && j == 0) {
                //this will be us, duh
                continue;
            }
            if(size > old_size) {
                uint8_t item = get_item(x, y);
                if(item == VILLAGER_CHAR) {
                    num_villagers++;
                }
                else if(item != ' ') {
                    num_others++;
                }
            }
            else {
                set_letter(' ', x, y);
                set_palette(current_palette, x, y);
            }
        }
    }
    if(num_others) {
        //we can't transform
        return false;
    }
    for(i = 0; i < size; i++) {
        for(j = 0; j < size; j++) {
            int x = character->pos.x + i;
            int y = character->pos.y + j;
            set_letter(character->symbol, x, y);
            set_palette(character->palette, x, y);
        }
    }
}
    
void set_banner(char *banner) {
    int n = strlen(banner);
    int padding;
    if(n > WIDTH) {
        n = WIDTH;
    }

    padding = (WIDTH-n)/2;
    memset(banner_row, ' ', padding);
    memcpy(banner_row + padding, banner, n);
    memset(banner_row + padding + n, ' ', padding);
}

void process_input(uint8_t c, struct character *character) {
    struct position new_pos = character->pos;
    switch(tolower(c)) {
    case 'a':
    case LEFT:
        new_pos.x -= 1;
        break;
    case 'd':
    case RIGHT:
        new_pos.x += 1;
        break;
    case 'w': 
    case UP:
        new_pos.y += 1;
        break;
    case 's':
    case DOWN:
        new_pos.y -= 1;
        break;
    }
    if(new_pos.x < 0) {
        new_pos.x = 0;
    }
    if(new_pos.y < MIN_HEIGHT) {
        new_pos.y = MIN_HEIGHT;
    }
    if(new_pos.x >= WIDTH) {
        new_pos.x = WIDTH-1;
    }
    if(new_pos.y >= MAX_HEIGHT) {
        new_pos.y = MAX_HEIGHT-1;
    }

    if(character->symbol == VILLAGER_CHAR) {
        update_char_pos(&new_pos, character);
    }
    else {
        update_player_pos(&new_pos, character);
    }
}

void rand_pos(struct position *pos) {
    do {
        pos->x = getrand() % WIDTH;
        pos->y = MIN_HEIGHT + (getrand() % (MAX_HEIGHT-MIN_HEIGHT));
    }
    while (get_item(pos->x, pos->y) != ' ');
}

void create_villagers(int num) {
    int i;
    for(i = 0; i < NUM_VILLAGERS; i++) {
        rand_pos(&villagers[i].pos);
        villagers[i].symbol = VILLAGER_CHAR;
        villagers[i].palette = -1;
        villagers[i].size = 1;
    }
}

bool is_night(int t) {
    if(t >= DAY_TICKS) {
        return true;
    }
    else {
        return false;
    }
}

void set_phase(int t, bool daytime) {
    int required_blips = (t - (daytime ? 0 : DAY_TICKS))>>2;
    int i;
    strcpy(letter_data + 24, daytime ? "Day  " : "Night");
    if(is_day != daytime || required_blips < current_blips) {
        for(i = 0; i < required_blips-1; i++) {
            letter_data[24 + WIDTH + i] = BAR_CHAR;
        }
        letter_data[24+WIDTH+i] = '>';
        memset(letter_data+24+WIDTH+i+1,' ',16-i-1);
        current_blips = required_blips;
    }
    else{
        for(i = current_blips >= 1 ? current_blips-1 : 0; i < required_blips - 1; i++) {
            letter_data[24 + WIDTH + i] = BAR_CHAR;
        }
        letter_data[24+WIDTH+i] = '>';
        current_blips = required_blips;
    }
    if(is_day != daytime) {
        //we need to set all the blips anyway
        is_day = daytime;
    }
}

void tick_simulation() {
    int i;
    static char *dirs = "wsad";
    time_of_day = (time_of_day + 1)&0x7f;
    if((time_of_day&0x3f) == 0) {
        current_palette = colours[time_of_day>>6];
        memset(palette_data, current_palette, BANNER_OFFSET);
    }
    //letter_data[30] = CHAR_TO_HEX(time_of_day&0xf);
    //letter_data[29] = CHAR_TO_HEX(time_of_day>>4);
    set_phase(time_of_day, !is_night(time_of_day));

    for(i = 0; i < NUM_VILLAGERS; i++) {
        uint8_t dir = dirs[getrand()&3];
        process_input(dir, villagers + i);
        //set_letter(villagers[i].symbol,villagers[i].pos.x,villagers[i].pos.y);
    }
    if(transforming) {
        if(time_of_day == player.transform_done) {
            transforming = false;
            update_player_form(&player, true);
        }
    }
}

void transform(struct character *ch) {
    if(ch->size == 1) {
        ch->old_symbol = ch->symbol;
        ch->symbol = 'W';
        ch->size = 2;
        ch->old_size = 1;
        ch->transform_done = (time_of_day + 4)&0x7f;
        ch->palette = PALETTE(BLACK, WHITE);
    }
    else {
        ch->old_symbol = 'W';
        ch->symbol = PLAYER_CHAR;
        ch->size = 1;
        ch->old_size = 2;
        ch->transform_done = (time_of_day + 1)&0x7f;
        ch->palette = -1;
    }
    transforming = true;
}

int _start(void) {
    crash_handler_word[0] = crash_handler;
    int i;
    cursor_pos = INITIAL_CURSOR_POS;
    clear_screen_with_border(BACKGROUND, FOREGROUND, 0);
    
    memcpy(letter_data, map, strlen(map));
    memset(palette_data + BANNER_OFFSET, PALETTE(BLACK,RED), WIDTH);
    set_banner("KILL THE VILLAGERS!");
    set_phase(time_of_day, true);
    current_palette = colours[0];

    set_letter(player.symbol,player.pos.x,player.pos.y);
    create_villagers(NUM_VILLAGERS);
    for(i = 0; i < NUM_VILLAGERS; i++) {
        set_letter(villagers[i].symbol,villagers[i].pos.x,villagers[i].pos.y);
    }
 
    while(1) {
        uint8_t last_pos = *ringbuffer_pos;
        uint8_t new_pos;
        while(last_pos == (new_pos = *ringbuffer_pos)) {
            uint64_t int_info = wait_for_interrupt();
            if(INT_ID(int_info) == CLOCK_ID) {
                tick_simulation();
            }
        }
        while(last_pos != new_pos) {
            uint8_t c;
            c = keyboard_ringbuffer[last_pos];
            if(!transforming) {
                //ignore key entry while this is happening
                if (c == ' ') {
                    //Tried to activate
                    if(is_day) {
                        set_banner("You can only transform at night");
                    }
                    else {
                        transform(&player);
                    }
                }
                else {
                    process_input(c, &player);
                }
            }
            last_pos = ((last_pos + 1) % RINGBUFFER_SIZE);
        }
    }

}
