/* LDM and STM: the four addressing modes, write back, the psr/user bank bit
 * and the aborts.
 *
 * In every mode the lowest numbered register ends up at the lowest address.
 */
#include "harness.h"
#include "encode.h"

#define REG(n) (1u << (n))

TEST(stmia_stores_upwards)
{
    t_setreg(0, 0xaaaaaaaa);
    t_setreg(2, 0xbbbbbbbb);
    t_setreg(3, 0xcccccccc);
    t_setreg(1, DATA_ADDR);

    /* stmia r1!, {r0, r2, r3} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 0, 1, REG(0) | REG(2) | REG(3)));

    CHECK_MEM(DATA_ADDR + 0, 0xaaaaaaaa);
    CHECK_MEM(DATA_ADDR + 4, 0xbbbbbbbb);
    CHECK_MEM(DATA_ADDR + 8, 0xcccccccc);
    CHECK_REG(1, DATA_ADDR + 12);
}

TEST(stmib_stores_above_the_base)
{
    t_write(DATA_ADDR, 0x99999999);
    t_setreg(0, 0xaaaaaaaa);
    t_setreg(2, 0xbbbbbbbb);
    t_setreg(1, DATA_ADDR);

    /* stmib r1, {r0, r2} */
    t_exec(mdt(C_AL, 1, 1, 0, 0, 0, 1, REG(0) | REG(2)));

    CHECK_MEM(DATA_ADDR + 0, 0x99999999);
    CHECK_MEM(DATA_ADDR + 4, 0xaaaaaaaa);
    CHECK_MEM(DATA_ADDR + 8, 0xbbbbbbbb);
    CHECK_REG(1, DATA_ADDR);
}

TEST(stmda_stores_downwards)
{
    t_setreg(0, 0xaaaaaaaa);
    t_setreg(2, 0xbbbbbbbb);
    t_setreg(1, DATA_ADDR);

    /* stmda r1!, {r0, r2} */
    t_exec(mdt(C_AL, 0, 0, 0, 1, 0, 1, REG(0) | REG(2)));

    CHECK_MEM(DATA_ADDR - 4, 0xaaaaaaaa);
    CHECK_MEM(DATA_ADDR - 0, 0xbbbbbbbb);
    CHECK_REG(1, DATA_ADDR - 8);
}

TEST(stmdb_stores_below_the_base)
{
    t_setreg(0, 0xaaaaaaaa);
    t_setreg(2, 0xbbbbbbbb);
    t_setreg(1, DATA_ADDR);

    /* stmdb r1!, {r0, r2}, i.e. the usual "push" */
    t_exec(mdt(C_AL, 1, 0, 0, 1, 0, 1, REG(0) | REG(2)));

    CHECK_MEM(DATA_ADDR - 8, 0xaaaaaaaa);
    CHECK_MEM(DATA_ADDR - 4, 0xbbbbbbbb);
    CHECK_MEM(DATA_ADDR, 0);
    CHECK_REG(1, DATA_ADDR - 8);
}

TEST(ldmia_loads_upwards)
{
    t_write(DATA_ADDR + 0, 0x11111111);
    t_write(DATA_ADDR + 4, 0x22222222);
    t_write(DATA_ADDR + 8, 0x33333333);
    t_setreg(1, DATA_ADDR);

    /* ldmia r1!, {r0, r2, r3} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 1, 1, REG(0) | REG(2) | REG(3)));

    CHECK_REG(0, 0x11111111);
    CHECK_REG(2, 0x22222222);
    CHECK_REG(3, 0x33333333);
    CHECK_REG(1, DATA_ADDR + 12);
}

TEST(ldmdb_loads_below_the_base)
{
    t_write(DATA_ADDR - 8, 0x11111111);
    t_write(DATA_ADDR - 4, 0x22222222);
    t_setreg(1, DATA_ADDR);

    /* ldmdb r1!, {r0, r2} */
    t_exec(mdt(C_AL, 1, 0, 0, 1, 1, 1, REG(0) | REG(2)));

    CHECK_REG(0, 0x11111111);
    CHECK_REG(2, 0x22222222);
    CHECK_REG(1, DATA_ADDR - 8);
}

