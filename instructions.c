#include "armv2.h"
#include <stdio.h>
#include <stdarg.h>

#define ALU_TYPE_IMM   0x02000000
#define MUL_TYPE_MLA   0x00200000
#define ALU_SETS_FLAGS 0x00100000
#define ALU_OPCODE_AND 0x0
#define ALU_OPCODE_EOR 0x1
#define ALU_OPCODE_SUB 0x2
#define ALU_OPCODE_RSB 0x3
#define ALU_OPCODE_ADD 0x4
#define ALU_OPCODE_ADC 0x5
#define ALU_OPCODE_SBC 0x6
#define ALU_OPCODE_RSC 0x7
#define ALU_OPCODE_TST 0x8
#define ALU_OPCODE_TEQ 0x9
#define ALU_OPCODE_CMP 0xa
#define ALU_OPCODE_CMN 0xb
#define ALU_OPCODE_ORR 0xc
#define ALU_OPCODE_MOV 0xd
#define ALU_OPCODE_BIC 0xe
#define ALU_OPCODE_MVN 0xf

#define ALU_SHIFT_LSL  0x0
#define ALU_SHIFT_LSR  0x1
#define ALU_SHIFT_ASR  0x2
#define ALU_SHIFT_ROR  0x3

static uint32_t operand_shift(struct armv2 *cpu, uint32_t bits, uint32_t type_flag, uint32_t *carry);

void flog(char* fmt, ...)
{
    static FILE *f = NULL;
    if(NULL == f) {
        f = fopen("/tmp/armv2.debug.log","wb");
        if(NULL == f) {
            return;
        }
    }
    va_list args;
    va_start(args,fmt);
    vfprintf(f,fmt,args);
    va_end(args);
    fflush(f);
}

uint32_t operand_shift(struct armv2 *cpu, uint32_t bits, uint32_t type_flag, uint32_t *carry)
{
    uint32_t rm = bits&0xf;
    uint32_t shift_type = (bits>>5)&0x3;
    uint32_t shift_amount;
    uint32_t shift_c = 0;
    uint32_t op2;

    if( type_flag ) {
        //shift amount comes from a register
        shift_amount = (GETREG(cpu, (bits >> 8) & 0xf)) & 0xff;
        if( ((bits >> 8) & 0xf) == PC ) {
            shift_amount = (shift_amount + 8) & 0xfc; //The mode bits are not used in rs
        }
    }
    else {
        //shift amount is in the instruction
        shift_amount = (bits >> 7) & 0x1f;
    }
    op2 = GETREG(cpu, rm);

    switch( shift_type ) {
    case ALU_SHIFT_LSL:
        if( shift_amount < 32 ) {
            shift_c = (op2 >> (32 - shift_amount)) & 1;
            op2 <<= shift_amount;
        }
        else if( shift_amount == 32 ) {
            shift_c = op2 & 1;
            op2 = 0;
        }
        else {
            shift_c = op2 = 0;
        }

        break;

    case ALU_SHIFT_LSR:
        if( shift_amount == 0 ) {
            if( type_flag == 0 ) {
                //this means LSR 32
                shift_c = op2 & 0x80000000;
                op2 = 0;
            }
        }
        else if( shift_amount < 32 ) {
            shift_c = (op2 >> (shift_amount - 1)) & 1;
            op2 >>= shift_amount;
        }
        else if( shift_amount == 32 ) {
            shift_c = op2 & 0x80000000;
            op2 = 0;
        }
        else {
            shift_c = op2 = 0;
        }

        break;

    case ALU_SHIFT_ASR:
        if( shift_amount == 0 ) {
            if( type_flag == 0 ) {
                //this means asr 32
                shift_c = (op2 >> 31) & 1;
                op2 = shift_c * 0xffffffff;
            }
        }
        else if( shift_amount < 32 ) {
            shift_c = (op2 >> (shift_amount - 1)) & 1;
            op2 = (uint32_t)(((int32_t)op2) >> shift_amount);
        }
        else {
            shift_c = (shift_amount >> 31) & 1;
            op2 = shift_c * 0xffffffff;
        }
        break;

    case ALU_SHIFT_ROR:
        if( shift_amount > 32 ) {
            //This is not clear to me from the spec. Should this do the same as 32 or as 0? Go with zero for now
            shift_amount &= 0x1f;
        }
        if( shift_amount == 0 ) {
            if( type_flag == 0 ) {
                //this means something weird. RRX
                shift_c = op2 & 1;
                op2 = (op2 >> 1) | (((cpu->regs.actual[PC] >> 29) & 1) << 31);
            }
        }
        else if (shift_amount < 32){
            shift_c = (op2 >> (shift_amount - 1)) & 1;
            op2 = (op2 >> shift_amount) | (op2 << (32 - shift_amount));
        }
        else if (shift_amount == 32) {
            shift_c = op2 & 0x80000000;
        }
        break;
    }
    if( carry ) {
        *carry = shift_c;
    }
    return op2;
}

