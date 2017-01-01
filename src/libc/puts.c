#include <stdio.h>

int puts(const char *s) 
{
    return fputs(s, stdout);
}

int fputs(const char * s, FILE *stream)
{
    size_t len = strlen(s);
    
    int r = fwrite(s, 1, len, stream);

    if( r == len ) {
        return r;
    }

    return EOF;
}

