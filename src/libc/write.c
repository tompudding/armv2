#include <stdio.h>

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
    return (long) bob(3, (void*)fd, buf, (void*)cnt);
}
long write(int fd, void *buf, size_t cnt) {
    return (long)bob(2, (void*)fd, buf, (void*)cnt);
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
