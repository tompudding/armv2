/* Data processing instructions: results and the NZCV flags.
 *
 * Logical operations are tested with an immediate operand 2 because a register
 * operand goes through the barrel shifter, whose carry out is what ends up in
 * C (see test_shift.c).
 */
#include "harness.h"
#include "encode.h"

struct alu_case {
    uint32_t    rn;      /* value put in r1 */
    uint32_t    op2;     /* value put in r2, or the immediate */
    const char *before;  /* flags before the instruction */
    uint32_t    result;  /* expected r0 */
    const char *after;   /* expected flags */
};

#define CASES(x) (x), sizeof(x) / sizeof((x)[0])

/* <op>s r0, r1, r2 */
static void run_reg_cases(uint32_t opcode, const char *name, const struct alu_case *cases, size_t n)
{
    for( size_t i = 0; i < n; i++ ) {
        t_reset();
        t_setflags(cases[i].before);
        t_setreg(0, 0xdeadbeef);
        t_setreg(1, cases[i].rn);
        t_setreg(2, cases[i].op2);
        t_context("%s r0, 0x%08x, 0x%08x with flags %s", name, cases[i].rn, cases[i].op2, cases[i].before);

        t_exec(dp_reg(C_AL, opcode, 1, 1, 0, 2, SH_LSL, 0));

        CHECK_HEX("r0", t_getreg(0), cases[i].result);
        CHECK_FLAGS(cases[i].after);
        t_clear_context();
    }
}

/* <op>s r0, r1, #imm  (imm must fit in 8 bits) */
static void run_imm_cases(uint32_t opcode, const char *name, const struct alu_case *cases, size_t n)
{
    for( size_t i = 0; i < n; i++ ) {
        t_reset();
        t_setflags(cases[i].before);
        t_setreg(0, 0xdeadbeef);
        t_setreg(1, cases[i].rn);
        t_context("%s r0, 0x%08x, #0x%02x with flags %s", name, cases[i].rn, cases[i].op2, cases[i].before);

        t_exec(dp_imm(C_AL, opcode, 1, 1, 0, 0, cases[i].op2));

        CHECK_HEX("r0", t_getreg(0), cases[i].result);
        CHECK_FLAGS(cases[i].after);
        t_clear_context();
    }
}

TEST(alu_and)
{
    static const struct alu_case cases[] = {
        {0xff00ff0f, 0x0f, "nzcv", 0x0000000f, "nzcv"},
        {0x000000f0, 0x0f, "nzCv", 0x00000000, "nZCv"},
        {0x800000ff, 0xf0, "nzcv", 0x000000f0, "nzcv"},
        /* C and V are not touched by logical operations */
        {0x000000ff, 0x00, "NZCV", 0x00000000, "nZCV"},
    };
    run_imm_cases(OP_AND, "ands", CASES(cases));

    /* ands r0, r1, #0x80000000 (0x02 rotated right by 2) sets N */
    t_reset();
    t_setflags("nzcv");
    t_setreg(1, 0x800000ff);
    t_exec(dp_imm(C_AL, OP_AND, 1, 1, 0, 1, 0x02));
    CHECK_REG(0, 0x80000000);
    CHECK_FLAGS("Nzcv");

    /* and r0, r1, r2 without the S bit leaves the flags alone */
    t_reset();
    t_setflags("NZCV");
    t_setreg(1, 0xff00ff00);
    t_setreg(2, 0x0f0f0f0f);
    t_exec(dp_reg(C_AL, OP_AND, 0, 1, 0, 2, SH_LSL, 0));
    CHECK_REG(0, 0x0f000f00);
    CHECK_FLAGS("NZCV");
}

TEST(alu_eor)
{
    static const struct alu_case cases[] = {
        {0x000000ff, 0x0f, "nzcv", 0x000000f0, "nzcv"},
        {0x000000ff, 0xff, "nzcv", 0x00000000, "nZcv"},
        {0x800000ff, 0xff, "nzCV", 0x80000000, "NzCV"},
    };
    run_imm_cases(OP_EOR, "eors", CASES(cases));
}