static enum armv2_status perform_load(struct page_info *page, uint32_t addr, uint32_t *out, int byte) {
    uint32_t value;

    if( NULL == page || NULL == out ) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    if( page->read_callback ) {
        if( byte ) {
            value = page->read_byte_callback(page->mapped_device, INPAGE(addr), 0);
        }
        else {
            value = page->read_callback(page->mapped_device, INPAGE(addr), 0);
        }
    }
    else if( NULL != page->memory ) {
        value = page->memory[INPAGE(addr) >> 2];

        if( byte ) {
            value = (value >> ((addr & 3) << 3)) & 0xff;
        }
    }
    else {
        //No callback and no memory page is an error
        return ARMV2STATUS_INVALID_PAGE;
    }

    //Looks good
    *out = value;
    return ARMV2STATUS_OK;
}

static enum armv2_status perform_store(struct page_info *page, uint32_t addr, uint32_t value, int callback)
{
    if( NULL == page ) {
        return ARMV2STATUS_INVALID_ARGS;
    }
    if( callback && page->write_callback ) {
        page->write_callback(page->mapped_device, INPAGE(addr), value);
    }
    else if( NULL != page->memory ) {
        page->memory[INPAGE(addr) >> 2] = value;
    }
    else {
        //No callback and no memory page is an error
        return ARMV2STATUS_INVALID_PAGE;
    }
    //Looks good
    return ARMV2STATUS_OK;
}

enum armv2_exception alu_instruction(struct armv2 *cpu, uint32_t instruction)
{
    uint32_t opcode   = (instruction>>21)&0xf;
    uint32_t rn       = (instruction>>16)&0xf;
    uint32_t rd       = (instruction>>12)&0xf;
    uint32_t result   = 0;
    uint32_t source_val;
    uint32_t shift_c = (cpu->regs.actual[PC]&FLAG_C);
    uint32_t arith_v = cpu->regs.actual[PC]&FLAG_V;
    uint64_t result64;

    if( instruction & ALU_TYPE_IMM ) {
        uint32_t right_rotate = (instruction >> 7) & 0x1e;
        if( right_rotate != 0 ) {
            source_val = ((instruction & 0xff) << (32 - right_rotate)) | ((instruction & 0xff) >> right_rotate);
        }
        else {
            source_val = instruction & 0xff;
        }
    }
    else {
        source_val = operand_shift(cpu, instruction & 0xfff, instruction & 0x10, &shift_c);
    }
    uint32_t op2;
    uint32_t op1;
    uint32_t carry = (cpu->regs.actual[PC] >> 29) & 1;
    uint32_t rn_val = rn == PC ? GETPC(cpu) : GETREG(cpu,rn);

