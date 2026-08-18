/* Software interrupts, exception entry, breakpoints and watchpoints */
#include "harness.h"
#include "encode.h"

TEST(swi_enters_supervisor_mode_at_the_vector)
{
    t_setflags("NzCv");
    t_exec(swi(C_AL, 0x12));

    CHECK_PC(g_vector_table[EXCEPT_SOFTWARE_INTERRUPT]);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
    /* the return address and the psr are saved in the supervisor r14 */
    CHECK_HEX("supervisor r14", t_getactual(LR_S),
              (CODE_ADDR + 8) | FLAG_N | FLAG_C | FLAG_I | MODE_SUP);
}

TEST(swi_from_user_mode_banks_the_registers)
{
    t_setactual(R_SP, 0x11111111);          /* user r13 */
    t_setactual(R13_S, 0x22222222);         /* supervisor r13 */
    t_setreg(0, (CODE_ADDR + 4) | MODE_USR);

    t_write(CODE_ADDR, MOVS_PC(0));         /* into user mode with the flags clear */
    t_write(CODE_ADDR + 4, swi(C_AL, 0));
    t_run(CODE_ADDR, 2);

    CHECK_PC(g_vector_table[EXCEPT_SOFTWARE_INTERRUPT]);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
    CHECK_HEX("r13", t_getreg(R_SP), 0x22222222);
    CHECK_HEX("supervisor r14", t_getactual(LR_S), (CODE_ADDR + 12) | MODE_USR);
    CHECK_HEX("user r13", t_getactual(R_SP), 0x11111111);
}

/* The comment field is ignored, other than the one magic value below */
TEST(swi_ignores_the_comment_field)
{
    t_exec(swi(C_AL, 0x00ffffff));
    CHECK_PC(g_vector_table[EXCEPT_SOFTWARE_INTERRUPT]);
}

TEST(swi_is_conditional)
{
    t_setflags("nzcv");
    t_exec(swi(C_EQ, 0));
    CHECK_PC(CODE_ADDR + 4);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
    CHECK_HEX("supervisor r14", t_getactual(LR_S), 0);
}

/* One swi number is reserved to stop the emulator, so that a debugger can
 * plant it as a breakpoint */
TEST(magic_swi_stops_the_emulator)
{
    enum armv2_status status = t_exec(swi(C_AL, SWI_BREAKPOINT));

    CHECK_MSG(ARMV2STATUS_BREAKPOINT == status, "status is %d, expected ARMV2STATUS_BREAKPOINT (%d)",
              status, ARMV2STATUS_BREAKPOINT);
    /* the pc is left pointing at the breakpoint so that execution can resume */
    CHECK_PC(CODE_ADDR);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
}

TEST(breakpoint_stops_before_the_instruction)
{
    t_write(CODE_ADDR, MOV_IMM(0, 42));
    set_breakpoint(cpu, CODE_ADDR);

    enum armv2_status status = t_run(CODE_ADDR, 1);

    CHECK_MSG(ARMV2STATUS_BREAKPOINT == status, "status is %d, expected ARMV2STATUS_BREAKPOINT (%d)",
              status, ARMV2STATUS_BREAKPOINT);
    CHECK_PC(CODE_ADDR);
    CHECK_REG(0, 0);                         /* the instruction did not run */
}

TEST(breakpoint_can_be_removed)
{
    t_write(CODE_ADDR, MOV_IMM(0, 42));
    set_breakpoint(cpu, CODE_ADDR);
    unset_breakpoint(cpu, CODE_ADDR);

    enum armv2_status status = t_run(CODE_ADDR, 1);

    CHECK_MSG(ARMV2STATUS_OK == status, "status is %d, expected ARMV2STATUS_OK", status);
    CHECK_REG(0, 42);
}

/* Watchpoints are checked after the instruction has run, so the store has
 * already happened and the instruction will be executed again when the
 * emulator is resumed */
TEST(write_watchpoint_stops_after_the_store)
{
    t_setreg(0, 0x12345678);
    t_setreg(1, DATA_ADDR);
    set_watchpoint(cpu, WRITE_WATCHPOINT, DATA_ADDR);

    enum armv2_status status = t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));   /* str r0, [r1] */

    CHECK_MSG(ARMV2STATUS_BREAKPOINT == status, "status is %d, expected ARMV2STATUS_BREAKPOINT (%d)",
              status, ARMV2STATUS_BREAKPOINT);
    CHECK_MEM(DATA_ADDR, 0x12345678);
    CHECK_PC(CODE_ADDR);
}

TEST(read_watchpoint_stops_the_emulator)
{
    t_write(DATA_ADDR, 0x0000f00d);
    t_setreg(1, DATA_ADDR);
    set_watchpoint(cpu, READ_WATCHPOINT, DATA_ADDR);

    enum armv2_status status = t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));   /* ldr r0, [r1] */

    CHECK_MSG(ARMV2STATUS_BREAKPOINT == status, "status is %d, expected ARMV2STATUS_BREAKPOINT (%d)",
              status, ARMV2STATUS_BREAKPOINT);
    CHECK_REG(0, 0x0000f00d);
}

