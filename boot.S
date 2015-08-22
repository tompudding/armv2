.syntax divided
.code 32

num_devices_opcode  = 0
map_memory_opcode   = 1
device_id_opcode    = 2
interrupt_data_opcode = 3
mov_register_opcode = 0
hw_manager          = 1
keyboard_device_id  = 0x41414141
display_device_id   = 0x9d99389e
keyboard_map_start  = 0x01000000
keyboard_map_end    = 0x01001000
display_map_start   = 0x01001000
display_map_end     = 0x01002000

/* Stack offsets */
keyboard_device_num = 4
display_device_num = 8

reset:
        B start
illegal_instruction:
        SWI #1
swi:
        SWI #2
prefetch_abort:
        SWI #3
data_abort:
        SWI #4
address_exception:
        SWI #5
IRQ:
        B interrupt_handler
FIQ:
        SWI #7

start:
        MOV SP,#0x100000
        SUB SP,SP,#4
        LDR R6,=keyboard_device_id
        LDR R7,=display_device_id
        /* Load the number of hardware devices into cr0 */
        CDP 1,#num_devices_opcode,CR0,CR0,CR0
        /* Put cr0 into r0 */
        MRC 1,#mov_register_opcode,R0,CR0,CR0
        MOV R4,R0
        /* Loop over the device numbers getting their id and comparing it to the keyboard id*/
        MOV R5,#-1
        B hw_id_loop
map_device:
        ;; R0 = device_id
        ;; R1 = map_start
        ;; R2 = map_end
        MCR 1,#mov_register_opcode,R0,CR0,CR0
        /* put the start value into cr1 */
        MCR 1,#mov_register_opcode,R1,CR1,CR0
        MCR 1,#mov_register_opcode,R2,CR2,CR0
        /* Perform the map operation! */
        CDP 1,#map_memory_opcode,CR0,CR1,CR2
        MOV PC,LR
hw_id_loop:
        ADD R5,R5,#1
        CMP R5,R4
        BGE hw_loop_done
        /* Load the current index (R5) into CR0 */
        MCR 1,#mov_register_opcode,R5,CR0,CR0
        /* Perform the get id operation */
        CDP 1,#device_id_opcode,CR0,CR0,CR0
        /* Move the output into R2 */
        MRC 1,#mov_register_opcode,R2,CR0,CR0
        CMP R2,R6
        BEQ keyboard_found
        CMP R2,R7
        BNE hw_id_loop
display_found:
        STR R5,[SP,#display_device_num]
        MOV R0,R5
        LDR R1,=display_map_start
        LDR R2,=display_map_end
        BL map_device
        B hw_id_loop
keyboard_found:
        /*found the keyboard, nice!*/
        STR R5,[SP,#keyboard_device_num]
        MOV R0,R5
        LDR R1,=keyboard_map_start
        LDR R2,=keyboard_map_end
        BL map_device
        B hw_id_loop
hw_loop_done:
        /* Let's try a test where we draw something to the screen */
        /* First loop over the whole thing setting the background and foreground to opposites */
        LDR R4,=display_map_start
        ADD R5,R4,#0x4b0
        MOV R0,#0xf0
fill_loop:
        STRB R0,[R4],#0x1
        CMP R4,R5
        BLT fill_loop
        ADR R0,text
write_loop:
        LDRB R1,[R0],#1
        STRB R1,[R5],#1
        CMP R1,#0
        BNE write_loop
        B inf_loop
.align 2
text:   .asciz "I am the very model of a modern major general"
.align 4

        /* Set CR1 to be the start value */
        /* Set CR2 to be the end value */
        /* Instruct */
inf_loop:
        B inf_loop
        LDR R0,=0x80ac
        ADR LR,exit
        MOVS PC,R0
        SWP R0,R0,[R1]
exit:
        SWI #8
interrupt_handler:
        @Let's ask the hw manager what the id and code of the interrupt was
        CDP 1,#interrupt_data_opcode,CR0,CR0,CR0
        @Put CR0 into R8
        MRC 1,#mov_register_opcode,R8,CR0,CR0
        @Put CR1 into R1
        MRC 1,#mov_register_opcode,R9,CR1,CR0
        LDR R10,=keyboard_device_id
        CMP R8,R10
        BNE interrupt_done
        MOV R8,#0
interrupt_done:
        SUBS PC,LR,#4