/* push/pop round trip */
TEST(stmdb_ldmia_round_trip)
{
    t_setreg(0, 0x0badf00d);
    t_setreg(4, 0x0000face);
    t_setreg(9, 0x00c0ffee);
    t_setreg(1, DATA_ADDR);

    t_write(CODE_ADDR + 0, mdt(C_AL, 1, 0, 0, 1, 0, 1, REG(0) | REG(4) | REG(9)));  /* push */
    t_write(CODE_ADDR + 4, MOV_IMM(0, 0));
    t_write(CODE_ADDR + 8, MOV_IMM(4, 0));
    t_write(CODE_ADDR + 12, MOV_IMM(9, 0));
    t_write(CODE_ADDR + 16, mdt(C_AL, 0, 1, 0, 1, 1, 1, REG(0) | REG(4) | REG(9))); /* pop */
    t_run(CODE_ADDR, 5);

    CHECK_REG(0, 0x0badf00d);
    CHECK_REG(4, 0x0000face);
    CHECK_REG(9, 0x00c0ffee);
    CHECK_REG(1, DATA_ADDR);
}

/* The register list is a bit mask, so the order registers are written in the
 * assembler source makes no difference */
TEST(register_list_order_is_by_register_number)
{
    t_setreg(1, DATA_ADDR);
    t_setreg(5, 0x55555555);
    t_setreg(12, 0xcccccccc);
    t_setreg(0, 0x00000000);

    /* stmia r1, {r12, r5, r0} */
    t_exec(mdt(C_AL, 0, 1, 0, 0, 0, 1, REG(12) | REG(5) | REG(0)));

    CHECK_MEM(DATA_ADDR + 0, 0x00000000);
    CHECK_MEM(DATA_ADDR + 4, 0x55555555);
    CHECK_MEM(DATA_ADDR + 8, 0xcccccccc);
}

/* When the write back register is the first one stored, the value written to
 * memory is its old value.
 *
 * Known to fail for the r1 case: the "is this the first register" flag is
 * cleared by the transfer loop's increment even for registers that are not in
 * the list, so the old base value is only stored when the base is r0. */
