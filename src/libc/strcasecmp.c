#include <ctype.h>

int strcasecmp(const char *s1, const char *s2) {
    int r = tolower(*s1) - tolower(*s2);

    while( 0 == r && *s1 && *s2 ) {
        r = tolower(*s1) - tolower(*s2);
        s1++;
        s2++;
    }

    return r;
}
