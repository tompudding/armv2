#include <assert.h>
#include "synapse.h"

void __assert_func( char *file, size_t line, char *assert_func, char *expression )
{
    printf("ASSERTION FAILURE in %s:%d\n", file, line);
    if(assert_func) {
        printf("FUNC : %s\n", assert_func);
    }
    if( expression ) {
        printf("EXPR : %s\n", expression);
    }
    while(1) {
        wait_for_interrupt();
    }
}
