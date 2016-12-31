.globl memcpy

memcpy:
        push {r4, lr}
        mov r4, r0
        cmp r2, #4
        blt last_part
cpy_loop:
        ldr r3, [r1]!
        str r3, [r4]!
        sub r2, #4
        cmp r2, #4
        ble cpy_loop
last_part:
        cmp r2, #0
        beq done
        ldrb r3, [r1]!
        strb r3, [r4]!
        sub r2, #1
        b last_part
done:
        pop {r4, pc}
