.global memmove
.extern memcpy     

memmove:
        cmp r0, r1
        blo memcpy
        /* We have the destination after the source, so we need to go backwards */
        add r0, r2
        add r1, r2
        cmp r2, #4
        blt last_part
cpy_loop:       
        ldr r3, [r1], #-4
        str r3, [r0], #-4
        sub r2, #4
        cmp r2, #4
        ble cpy_loop
last_part:
        cmp r2, #0
        beq done
        ldrb r3, [r1], #-1
        strb r3, [r0], #-1
        sub r2, #1
        b last_part
done:
        mov pc, lr
