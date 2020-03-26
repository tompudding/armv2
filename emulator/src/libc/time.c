#include <time.h>
#include "synapse.h"

time_t time(time_t *t) {
    time_t val = *clock_word;
    if(t) {
        *t = val;
    }
    return val;
}
