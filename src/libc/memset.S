.globl memset

memset:
        /* void *memset(void *s, int c, size_t n) */
        push {r4-r6,lr}
        mov r3, r0 /* back this up as we'll need to return it */
alignment_loop: 
        and r4, r3, #0x3
        /*first a little loop to get it aligned*/
        cmp r4, #0
        beq aligned
        strb r1,[r3],#1
        sub r2,#1
        cmp r2,#0
        beq done
        b alignment_loop
aligned:        
        ldr r5,=0x01010101
        mul r1, r5, r1
        cmp r2, #4
        blo last_part
        /* While r2 is greater than 4, this is easy */
word_loop:
        str r1, [r3], #4
        sub r2, #4
        cmp r2, #3
        bhi word_loop
last_part:
        lsr r1, #24
last_part_loop: 
        cmp r2, #0
        beq done
        strb r1, [r3], #1
        sub r2, #1
        b last_part_loop
done:
        pop {r4-r6, pc}
