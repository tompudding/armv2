/* LDR and STR, including addressing modes, byte transfers and the aborts */
#include "harness.h"
#include "encode.h"

static void check_exception(uint32_t vector)
{
    CHECK_HEX("exception vector", t_nextpc(), vector);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
    CHECK_HEX("saved pc", t_getactual(LR_S) & 0x03fffffc, CODE_ADDR + 8);
}

TEST(str_ldr_word_with_immediate_offset)
{
    t_setreg(0, 0x12345678);
    t_setreg(1, DATA_ADDR);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 4));       /* str r0, [r1, #4] */
    CHECK_MEM(DATA_ADDR + 4, 0x12345678);
    CHECK_REG(1, DATA_ADDR);                             /* no writeback */

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 2, 4));       /* ldr r2, [r1, #4] */
    CHECK_REG(2, 0x12345678);
    CHECK_REG(1, DATA_ADDR);
}

TEST(str_ldr_with_no_offset)
{
    t_setreg(0, 0xcafebabe);
    t_setreg(1, DATA_ADDR);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));       /* str r0, [r1] */
    CHECK_MEM(DATA_ADDR, 0xcafebabe);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 3, 0));       /* ldr r3, [r1] */
    CHECK_REG(3, 0xcafebabe);
}

TEST(ldr_with_negative_offset)
{
    t_write(DATA_ADDR - 4, 0x11223344);
    t_setreg(1, DATA_ADDR);

    t_exec(sdt(C_AL, 0, 1, 0, 0, 0, 1, 1, 0, 4));       /* ldr r0, [r1, #-4] */
    CHECK_REG(0, 0x11223344);
    CHECK_REG(1, DATA_ADDR);
}

TEST(ldr_preindexed_with_writeback)
{
    t_write(DATA_ADDR + 8, 0xaabbccdd);
    t_setreg(1, DATA_ADDR);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 1, 1, 1, 0, 8));       /* ldr r0, [r1, #8]! */
    CHECK_REG(0, 0xaabbccdd);
    CHECK_REG(1, DATA_ADDR + 8);
}

/* Post indexed transfers always write the base register back */
TEST(ldr_postindexed)
{
    t_write(DATA_ADDR, 0x55667788);
    t_setreg(1, DATA_ADDR);

    t_exec(sdt(C_AL, 0, 0, 1, 0, 0, 1, 1, 0, 4));       /* ldr r0, [r1], #4 */
    CHECK_REG(0, 0x55667788);
    CHECK_REG(1, DATA_ADDR + 4);

    t_reset();
    t_write(DATA_ADDR, 0x55667788);
    t_setreg(1, DATA_ADDR);
    t_exec(sdt(C_AL, 0, 0, 0, 0, 0, 1, 1, 0, 4));       /* ldr r0, [r1], #-4 */
    CHECK_REG(0, 0x55667788);
    CHECK_REG(1, DATA_ADDR - 4);
}

TEST(str_postindexed)
{
    t_setreg(0, 0x0f0f0f0f);
    t_setreg(1, DATA_ADDR);

    t_exec(sdt(C_AL, 0, 0, 1, 0, 0, 0, 1, 0, 4));       /* str r0, [r1], #4 */
    CHECK_MEM(DATA_ADDR, 0x0f0f0f0f);
    CHECK_REG(1, DATA_ADDR + 4);
}

