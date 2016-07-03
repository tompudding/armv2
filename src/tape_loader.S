.syntax divided
.code 32

        /* This is a simple loader that's going to take all the code that comes after us, move it to 0x8000 (since then I can
           shortcut and not have to fix anything up, and jump to it */

start:
        LDR R0,code_length
        LDR R1,target_position
        ADR R2,code_start
        ADD R3,R2,R0
loop:
        LDR R4,[R2],#4
        STR R4,[R1],#4
        CMP R2,R3
        BLS loop
done:
        LDR R0,entry_point
        MOV PC,R0

code_length:    .word 0x41414141
entry_point:    .word 0xcafebabe
target_position:        .word 0x8000
code_start:
