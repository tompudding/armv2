.globl memset

memset:
        /* void *memset(void *s, int c, size_t n) */
        push {r4,lr}
        mov r3, r0 /* we'll need to return this so back it up */
        ldr r4,=0x01010101
        mul r4, r1, r4
        cmp r2, #4
        blt last_part
        /* While r2 is greater than 4, this is easy */
word_loop:
        str r4, [r3]!
        subs r2, #4
        cmp r2,#4
        ble word_loop
last_part:
        cmp r2, #0
        beq done
        str r1, [r3]!
        subs r2, #1
        b last_part
done:
        pop {r4,pc}