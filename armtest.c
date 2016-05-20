#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include "armv2.h"

int main(int argc, char *argv[]) {
    struct armv2 armv2;
    enum armv2_status result = ARMV2STATUS_OK;

    if(ARMV2STATUS_OK != (result = init(&armv2,(1<<20)))) {
        LOG("Error %d creating\n",result);
        return result;
    }
    if(ARMV2STATUS_OK != (result = load_rom(&armv2,"boot.rom"))) {
        LOG("Error loading rom %d\n",result);
        return result;
    }
    run_armv2(&armv2,-1);
    goto cleanup;

cleanup:
    cleanup_armv2(&armv2);
    return result;
}