TEST(stm_with_base_first_in_list_stores_old_base)
{
    t_setreg(0, DATA_ADDR);
    t_setreg(2, 0x22222222);

    /* stmia r0!, {r0, r2} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 0, 0, REG(0) | REG(2)));

    CHECK_MEM(DATA_ADDR + 0, DATA_ADDR);
    CHECK_MEM(DATA_ADDR + 4, 0x22222222);
    CHECK_REG(0, DATA_ADDR + 8);

    t_reset();
    t_setreg(1, DATA_ADDR);
    t_setreg(2, 0x22222222);

    /* stmia r1!, {r1, r2} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 0, 1, REG(1) | REG(2)));

    CHECK_MEM(DATA_ADDR + 0, DATA_ADDR);
    CHECK_MEM(DATA_ADDR + 4, 0x22222222);
    CHECK_REG(1, DATA_ADDR + 8);
}

/* If it is not the first, the written back value is stored instead. The ARM2
 * datasheet says this case is unpredictable, so this test is just recording
 * what the emulator does. */
TEST(stm_with_base_later_in_list_stores_new_base)
{
    t_setreg(0, 0x11111111);
    t_setreg(1, DATA_ADDR);

    /* stmia r1!, {r0, r1} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 0, 1, REG(0) | REG(1)));

    CHECK_MEM(DATA_ADDR + 0, 0x11111111);
    CHECK_MEM(DATA_ADDR + 4, DATA_ADDR + 8);
    CHECK_REG(1, DATA_ADDR + 8);
}

/* Loading the base register overwrites the written back value */
TEST(ldm_of_base_register_wins_over_write_back)
{
    t_write(DATA_ADDR, 0x0000abcd);
    t_setreg(1, DATA_ADDR);

    /* ldmia r1!, {r1} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 1, 1, REG(1)));

    CHECK_REG(1, 0x0000abcd);
}

/* Storing r15 stores the address of the instruction plus 4 with the psr bits,
 * to match str (see test_ldrstr.c) */
TEST(stm_of_pc)
{
    t_setflags("NzCvI");
    t_setreg(1, DATA_ADDR);

    /* stmia r1, {r0, pc} */
    t_exec(mdt(C_AL, 0, 1, 0, 0, 0, 1, REG(0) | REG(15)));

    CHECK_MEM(DATA_ADDR + 4, (CODE_ADDR + 4) | FLAG_N | FLAG_C | FLAG_I | MODE_SUP);
}

/* With the S bit set, a transfer that does not include r15 uses the user mode
 * bank rather than the current one */
TEST(ldm_with_psr_bit_uses_user_bank)
{
    t_setactual(13, 0x0);                /* user r13 */
    t_setactual(R13_S, 0xdeadbeef);      /* supervisor r13 */
    t_write(DATA_ADDR, 0x00001234);
    t_setreg(1, DATA_ADDR);

    /* ldmia r1, {r13}^ */
    t_exec(mdt(C_AL, 0, 1, 1, 0, 1, 1, REG(13)));

    CHECK_HEX("user r13", t_getactual(13), 0x00001234);
    CHECK_HEX("supervisor r13", t_getactual(R13_S), 0xdeadbeef);
}

TEST(ldm_without_psr_bit_uses_current_bank)
{
    t_setactual(13, 0x0);
    t_setactual(R13_S, 0xdeadbeef);
    t_write(DATA_ADDR, 0x00001234);
    t_setreg(1, DATA_ADDR);

    /* ldmia r1, {r13} */
    t_exec(mdt(C_AL, 0, 1, 0, 0, 1, 1, REG(13)));

    CHECK_HEX("user r13", t_getactual(13), 0);
    CHECK_HEX("supervisor r13", t_getactual(R13_S), 0x00001234);
}

TEST(stm_with_psr_bit_uses_user_bank)
{
    t_setactual(13, 0x11112222);
    t_setactual(R13_S, 0xdeadbeef);
    t_setreg(1, DATA_ADDR);

    /* stmia r1, {r13}^ */
    t_exec(mdt(C_AL, 0, 1, 1, 0, 0, 1, REG(13)));

    CHECK_MEM(DATA_ADDR, 0x11112222);
}

/* Known to fail: multi_data_transfer_instruction sets cpu->pc to the loaded
 * address, where every other write to the pc sets it to the address minus four
 * to allow for the increment at the top of the run loop, so execution resumes
 * one instruction late */
TEST(ldm_into_pc_returns_to_the_loaded_address)
{
    t_write(DATA_ADDR, 0x00000300);
    t_setreg(1, DATA_ADDR);

    /* ldmia r1!, {pc} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 1, 1, REG(15)));

    CHECK_PC(0x300);
}

/* Only an ldm with the S bit set restores the psr; without it just the pc part
 * of r15 is written.
 *
 * Known to fail: the loaded word is written over the whole of r15 either way,
 * so an ordinary return clears the flags and drops into user mode. */
TEST(ldm_into_pc_without_psr_bit_keeps_the_psr)
{
    t_write(DATA_ADDR, 0x00000300);
    t_setflags("NzCvI");
    t_setreg(1, DATA_ADDR);

    /* ldmia r1!, {pc} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 1, 1, REG(15)));

    CHECK_FLAGS("NzCv");
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
}

TEST(ldmstm_address_exception)
{
    t_setreg(0, 0x11111111);
    t_setreg(1, 0x04000000);

    /* stmia r1!, {r0, r2} */
    t_exec(mdt(C_AL, 0, 1, 0, 1, 0, 1, REG(0) | REG(2)));

    CHECK_HEX("exception vector", t_nextpc(), g_vector_table[EXCEPT_ADDRESS]);
    /* the base is still written back before the exception is taken */
    CHECK_REG(1, 0x04000008);
}

TEST(ldmstm_unaligned_base_aborts)
{
    t_write(DATA_ADDR, 0x11111111);
    t_setreg(0, 0xdeadbeef);
    t_setreg(1, DATA_ADDR + 2);

    /* ldmia r1, {r0} */
    t_exec(mdt(C_AL, 0, 1, 0, 0, 1, 1, REG(0)));

    CHECK_HEX("exception vector", t_nextpc(), g_vector_table[EXCEPT_DATA_ABORT]);
    CHECK_REG(0, 0xdeadbeef);
}
