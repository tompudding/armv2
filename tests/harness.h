/* Minimal test harness for the armv2 emulator core.
 *
 * Tests are registered automatically by the TEST() macro, so adding a test is
 * just a matter of writing it in one of the tests/test_*.c files. The runner in
 * harness.c resets the CPU before every test.
 */
#ifndef ARMV2_TESTS_HARNESS_H
#define ARMV2_TESTS_HARNESS_H

#include <stdint.h>
#include <stddef.h>
#include "armv2.h"

/* The cpu under test. Called "cpu" so that the macros in armv2.h (GETREG,
 * DEREF, ...) can be used directly from test code. */
extern struct armv2 *cpu;

/* Where the harness puts code and scratch data by default. Page 0 (which holds
 * CODE_ADDR) is never writable, exactly as it is on a real machine, so data
 * lives on page 2. */
#define CODE_ADDR 0x00000100u
#define DATA_ADDR 0x00002000u

/* Reset the CPU: supervisor mode, all registers zero, interrupts masked, with
 * the code and data pages faulted in. */
void t_reset(void);
/* Same, but with a restricted amount of physical RAM, for testing what happens
 * when a page cannot be faulted in. */
void t_reset_ram(uint32_t ram_size);

void     t_map(uint32_t addr);                 /* make sure addr's page exists */
void     t_fault(uint32_t addr);               /* fault a page in at this exact address */
void     t_unmap(uint32_t addr);               /* throw addr's page away again */
void     t_write(uint32_t addr, uint32_t value);
uint32_t t_read(uint32_t addr);

void     t_setreg(uint32_t reg, uint32_t value);      /* current bank */
uint32_t t_getreg(uint32_t reg);
void     t_setactual(uint32_t reg, uint32_t value);   /* raw regs.actual[] slot */
uint32_t t_getactual(uint32_t reg);

/* Flags are handled as 4 character strings, upper case for set and lower case
 * for clear, e.g. "nZCv" is Z and C set, N and V clear. t_setflags() only
 * touches the flags named in the string. */
void        t_setflags(const char *flags);
void        t_setflags_bits(uint32_t nzcv);    /* bit3 = N ... bit0 = V */
const char *t_flags(void);

/* There is no setter for the mode: a test that wants to be in another mode
 * executes the instruction that gets it there, so that the register banking is
 * done by the cpu rather than by a copy of it living here. MOVS_PC() in
 * encode.h is the usual way in. */
uint32_t t_getmode(void);
void     t_set_i_flag(int on);
int      t_get_i_flag(void);

/* The address of the next instruction that would be executed. */
uint32_t t_nextpc(void);

/* Execute a single instruction placed at CODE_ADDR / at addr. */
enum armv2_status t_exec(uint32_t instruction);
enum armv2_status t_exec_at(uint32_t addr, uint32_t instruction);
/* Execute count instructions starting at addr (the caller writes them). */
enum armv2_status t_run(uint32_t addr, int32_t count);

/* Checks. Each records a failure against the running test and carries on. */
void t_check_hex(const char *what, uint32_t got, uint32_t want, const char *file, int line);
void t_check_str(const char *what, const char *got, const char *want, const char *file, int line);
void t_check_msg(int ok, const char *file, int line, const char *fmt, ...)
    __attribute__((format(printf, 4, 5)));

#define CHECK_HEX(what, got, want) t_check_hex((what), (got), (want), __FILE__, __LINE__)
#define CHECK_REG(reg, want)       t_check_hex("r" #reg, t_getreg(reg), (want), __FILE__, __LINE__)
#define CHECK_FLAGS(want)          t_check_str("flags", t_flags(), (want), __FILE__, __LINE__)
#define CHECK_PC(want)             t_check_hex("next pc", t_nextpc(), (want), __FILE__, __LINE__)
#define CHECK_MEM(addr, want)      t_check_hex("mem[" #addr "]", t_read(addr), (want), __FILE__, __LINE__)
#define CHECK(cond)                t_check_msg(!!(cond), __FILE__, __LINE__, "%s", #cond)
#define CHECK_MSG(cond, ...)       t_check_msg(!!(cond), __FILE__, __LINE__, __VA_ARGS__)

/* Used by the checks to say which case of a table driven test failed. */
void t_context(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void t_clear_context(void);

typedef void (*test_fn_t)(void);
void t_register(const char *name, test_fn_t fn, const char *file, int line);

#define TEST(name)                                                          \
    static void name(void);                                                 \
    static void __attribute__((constructor)) t_register_##name(void) {      \
        t_register(#name, name, __FILE__, __LINE__);                        \
    }                                                                       \
    static void name(void)

#endif
