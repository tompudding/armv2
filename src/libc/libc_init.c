#include <stdio.h>

struct _reent global_reent = {0};
struct _reent *_impure_ptr = &global_reent;

int _errno = 0;

int *__errno() {
    return &_errno;
}

int fileno(FILE *s) {
    return s->_file;
}

int libc_init(void) {
    //initiliase things
    stdin  = &global_reent.__sf[0];
    stdout = &global_reent.__sf[1];
    stderr = &global_reent.__sf[2];

    stdin->_file  = 0;
    stdout->_file = 1;
    stderr->_file = 2;

    terminal_init();
}
