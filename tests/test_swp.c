/* SWP and SWPB */
#include "harness.h"
#include "encode.h"

TEST(swp_word)
{
    t_write(DATA_ADDR, 0x11111111);
    t_setreg(1, 0x22222222);
    t_setreg(2, DATA_ADDR);

    t_exec(swp(C_AL, 0, 2, 0, 1));          /* swp r0, r1, [r2] */

    CHECK_REG(0, 0x11111111);
    CHECK_MEM(DATA_ADDR, 0x22222222);
    CHECK_REG(1, 0x22222222);
    CHECK_REG(2, DATA_ADDR);
}

/* The usual atomic exchange, where the source and destination are the same.
 *
 * Known to fail: swap_instruction writes rd before it reads rm, so the value
 * it has just loaded is what gets stored back. */
TEST(swp_same_register)
{
    t_write(DATA_ADDR, 0x0000dead);
    t_setreg(0, 0x0000beef);
    t_setreg(2, DATA_ADDR);

    t_exec(swp(C_AL, 0, 2, 0, 0));          /* swp r0, r0, [r2] */

    CHECK_REG(0, 0x0000dead);
    CHECK_MEM(DATA_ADDR, 0x0000beef);
}

TEST(swp_does_not_touch_flags)
{
    t_setflags("NzCv");
    t_write(DATA_ADDR, 1);
    t_setreg(2, DATA_ADDR);
    t_exec(swp(C_AL, 0, 2, 0, 1));
    CHECK_FLAGS("NzCv");
}

TEST(swpb_at_the_start_of_a_page)
{
    t_write(DATA_ADDR, 0x11223344);
    t_setreg(1, 0x000000ff);
    t_setreg(2, DATA_ADDR);

    t_exec(swp(C_AL, 1, 2, 0, 1));          /* swpb r0, r1, [r2] */

    CHECK_REG(0, 0x44);
    CHECK_MEM(DATA_ADDR, 0x112233ff);
}

/* Known to fail: the byte merge in swap_instruction indexes page->memory with
 * the byte offset instead of the word offset, so it merges in a word from
 * further up the page, and reads past the end of the page altogether for byte
 * offsets above 0x400 */
TEST(swpb_elsewhere_in_a_page)
{
    t_write(DATA_ADDR + 0, 0x11223344);
    t_write(DATA_ADDR + 4, 0xaabbccdd);     /* page->memory[1] */
    t_write(DATA_ADDR + 16, 0x99999999);    /* page->memory[4], wrongly used as the merge source */
    t_setreg(1, 0x000000ff);
    t_setreg(2, DATA_ADDR + 4);

    t_exec(swp(C_AL, 1, 2, 0, 1));          /* swpb r0, r1, [r2] */

    CHECK_REG(0, 0xdd);
    CHECK_MEM(DATA_ADDR + 4, 0xaabbccff);
}

TEST(swp_unaligned_aborts)
{
    t_write(DATA_ADDR, 0x11111111);
    t_setreg(1, 0x22222222);
    t_setreg(2, DATA_ADDR + 2);

    t_exec(swp(C_AL, 0, 2, 0, 1));

    CHECK_HEX("exception vector", t_nextpc(), g_vector_table[EXCEPT_DATA_ABORT]);
    CHECK_MEM(DATA_ADDR, 0x11111111);
}

TEST(swp_address_exception)
{
    t_setreg(2, 0x08000000);
    t_exec(swp(C_AL, 0, 2, 0, 1));
    CHECK_HEX("exception vector", t_nextpc(), g_vector_table[EXCEPT_ADDRESS]);
}

/* A swap needs both read and write permission */
TEST(swp_on_read_only_page_aborts_in_user_mode)
{
    t_write(0x40, 0x11111111);
    t_setreg(1, 0x22222222);
    t_setreg(2, 0x40);
    t_setreg(3, (CODE_ADDR + 4) | MODE_USR);

    t_write(CODE_ADDR, MOVS_PC(3));                     /* into user mode */
    t_write(CODE_ADDR + 4, swp(C_AL, 0, 2, 0, 1));      /* swp r0, r1, [r2] */
    t_run(CODE_ADDR, 2);

    CHECK_HEX("exception vector", t_nextpc(), g_vector_table[EXCEPT_DATA_ABORT]);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
    CHECK_MEM(0x40, 0x11111111);
}
