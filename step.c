#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include "armv2.h"

enum armv2_status run_armv2(struct armv2 *cpu, int32_t instructions)
{
    uint32_t running = 1;
    uint32_t old_mode = 0;

    //instructions of -1 means run forever
    while(running) {
        old_mode = GETMODE(cpu);

        if( instructions == 0 ) {
            return ARMV2STATUS_OK;
        }

        if( instructions > 0 ) {
            instructions--;
        }

        if( WAITING(cpu) && PIN_OFF(cpu, I) && PIN_OFF(cpu, F) ) {
            return ARMV2STATUS_WAIT_FOR_INTERRUPT;
        }

        enum armv2_exception exception = EXCEPT_NONE;
        cpu->pc = (cpu->pc + 4) & 0x3ffffff;

        //check if PC is valid
        SETPC(cpu,cpu->pc + 8);

        //Before we do anything, we check to see if we need to do an FIQ or an IRQ
        if( FLAG_CLEAR(cpu,F) ) {
            if( PIN_ON(cpu,F) ) {
                //crumbs, time to do an FIQ!
                cpu->regs.actual[R14_F] = cpu->regs.actual[PC] - 4;
                SETMODE(cpu, MODE_FIQ);
                SETFLAG(cpu, F);
                SETFLAG(cpu, I);

                for(uint32_t i = 8; i < 15; i++) {
                    cpu->regs.effective[i] = &cpu->regs.actual[R8_F + (i - 8)];
                }
                cpu->pc = 0x1c - 4;
                continue;
            }
        }
        if( FLAG_CLEAR(cpu,I) ) {
            if( PIN_ON(cpu,I) ) {
                //crumbs, time to do an IRQ!
                //set the LR first
                cpu->regs.actual[R14_I] = cpu->regs.actual[PC] - 4;
                //set the mode to IRQ mode
                SETMODE(cpu, MODE_IRQ);
                //mask interrupts so they won't be taken next time.
                CLEARPIN(cpu, I);
                SETFLAG(cpu, I);
                //in case it's waiting for an interrupt
                CLEARCPUFLAG(cpu, WAIT);
                cpu->pc = 0x18 - 4;

                for(uint32_t i = 8;i < 13; i++) {
                    cpu->regs.effective[i] = &cpu->regs.actual[i];
                }

                for(uint32_t i = 13;i < 15; i++) {
                    cpu->regs.effective[i] = &cpu->regs.actual[R13_I + (i - 13)];
                }
                continue;
            }
        }

        if(cpu->page_tables[PAGEOF(cpu->pc)] == NULL) {
            //Trying to execute an unmapped page!
            //some sort of exception
            exception = EXCEPT_PREFETCH_ABORT;
            goto handle_exception;
        }

        if( HAS_BREAKPOINT(cpu, cpu->pc) ) {
            exception = EXCEPT_BREAKPOINT;
            goto handle_exception;
        }

        uint32_t instruction = DEREF(cpu, cpu->pc);
        switch(CONDITION_BITS(instruction)) {
        case COND_EQ: //Z set
            if(FLAG_SET(cpu, Z)) {
                break;
            }
            continue;
        case COND_NE: //Z clear
            if(FLAG_CLEAR(cpu, Z)) {
                break;
            }
            continue;
        case COND_CS: //C set
            if(FLAG_SET(cpu, C)) {
                break;
            }
            continue;
        case COND_CC: //C clear
            if(FLAG_CLEAR(cpu, C)) {
                break;
            }
            continue;
        case COND_MI: //N set
            if(FLAG_SET(cpu, N)) {
                break;
            }
            continue;
        case COND_PL: //N clear
            if(FLAG_CLEAR(cpu, N)) {
                break;
            }
            continue;
        case COND_VS: //V set
            if(FLAG_SET(cpu, V)) {
                break;
            }
            continue;
        case COND_VC: //V clear
            if(FLAG_CLEAR(cpu, V)) {
                continue;
            }
            break;
        case COND_HI: //C set and Z clear
            if(FLAG_SET(cpu, C) && FLAG_CLEAR(cpu, Z)) {
                break;
            }
            continue;
        case COND_LS: //C clear or Z set
            if(FLAG_CLEAR(cpu, C) || FLAG_SET(cpu, Z)) {
                break;
            }
            continue;
        case COND_GE: //N set and V set,  or N clear and V clear
            if( (!!FLAG_SET(cpu, N)) == (!!FLAG_SET(cpu, V)) ) {
                break;
            }
            continue;
        case COND_LT: //N set and V clear or N clear and V set
            if( (!!FLAG_SET(cpu, N)) != (!!FLAG_SET(cpu, V)) ) {
                break;
            }
            continue;
        case COND_GT: //Z clear and either N set and V set, or N clear and V clear
            if((FLAG_CLEAR(cpu, Z) && (!!FLAG_SET(cpu, N)) == (!!FLAG_SET(cpu, V)) )) {
                break;
            }
            continue;
        case COND_LE: //Z set or N set and V clear, or N clear and V set
            if((FLAG_SET(cpu, Z) || (!!FLAG_SET(cpu, N)) != (!!FLAG_SET(cpu, V)) )) {
                break;
            }
            continue;
        case COND_AL: //Always
            break;
        case COND_NV: //Never
            continue;
        }
        instruction_handler_t handler = NULL;
        //We're executing the instruction
        switch((instruction >> 26) & 03) {
        case 0:
            if((instruction & 0x0fc000f0) == 0x00000090) {
                handler = multiply_instruction;
            }
            else if((instruction & 0x0fb00ff0) == 0x01000090) {
                handler = swap_instruction;
            }
            else {
                //data processing instruction...
                handler = alu_instruction;
            }
            break;
        case 1:
            //LDR or STR, or undefined
            handler = single_data_transfer_instruction;
            break;
        case 2:
            //LDM or STM or branch
            if(instruction & 0x02000000) {
                handler = branch_instruction;
            }
            else {
                handler = multi_data_transfer_instruction;
            }
            break;
        case 3:
            //coproc functions or swi
            if((instruction & 0x0f000000) == 0x0f000000) {
                handler = software_interrupt_instruction;
            }
            else if((instruction & 0x02000000) == 0) {
                handler = coprocessor_data_transfer_instruction;
            }
            else if(instruction & 0x10) {
                handler = coprocessor_register_transfer_instruction;
            }
            else {
                handler = coprocessor_data_operation_instruction;
            }
            break;
        }
        old_mode = GETMODE(cpu);
        exception = handler(cpu, instruction);

        if( HASCPUFLAG(cpu, WATCHPOINT) && exception == EXCEPT_NONE) {
            exception = EXCEPT_BREAKPOINT;
            CLEARCPUFLAG(cpu, WATCHPOINT);
        }

        //handle the exception if there was one
    handle_exception:
        if(exception != EXCEPT_NONE) {
            //LOG("Instruction exception %d\n",exception);
            if(exception == EXCEPT_BREAKPOINT) {
                if(instructions == -1) {
                    //this means we're running forver, so treat this as an SWI
                    exception = EXCEPT_SOFTWARE_INTERRUPT;
                }
                else {
                    //This is special and means stop executing the emulator
                    //Don't advance PC next time since we're at a bkpt
                    cpu->pc -= 4;
                    return ARMV2STATUS_BREAKPOINT;
                }
            }
            struct exception_handler ex_handler = cpu->exception_handlers[exception];
            cpu->regs.actual[ex_handler.save_reg] = cpu->regs.actual[PC];
            cpu->regs.actual[PC] = ((cpu->regs.actual[PC]) & 0xfffffffc) | ex_handler.mode;
            cpu->pc = ex_handler.pc - 4;
        }

        if(GETMODE(cpu) != old_mode) {
            //The instruction changed the mode of the processor so we need to bank registers
            if(MODE_FIQ == old_mode) {
                for(uint32_t i = 8;i < NUM_EFFECTIVE_REGS; i++) {
                    cpu->regs.effective[i] = &cpu->regs.actual[i];
                }
            }
            switch(GETMODE(cpu)) {
            case MODE_SUP:
                for(uint32_t i = 13;i < 15; i++) {
                    cpu->regs.effective[i] = &cpu->regs.actual[R13_S + (i - 13)];
                }
                break;
            case MODE_IRQ:
                for(uint32_t i = 13;i < 15; i++) {
                    cpu->regs.effective[i] = &cpu->regs.actual[R13_I + (i - 13)];
                }
                break;
            case MODE_FIQ:
                for(uint32_t i = 8;i < 15; i++) {
                    cpu->regs.effective[i] = &cpu->regs.actual[R8_F + (i - 8)];
                }
                break;
            case MODE_USR:
                for(uint32_t i = 13;i < 15;i++) {
                    cpu->regs.effective[i] = &cpu->regs.actual[i];
                }
                break;
            default:
                break;
            }
        }

    }
    return ARMV2STATUS_OK;
}