    switch(opcode) {
    case ALU_OPCODE_AND:
    case ALU_OPCODE_TST:
        result = rn_val & source_val;
        break;

    case ALU_OPCODE_EOR:
    case ALU_OPCODE_TEQ:
        result = rn_val ^ source_val;
        break;

    case ALU_OPCODE_SUB:
    case ALU_OPCODE_CMP:
        op2 = ~source_val;
        op1 = rn_val;
        result64 = ((uint64_t)op1) + op2 + 1;
        result = result64 & 0xffffffff;
        shift_c = result64 >> 32;
        /*      ADDITION SIGN BITS */
        /*    num1sign num2sign sumsign */
        /*   --------------------------- */
        /*        0 0 0 */
        /* *OVER* 0 0 1 (adding two positives should be positive) */
        /*        0 1 0 */
        /*        0 1 1 */
        /*        1 0 0 */
        /*        1 0 1 */
        /* *OVER* 1 1 0 (adding two negatives should be negative) */
        /*        1 1 1 */

        arith_v = (op1 ^ op2 ^ 0x80000000) & (op1 ^ result) & 0x80000000;

        break;
    case ALU_OPCODE_RSB:
        op1 = source_val;
        op2 = ~rn_val;
        result64 = ((uint64_t)op1) + op2 + 1;
        result = result64 & 0xffffffff;
        shift_c = result64 >> 32;
        arith_v = (op1 ^ op2 ^ 0x80000000) & (op1 ^ result) & 0x80000000;
        break;

    case ALU_OPCODE_ADD:
    case ALU_OPCODE_CMN:
        op2 = source_val;
        op1 = rn_val;
        result64 = ((uint64_t)op1) + op2;
        result = result64 & 0xffffffff;
        shift_c = result64 >> 32;
        arith_v = (op1 ^ op2 ^ 0x80000000) & (op1 ^ result) & 0x80000000;
        break;

    case ALU_OPCODE_ADC:
        op1 = rn_val;
        op2 = source_val;
        result64 = ((uint64_t)op1) + op2 + carry;
        result = result64 & 0xffffffff;
        shift_c = result64 >> 32;
        arith_v = (op1 ^ op2 ^ 0x80000000) & (op1 ^ result) & 0x80000000;
        break;

    case ALU_OPCODE_SBC:
        op1 = rn_val;
        op2 = ~source_val;
        result64 = ((uint64_t)op1) + op2 + carry;
        result = result64 & 0xffffffff;
        shift_c = result64 >> 32;
        arith_v = (op1 ^ op2 ^ 0x80000000) & (op1 ^ result) & 0x80000000;
        break;

    case ALU_OPCODE_RSC:
        op1 = ~rn_val;
        op2 = source_val;
        result64 = ((uint64_t)op2) + op1 + carry;
        result = result64 & 0xffffffff;
        shift_c = result64 >> 32;
        arith_v = (result ^ rn_val) & 0x80000000;
        break;

    case ALU_OPCODE_ORR:
        result = rn_val | source_val;
        break;

    case ALU_OPCODE_MOV:
        result = source_val;
        break;

    case ALU_OPCODE_BIC:
        result = rn_val & (~source_val);
        break;

    case ALU_OPCODE_MVN:
        result = ~source_val;
        break;
    }
    if( rd == PC ) {
        if( instruction & ALU_SETS_FLAGS ) {
            //this means we update the whole register, except for prohibited flags in user mode
            if( GETMODE(cpu) == MODE_USR ) {
                cpu->regs.actual[PC] = (cpu->regs.actual[PC] & PC_PROTECTED_BITS)
                    | (result & PC_UNPROTECTED_BITS);
            }
            else {
                cpu->regs.actual[PC] = result;
            }
        }
        else {
            //Only update the PC part
            SETPC(cpu,result);
        }
        cpu->pc = GETPC(cpu)-4;
    }
    else {
        if( instruction&ALU_SETS_FLAGS ) {
            uint32_t n = (result & FLAG_N);
            uint32_t z = result == 0 ? FLAG_Z : 0;
            uint32_t c = shift_c ? FLAG_C : 0;
            uint32_t v = arith_v ? FLAG_V : 0;
            cpu->regs.actual[PC] = (cpu->regs.actual[PC] & 0x0fffffff) | n | z | c | v;
        }
        if( (opcode & 0xc) != 0x8 ) {
            GETREG(cpu,rd) = result;
        }
    }

    return EXCEPT_NONE;
}

enum armv2_exception multiply_instruction(struct armv2 *cpu, uint32_t instruction)
{
    //mul rd,rm,rs means rd = (rm * rs) & 0xffffffff
    //mla rd,rm,rs,rn means rd = (rm * rs + rn) & 0xffffffff
    uint32_t rm = instruction & 0xf;
    uint32_t rn = (instruction >> 12) & 0xf;
    uint32_t rs = (instruction >>  8) & 0xf;
    uint32_t rd = (instruction >> 16) & 0xf;
    uint32_t result;

