#include <stdio.h>
#undef putc
#undef putchar
#undef getc
#undef getchar
#include <unistd.h>
#include "xprintf.h"

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

int fgetc(FILE *stream) 
{
    char c = 0;

    if(1 == read(fileno(stream), &c, 1)) {
        //echo to out
        if(stream == stdin) {
            write(fileno(stdout), &c, 1);
        }
        return (int)c;
    }

    return EOF;
}

int getchar(void) 
{
    fgetc(stdin);
}

static unsigned char getchar_cb(void) 
{
    return (unsigned char)fgetc(stdin);
}

char *fgets(char *s, int size, FILE *stream)
{
    int num = xfgets(getchar_cb, s, size);
    if(num > 0) {
        return s;
    }
    return NULL;
}

int getc(FILE *stream)
{
    return fgetc(stream);
}

char *gets(char *s)
{
    return fgets(s, 0x7fffffff, stdin);
}
