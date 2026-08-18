/* IRQ and FIQ entry, and the register banking that goes with it.
 *
 * Interrupts are taken between instructions rather than by an instruction, so
 * these tests arm a pin and then run: the instruction sitting at the pc must
 * not execute, and the cpu must end up at the vector in the right mode.
 */
#include "harness.h"
#include "encode.h"

static int f_flag_set(void)
{
    return (cpu->regs.actual[PC] & FLAG_F) != 0;
}

TEST(irq_enters_irq_mode_at_the_vector)
{
    t_setflags("nzcvi");                     /* interrupts enabled */
    t_write(CODE_ADDR, MOV_IMM(0, 42));      /* this must not run */
    interrupt(cpu, 1, 2);

    t_run(CODE_ADDR, 1);

    CHECK_PC(g_vector_table[EXCEPT_IRQ]);
    CHECK_HEX("mode", t_getmode(), MODE_IRQ);
    CHECK_REG(0, 0);
    /* r14_irq holds the return address plus four, so the handler returns with
     * "subs pc, lr, #4" */
    CHECK_HEX("irq r14", t_getactual(LR_I) & 0x03fffffc, CODE_ADDR + 4);
    CHECK_MSG(t_get_i_flag(), "taking an irq must mask further irqs");
    CHECK_MSG(!f_flag_set(), "taking an irq must not mask fiqs");
    CHECK_MSG(!PIN_ON(cpu, I), "the irq pin should have been acknowledged");
}

TEST(irq_is_not_taken_while_masked)
{
    t_setflags("I");                         /* interrupts disabled */
    SETPIN(cpu, I);                          /* a device asserts the pin anyway */
    t_write(CODE_ADDR, MOV_IMM(0, 42));

    t_run(CODE_ADDR, 1);

    CHECK_REG(0, 42);
    CHECK_PC(CODE_ADDR + 4);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
}

/* The banked r13 and r14 come into scope, the rest of the registers do not */
TEST(irq_banks_r13_and_r14_only)
{
    t_setflags("nzcvi");
    t_setactual(R_SP, 0x11111111);           /* user r13 */
    t_setactual(R13_I, 0x22222222);          /* irq r13 */
    t_setactual(8, 0x88888888);
    t_setactual(12, 0xcccccccc);
    t_write(CODE_ADDR, NOP);
    interrupt(cpu, 1, 2);

    t_run(CODE_ADDR, 1);

    CHECK_HEX("r13", t_getreg(R_SP), 0x22222222);
    CHECK_HEX("r8", t_getreg(8), 0x88888888);
    CHECK_HEX("r12", t_getreg(12), 0xcccccccc);
    CHECK_HEX("user r13", t_getactual(R_SP), 0x11111111);
}

TEST(fiq_enters_fiq_mode_at_the_vector)
{
    t_setflags("nzcvif");                    /* both kinds enabled */
    SETPIN(cpu, F);
    t_write(CODE_ADDR, MOV_IMM(0, 42));

    t_run(CODE_ADDR, 1);

    CHECK_PC(g_vector_table[EXCEPT_FIQ]);
    CHECK_HEX("mode", t_getmode(), MODE_FIQ);
    CHECK_REG(0, 0);
    CHECK_HEX("fiq r14", t_getactual(LR_F) & 0x03fffffc, CODE_ADDR + 4);
    CHECK_MSG(t_get_i_flag(), "taking an fiq must mask irqs");
    CHECK_MSG(f_flag_set(), "taking an fiq must mask further fiqs");
}

TEST(fiq_is_not_taken_while_masked)
{
    t_setflags("F");
    SETPIN(cpu, F);
    t_write(CODE_ADDR, MOV_IMM(0, 42));

    t_run(CODE_ADDR, 1);

    CHECK_REG(0, 42);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
}

/* fiq gets its own r8 to r14, which is what makes it fast: a handler can keep
 * state in them without saving anything */