    if( instruction & MUL_TYPE_MLA ) {
        //using rn so get its value
        rn = GETREG(cpu,rn);
    }
    else {
        rn = 0;
    }

    if( rs == PC ) {
        //GETPC doesn't include the flags
        rs = GETPC(cpu);
    }
    else {
        rs = GETREG(cpu,rs);
    }

    if( rm == PC ) {
        //Apparently it's PC +12 instead of plus 8, whatever
        rm = (GETPC(cpu) + 4) & 0x03fffffc;
    }
    else {
        rm = GETREG(cpu,rm);
    }

    if( rd == 15 ) {
        result = 0;
    }
    else {
        result = (rm * rs + rn) & 0xffffffff;
        GETREG(cpu,rd) = (rm * rs + rn) & 0xffffffff;
    }
    if( instruction&ALU_SETS_FLAGS ) {
        //apparently we set C to a meaningless value! I'll just leave it
        uint32_t n = (result & FLAG_N);
        uint32_t z = result == 0 ? FLAG_Z : 0;
        cpu->regs.actual[PC] = (cpu->regs.actual[PC] & 0x3fffffff) | n | z;
    }

    return EXCEPT_NONE;
}

#define SDT_REGISTER   ALU_TYPE_IMM
#define SDT_PREINDEX   0x01000000
#define SDT_OFFSET_ADD 0x00800000
#define SDT_LOAD_BYTE  0x00400000
#define SDT_WRITE_BACK 0x00200000
#define SDT_LDR        0x00100000

enum armv2_exception single_data_transfer_instruction(struct armv2 *cpu, uint32_t instruction)
{
    //LDR/STR{B}{T} rd,address
    //address is one of:
    //[rn](!)
    //[rn,#imm](!)
    //[rn,Rm](!)
    //[rn,rm <shift> count](!)
    //[rn],#imm
    //[rn],Rm
    //[rn],rm <shift> count
    //First get the value of operand 2
    uint32_t op2;
    uint32_t rd = (instruction >> 12) & 0xf;
    uint32_t rn = (instruction >> 16) & 0xf;
    uint32_t rn_val;
    struct page_info *page;

    if( !(instruction & SDT_REGISTER) ) {
        op2 = instruction & 0xfff;
    }
    else {
        op2 = operand_shift(cpu, instruction & 0xfff, 0, NULL);
    }
    if( rn == PC ) {
        rn_val = GETPC(cpu);
    }
    else {
        rn_val = GETREG(cpu, rn);
    }

    if( instruction & SDT_PREINDEX ) {
        //we do the addition before the lookup
        if( instruction & SDT_OFFSET_ADD ) {
            rn_val += op2;
        }
        else {
            rn_val -= op2;
        }
    }

    //Do the lookup
    if( rn_val & 0xfc000000 ) {
        //The address bus is 26 bits so this is a address exception
        return EXCEPT_ADDRESS;
    }
    page = cpu->page_tables[PAGEOF(rn_val)];
    if( NULL == page ) {
        //This is a data abort. Could also check for permission here
        return EXCEPT_DATA_ABORT;
    }

