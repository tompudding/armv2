/* MUL and MLA */
#include "harness.h"
#include "encode.h"

/* mul rd, rm, rs */
TEST(mul_basic)
{
    t_setreg(1, 7);
    t_setreg(2, 6);
    t_exec(mul(C_AL, 0, 0, 0, 0, 2, 1));
    CHECK_REG(0, 42);

    /* only the bottom 32 bits of the product are kept */
    t_reset();
    t_setreg(1, 0x10000);
    t_setreg(2, 0x10000);
    t_exec(mul(C_AL, 0, 0, 0, 0, 2, 1));
    CHECK_REG(0, 0);

    t_reset();
    t_setreg(1, 0xfffffffe);   /* -2 */
    t_setreg(2, 3);
    t_exec(mul(C_AL, 0, 0, 0, 0, 2, 1));
    CHECK_REG(0, 0xfffffffa); /* -6 */

    t_reset();
    t_setreg(1, 0xffffffff);
    t_setreg(2, 0xffffffff);
    t_exec(mul(C_AL, 0, 0, 0, 0, 2, 1));
    CHECK_REG(0, 1);
}

/* muls sets N and Z from the result and leaves C and V alone */
TEST(mul_flags)
{
    t_setflags("nzCV");
    t_setreg(1, 7);
    t_setreg(2, 0);
    t_exec(mul(C_AL, 0, 1, 0, 0, 2, 1));
    CHECK_REG(0, 0);
    CHECK_FLAGS("nZCV");

    t_reset();
    t_setflags("nZcv");
    t_setreg(1, 0xffffffff);
    t_setreg(2, 2);
    t_exec(mul(C_AL, 0, 1, 0, 0, 2, 1));
    CHECK_REG(0, 0xfffffffe);
    CHECK_FLAGS("Nzcv");

    /* without the S bit nothing changes */
    t_reset();
    t_setflags("NZCV");
    t_setreg(1, 2);
    t_setreg(2, 3);
    t_exec(mul(C_AL, 0, 0, 0, 0, 2, 1));
    CHECK_REG(0, 6);
    CHECK_FLAGS("NZCV");
}

/* mla rd, rm, rs, rn */
TEST(mla_basic)
{
    t_setreg(1, 7);
    t_setreg(2, 6);
    t_setreg(3, 3);
    t_exec(mul(C_AL, 1, 0, 0, 3, 2, 1));
    CHECK_REG(0, 45);

    t_reset();
    t_setreg(1, 5);
    t_setreg(2, 0);
    t_setreg(3, 0xffffffff);
    t_exec(mul(C_AL, 1, 1, 0, 3, 2, 1));
    CHECK_REG(0, 0xffffffff);
    CHECK_FLAGS("Nzcv");
}

/* r15 as rs reads as the address of the instruction plus 8 with the psr bits
 * masked off, and as rm as the address plus 12 */
TEST(mul_with_pc_operands)
{
    t_setflags("NZCVI");
    t_setreg(1, 1);
    t_exec(mul(C_AL, 0, 0, 0, 0, R_PC, 1));   /* mul r0, r1, pc */
    CHECK_REG(0, CODE_ADDR + 8);

    t_reset();
    t_setflags("NZCVI");
    t_setreg(2, 1);
    t_exec(mul(C_AL, 0, 0, 0, 0, 2, R_PC));   /* mul r0, pc, r2 */
    CHECK_REG(0, CODE_ADDR + 12);
}

/* r15 as the destination is not allowed; the emulator throws the result away
 * and leaves the pc alone */
TEST(mul_to_pc_is_ignored)
{
    t_setreg(1, 7);
    t_setreg(2, 6);
    t_exec(mul(C_AL, 0, 0, R_PC, 0, 2, 1));
    CHECK_PC(CODE_ADDR + 4);
}
