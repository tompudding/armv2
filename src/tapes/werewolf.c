#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include <stdbool.h>
#include <stdlib.h>
#include "synapse.h"
#include <terminal.h>


size_t border_size = 1;

#define BACKGROUND BLUE
#define FOREGROUND LIGHT_BLUE
uint32_t normal        = PALETTE(BACKGROUND,FOREGROUND);
uint32_t inverted      = PALETTE(FOREGROUND,BACKGROUND);
bool     is_day        = true;
bool     level_banner  = false;
int      current_blips = 0;

#define MAX_HEIGHT                 (HEIGHT-2)
#define MIN_HEIGHT                 2
#define DAY_TICKS                  0x40
#define BAR_CHAR                   '='
#define VILLAGER_CHAR              'n'
#define VILLAGER_ARMED             'a'
#define VILLAGER_ARMED_SUSPICIOUS  'A'
#define VILLAGER_SCARED            's'
#define VILLAGER_SCARED_SUSPICIOUS 'S'
#define VILLAGER_SUSPICIOUS        'N'
#define PLAYER_CHAR                'x'
#define DEAD_CHAR                  '\x7f'
#define WEREWOLF_CHAR              'W'
#define MAX(a,b) ((a) < (b) ? (b) : (a))

int colours[] = {PALETTE(BLUE, LIGHT_BLUE),
                 PALETTE(BLACK, RED)};
int current_palette = -1;
bool transforming = false;
bool game_over = false;
int level = 1;

char *villager_types = "naAsSN\x7f";

#define BANNER_OFFSET ((HEIGHT-MIN_HEIGHT)*WIDTH)
#define banner_row (letter_data + BANNER_OFFSET)

#define CHAR_TO_HEX(c) ((c) > 9 ? ('a' + (c) - 10) : ('0' + (c)))

char *map =
    "            Health                      "
    "   Villagers Left                       "
    "                                        "
    "                                        "
    "                                        "
    "    \x90`` ``\x8e                             "
    "    }     }                             "
    "    }     }                             "
    "       w                                "
    "    }     }                             "
    "    }     }                             "
    "    \x8d`` ``\x9d                             "
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
    bool dead;
    int health;
    bool armed;
    bool suspicious;
    bool scared;
    bool walking_to_point;
    struct position destination;
};

static void end_game(char *, bool);
static void lose_game();
static void win_game();

struct position cabinet_pos = {.x = 7, .y = 21};
struct position doors[4] = {{7,18},{7,24},{4,21},{10,21}};

#define MAX_NUM_VILLAGERS 100
#define OBSERVE_DISTANCE 60
struct character player = {.pos = {.x = 20, .y = 15}, .symbol=PLAYER_CHAR, .palette = -1, .size=1, .health=100};
struct character villagers[MAX_NUM_VILLAGERS];
int time_of_day = 0x30; //0 - 10
int num_villagers = 1;
int current_villagers = 1;

static int set_letter(char c, int x, int y) {
    letter_data[WIDTH*(HEIGHT-1-y) + x] = c;
}

static int distance(struct position *a, struct position *b) {
    int x = a->x - b->x;
    int y = a->y - b->y;
    return x*x + y*y;
}

static bool line_of_sight(struct position *a, struct position *b) {
    return true;
}

static int set_palette(int c, int x, int y) {
    if(c == -1) {
        c = current_palette;
    }
    palette_data[WIDTH*(HEIGHT-1-y) + x] = c;
}

static uint8_t get_item(int x, int y) {
    return letter_data[WIDTH*(HEIGHT-1-y) + x];
}

static bool is_villager(uint8_t item) {
    return strchr(villager_types, item);
}

static bool is_player(uint8_t item) {
    return item == PLAYER_CHAR || item == WEREWOLF_CHAR;
}

static void update_health() {
    letter_data[19] = '0' + player.health/100;
    letter_data[20] = '0' + (player.health/10)%10;
    letter_data[21] = '0' + player.health%10;
}

static void next_level() {
    char level_text[] = "LEVEL 00";
    level++;
    num_villagers += 5;
    current_villagers = num_villagers;
    memset(villagers, 0, sizeof(villagers));
    level_text[6] += level/10;
    level_text[7] += level%10;
    end_game(level_text,false);
}