    //do the load/store
    if( instruction&SDT_LDR ) {
        //LDR
        uint32_t value;
        //must be aligned
        if( rn_val & 0x3 && !(instruction & SDT_LOAD_BYTE) ) {
            return EXCEPT_DATA_ABORT;
        }
        if( GETMODE(cpu) == MODE_USR && !(page->flags & PERM_READ) ) {
            return EXCEPT_DATA_ABORT;
        }

        if( ARMV2STATUS_OK != perform_load(page,rn_val,&value, instruction & SDT_LOAD_BYTE) ) {
            return EXCEPT_DATA_ABORT;
        }

        if( rd == PC ) {
            //don't set any of the flags
            cpu->pc = value - 4;
            SETPC(cpu,value);
        }
        else {
            GETREG(cpu, rd) = value;
        }
    }
    else {
        //STR
        uint32_t value;
        if( GETMODE(cpu) == MODE_USR && !(page->flags & PERM_WRITE) ) {
            return EXCEPT_DATA_ABORT;
        }
        if( rd == PC ) {
            value = ((cpu->pc + 4) & 0x03fffffc) | GETMODEPSR(cpu);
        }
        else {
            value = GETREG(cpu, rd);
        }

        if( instruction & SDT_LOAD_BYTE ) {
            uint32_t byte_mask = 0xff << ((rn_val & 3) << 3);
            uint32_t rest_mask = ~byte_mask;
            uint32_t store_val;

            if( page->write_byte_callback ) {
                page->write_byte_callback(page->mapped_device, INPAGE(rn_val), value & 0xff);
            }
            else {
                if( page->read_byte_callback ) {
                    store_val = page->read_byte_callback(page->mapped_device, INPAGE(rn_val), 0);
                }
                else {
                    store_val = (page->memory[INPAGE(rn_val) >> 2] & rest_mask)
                        | ((value & 0xff) << ((rn_val & 3) << 3));
                }
                (void) perform_store(page, rn_val, store_val, 0);
            }
        }
        else {
            //must be aligned
            if( rn_val & 0x3 ) {
                return EXCEPT_DATA_ABORT;
            }
            (void) perform_store(page, rn_val, value, 1);
        }
    }
    //Now for any post indexing
    if( (instruction & SDT_PREINDEX) == 0 ) {
        if( instruction & SDT_OFFSET_ADD ) {
            rn_val += op2;
        }
        else {
            rn_val -= op2;
        }
    }
    if( (instruction & SDT_PREINDEX) == 0  || instruction & SDT_WRITE_BACK ) {
        if( rn == PC ) {
            cpu->pc = rn_val - 4;
            SETPC(cpu, rn_val);
        }
        else {
            GETREG(cpu, rn) = rn_val;
        }
    }

    return EXCEPT_NONE;
}
enum armv2_exception branch_instruction(struct armv2 *cpu, uint32_t instruction)
{
    if( (instruction >> 24 & 1) ) {
        GETREG(cpu, LR) = cpu->pc + 4;
    }
    cpu->pc = (cpu->pc + 8 + ((instruction & 0xffffff) << 2) - 4) & 0xffffff;
    //+8 due to the weird prefetch thing, -4 for the hack as we're going to add 4 in the next loop

    return EXCEPT_NONE;
}

#define MDT_LDM        SDT_LDR
#define MDT_WRITE_BACK SDT_WRITE_BACK
#define MDT_HAT        SDT_LOAD_BYTE
#define MDT_OFFSET_ADD SDT_OFFSET_ADD
#define MDT_PREINDEX   SDT_PREINDEX

enum armv2_exception multi_data_transfer_instruction(struct armv2 *cpu, uint32_t instruction)
{
    uint32_t rn         = (instruction>>16) & 0xf;
    uint32_t ldm        = instruction & MDT_LDM;
    uint32_t write_back = instruction & MDT_WRITE_BACK;
    uint32_t setflags   = instruction & MDT_HAT;
    uint32_t offset     = instruction & MDT_OFFSET_ADD;
    uint32_t preindex   = instruction & MDT_PREINDEX;
    uint32_t user_bank  = GETMODE(cpu) ? setflags : MDT_HAT;
    uint32_t address;
    uint32_t num_registers = __builtin_popcount(instruction & 0xffff);
    int rs;
    enum armv2_exception retval = EXCEPT_NONE;
    uint32_t write_back_old = 0;
    uint32_t write_back_value = 0;
    uint32_t first_loop = 1;

    if( rn == PC ) {
        //psr bits are used, so that's an exception if the flags aren't set, weird
        address = cpu->pc | GETMODEPSR(cpu);
        write_back = 0;
    }
    else {
        address = GETREG(cpu, rn);
    }

