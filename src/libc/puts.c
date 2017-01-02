#include <stdio.h>

int puts(const char *s) 
{
    return fputs(s, stdout);
}

int fputs(const char * s, FILE *stream)
{
    size_t len = strlen(s);
    
    //int r = fwrite(s, 1, len, stream);
    int r = write(fileno(stream), s, strlen(s));

    if( r == len ) {
        r = write(fileno(stream), '\n', 1);

        if(1 == r) {
            return len + 1;
        }
    }

    return EOF;
}

