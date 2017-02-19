#include <time.h>
#include "synapse.h"

time_t time(time_t *t) {
    time_t val = 0;
    if(t) {
        *t = val;
    }
    return val;
}
