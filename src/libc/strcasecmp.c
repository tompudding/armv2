#include <ctype.h>
#include <string.h>

int strcasecmp(const char *s1, const char *s2) {
    int r = tolower(*s1) - tolower(*s2);

    while( 0 == r && *s1 && *s2 ) {
        r = tolower(*s1) - tolower(*s2);
        s1++;
        s2++;
    }

    return r;
}

char *strcpy(char *dest, const char *src) {
    return memcpy(dest, src, strlen(src));
}

char *strchr(const char *s, int c) {
    do {
        if(*s == c) {
            return s;
        }
    } while(*s++);

    return NULL;
}