TEST(ldr_with_register_offset)
{
    t_write(DATA_ADDR + 16, 0xdeadbeef);
    t_setreg(1, DATA_ADDR);
    t_setreg(2, 16);

    t_exec(sdt(C_AL, 1, 1, 1, 0, 0, 1, 1, 0, sdt_offset_reg(2, SH_LSL, 0)));   /* ldr r0, [r1, r2] */
    CHECK_REG(0, 0xdeadbeef);

    /* ldr r0, [r1, r2, lsl #2] */
    t_reset();
    t_write(DATA_ADDR + 16, 0xdeadbeef);
    t_setreg(1, DATA_ADDR);
    t_setreg(2, 4);
    t_exec(sdt(C_AL, 1, 1, 1, 0, 0, 1, 1, 0, sdt_offset_reg(2, SH_LSL, 2)));
    CHECK_REG(0, 0xdeadbeef);

    /* a register offset can be subtracted too */
    t_reset();
    t_write(DATA_ADDR - 16, 0x12341234);
    t_setreg(1, DATA_ADDR);
    t_setreg(2, 16);
    t_exec(sdt(C_AL, 1, 1, 0, 0, 0, 1, 1, 0, sdt_offset_reg(2, SH_LSL, 0)));
    CHECK_REG(0, 0x12341234);
}

/* A register offset never updates the flags, even though it goes through the
 * barrel shifter */
TEST(ldr_register_offset_does_not_set_flags)
{
    t_setflags("nzcv");
    t_setreg(1, DATA_ADDR);
    t_setreg(2, 5);         /* bit 0 set, which is what lsl #0 would put in C */
    t_exec(sdt(C_AL, 1, 1, 1, 0, 0, 1, 1, 0, sdt_offset_reg(2, SH_LSL, 0)));
    CHECK_FLAGS("nzcv");
}

TEST(ldrb_reads_the_addressed_byte)
{
    t_write(DATA_ADDR, 0xddccbbaa);
    t_setreg(1, DATA_ADDR);

    for( uint32_t i = 0; i < 4; i++ ) {
        t_context("byte %u", i);
        t_exec(sdt(C_AL, 0, 1, 1, 1, 0, 1, 1, 0, i));   /* ldrb r0, [r1, #i] */
        CHECK_HEX("r0", t_getreg(0), (0xddccbbaa >> (i * 8)) & 0xff);
        t_clear_context();
    }
}

TEST(strb_only_writes_the_addressed_byte)
{
    for( uint32_t i = 0; i < 4; i++ ) {
        static const uint32_t expected[4] = {0x11223399, 0x11229944, 0x11993344, 0x99223344};

        t_reset();
        t_write(DATA_ADDR, 0x11223344);
        t_setreg(0, 0xabcd99);
        t_setreg(1, DATA_ADDR);
        t_context("byte %u", i);

        t_exec(sdt(C_AL, 0, 1, 1, 1, 0, 0, 1, 0, i));   /* strb r0, [r1, #i] */
        CHECK_HEX("word", t_read(DATA_ADDR), expected[i]);
        t_clear_context();
    }
}

/* Loading into r15 branches, and does not touch the flags */
TEST(ldr_into_pc)
{
    t_write(DATA_ADDR, 0x00000300);
    t_setflags("NzCv");
    t_setreg(1, DATA_ADDR);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, R_PC, 0));    /* ldr pc, [r1] */
    CHECK_PC(0x300);
    CHECK_FLAGS("NzCv");
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
}

/* r15 as the base register reads as the address of the instruction plus 8,
 * which is how pc relative literal loads work */
TEST(ldr_pc_relative)
{
    t_write(CODE_ADDR + 12, 0x5a5a5a5a);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, R_PC, 0, 4));    /* ldr r0, [pc, #4] */
    CHECK_REG(0, 0x5a5a5a5a);
}

/* Storing r15 stores the address of the instruction plus 4 along with the psr
 * bits. A real ARM2 stores the address plus 12; boot.S is written to match
 * what the emulator does here (see the comment in handle_error). */
TEST(str_of_pc)
{
    t_setflags("NzCvI");
    t_setreg(1, DATA_ADDR);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, R_PC, 0));    /* str pc, [r1] */

    CHECK_MEM(DATA_ADDR, (CODE_ADDR + 4) | FLAG_N | FLAG_C | FLAG_I | MODE_SUP);
}

/* Unaligned word transfers abort. A real ARM2 rotates the loaded word
 * instead, but nothing in the machine relies on that. */
