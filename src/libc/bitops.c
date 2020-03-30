#include <stdint.h>

int32_t __bswapsi2 (int32_t a) {
    return ( ((a & 0xff) << 24) | ((a & 0xff00) << 8) | ((a & 0xff0000) >> 8) | ((a & 0xff000000) >> 24) );
}
