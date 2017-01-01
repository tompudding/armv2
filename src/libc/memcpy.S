.globl memcpy

memcpy:
        push {r4, lr}
        and r3, r0, #3
        and r5, r1, #3
        cmp r3, r5
        mov r4, r0
        bne last_part /* If the alignments are different it's a headache */
        cmp r2, #4
        blo last_part
        /* We've got more than 4 bytes to do and the src and dst alignment is the same, but
           we might not be aligned. In that case we want to do the first few byte by byte
           until we're aligned */
alignment_loop: 
        cmp r3, #0
        beq aligned
        ldrb r3, [r1], #1
        strb r3, [r4], #1
        and r3, r4, #3
        sub r2, #1
        cmp r2, #0
        beq done
        b alignment_loop
aligned:        
        cmp r2, #4
        blo last_part
cpy_loop:
        ldr r3, [r1], #4
        str r3, [r4], #4
        sub r2, #4
        cmp r2, #3
        bhi cpy_loop
last_part:
        cmp r2, #0
        beq done
        ldrb r3, [r1], #1
        strb r3, [r4], #1
        sub r2, #1
        b last_part
done:
        pop {r4, pc}

        