static void update_num_villagers() {
    letter_data[WIDTH+19] = '0' + current_villagers/10;
    letter_data[WIDTH+20] = '0' + current_villagers%10;
    if(current_villagers == 0) {
        next_level();
    }
}

static void hurt_player() {
    player.health -= player.size == 2 ? 20 : 50;
    update_health();
    if(player.health <= 0) {
        lose_game();
    }
    rng[0] = 1;
}

static void update_werewolf_pos(struct position *new_pos, struct character *character) {
}

static bool update_char_pos(struct position *new_pos, struct character *character) {
    uint8_t current = get_item(new_pos->x, new_pos->y);
    if(current != ' ' && !is_villager(current) && !is_player(current)) {
        //if(current != ' ') {
        return false;
    }
    if((is_player(current) && character->armed && character->suspicious) || current == WEREWOLF_CHAR) {
        character->dead = true;
        current_villagers--;
        rng[0] = 2;
        if(character->armed) {
            hurt_player();
        }
        update_num_villagers();
        return true;
    }
    set_letter(' ', character->pos.x, character->pos.y);
    character->pos = *new_pos;
    set_letter(character->symbol, character->pos.x, character->pos.y);
    return true;
}

static void update_player_pos(struct position *new_pos, struct character *character) {
    int i,j;

    for(i = 0; i < character->size; i++) {
        for(j = 0; j < character->size; j++) {
            int x = new_pos->x + i;
            int y = new_pos->y + j;

            uint8_t current = get_item(x, y);
            if(is_villager(current)) {
                //this is fine
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
            set_palette(current_palette, x, y);
        }
    }
    character->pos = *new_pos;
    for(i = 0; i < character->size; i++) {
        for(j = 0; j < character->size; j++) {
            int x = character->pos.x + i;
            int y = character->pos.y + j;
            set_letter(character->symbol, x, y);
            set_palette(character->palette, x, y);
        }
    }
}

static bool update_player_form(struct character *character, bool new_form) {
    //firstly lets get the things where we're going into
    int i,j;
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
                if(is_villager(item)) {
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
            int symbol = character->symbol;
            if(!new_form) {
                symbol = PLAYER_CHAR;
            }
            set_letter(character->symbol, x, y);
            set_palette(character->palette, x, y);
        }
    }
}

static void update_symbol(struct character *character) {
    if(character->armed) {
        character->symbol = character->suspicious ? VILLAGER_ARMED_SUSPICIOUS : VILLAGER_ARMED;
    }
    else if(character->scared) {
        character->symbol = character->suspicious ? VILLAGER_SCARED_SUSPICIOUS : VILLAGER_SCARED;
    }
    else {
        character->symbol = character->suspicious ? VILLAGER_SUSPICIOUS : VILLAGER_CHAR;
    }
}

static void set_banner_row(char *banner, uint8_t *row) {
    int n = strlen(banner);
    int padding;
    if(n > WIDTH) {
        n = WIDTH;
    }

    padding = (WIDTH-n)/2;
    memset(row, ' ', padding);
    memcpy(row + padding, banner, n);
    memset(row + padding + n, ' ', padding);
}

static void set_banner(char *banner) {
    return set_banner_row(banner, banner_row);
}

static void cap_pos(struct position *new_pos, int size) {
    if(new_pos->x < 0) {
        new_pos->x = 0;
    }
    if(new_pos->y < MIN_HEIGHT) {
        new_pos->y = MIN_HEIGHT;
    }
    if(new_pos->x + size - 1 >= WIDTH) {
        new_pos->x = WIDTH-1-(size - 1);
    }
    if(new_pos->y + size - 1 >= MAX_HEIGHT) {
        new_pos->y = MAX_HEIGHT-1-(size-1);;
    }
}

static void process_input(uint8_t c, struct character *character) {
    struct position new_pos = character->pos;
    switch(tolower(c)) {
    case 'a':
    case KEY_LEFT:
        new_pos.x -= 1;
        break;
    case 'd':
    case KEY_RIGHT:
        new_pos.x += 1;
        break;
    case 'w':
    case KEY_UP:
        new_pos.y += 1;
        break;
    case 's':
    case KEY_DOWN:
        new_pos.y -= 1;
        break;
    }
    cap_pos(&new_pos, character->size);

    update_player_pos(&new_pos, character);
}

