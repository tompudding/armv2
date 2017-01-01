.globl strlen

strlen:
        mov r2,#0
loop:   
        ldrb r1, [r0], #1
        add r2, #1
        cmp r1, #0
        bne loop
        mov r0, r2
        moveq pc, lr
        
