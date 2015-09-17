.syntax divided
.code 32

num_devices_opcode   = 0
map_memory_opcode    = 1
device_id_opcode     = 2
interrupt_data_opcode = 3
wait_for_interrupt_opcode = 4
gettime_opcode       = 5
mov_register_opcode  = 0
hw_manager           = 1
keyboard_device_id   = 0x41414141
display_device_id    = 0x9d99389e
tape_device_id       = 0x2730eb6c
keyboard_map_start   = 0x01000000
keyboard_map_end     = 0x01001000
display_map_start    = 0x01001000
display_map_end      = 0x01002000
tape_map_start       = 0x01002000
tape_map_end         = 0x01003000
interrupt_ringbuffer = 0x000bff00
interrupt_ringbuffer_pos = 0x000bfefc
wfi_ringbuffer_pos       = 0x000bfef8
FLAG_I                   = 0x08000000

/* Syscalls */
sys_wait_for_interrupt  = 17
sys_gettime             = 18
sys_getrand             = 19

/* Stack offsets */
keyboard_device_num = 0x4
display_device_num  = 0x8
tape_device_num     = 0xc

reset:
        B start
illegal_instruction:
        B handle_illegal_instruction
swi:
        B software_interrupt
prefetch_abort:
        B handle_prefetch_error
data_abort:
        B handle_data_abort
address_exception:
        B handle_address_exception
IRQ:
        B interrupt_handler
FIQ:
        SWI #7

start:
        @ Set the stack up for supervisor mode...
        MOV SP,#0x100000
        SUB SP,SP,#4
        @ Now switch to IRQ mode to set that stack up...
        ORRS PC,PC,#2
        NOP
        MOV SP,#0xe0000
        SUB SP,SP,#4
        ORRS PC,PC,#3
        NOP
        LDR R6,=keyboard_device_id
        LDR R7,=display_device_id
        LDR R8,=tape_device_id
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
        BEQ display_found
        CMP R2,R8
        BNE hw_id_loop
tape_found:
        STR R5,[SP,#tape_device_num]
        MOV R0,R5
        LDR R1,=tape_map_start
        LDR R2,=tape_map_end
        BL map_device
        B hw_id_loop
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
        ADR R0,usr_mode
        MOVS PC,R0
usr_mode:
        LDR SP,=0xf0000
        LDR R0,entry_point
        ADR LR,exit
        MOVS PC,R0
        SWP R0,R0,[R1]
exit:
        SWI #8
interrupt_handler:
        PUSH {R8-R12}
        @Let's ask the hw manager what the id and code of the interrupt was
        CDP 1,#interrupt_data_opcode,CR0,CR0,CR0
        @Put CR0 into R8
        MRC 1,#mov_register_opcode,R8,CR0,CR0
        @Put CR1 into R1
        MRC 1,#mov_register_opcode,R9,CR1,CR0
        LDR R10,=interrupt_ringbuffer_pos
        LDR R11,[R10]
        LDR R12,=interrupt_ringbuffer
        ADD R12,R11
        STR R8,[R12],#4
        STR R9,[R12],#4
        ADD R11,#8
        AND R11,#0xff
        STR R11,[R10]
        POP {R8-R12}
        SUBS PC,LR,#4

software_interrupt:
        cmp R7,#sys_wait_for_interrupt
        BEQ wfi
        CMP R7,#sys_gettime
        BNE software_interrupt_done
gettime:
        CDP 1,#gettime_opcode,CR0,CR0,CR0
        MRC 1,#mov_register_opcode,R0,CR0,CR0
        /* put the start value into cr1 */
        MRC 1,#mov_register_opcode,R1,CR1,CR0
        ADR R3,scratch
        STR R0,[R3]
        STR R1,[R3,#4]
        MOV R0,R3
        B software_interrupt_done
wfi:
        MOV R0,#FLAG_I
        ORRS PC,R0,PC
        NOP
        PUSH {R8-R12}
        LDR R10,=interrupt_ringbuffer_pos
        LDR R8,=wfi_ringbuffer_pos
        LDR R9,[R8]
check_position:
        LDR R11,[R10]
        CMP R9,R11
        BNE return_interrupt
        /* Clear the interrupt flag again by setting the mode to SUP*/
        ORRS PC,PC,#3
        NOP
        CDP 1,#wait_for_interrupt_opcode,CR0,CR0,CR0
        ORRS PC,R0,PC
        NOP
        B check_position
return_interrupt:
        LDR R10,=interrupt_ringbuffer
        LDR R0,[R10,R9]
        ADD R9,#4
        LDR R1,[R10,R9]
        ADD R9,#4
        AND R9,#0xff
        STR R9,[R8]
        POP {R8-R12}
software_interrupt_done:
        SUBS PC,LR,#4

handle_illegal_instruction:
        MOV R0,#0
        B handle_error
handle_prefetch_error:
        MOV R0,#1
        B handle_error
handle_data_abort:
        MOV R0,#2
        B handle_error
handle_address_exception:
        MOV R0,#3
handle_error:
        MOV R1,LR
        ADR R5,handle_error_usr
        MOVS PC,R5
handle_error_usr:
        MOV R2,SP
        MOV R3,LR
        LDR R4,=0x20000
        LDR R4,[R4]
        MOV PC,R4

entry_point:
        .word 0xcafebabe
scratch:
        .word 0x00000000
        .word 0x00000000
        .word 0x00000000
        .word 0x00000000
