#include <stdio.h>

struct _reent global_reent = {0};
struct _reent *_impure_ptr = &global_reent;

int __errno = 0;

int libc_init(void) {
    //initiliase things
}
