.globl strlen

strlen:
        add r2, r0, #1 /* Pointing 1 past the first character */
alignment_loop: 
        and r3, r0, #3
        cmp r3, #0
        beq aligned
        ldrb r3, [r0], #1
        cmp r3, #0
        beq done
        b alignment_loop
aligned:
        ldr r1, [r0]
        tst r1, #0xff
        tstne r1, #0xff00
        tstne r1, #0xff0000
        tstne r1, #0xff000000
        addne r0, #4
        bne aligned
last_word:
        /* guaranteed there's a null in r1 */
        ldrb r1, [r0], #1
        cmp r1, #0
        bne last_word
        /* now r0 is pointing one past the null at the end */
done:   
        sub r0, r0, r2
        mov pc, lr
        