    //the pre/post addressing and offset direction seem a bit weird to me, but here's how I think it affects things
    if( offset == 0 ) {
        address -= (num_registers * 4);
        write_back_value = address;
    }
    else {
        write_back_value = address + (num_registers * 4);
    }
    if( !!preindex == !!offset ) {
        address += 4;
    }
    //Do the lookup
    if( address & 0xfc000000 ) {
        //The address bus is 26 bits so this is a address exception
        //note that only the base address is check for address exception. A write of 2 registers to
        //0x03fffffc will cause the second to be written to (0x04000000 & 0x03ffffff) == 0. Hmmm
        retval = EXCEPT_ADDRESS;
        //we don't return, we're supposed to complete the instruction

    }

    if( write_back ) {
        write_back_old = user_bank ? GETUSERREG(cpu, rn) : GETREG(cpu, rn);
        if( user_bank ) {
            GETUSERREG(cpu,rn) = write_back_value;
        }
        else {
            GETREG(cpu,rn) = write_back_value;
        }
    }
    if( retval != EXCEPT_NONE ) {
        return retval;
    }
    //shitty hack, cancel the increment we're about to do
    address -= 4;
    for(rs = 0; rs < 16; rs++, first_loop = 0) {
        uint32_t value;
        struct page_info *page;
        if( ((instruction >> rs) & 1) == 0 ) {
            continue;
        }
        address += 4;

        page = cpu->page_tables[PAGEOF(address)];
        if( NULL == page ) {
            //This is a data abort. Could also check for permission here
            retval = EXCEPT_DATA_ABORT;
            continue;
        }
        if( address & 0x3 ) {
            retval = EXCEPT_DATA_ABORT;
            continue;
        }
        if( ldm ) {
            //we're loading from memory into registers
            if( GETMODE(cpu) == MODE_USR && !(page->flags & PERM_READ) ) {
                retval = EXCEPT_DATA_ABORT;
                continue;
            }
            if( ARMV2STATUS_OK != perform_load(page, address, &value, 0) ) {
                retval = EXCEPT_DATA_ABORT;
                continue;
            }

            if( rs == PC ) {
                //this means we update the whole register, except for prohibited flags in user mode
                if( GETMODE(cpu) == MODE_USR ) {
                    cpu->regs.actual[PC] = (cpu->regs.actual[PC] & PC_PROTECTED_BITS)
                        | ((value - 4) & PC_UNPROTECTED_BITS);
                }
                else {
                    cpu->regs.actual[PC] = value;
                }
                cpu->pc = GETPC(cpu);
            }
            else {
                if( user_bank ) {
                    GETUSERREG(cpu, rs) = value;
                }
                else {
                    GETREG(cpu, rs) = value;
                }
            }
        }
        else {
            //str
            if( GETMODE(cpu) == MODE_USR && !(page->flags & PERM_WRITE) ) {
                retval = EXCEPT_DATA_ABORT;
                continue;
            }
            if( retval != EXCEPT_NONE ) {
                //stores are prevented after a data abort
                continue;
            }
            if( rs == PC ) {
                value = ((cpu->pc + 4) & 0x03fffffc) | GETMODEPSR(cpu);
            }
            else {
                //slight quirk, if this is the first register we're storing and it's the writeback register, we must
                //use it's old value
                value = user_bank ? GETUSERREG(cpu, rs) : GETREG(cpu, rs);
                if( write_back && first_loop && rs == rn ) {
                    value = write_back_old;
                }
            }
            (void) perform_store(page, address, value, 1);
        }
    }

    return retval;
}


enum armv2_exception swap_instruction(struct armv2 *cpu, uint32_t instruction)
{
    //LOG("%s\n", __func__);
    uint32_t rm   = instruction & 0xf;
    uint32_t rd   = (instruction >> 12) & 0xf;
    uint32_t rn   = (instruction >> 16) & 0xf;
    uint32_t byte = instruction & SDT_LOAD_BYTE;
    uint32_t value;
    struct page_info *page;

    uint32_t address = rn == PC ? (cpu->pc | GETMODEPSR(cpu)) : GETREG(cpu, rn);

    if( address & 0xfc000000 ) {
        //The address bus is 26 bits so this is a address exception
        return EXCEPT_ADDRESS;
    }
    page = cpu->page_tables[PAGEOF(address)];
    if( NULL == page ) {
        //This is a data abort. Could also check for permission here
        return EXCEPT_DATA_ABORT;
    }

