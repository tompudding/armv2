/* The barrel shifter: results and carry out for every shift type, both with
 * the amount encoded in the instruction and taken from a register.
 *
 * "movs r0, r1, <shift>" is used throughout, so r0 is the shifted value and C
 * is the shifter carry out.
 */
#include "harness.h"
#include "encode.h"

struct shift_case {
    uint32_t    rm;
    uint32_t    amount;
    const char *before;
    uint32_t    result;
    const char *after;
};

#define CASES(x) (x), sizeof(x) / sizeof((x)[0])

/* movs r0, r1, <type> #amount */
static void run_shift_imm(uint32_t type, const char *name, const struct shift_case *cases, size_t n)
{
    for( size_t i = 0; i < n; i++ ) {
        t_reset();
        t_setflags(cases[i].before);
        t_setreg(1, cases[i].rm);
        t_context("movs r0, 0x%08x, %s #%u with flags %s", cases[i].rm, name, cases[i].amount,
                  cases[i].before);

        t_exec(dp_reg(C_AL, OP_MOV, 1, 0, 0, 1, type, cases[i].amount));

        CHECK_HEX("r0", t_getreg(0), cases[i].result);
        CHECK_FLAGS(cases[i].after);
        t_clear_context();
    }
}

/* movs r0, r1, <type> r2 */
static void run_shift_reg(uint32_t type, const char *name, const struct shift_case *cases, size_t n)
{
    for( size_t i = 0; i < n; i++ ) {
        t_reset();
        t_setflags(cases[i].before);
        t_setreg(1, cases[i].rm);
        t_setreg(2, cases[i].amount);
        t_context("movs r0, 0x%08x, %s r2(=%u) with flags %s", cases[i].rm, name, cases[i].amount,
                  cases[i].before);

        t_exec(dp_regshift(C_AL, OP_MOV, 1, 0, 0, 1, type, 2));

        CHECK_HEX("r0", t_getreg(0), cases[i].result);
        CHECK_FLAGS(cases[i].after);
        t_clear_context();
    }
}

TEST(shift_lsl_immediate)
{
    static const struct shift_case cases[] = {
        {0x00000001,  1, "nzcv", 0x00000002, "nzcv"},
        {0x80000000,  1, "nzcv", 0x00000000, "nZCv"},
        {0x00000003, 31, "nzcv", 0x80000000, "NzCv"},
        {0x00000001, 31, "nzcv", 0x80000000, "Nzcv"},
        {0xffffffff,  4, "nzcv", 0xfffffff0, "NzCv"},
        {0x08000000,  4, "nzcv", 0x80000000, "Nzcv"},
    };
    run_shift_imm(SH_LSL, "lsl", CASES(cases));
}

TEST(shift_lsr_immediate)
{
    static const struct shift_case cases[] = {
        {0x00000003,  1, "nzcv", 0x00000001, "nzCv"},
        {0x80000000, 31, "nzcv", 0x00000001, "nzcv"},
        {0x000000ff,  4, "nzcv", 0x0000000f, "nzCv"},
        /* lsr #0 in the encoding means lsr #32 */
        {0x80000000,  0, "nzcv", 0x00000000, "nZCv"},
        {0x7fffffff,  0, "nzCv", 0x00000000, "nZcv"},
    };
    run_shift_imm(SH_LSR, "lsr", CASES(cases));
}

TEST(shift_asr_immediate)
{
    static const struct shift_case cases[] = {
        {0x80000000,  1, "nzcv", 0xc0000000, "Nzcv"},
        {0x00000003,  1, "nzcv", 0x00000001, "nzCv"},
        {0xfffffff0,  4, "nzcv", 0xffffffff, "Nzcv"},
        {0x7fffffff,  4, "nzcv", 0x07ffffff, "nzCv"},
        /* asr #0 in the encoding means asr #32 */
        {0x80000000,  0, "nzcv", 0xffffffff, "NzCv"},
        {0x7fffffff,  0, "nzCv", 0x00000000, "nZcv"},
    };
    run_shift_imm(SH_ASR, "asr", CASES(cases));
}

TEST(shift_ror_immediate)
{
    static const struct shift_case cases[] = {
        {0x0000000f,  4, "nzcv", 0xf0000000, "NzCv"},
        {0x12345678,  8, "nzcv", 0x78123456, "nzcv"},
        {0x00000001,  1, "nzcv", 0x80000000, "NzCv"},
    };
    run_shift_imm(SH_ROR, "ror", CASES(cases));
}

/* ror #0 in the encoding means rrx: a 33 bit rotate right through carry */
TEST(shift_rrx)
{
    static const struct shift_case cases[] = {
        {0x00000001, 0, "nzCv", 0x80000000, "NzCv"},
        {0x00000001, 0, "nzcv", 0x00000000, "nZCv"},
        {0x00000002, 0, "nzcv", 0x00000001, "nzcv"},
        {0x00000002, 0, "nzCv", 0x80000001, "Nzcv"},
    };
    run_shift_imm(SH_ROR, "rrx", CASES(cases));
}

