.globl memcpy

memcpy:
        push {r4, lr}
        mov r4, r0
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