TEST(unaligned_word_transfers_abort)
{
    t_setreg(1, DATA_ADDR + 2);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));       /* ldr r0, [r1] */
    check_exception(0x10);

    t_reset();
    t_write(DATA_ADDR, 0x11111111);
    t_setreg(0, 0x22222222);
    t_setreg(1, DATA_ADDR + 1);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));       /* str r0, [r1] */
    check_exception(0x10);
    CHECK_MEM(DATA_ADDR, 0x11111111);
}

/* An aborted transfer does not write the base register back */
TEST(aborted_transfer_does_not_write_back)
{
    t_setreg(1, DATA_ADDR + 2);
    t_exec(sdt(C_AL, 0, 0, 1, 0, 0, 1, 1, 0, 4));       /* ldr r0, [r1], #4 */
    check_exception(0x10);
    CHECK_REG(1, DATA_ADDR + 2);
}

/* Byte transfers have no alignment requirement */
TEST(unaligned_byte_transfers_are_fine)
{
    t_write(DATA_ADDR, 0x11223344);
    t_setreg(1, DATA_ADDR + 1);
    t_exec(sdt(C_AL, 0, 1, 1, 1, 0, 1, 1, 0, 0));       /* ldrb r0, [r1] */
    CHECK_REG(0, 0x33);
    CHECK_PC(CODE_ADDR + 4);
}

/* The address bus is 26 bits wide, anything above that is an address
 * exception */
TEST(address_exception_above_64mb)
{
    t_setreg(1, 0x04000000);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));       /* ldr r0, [r1] */
    check_exception(0x14);

    t_reset();
    t_setreg(0, 0x11111111);
    t_setreg(1, 0xfffffffc);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));       /* str r0, [r1] */
    check_exception(0x14);
}

/* Pages are faulted in on demand, until the machine runs out of memory */
TEST(data_abort_when_out_of_memory)
{
    t_reset_ram(2 * PAGE_SIZE);                          /* only the code and data pages fit */
    t_setreg(1, 0x00400000);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));       /* ldr r0, [r1] */
    check_exception(0x10);
}

/* Page zero holds the boot rom and is never writable, which user mode code
 * finds out about the hard way */
TEST(user_mode_write_to_read_only_page_aborts)
{
    t_setmode(MODE_USR);
    t_setreg(0, 0x12345678);
    t_setreg(1, 0x40);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));       /* str r0, [r1] */

    CHECK_HEX("exception vector", t_nextpc(), 0x10);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
    CHECK_MEM(0x40, 0);

    /* reading it is fine */
    t_reset();
    t_write(0x40, 0x99887766);
    t_setmode(MODE_USR);
    t_setreg(1, 0x40);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));       /* ldr r0, [r1] */
    CHECK_REG(0, 0x99887766);
    CHECK_HEX("mode", t_getmode(), MODE_USR);
}

/* Page zero holds the boot rom, so it must come out read only whichever
 * address in it is touched first.
 *
 * Known to fail: fault() compares the faulting address with zero rather than
 * the page number. */
TEST(page_zero_is_read_only_however_it_is_faulted_in)
{
    t_unmap(0);
    t_fault(CODE_ADDR);          /* fault page zero in via an address inside it */

    t_setmode(MODE_USR);
    t_setreg(0, 0x12345678);
    t_setreg(1, 0x40);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));       /* str r0, [r1] */

    CHECK_HEX("exception vector", t_nextpc(), 0x10);
    CHECK_MEM(0x40, 0);
}

/* Supervisor mode ignores the page permissions */
TEST(supervisor_mode_write_to_read_only_page_is_allowed)
{
    t_setreg(0, 0x12345678);
    t_setreg(1, 0x40);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));       /* str r0, [r1] */

    CHECK_PC(CODE_ADDR + 4);
    CHECK_MEM(0x40, 0x12345678);
}