TEST(shift_lsl_register)
{
    static const struct shift_case cases[] = {
        {0x00000001,     1, "nzcv", 0x00000002, "nzcv"},
        {0x80000000,     1, "nzcv", 0x00000000, "nZCv"},
        /* shifting by 32 leaves bit 0 in the carry */
        {0x80000001,    32, "nzcv", 0x00000000, "nZCv"},
        {0x80000000,    32, "nzcv", 0x00000000, "nZcv"},
        /* and by more than 32 clears everything */
        {0xffffffff,    33, "nzCv", 0x00000000, "nZcv"},
        {0xffffffff,   255, "nzCv", 0x00000000, "nZcv"},
        /* only the bottom byte of rs is used */
        {0xdeadbeef, 0x104, "nzcv", 0xeadbeef0, "NzCv"},
    };
    run_shift_reg(SH_LSL, "lsl", CASES(cases));
}

TEST(shift_lsr_register)
{
    static const struct shift_case cases[] = {
        {0x00000003,     1, "nzcv", 0x00000001, "nzCv"},
        {0x80000000,    32, "nzcv", 0x00000000, "nZCv"},
        {0x7fffffff,    32, "nzcv", 0x00000000, "nZcv"},
        {0xffffffff,    33, "nzCv", 0x00000000, "nZcv"},
        /* only the bottom byte of rs is used: 0x120 & 0xff == 32 */
        {0x80000000, 0x120, "nzcv", 0x00000000, "nZCv"},
    };
    run_shift_reg(SH_LSR, "lsr", CASES(cases));
}

TEST(shift_asr_register)
{
    static const struct shift_case cases[] = {
        {0x80000000,  1, "nzcv", 0xc0000000, "Nzcv"},
        {0xfffffff0,  4, "nzcv", 0xffffffff, "Nzcv"},
        {0x00000003,  1, "nzcv", 0x00000001, "nzCv"},
        /* shifting a positive value right by 32 or more gives zero */
        {0x7fffffff, 32, "nzCv", 0x00000000, "nZcv"},
        {0x7fffffff, 99, "nzCv", 0x00000000, "nZcv"},
    };
    run_shift_reg(SH_ASR, "asr", CASES(cases));
}

TEST(shift_ror_register)
{
    static const struct shift_case cases[] = {
        {0x0000000f,  4, "nzcv", 0xf0000000, "NzCv"},
        /* a rotate of exactly 32 is a no-op with bit 31 in the carry */
        {0x80000001, 32, "nzcv", 0x80000001, "NzCv"},
        {0x7fffffff, 32, "nzCv", 0x7fffffff, "nzcv"},
        /* rotates above 32 wrap round */
        {0x0000000f, 36, "nzcv", 0xf0000000, "NzCv"},
    };
    run_shift_reg(SH_ROR, "ror", CASES(cases));
}

// A shift of zero passes rm through untouched and leaves the carry alone.
TEST(shift_lsl_zero_preserves_carry)
{
    static const struct shift_case imm_cases[] = {
        {0x0f0f0f0f, 0, "nzcv", 0x0f0f0f0f, "nzcv"},
        {0x0f0f0f0f, 0, "nzCv", 0x0f0f0f0f, "nzCv"},
    };
    static const struct shift_case reg_cases[] = {
        {0x0f0f0f0f,     0, "nzcv", 0x0f0f0f0f, "nzcv"},
        /* 0x100 & 0xff == 0, so this is a shift by zero too */
        {0x0f0f0f0f, 0x100, "nzcv", 0x0f0f0f0f, "nzcv"},
    };
    run_shift_imm(SH_LSL, "lsl", CASES(imm_cases));
    run_shift_reg(SH_LSL, "lsl", CASES(reg_cases));
}

// An arithmetic shift right by 32 or more fills the whole word with the sign
// bit, which also ends up in the carry.
TEST(shift_asr_register_32_or_more)
{
    static const struct shift_case cases[] = {
        {0x80000000, 32, "nzcv", 0xffffffff, "NzCv"},
        {0x80000000, 40, "nzcv", 0xffffffff, "NzCv"},
        {0xffffffff, 32, "nzcv", 0xffffffff, "NzCv"},
    };
    run_shift_reg(SH_ASR, "asr", CASES(cases));
}

/* Any non zero multiple of 32 rotates the word back to where it started and
 * puts bit 31 in the carry, exactly like a rotate of 32. */
TEST(shift_ror_register_multiple_of_32)
{
    static const struct shift_case cases[] = {
        {0x80000001, 64, "nzcv", 0x80000001, "NzCv"},
    };
    run_shift_reg(SH_ROR, "ror", CASES(cases));
}

/* The shifted value is operand 2 of a normal data processing instruction */
TEST(shift_feeds_operand_two)
{
    t_setreg(1, 0x00000010);
    t_setreg(3, 0x00000001);
    t_exec(dp_reg(C_AL, OP_ADD, 0, 3, 0, 1, SH_LSL, 4));   /* add r0, r3, r1, lsl #4 */
    CHECK_REG(0, 0x101);

    t_reset();
    t_setreg(1, 0xfffffff0);
    t_setreg(2, 4);
    t_setreg(3, 0x100);
    t_exec(dp_regshift(C_AL, OP_ADD, 0, 3, 0, 1, SH_ASR, 2));  /* add r0, r3, r1, asr r2 */
    CHECK_REG(0, 0xff);

    /* An arithmetic instruction takes its carry from the adder, not the shifter */
    t_reset();
    t_setflags("nzcv");
    t_setreg(1, 0x00000003);
    t_setreg(3, 0x00000000);
    t_exec(dp_reg(C_AL, OP_ADD, 1, 3, 0, 1, SH_LSR, 1));   /* adds r0, r3, r1, lsr #1 */
    CHECK_REG(0, 1);
    CHECK_FLAGS("nzcv");
}
