#include <stdio.h>
#include <errno.h>
#include <time.h>
#include "terminal.h"

int (*bob)(int, void *arg1, void *arg2, void *arg3) = 0x41414141;

//int _open_r(const char *file, int flags, int mode) {
//}
int close(int fd) {
    return bob(5, (void*)fd, 0, 0);
}

off_t lseek(int fd, off_t pos, int whence) {
    return (off_t) bob(4, (void*)fd, (void*) pos, (void*)whence);
}

long read(int fd, void *buf, size_t cnt) {
    if(fd == fileno(stdin)) {
        return tty_read(buf, cnt);
    }
    else {
        errno = EBADF;
        return -1;
    }
}

long write(int fd, void *buf, size_t cnt) {
    if(fd == fileno(stdout)) {
        return tty_write(buf, cnt);
    }
    else {
        errno = EBADF;
        return -1;
    }
}

//int _fork_r(void *reent) {
//}
//int _wait_r( int *status) {
//}
//int _stat_r( const char *file, struct stat *pstat) {
//}
int fstat(int fd, struct stat *pstat) {
    return (int)bob(1, (void*)fd, pstat, 0);
}
//int _link_r(const char *old, const char *new) {
//}
//int _unlink_r( const char *file) {
//}
char *sbrk(size_t incr) {
    return (char*)bob(0,(void*)incr,0,0);
}

int isatty(int fd) {
    return bob(-1,(void*)fd,0,0);
}

void *malloc(size_t size) {
    return bob(6, (void*)size, 0, 0);
}

void free(void *ptr) {
    bob(7, ptr, 0, 0);
}

int atoi(char *s) 
{
    long out;
    char *s_t = s;
    if(xatoi(&s_t, &out)) {
        return (int)out;
    }

    errno = EINVAL;
    return -1;
}

struct tm *localtime(const time_t *timep) {
    return (void*)bob(8, timep, 0, 0);
}
