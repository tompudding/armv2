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
    return memcpy(dest, src, strlen(src)+1);
}

int strcmp(const char* s1, const char* s2)
{
    while(*s1 && (*s1==*s2))
        s1++,s2++;
    return *(const unsigned char*)s1-*(const unsigned char*)s2;
}

int strncmp(const char* s1, const char* s2, size_t n)
{
    while(*s1 && (*s1==*s2) && --n > 0)
        s1++,s2++;
    return *(const unsigned char*)s1-*(const unsigned char*)s2;
}

#define strncpy(a, b, len) strcmp(a,b)

char *strchr(const char *s, int c) {
    do {
        if(*s == c) {
            return s;
        }
    } while(*s++);

    return NULL;
}
