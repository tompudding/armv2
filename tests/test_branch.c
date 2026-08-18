/* B and BL */
#include "harness.h"
#include "encode.h"

TEST(branch_forwards)
{
    t_exec(branch(C_AL, 0, CODE_ADDR, CODE_ADDR + 0x40));
    CHECK_PC(CODE_ADDR + 0x40);
}

TEST(branch_backwards)
{
    t_exec_at(0x800, branch(C_AL, 0, 0x800, 0x100));
    CHECK_PC(0x100);
}

TEST(branch_to_itself)
{
    t_exec(branch(C_AL, 0, CODE_ADDR, CODE_ADDR));
    CHECK_PC(CODE_ADDR);
}

TEST(branch_executes_at_target)
{
    t_write(CODE_ADDR, branch(C_AL, 0, CODE_ADDR, CODE_ADDR + 0x20));
    t_write(CODE_ADDR + 4, MOV_IMM(0, 1));               /* skipped */
    t_write(CODE_ADDR + 0x20, MOV_IMM(0, 42));
    t_run(CODE_ADDR, 2);

    CHECK_REG(0, 42);
    CHECK_PC(CODE_ADDR + 0x24);
}

TEST(branch_does_not_touch_flags_or_registers)
{
    t_setflags("NzCv");
    t_setreg(R_LR, 0x12345678);
    t_exec(branch(C_AL, 0, CODE_ADDR, CODE_ADDR + 8));

    CHECK_FLAGS("NzCv");
    CHECK_HEX("lr", t_getreg(R_LR), 0x12345678);
}

TEST(branch_not_taken)
{
    t_setflags("nzcv");
    t_exec(branch(C_EQ, 0, CODE_ADDR, CODE_ADDR + 0x40));
    CHECK_PC(CODE_ADDR + 4);
}

TEST(branch_taken_conditionally)
{
    t_setflags("nZcv");
    t_exec(branch(C_EQ, 0, CODE_ADDR, CODE_ADDR + 0x40));
    CHECK_PC(CODE_ADDR + 0x40);
}

/* bl puts the address of the following instruction in r14 */
TEST(branch_with_link_sets_lr)
{
    t_exec(branch(C_AL, 1, CODE_ADDR, CODE_ADDR + 0x40));
    CHECK_PC(CODE_ADDR + 0x40);
    CHECK_HEX("lr", t_getreg(R_LR) & 0x03fffffc, CODE_ADDR + 4);
}

TEST(branch_with_link_and_return)
{
    t_write(CODE_ADDR, branch(C_AL, 1, CODE_ADDR, CODE_ADDR + 0x40));
    t_write(CODE_ADDR + 0x40, MOV_IMM(0, 42));
    t_write(CODE_ADDR + 0x44, MOV_REG(R_PC, R_LR));      /* mov pc, lr */
    t_write(CODE_ADDR + 4, MOV_IMM(1, 7));
    t_run(CODE_ADDR, 4);

    CHECK_REG(0, 42);
    CHECK_REG(1, 7);
    CHECK_PC(CODE_ADDR + 8);
}

/* bl uses the current bank of r14, so a subroutine called from supervisor
 * mode does not clobber the user mode link register */
TEST(branch_with_link_uses_banked_lr)
{
    t_setactual(R_LR, 0xcafebabe);       /* the user mode r14 */
    t_exec(branch(C_AL, 1, CODE_ADDR, CODE_ADDR + 0x40));

    CHECK_HEX("user r14", t_getactual(R_LR), 0xcafebabe);
    CHECK_HEX("supervisor r14", t_getactual(LR_S) & 0x03fffffc, CODE_ADDR + 4);
}

/* bl saves the psr in r14 along with the return address, so that a subroutine
 * can return with "movs pc, lr" and restore the flags its caller had. */
TEST(branch_with_link_saves_psr_in_lr)
{
    t_setflags("NzCvI");
    t_exec(branch(C_AL, 1, CODE_ADDR, CODE_ADDR + 0x40));
    CHECK_HEX("lr", t_getreg(R_LR), (CODE_ADDR + 4) | FLAG_N | FLAG_C | FLAG_I | MODE_SUP);
}

/* The address bus is 26 bits, so a branch has to work anywhere in it.
 *
 * Known to fail: branch_instruction masks the new pc with 0xffffff rather than
 * 0x3ffffff, so branches wrap round at 16MB. */
TEST(branch_above_16mb)
{
    t_map(0x01000000);
    t_exec_at(0x01000100, branch(C_AL, 0, 0x01000100, 0x01000200));
    CHECK_PC(0x01000200);
}