TEST(alu_orr)
{
    static const struct alu_case cases[] = {
        {0x000000f0, 0x0f, "nzcv", 0x000000ff, "nzcv"},
        {0x00000000, 0x00, "nzcv", 0x00000000, "nZcv"},
        {0x80000000, 0x01, "nzcv", 0x80000001, "Nzcv"},
    };
    run_imm_cases(OP_ORR, "orrs", CASES(cases));
}

TEST(alu_bic)
{
    static const struct alu_case cases[] = {
        {0x000000ff, 0x0f, "nzcv", 0x000000f0, "nzcv"},
        {0x0000000f, 0x0f, "nzcv", 0x00000000, "nZcv"},
        {0xffffffff, 0x01, "nzcv", 0xfffffffe, "Nzcv"},
    };
    run_imm_cases(OP_BIC, "bics", CASES(cases));
}

TEST(alu_mov)
{
    static const struct alu_case cases[] = {
        {0xdeadbeef, 0x00, "nzcv", 0x00000000, "nZcv"},
        {0xdeadbeef, 0xff, "NZcv", 0x000000ff, "nzcv"},
        {0xdeadbeef, 0x01, "nzCV", 0x00000001, "nzCV"},
    };
    run_imm_cases(OP_MOV, "movs", CASES(cases));
}

TEST(alu_mvn)
{
    static const struct alu_case cases[] = {
        {0xdeadbeef, 0x00, "nzcv", 0xffffffff, "Nzcv"},
        {0xdeadbeef, 0xff, "nzcv", 0xffffff00, "Nzcv"},
    };
    run_imm_cases(OP_MVN, "mvns", CASES(cases));
}

TEST(alu_add)
{
    static const struct alu_case cases[] = {
        {1,          2,          "nzcv", 3,          "nzcv"},
        {0xffffffff, 1,          "nzcv", 0,          "nZCv"},
        {0x7fffffff, 1,          "nzcv", 0x80000000, "NzcV"},
        {0x80000000, 0x80000000, "nzcv", 0,          "nZCV"},
        {0xfffffffe, 1,          "nzcv", 0xffffffff, "Nzcv"},
        {0x80000000, 0xffffffff, "nzcv", 0x7fffffff, "nzCV"},
        /* every flag is recomputed, not just set */
        {5,          0,          "NZCV", 5,          "nzcv"},
        /* C in is ignored by add */
        {1,          1,          "nzCv", 2,          "nzcv"},
    };
    run_reg_cases(OP_ADD, "adds", CASES(cases));
}

TEST(alu_sub)
{
    static const struct alu_case cases[] = {
        {5,          3,          "nzcv", 2,          "nzCv"},
        {3,          5,          "nzcv", 0xfffffffe, "Nzcv"},
        {5,          5,          "nzcv", 0,          "nZCv"},
        {5,          0,          "nzcv", 5,          "nzCv"},
        /* C is "not borrow", so a subtraction that borrows clears it */
        {0,          1,          "nzCv", 0xffffffff, "Nzcv"},
        {0x80000000, 1,          "nzcv", 0x7fffffff, "nzCV"},
        {0x7fffffff, 0xffffffff, "nzcv", 0x80000000, "NzcV"},
        {0,          0,          "NZCV", 0,          "nZCv"},
    };
    run_reg_cases(OP_SUB, "subs", CASES(cases));
}

/* rsb r0, r1, r2 computes r2 - r1 */
TEST(alu_rsb)
{
    static const struct alu_case cases[] = {
        {3,          5,          "nzcv", 2,          "nzCv"},
        {5,          3,          "nzcv", 0xfffffffe, "Nzcv"},
        {5,          5,          "nzcv", 0,          "nZCv"},
        {1,          0x80000000, "nzcv", 0x7fffffff, "nzCV"},
    };
    run_reg_cases(OP_RSB, "rsbs", CASES(cases));
}

TEST(alu_adc)
{
    static const struct alu_case cases[] = {
        {1,          1, "nzcv", 2,          "nzcv"},
        {1,          1, "nzCv", 3,          "nzcv"},
        {0xffffffff, 0, "nzCv", 0,          "nZCv"},
        {0xffffffff, 0, "nzcv", 0xffffffff, "Nzcv"},
        {0x7fffffff, 0, "nzCv", 0x80000000, "NzcV"},
        {0xfffffffe, 1, "nzCv", 0,          "nZCv"},
    };
    run_reg_cases(OP_ADC, "adcs", CASES(cases));
}

