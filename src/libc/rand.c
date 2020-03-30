#include <stdlib.h>
#include "synapse.h"

int rand(void) {
    return (rng[0] & 0x7fffffff);
}

void srand(unsigned int seed) {
    rng[0] = (uint32_t)seed;
}

long int random(void) {
    return rand();
}

void srandom(unsigned int seed) {
    srand(seed);
}