static bool in_room(struct position *pos) {
    return ((pos->x > 4) && (pos->x < 10) && (pos->y > 18) && (pos->y < 24));
}

static struct position *nearest_door(struct position *pos) {
    struct position *out = doors;
    int min = 0x7fffffff;
    int i;
    for(i = 0; i < 4; i++) {
        int d = distance(pos, doors + i);
        if(d < min) {
            min = d;
            out = doors + i;
        }
    }
    return out;
}

static bool proceed_to_point(struct character *villager, struct position *pos) {
    struct position *chosen;
    if(in_room(pos) != in_room(&villager->pos)) {
        //move to the nearest door
        chosen = nearest_door(pos);
        if(chosen->x == villager->pos.x && chosen->y == villager->pos.y) {
            //they made it to the door
            chosen = pos;
        }
    }
    else {
        chosen = pos;
    }
    int x = chosen->x - villager->pos.x;
    int y = chosen->y - villager->pos.y;
    if(x == 0 && y == 0) {
        return false;
    }
    struct position new_pos = villager->pos;

    if(abs(x)) {
        int diff = x > 0 ? 1 : -1;
        new_pos.x = villager->pos.x + diff;
        cap_pos(&new_pos, villager->size);
        if(update_char_pos(&new_pos, villager)) {
            return true;
        }
    }
    new_pos.x = villager->pos.x;
    if(0 == abs(y)) {
        return false;
    }

    //try the other one if that didn't work
    int diff = y > 0 ? 1 : -1;
    new_pos.y = villager->pos.y + diff;
    cap_pos(&new_pos, villager->size);
    if(!update_char_pos(&new_pos, villager)) {
        return false;
    }

    return true;
}

static void rand_pos(struct position *pos) {
    do {
        pos->x = rand() % WIDTH;
        pos->y = MIN_HEIGHT + (rand() % (MAX_HEIGHT-MIN_HEIGHT));
    }
    while (get_item(pos->x, pos->y) != ' ');
}


static void end_game(char *message, bool end_game) {
    uint8_t *row = letter_data + WIDTH*HEIGHT/2;
    set_banner_row(message,letter_data + WIDTH*HEIGHT/2);
    memset(palette_data + WIDTH*HEIGHT/2, PALETTE(DARK_GREY, WHITE), WIDTH*2);
    if(end_game) {
        set_banner_row("RELOAD TAPE TO PLAY AGAIN", row + WIDTH);
    }
    else {
        set_banner_row("PRESS ENTER TO CONTINUE", row + WIDTH);
    }
    if(end_game) {
        game_over = true;
    }
    else {
        level_banner = true;
    }
}

static void start_game(char *message, char *m2) {
    uint8_t *row = letter_data + WIDTH*HEIGHT/2;
    set_banner_row(message,letter_data + WIDTH*HEIGHT/2);
    set_banner_row(m2,letter_data + (WIDTH*HEIGHT/2) + WIDTH);
    memset(palette_data + WIDTH*HEIGHT/2, PALETTE(DARK_GREY, WHITE), WIDTH*3);
    set_banner_row("PRESS ENTER TO START", row + WIDTH*2);
    level_banner = true;
}

static void win_game() {
    end_game("YOU WIN", true);
}

static void lose_game() {
    end_game("YOU LOSE", true);
}


static void create_villagers(int num) {
    int i;
    for(i = 0; i < num_villagers; i++) {
        rand_pos(&villagers[i].pos);
        villagers[i].symbol = VILLAGER_CHAR;
        villagers[i].palette = -1;
        villagers[i].size = 1;
    }
}

static bool is_night(int t) {
    if(t >= DAY_TICKS) {
        return true;
    }
    else {
        return false;
    }
}