/* sbc computes rn - op2 - NOT(C) */
TEST(alu_sbc)
{
    static const struct alu_case cases[] = {
        {5, 3, "nzCv", 2,          "nzCv"},
        {5, 3, "nzcv", 1,          "nzCv"},
        {0, 0, "nzCv", 0,          "nZCv"},
        {0, 0, "nzcv", 0xffffffff, "Nzcv"},
        {1, 0, "nzcv", 0,          "nZCv"},
    };
    run_reg_cases(OP_SBC, "sbcs", CASES(cases));
}

/* rsc computes op2 - rn - NOT(C) */
TEST(alu_rsc)
{
    static const struct alu_case cases[] = {
        {3, 5, "nzCv", 2,          "nzCv"},
        {3, 5, "nzcv", 1,          "nzCv"},
        {0, 0, "nzCv", 0,          "nZCv"},
    };
    run_reg_cases(OP_RSC, "rscs", CASES(cases));
}

/* V is set when the operands have different signs and the result does not have
 * the sign of operand 2, the same rule as every other subtraction.
 *
 * Known to fail: rsc computes V as (result ^ rn) & 0x80000000 instead. */
TEST(alu_rsc_overflow_flag)
{
    static const struct alu_case cases[] = {
        /* 3 - 5 = -2, no overflow, but the emulator sets V because the result
         * and rn have different signs */
        {5,          3,          "nzCv", 0xfffffffe, "Nzcv"},
        /* 0 - (-1) = 1, no overflow, but the emulator sets V */
        {0xffffffff, 0,          "nzCv", 1,          "nzcv"},
        /* 1 - (-2^31) does overflow, but the emulator clears V */
        {0x80000000, 1,          "nzCv", 0x80000001, "Nzcv"},
    };
    run_reg_cases(OP_RSC, "rscs", CASES(cases));
}

/* The comparison operations set the flags but must not write rd */
TEST(alu_cmp)
{
    static const struct alu_case cases[] = {
        {5,          3, "nzcv", 0xdeadbeef, "nzCv"},
        {3,          5, "nzcv", 0xdeadbeef, "Nzcv"},
        {5,          5, "NZCV", 0xdeadbeef, "nZCv"},
        {0x80000000, 1, "nzcv", 0xdeadbeef, "nzCV"},
    };
    run_reg_cases(OP_CMP, "cmp", CASES(cases));
}

TEST(alu_cmn)
{
    static const struct alu_case cases[] = {
        {0xffffffff, 1, "nzcv", 0xdeadbeef, "nZCv"},
        {1,          1, "nzcv", 0xdeadbeef, "nzcv"},
        {0x7fffffff, 1, "nzcv", 0xdeadbeef, "NzcV"},
    };
    run_reg_cases(OP_CMN, "cmn", CASES(cases));
}

TEST(alu_tst)
{
    static const struct alu_case cases[] = {
        {0xf0, 0x0f, "nzcv", 0xdeadbeef, "nZcv"},
        {0xff, 0x0f, "nzCv", 0xdeadbeef, "nzCv"},
    };
    run_imm_cases(OP_TST, "tst", CASES(cases));

    /* tst r1, #0x80000000 (0x02 rotated right by 2) */
    t_reset();
    t_setflags("nzcv");
    t_setreg(0, 0xdeadbeef);
    t_setreg(1, 0x80000001);
    t_exec(dp_imm(C_AL, OP_TST, 1, 1, 0, 1, 0x02));
    CHECK_REG(0, 0xdeadbeef);
    CHECK_FLAGS("Nzcv");
}

TEST(alu_teq)
{
    static const struct alu_case cases[] = {
        {0x0f, 0x0f, "nzcv", 0xdeadbeef, "nZcv"},
        {0xf0, 0x0f, "nzCv", 0xdeadbeef, "nzCv"},
    };
    run_imm_cases(OP_TEQ, "teq", CASES(cases));
}

/* Operand 2 immediates are an 8 bit value rotated right by twice the 4 bit
 * rotate field */
