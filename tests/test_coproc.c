/* Coprocessor instructions. Coprocessor 1 is the hardware manager, which is
 * how the boot rom finds and maps the devices attached to the machine.
 */
#include "harness.h"
#include "encode.h"
#include "hw_manager.h"

#define CP_HW_MANAGER 1

/* mcr writes an ARM register into a coprocessor register, mrc reads it back */
TEST(coprocessor_register_transfer_round_trip)
{
    t_setreg(5, 0x12345678);

    /* mcr p1, 0, r5, cr1, cr0 */
    t_exec(mrc_mcr(C_AL, 0, CP_HW_MANAGER, 0, 5, 1, 0, 0));
    CHECK_HEX("hw manager register 1", cpu->hardware_manager.regs[1], 0x12345678);

    /* mrc p1, 0, r6, cr1, cr0 */
    t_exec(mrc_mcr(C_AL, 1, CP_HW_MANAGER, 0, 6, 1, 0, 0));
    CHECK_REG(6, 0x12345678);
}

/* mrc into r15 only sets the flags */
TEST(coprocessor_read_into_pc_sets_the_flags)
{
    t_setflags("nzcv");
    cpu->hardware_manager.regs[1] = FLAG_N | FLAG_V;

    /* mrc p1, 0, pc, cr1, cr0 */
    t_exec(mrc_mcr(C_AL, 1, CP_HW_MANAGER, 0, R_PC, 1, 0, 0));

    CHECK_FLAGS("NzcV");
    CHECK_PC(CODE_ADDR + 4);
}

/* cdp asks the hardware manager to do something; the results come back in its
 * registers */
TEST(hardware_manager_device_count)
{
    /* cdp p1, NUM_DEVICES, cr0, cr0, cr0 */
    t_exec(cdp(C_AL, CP_HW_MANAGER, NUM_DEVICES, 0, 0, 0, 0));
    /* mrc p1, 0, r0, cr0, cr0 */
    t_exec(mrc_mcr(C_AL, 1, CP_HW_MANAGER, 0, 0, 0, 0, 0));

    CHECK_REG(0, 0);        /* a bare cpu has no hardware attached */
}

TEST(hardware_manager_gettime)
{
    /* cdp p1, GETTIME, cr0, cr0, cr0 */
    t_exec(cdp(C_AL, CP_HW_MANAGER, GETTIME, 0, 0, 0, 0));
    t_exec(mrc_mcr(C_AL, 1, CP_HW_MANAGER, 0, 0, 0, 0, 0));
    t_exec(mrc_mcr(C_AL, 1, CP_HW_MANAGER, 0, 1, 1, 0, 0));

    CHECK_REG(0, 0x617a6977);
    CHECK_REG(1, 0x79726472);
}

/* Waiting for an interrupt with interrupts enabled parks the cpu until one
 * arrives */
TEST(hardware_manager_wait_for_interrupt)
{
    t_setflags("if");
    t_write(CODE_ADDR, cdp(C_AL, CP_HW_MANAGER, WAIT_FOR_INTERRUPT, 0, 0, 0, 0));
    t_write(CODE_ADDR + 4, MOV_IMM(0, 42));

    enum armv2_status status = t_run(CODE_ADDR, 10);

    CHECK_MSG(ARMV2STATUS_WAIT_FOR_INTERRUPT == status,
              "status is %d, expected ARMV2STATUS_WAIT_FOR_INTERRUPT (%d)",
              status, ARMV2STATUS_WAIT_FOR_INTERRUPT);
    CHECK_REG(0, 0);        /* the following instruction has not run */
}

/* ... and it does not park if interrupts are masked, or we would never get
 * going again */
TEST(wait_for_interrupt_is_ignored_with_interrupts_masked)
{
    t_setflags("I");
    t_write(CODE_ADDR, cdp(C_AL, CP_HW_MANAGER, WAIT_FOR_INTERRUPT, 0, 0, 0, 0));
    t_write(CODE_ADDR + 4, MOV_IMM(0, 42));

    enum armv2_status status = t_run(CODE_ADDR, 2);

    CHECK_MSG(ARMV2STATUS_OK == status, "status is %d, expected ARMV2STATUS_OK", status);
    CHECK_REG(0, 42);
}

/* Instructions for coprocessors that are not there do nothing at all. A real
 * ARM2 would take the undefined instruction trap. */
TEST(unknown_coprocessor_is_ignored)
{
    t_setreg(0, 0x11111111);
    t_setflags("nzcv");

    t_exec(cdp(C_AL, 9, 0, 0, 0, 0, 0));
    CHECK_PC(CODE_ADDR + 4);
    CHECK_REG(0, 0x11111111);
    CHECK_FLAGS("nzcv");

    t_exec(mrc_mcr(C_AL, 1, 9, 0, 0, 0, 0, 0));
    CHECK_PC(CODE_ADDR + 4);
    CHECK_REG(0, 0x11111111);
}

/* Coprocessor loads and stores are not implemented at all */
TEST(coprocessor_data_transfer_is_a_no_op)
{
    t_setreg(1, DATA_ADDR);
    t_write(DATA_ADDR, 0x11111111);

    /* ldc p1, cr0, [r1] */
    t_exec((C_AL << 28) | 0x0c100000 | (1u << 16) | (0u << 12) | (CP_HW_MANAGER << 8));

    CHECK_PC(CODE_ADDR + 4);
    CHECK_MEM(DATA_ADDR, 0x11111111);
}