TEST(a_write_watchpoint_does_not_fire_on_a_read)
{
    t_write(DATA_ADDR, 0x0000f00d);
    t_setreg(1, DATA_ADDR);
    set_watchpoint(cpu, WRITE_WATCHPOINT, DATA_ADDR);

    enum armv2_status status = t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));   /* ldr r0, [r1] */

    CHECK_MSG(ARMV2STATUS_OK == status, "status is %d, expected ARMV2STATUS_OK", status);
    CHECK_PC(CODE_ADDR + 4);
}

TEST(watchpoints_can_be_removed)
{
    t_setreg(1, DATA_ADDR);
    set_watchpoint(cpu, ACCESS_WATCHPOINT, DATA_ADDR);
    unset_watchpoint(cpu, ACCESS_WATCHPOINT, DATA_ADDR);

    enum armv2_status status = t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));   /* str r0, [r1] */

    CHECK_MSG(ARMV2STATUS_OK == status, "status is %d, expected ARMV2STATUS_OK", status);
    CHECK_PC(CODE_ADDR + 4);
}

/* Code pages are faulted in on demand, the same as data pages. A freshly
 * faulted page is zeroed, and an all zero word is "andeq r0, r0, r0", which
 * with Z clear does nothing at all -- so all this checks is that we carried on
 * rather than aborting. */
TEST(executing_an_unmapped_page_faults_it_in)
{
    CHECK_MSG(NULL == cpu->page_tables[PAGEOF(0x9000)], "test setup: page 9 should start unmapped");

    t_run(0x9000, 1);

    CHECK_PC(0x9004);
    CHECK_MSG(NULL != cpu->page_tables[PAGEOF(0x9000)], "page 9 should have been faulted in");
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
}

/* ...but if there is no memory left to fault it in with, that is a prefetch
 * abort */
TEST(prefetch_abort_when_the_page_cannot_be_faulted_in)
{
    t_reset_ram(2 * PAGE_SIZE);              /* the code and data pages use it all */

    t_run(0x00400000, 1);

    CHECK_PC(g_vector_table[EXCEPT_PREFETCH_ABORT]);
    CHECK_HEX("mode", t_getmode(), MODE_SUP);
    CHECK_HEX("saved pc", t_getactual(LR_S) & 0x03fffffc, 0x00400008);
}

/* Taking an exception masks irqs, so that a handler can save what it needs to
 * before it can be interrupted itself */
TEST(exception_entry_masks_interrupts)
{
    t_setflags("i");                         /* interrupts enabled */
    t_exec(swi(C_AL, 0));
    CHECK_MSG(t_get_i_flag(), "swi entry must mask irqs");

    t_reset();
    t_setflags("i");
    t_setreg(1, DATA_ADDR + 2);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));   /* unaligned ldr, so a data abort */
    CHECK_MSG(t_get_i_flag(), "data abort entry must mask irqs");
}

/* Each exception has its own vector at the bottom of memory.
 *
 * These are deliberately written out rather than taken from g_vector_table:
 * this is the test that pins the numbers down, and the vectors have to keep
 * matching the branch table at the top of src/boot.S. Comparing the table with
 * itself would assert nothing. */
TEST(exception_vectors)
{
    static const struct { const char *name; uint32_t vector; } expected[] = {
        {"reset",                 0x00},
        {"undefined instruction", 0x04},
        {"software interrupt",    0x08},
        {"prefetch abort",        0x0c},
        {"data abort",            0x10},
        {"address exception",     0x14},
        {"irq",                   0x18},
        {"fiq",                   0x1c},
    };

    for( size_t i = 0; i < sizeof(expected) / sizeof(expected[0]); i++ ) {
        t_context("%s", expected[i].name);
        CHECK_HEX("vector", cpu->exception_handlers[i].pc, expected[i].vector);
        t_clear_context();
    }

    CHECK_HEX("irq mode", cpu->exception_handlers[EXCEPT_IRQ].mode, MODE_IRQ);
    CHECK_HEX("irq save register", cpu->exception_handlers[EXCEPT_IRQ].save_reg, LR_I);
    CHECK_HEX("fiq mode", cpu->exception_handlers[EXCEPT_FIQ].mode, MODE_FIQ);
    CHECK_HEX("fiq save register", cpu->exception_handlers[EXCEPT_FIQ].save_reg, LR_F);
    CHECK_HEX("swi mode", cpu->exception_handlers[EXCEPT_SOFTWARE_INTERRUPT].mode, MODE_SUP);
    CHECK_HEX("swi save register", cpu->exception_handlers[EXCEPT_SOFTWARE_INTERRUPT].save_reg, LR_S);
}
