.globl memset

memset:
        /* void *memset(void *s, int c, size_t n) */
        ldr r3,=0x01010101
        mul r1, r3, r1
        mov r3, r0 /* we'll need to return this so back it up */
        cmp r2, #4
        blt last_part
        /* While r2 is greater than 4, this is easy */
word_loop:
        str r1, [r3]!
        sub r2, #4
        cmp r2,#4
        ble word_loop
last_part:
        lsr r1, #24
last_part_loop: 
        cmp r2, #0
        beq done
        str r1, [r3]!
        sub r2, #1
        b last_part_loop
done:
        mov pc, lr
