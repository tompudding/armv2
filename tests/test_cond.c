/* Condition code evaluation: every condition against every combination of
 * NZCV. Each test runs "<cond> MOV r0, #1" with r0 pre-loaded with 0 and
 * checks whether the instruction was executed.
 */
#include "harness.h"
#include "encode.h"

static int cond_should_execute(uint32_t cond, int n, int z, int c, int v)
{
    switch( cond ) {
    case C_EQ: return z;
    case C_NE: return !z;
    case C_CS: return c;
    case C_CC: return !c;
    case C_MI: return n;
    case C_PL: return !n;
    case C_VS: return v;
    case C_VC: return !v;
    case C_HI: return c && !z;
    case C_LS: return !c || z;
    case C_GE: return n == v;
    case C_LT: return n != v;
    case C_GT: return !z && (n == v);
    case C_LE: return z || (n != v);
    case C_AL: return 1;
    case C_NV: return 0;
    default:   return 0;
    }
}

static void check_condition(uint32_t cond)
{
    for( uint32_t flags = 0; flags < 16; flags++ ) {
        int n = (flags >> 3) & 1;
        int z = (flags >> 2) & 1;
        int c = (flags >> 1) & 1;
        int v = (flags >> 0) & 1;
        int expected = cond_should_execute(cond, n, z, c, v);

        t_reset();
        t_setflags_bits(flags);
        t_setreg(0, 0);
        t_context("cond %x flags %s", cond, t_flags());
        t_exec(dp_imm(cond, OP_MOV, 0, 0, 0, 0, 1));

        CHECK_HEX("r0", t_getreg(0), expected ? 1u : 0u);
        /* Whether it ran or not, execution continues at the next word */
        CHECK_PC(CODE_ADDR + 4);
        t_clear_context();
    }
}

TEST(cond_eq) { check_condition(C_EQ); }
TEST(cond_ne) { check_condition(C_NE); }
TEST(cond_cs) { check_condition(C_CS); }
TEST(cond_cc) { check_condition(C_CC); }
TEST(cond_mi) { check_condition(C_MI); }
TEST(cond_pl) { check_condition(C_PL); }
TEST(cond_vs) { check_condition(C_VS); }

/* Known to fail: the COND_VC case in step.c has its break and its continue the
 * wrong way round, so vc executes when V is set */
TEST(cond_vc) { check_condition(C_VC); }

TEST(cond_hi) { check_condition(C_HI); }
TEST(cond_ls) { check_condition(C_LS); }
TEST(cond_ge) { check_condition(C_GE); }
TEST(cond_lt) { check_condition(C_LT); }
TEST(cond_gt) { check_condition(C_GT); }
TEST(cond_le) { check_condition(C_LE); }
TEST(cond_al) { check_condition(C_AL); }
TEST(cond_nv) { check_condition(C_NV); }

/* A skipped instruction must not have any other side effects either */
TEST(cond_skipped_instruction_has_no_side_effects)
{
    t_setflags("nzcv");
    t_setreg(1, 0x1000);
    t_setreg(0, 0xdeadbeef);
    t_write(0x1000, 0x11111111);

    /* streq r0, [r1], #4 -- with Z clear this must not store or write back */
    t_exec(sdt(C_EQ, 0, 0, 1, 0, 0, 0, 1, 0, 4));

    CHECK_MEM(0x1000, 0x11111111);
    CHECK_REG(1, 0x1000);
    CHECK_FLAGS("nzcv");
}