    if( address & 0x3 && !byte ) {
        return EXCEPT_DATA_ABORT;
    }

    if( GETMODE(cpu) == MODE_USR && (page->flags & (PERM_READ | PERM_WRITE)) != (PERM_READ | PERM_WRITE) ) {
        return EXCEPT_DATA_ABORT;
    }

    //First load
    if( ARMV2STATUS_OK != perform_load(page, address, &value, 0) ) {
        return EXCEPT_DATA_ABORT;
    }
    if( byte ) {
        value = (value >> ((address & 3) << 3)) & 0xff;
    }

    if( rd == PC ) {
        //don't set any of the flags
        cpu->pc = value - 4;
        SETPC(cpu, value); //the -4 is a hack because we increment on the next loop
    }
    else {
        GETREG(cpu, rd) = value;
    }

    //Now store
    if( rm == PC ) {
        value = ((cpu->pc + 4) & 0x03fffffc) | GETMODEPSR(cpu);
    }
    else {
        value = GETREG(cpu, rm);
    }

    if( byte ) {
        uint32_t byte_mask = 0xff << ((address & 3) << 3);
        uint32_t rest_mask = ~byte_mask;
        value = (page->memory[INPAGE(address)] & rest_mask) | ((value & 0xff) << ((address & 3) << 3));
    }
    else {
        //must be aligned
        if( address & 0x3 ) {
            return EXCEPT_DATA_ABORT;
        }
    }

    (void) perform_store(page, address, value, 1);

    return EXCEPT_NONE;
}

enum armv2_exception software_interrupt_instruction(struct armv2 *cpu, uint32_t instruction)
{
    uint32_t type = instruction & 0x00ffffff;
    return type == SWI_BREAKPOINT ? EXCEPT_BREAKPOINT : EXCEPT_SOFTWARE_INTERRUPT;
}

//Not bothering transfers yet
enum armv2_exception coprocessor_data_transfer_instruction(struct armv2 *cpu, uint32_t instruction)
{
    return EXCEPT_NONE;
}

enum armv2_exception coprocessor_register_transfer_instruction(struct armv2 *cpu, uint32_t instruction)
{
    uint32_t crm      = (instruction >>  0) & 0xf;
    uint32_t aux      = (instruction >>  5) & 0x7;
    uint32_t proc_num = (instruction >>  8) & 0xf;
    uint32_t crd      = (instruction >> 12) & 0xf;
    uint32_t crn      = (instruction >> 16) & 0xf;
    uint32_t opcode   = (instruction >> 20) & 0xf;
    coprocessor_data_operation_t handler = NULL;

    switch(proc_num) {
    case COPROCESSOR_HW_MANAGER:
        handler = hw_manager_register_transfer;
        break;

    case COPROCESSOR_MMU:
        handler = mmu_register_transfer;
        break;

    case COPROCESSOR_INTERRUPT_CONTROLLER:
        handler = interrupt_controller_transfer;

    default:
        handler = NULL;
        break;
    }
    if( handler ) {
        (void) handler(cpu, crm, aux, crd, crn, opcode);
    }
    return EXCEPT_NONE;
}
enum armv2_exception coprocessor_data_operation_instruction(struct armv2 *cpu, uint32_t instruction)
{
    uint32_t crm      = (instruction >>  0) & 0xf;
    uint32_t aux      = (instruction >>  5) & 0x7;
    uint32_t proc_num = (instruction >>  8) & 0xf;
    uint32_t crd      = (instruction >> 12) & 0xf;
    uint32_t crn      = (instruction >> 16) & 0xf;
    uint32_t opcode   = (instruction >> 20) & 0xf;
    coprocessor_data_operation_t handler = NULL;

    switch(proc_num) {
    case COPROCESSOR_HW_MANAGER:
        handler = hw_manager_data_operation;
        break;

    case COPROCESSOR_MMU:
        handler = mmu_data_operation;
        break;

    case COPROCESSOR_INTERRUPT_CONTROLLER:
        handler = interrupt_controller_operation;

    default:
        handler = NULL;
        break;
    }

    if( handler ) {
        (void) handler(cpu, crm, aux, crd, crn, opcode);
    }

    return EXCEPT_NONE;
}