static void set_phase(int t, bool daytime) {
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


static bool transform(struct character *ch) {
    int i,j;
    if(ch->size == 1) {
        for(i = 0; i < 2; i++) {
            for(j = 0; j < 2; j++) {
                int x = ch->pos.x + i;
                int y = ch->pos.y + j;
                if(i == 0 && j == 0) {
                    continue;
                }
                uint8_t item = get_item(x,y);
                if(item != ' ' && !is_villager(item)) {
                    return false;
                }
            }
        }
        ch->old_symbol = ch->symbol;
        ch->symbol = WEREWOLF_CHAR;
        ch->size = 2;
        ch->old_size = 1;
        ch->transform_done = (time_of_day + 4)&0x7f;
        ch->palette = PALETTE(BLACK, WHITE);
        rng[0] = 0;
    }
    else {
        ch->old_symbol = WEREWOLF_CHAR;
        ch->symbol = PLAYER_CHAR;
        ch->size = 1;
        ch->old_size = 2;
        ch->transform_done = (time_of_day + 1)&0x7f;
        ch->palette = -1;
    }
    transforming = true;
    for(i = 0; i < num_villagers; i++) {
        if(villagers[i].dead) {
            continue;
        }
        if(distance(&villagers[i].pos, &player.pos) < OBSERVE_DISTANCE &&
           line_of_sight(&villagers[i].pos, &player.pos)) {
            villagers[i].suspicious = true;
            update_symbol(villagers + i);
        }
    }
    return true;
}

static void update_villager(struct character *villager) {
    if(villager->suspicious) {
        int i;
        for(i = 0; i < num_villagers; i++) {
            if(villagers + i == villager || villagers[i].suspicious) {
                continue;
            }

            if(distance(&villagers[i].pos,&villager->pos) < 10) {
                villagers[i].suspicious = true;
                update_symbol(villagers + i);
            }
        }
    }

    if(!villager->scared || (!villager->suspicious && villager->armed && player.size == 1)) {
        if(player.size == 2 && distance(&villager->pos, &player.pos) < OBSERVE_DISTANCE &&
           line_of_sight(&villager->pos, &player.pos)) {
            villager->scared = true;
            update_symbol(villager);
        }
        else {
            //pick a point on the screen and walk towards it
            if(!villager->walking_to_point) {
                villager->destination.x = rand()%WIDTH;
                villager->destination.y = MIN_HEIGHT + rand() % (MAX_HEIGHT - MIN_HEIGHT);
                villager->walking_to_point = true;
            }
            villager->walking_to_point = proceed_to_point(villager, &villager->destination);
            return;
        }
    }

    else if((villager->scared || villager->suspicious) && !villager->armed) {
        //go to a random weapons cabinet
        villager->destination.x = 7;
        villager->destination.y = 21;
        villager->walking_to_point = true;
        if(proceed_to_point(villager, &villager->destination)) {
            if(distance(&villager->pos,&cabinet_pos) <= 2) {
                villager->armed = true;
                update_symbol(villager);
            }
        }
    }
    else if(villager->armed) {
        //go to the werewolf
        proceed_to_point(villager, &player.pos);
    }

}

static void set_observed(bool observed) {
    memcpy(letter_data + 3, observed ? "OBSERVED" : "HIDDEN  ", 8 );
}

static void tick_simulation() {
    int i;
    static char *dirs = "wsad";
    time_of_day = (time_of_day + 1)&0x7f;
    if((time_of_day&0x3f) == 0) {
        current_palette = colours[time_of_day>>6];
        memset(palette_data, current_palette, BANNER_OFFSET);
    }
    if(time_of_day == 0) {
        if(player.size == 2) {
            //No werewolf during the day!
            transform(&player);
            transforming = false;
            update_player_form(&player, true);
            set_banner("You turned back at dawn");
        }
        //non supicious villagers put their weapons down
        for(i = 0; i < num_villagers; i++) {
            if(villagers[i].dead) {
                continue;
            }
            if(!villagers[i].suspicious) {
                villagers[i].armed = false;
                villagers[i].scared = false;
                villagers[i].symbol = VILLAGER_CHAR;
            }
        }
    }
    //letter_data[30] = CHAR_TO_HEX(time_of_day&0xf);
    //letter_data[29] = CHAR_TO_HEX(time_of_day>>4);
    set_phase(time_of_day, !is_night(time_of_day));
    bool observed = false;

    for(i = 0; i < num_villagers; i++) {
        if(level_banner) {
            return;
        }
        int x = villagers[i].pos.x;
        int y = villagers[i].pos.y;
        uint8_t current = get_item(x,y);
        if(villagers[i].dead) {
            //just redraw if it's empty
            if(!is_player(current)) {
                set_letter(DEAD_CHAR, x, y);
            }
        }
        else if(current == WEREWOLF_CHAR || (current == PLAYER_CHAR && villagers[i].armed && villagers[i].suspicious)) {
            villagers[i].dead = true;
            current_villagers--;
            rng[0] = 2;
            update_num_villagers();
            if(villagers[i].armed) {
                hurt_player();
            }
        }
        else {
            if(distance(&villagers[i].pos, &player.pos) < OBSERVE_DISTANCE) {
                observed = true;
            }
            update_villager(villagers + i);
            //set_letter(villagers[i].symbol,villagers[i].pos.x,villagers[i].pos.y);
        }
    }
    set_observed(observed);
    if(transforming) {
        if(time_of_day == player.transform_done) {
            transforming = false;
            update_player_form(&player, true);
        }
        else if(player.transform_done - time_of_day == 3) {
            update_player_form(&player, false);
        }
        else if(player.transform_done - time_of_day == 2) {
            update_player_form(&player, true);
        }
        else if(player.transform_done - time_of_day == 1) {
            update_player_form(&player, false);
        }
    }
    else {
        update_player_pos(&player.pos, &player);
    }
}

static void kill_villagers() {
    int i;
    bool killed = false;
    for(i = 0; i < num_villagers; i++) {
        int x = villagers[i].pos.x;
        int y = villagers[i].pos.y;
        uint8_t current = get_item(x,y);
        if(villagers[i].dead) {
            //just redraw if it's empty
            if(!is_player(current)) {
                set_letter(DEAD_CHAR, x, y);
            }
        }
        else if(current == WEREWOLF_CHAR || (current == PLAYER_CHAR && villagers[i].armed && villagers[i].suspicious)) {
            killed = villagers[i].dead = true;
            current_villagers--;
            rng[0] = 2;
            if(villagers[i].armed) {
                hurt_player();
            }
        }
    }
    if(killed) {
        update_num_villagers();
    }
}

void reset() {
    int i;
    current_palette = -1;
    current_blips = 0;
    time_of_day = 0x30;
    clear_screen_default();
    memset(&player, 0, sizeof(player));
    player.pos.x = 20;
    player.pos.y = 15;
    player.symbol = PLAYER_CHAR;
    player.palette = -1;
    player.size = 1;
    player.health = 100;

    is_day = true;
    transforming = false;

    memcpy(letter_data, map, strlen(map));
    memset(palette_data + BANNER_OFFSET, PALETTE(BLACK,RED), WIDTH*2);
    set_banner("KILL THE VILLAGERS!");
    set_phase(time_of_day, true);
    current_palette = colours[0];
    memset(palette_data, current_palette, BANNER_OFFSET);

    set_letter(player.symbol,player.pos.x,player.pos.y);
    create_villagers(num_villagers);
    update_num_villagers(current_villagers);
    update_health(player.health);
    for(i = 0; i < num_villagers; i++) {
        set_letter(villagers[i].symbol,villagers[i].pos.x,villagers[i].pos.y);
    }
}

int main(void) {
    int i;

    set_screen_data(BACKGROUND, FOREGROUND, 0);
    reset();

    start_game("CAPS=suspicious a=armed s=scared","n=normal w=weapons x=you!");

    while(1) {
        if(game_over) {
            break;
        }
        uint8_t last_pos = *ringbuffer_pos;
        uint8_t new_pos;
        while(last_pos == (new_pos = *ringbuffer_pos)) {
            uint64_t int_info = wait_for_interrupt();
            if(INT_ID(int_info) == CLOCK_ID) {
                if(!level_banner) {
                    tick_simulation();
                }
            }
        }
        while(last_pos != new_pos) {
            uint8_t c;
            c = keyboard_ringbuffer[last_pos];
            if(level_banner) {
                if(c == '\n') {
                    level_banner = false;
                    reset();
                    break;
                }
            }
            else if(!transforming) {
                //ignore key entry while this is happening
                if (c == ' ') {
                    //Tried to activate
                    if(is_day) {
                        set_banner("You can only transform at night");
                    }
                    else {
                        if(!transform(&player)) {
                            set_banner("No room to transform here");
                        }
                    }
                }
                else if(!level_banner){
                    process_input(c, &player);
                    kill_villagers();
                }
            }
            last_pos = ((last_pos + 1) % RINGBUFFER_SIZE);
        }
    }
    while(1) {
        wait_for_interrupt();
    }

}