TEST(fiq_banks_r8_to_r14)
{
    /* r8 to r13; r14_fiq is left out because taking the fiq overwrites it with
     * the return address, which fiq_enters_fiq_mode_at_the_vector covers */
    static const uint32_t user[6] = {0x88888888, 0x99999999, 0xaaaaaaaa, 0xbbbbbbbb,
                                     0xcccccccc, 0xdddddddd};
    static const uint32_t fiq[6]  = {0xf8f8f8f8, 0xf9f9f9f9, 0xfafafafa, 0xfbfbfbfb,
                                     0xfcfcfcfc, 0xfdfdfdfd};

    t_setflags("nzcvif");
    for( uint32_t i = 0; i < 6; i++ ) {
        t_setactual(8 + i, user[i]);
        t_setactual(R8_F + i, fiq[i]);
    }
    t_setactual(R_LR, 0xeeeeeeee);
    t_write(CODE_ADDR, NOP);
    SETPIN(cpu, F);

    t_run(CODE_ADDR, 1);

    for( uint32_t i = 0; i < 6; i++ ) {
        t_context("r%u", 8 + i);
        CHECK_HEX("fiq bank", t_getreg(8 + i), fiq[i]);
        CHECK_HEX("user bank untouched", t_getactual(8 + i), user[i]);
        t_clear_context();
    }
    CHECK_HEX("user r14 untouched", t_getactual(R_LR), 0xeeeeeeee);
    /* r0 to r7 are shared with every other mode */
    CHECK_HEX("r7", t_getreg(7), 0);
}

TEST(fiq_takes_priority_over_irq)
{
    t_setflags("nzcvif");
    SETPIN(cpu, F);
    SETPIN(cpu, I);
    t_write(CODE_ADDR, NOP);

    t_run(CODE_ADDR, 1);

    CHECK_PC(g_vector_table[EXCEPT_FIQ]);
    CHECK_HEX("mode", t_getmode(), MODE_FIQ);
}

/* The whole round trip: interrupt, handler, and back to what we were doing */
TEST(returning_from_an_irq_restores_the_previous_mode)
{
    t_setflags("nzcvi");
    t_setactual(R13_S, 0x00005555);          /* supervisor r13 */
    t_setactual(R13_I, 0x00009999);          /* irq r13 */
    t_write(CODE_ADDR, MOV_IMM(0, 42));
    /* subs pc, lr, #4 at the irq vector */
    t_write(g_vector_table[EXCEPT_IRQ], dp_imm(C_AL, OP_SUB, 1, R_LR, R_PC, 0, 4));
    interrupt(cpu, 1, 2);

    t_run(CODE_ADDR, 3);                     /* take it, return from it, run the instruction */

    CHECK_REG(0, 42);
    CHECK_PC(CODE_ADDR + 4);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
    CHECK_HEX("r13", t_getreg(R_SP), 0x00005555);
    CHECK_MSG(!t_get_i_flag(), "returning from the handler should unmask irqs again");
}

/* The handler asks the hardware manager which device interrupted it */
TEST(interrupt_data_is_readable_from_the_handler)
{
    t_setflags("nzcvi");
    t_write(CODE_ADDR, NOP);
    /* cdp p1, INTERRUPT_DATA, cr0, cr0, cr0 ; mrc r0, cr0 ; mrc r1, cr1 */
    t_write(g_vector_table[EXCEPT_IRQ] + 0, cdp(C_AL, 1, 3, 0, 0, 0, 0));
    t_write(g_vector_table[EXCEPT_IRQ] + 4, mrc_mcr(C_AL, 1, 1, 0, 0, 0, 0, 0));
    t_write(g_vector_table[EXCEPT_IRQ] + 8, mrc_mcr(C_AL, 1, 1, 0, 1, 1, 0, 0));
    interrupt(cpu, 7, 9);

    t_run(CODE_ADDR, 4);

    CHECK_REG(0, 7);                         /* the device that interrupted */
    CHECK_REG(1, 9);                         /* and its code */
}

/* A second interrupt while one is being handled is dropped rather than queued */
TEST(interrupts_are_dropped_while_masked)
{
    t_setflags("nzcvi");
    t_write(CODE_ADDR, NOP);
    interrupt(cpu, 7, 9);
    t_run(CODE_ADDR, 1);                     /* now in irq mode with irqs masked */

    interrupt(cpu, 3, 4);                    /* this one goes nowhere */

    CHECK_MSG(!PIN_ON(cpu, I), "a masked interrupt must not leave the pin asserted");
    CHECK_HEX("last interrupt id", cpu->hardware_manager.last_interrupt_id, 7);
    CHECK_HEX("last interrupt code", cpu->hardware_manager.last_interrupt_code, 9);
}
