#include <stdio.h>
#undef putc
#undef putchar
#include <unistd.h>

int puts(const char *s) 
{
    return fputs(s, stdout);
}

int fputs(const char * s, FILE *stream)
{
    size_t len = strlen(s);
    
    //int r = fwrite(s, 1, len, stream);
    int r = write(fileno(stream), s, len);

    if( r == len ) {
        r = write(fileno(stream), "\n", 1);

        if(1 == r) {
            return len + 1;
        }
    }

    return EOF;
}


int fputc(int c, FILE *stream) 
{
    if(1 == write(fileno(stream), (const char *)&c, 1)) {
        return (int)c;
    }

    return EOF;
}

int putc(int c, FILE *stream)
{
    return fputc(c, stream);
}

int putchar(int c) 
{
    return fputc(c, stdout);
}