TEST(alu_immediate_rotation)
{
    static const struct { uint32_t rotate, imm; uint32_t expected; } cases[] = {
        { 0,  0xff, 0x000000ff},
        { 1,  0x02, 0x80000000},
        { 2,  0xff, 0xf000000f},
        { 4,  0xff, 0xff000000},
        { 8,  0xff, 0x00ff0000},
        {15,  0x03, 0x0000000c},
    };

    for( size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++ ) {
        t_reset();
        t_context("mov r0, #0x%02x ror %u", cases[i].imm, cases[i].rotate * 2);
        t_exec(dp_imm(C_AL, OP_MOV, 0, 0, 0, cases[i].rotate, cases[i].imm));
        CHECK_HEX("r0", t_getreg(0), cases[i].expected);
        t_clear_context();
    }
}

/* r15 read as rn gives the address of the instruction plus 8.
 *
 * Note: on a real ARM2 the PSR bits would be included here as well; the
 * emulator masks them off, which is what makes "add rd, pc, #n" (i.e. adr)
 * produce a clean address.
 */
TEST(alu_pc_as_operand_one)
{
    t_exec(dp_imm(C_AL, OP_ADD, 0, R_PC, 0, 0, 4));
    CHECK_REG(0, CODE_ADDR + 8 + 4);

    t_reset();
    t_exec(dp_imm(C_AL, OP_SUB, 0, R_PC, 0, 0, 8));
    CHECK_REG(0, CODE_ADDR);
}

/* r15 read through the barrel shifter (as rm) keeps the PSR bits, which is
 * how a real ARM2 behaves */
TEST(alu_pc_as_operand_two_includes_psr)
{
    t_setflags("NzCvI");
    t_exec(MOV_REG(0, R_PC));
    CHECK_REG(0, (CODE_ADDR + 8) | FLAG_N | FLAG_C | FLAG_I | MODE_SUP);
}

TEST(alu_write_to_pc_branches)
{
    t_setreg(1, 0x200);
    t_setflags("NZCV");
    t_exec(MOV_REG(R_PC, 1));

    CHECK_PC(0x200);
    /* No S bit, so the flags are untouched */
    CHECK_FLAGS("NZCV");
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
}

TEST(alu_write_to_pc_executes_at_target)
{
    t_write(CODE_ADDR, dp_imm(C_AL, OP_ADD, 0, R_PC, R_PC, 0, 0x40));  /* add pc, pc, #0x40 */
    t_write(CODE_ADDR + 0x48, MOV_IMM(0, 42));
    t_run(CODE_ADDR, 2);

    CHECK_REG(0, 42);
    CHECK_PC(CODE_ADDR + 0x4c);
}

/* With the S bit set and rd == r15, the whole of r15 including the PSR is
 * written, as long as we are not in user mode */
TEST(alu_write_to_pc_with_s_bit_sets_psr)
{
    t_setflags("nzcv");
    t_setreg(1, FLAG_N | FLAG_C | 0x200 | MODE_SUP);
    t_exec(dp_reg(C_AL, OP_MOV, 1, 0, R_PC, 1, SH_LSL, 0));

    CHECK_PC(0x200);
    CHECK_FLAGS("NzCv");
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
}

/* In user mode the interrupt disable bits and the mode bits are protected */
TEST(alu_write_to_pc_with_s_bit_in_user_mode)
{
    /* into user mode with the flags clear and interrupts still disabled */
    t_setreg(0, (CODE_ADDR + 4) | FLAG_I | MODE_USR);
    t_setreg(1, 0xf0000000 | 0x200 | MODE_SUP);

    t_write(CODE_ADDR, MOVS_PC(0));
    t_write(CODE_ADDR + 4, dp_reg(C_AL, OP_MOV, 1, 0, R_PC, 1, SH_LSL, 0));  /* movs pc, r1 */
    t_run(CODE_ADDR, 2);

    CHECK_PC(0x200);
    CHECK_FLAGS("NZCV");
    CHECK_MSG(t_getmode() == MODE_USR, "mode is %u, user mode code must not be able to change it",
              t_getmode());
    CHECK_MSG(t_get_i_flag(), "the I flag must not be clearable from user mode");
}
