#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#include "harness.h"

#define MAX_TESTS       512
#define MAX_FAIL_TEXT   8192
#define CONTEXT_LEN     256

struct test_entry {
    const char *name;
    test_fn_t   fn;
    const char *file;
    int         line;
};

static struct test_entry tests[MAX_TESTS];
static size_t num_tests = 0;

static struct armv2 the_cpu;
struct armv2 *cpu = &the_cpu;

static char fail_text[MAX_FAIL_TEXT];
static size_t fail_len = 0;
static int fail_count = 0;
static int check_count = 0;
static char context[CONTEXT_LEN] = {0};

/* The emulator logs to stdout on init/cleanup, which would drown the results */
static int saved_stdout = -1;

static void mute(void)
{
    int devnull;
    fflush(stdout);
    saved_stdout = dup(STDOUT_FILENO);
    devnull = open("/dev/null", O_WRONLY);
    if( devnull >= 0 ) {
        dup2(devnull, STDOUT_FILENO);
        close(devnull);
    }
}

static void unmute(void)
{
    fflush(stdout);
    if( saved_stdout >= 0 ) {
        dup2(saved_stdout, STDOUT_FILENO);
        close(saved_stdout);
        saved_stdout = -1;
    }
}

void t_register(const char *name, test_fn_t fn, const char *file, int line)
{
    if( num_tests >= MAX_TESTS ) {
        fprintf(stderr, "Too many tests, raise MAX_TESTS\n");
        exit(2);
    }
    tests[num_tests].name = name;
    tests[num_tests].fn   = fn;
    tests[num_tests].file = file;
    tests[num_tests].line = line;
    num_tests++;
}

/* Constructors run in an order we don't control, so sort for stable output */
static int compare_tests(const void *a, const void *b)
{
    const struct test_entry *ta = a;
    const struct test_entry *tb = b;
    int result = strcmp(ta->file, tb->file);

    return result != 0 ? result : (ta->line - tb->line);
}

void t_reset(void)
{
    t_reset_ram(MAX_MEMORY);
}

void t_reset_ram(uint32_t ram_size)
{
    mute();
    (void)cleanup_armv2(cpu);
    if( ARMV2STATUS_OK != init(cpu, ram_size) ) {
        unmute();
        fprintf(stderr, "Failed to initialise cpu\n");
        exit(2);
    }
    unmute();

    t_map(CODE_ADDR);
    t_map(DATA_ADDR);
}

/* Fault a page in the way the machine does when it loads the boot rom, i.e.
 * with the address of the start of the page. fault() only marks page zero read
 * only when it is handed address zero exactly, see page_zero_is_read_only. */
void t_map(uint32_t addr)
{
    if( NULL == cpu->page_tables[PAGEOF(addr)] ) {
        t_fault(addr);
    }
}

void t_fault(uint32_t addr)
{
    mute();
    (void)fault(cpu, addr);
    unmute();
}

void t_unmap(uint32_t addr)
{
    struct page_info *page = cpu->page_tables[PAGEOF(addr)];

    if( NULL != page ) {
        if( NULL != page->memory ) {
            munmap(page->memory, PAGE_SIZE);
        }
        free(page);
        cpu->page_tables[PAGEOF(addr)] = NULL;
        cpu->free_ram += PAGE_SIZE;
    }
}

void t_write(uint32_t addr, uint32_t value)
{
    t_map(addr);
    DEREF(cpu, addr) = value;
}

uint32_t t_read(uint32_t addr)
{
    t_map(addr);
    return DEREF(cpu, addr);
}

void t_setreg(uint32_t reg, uint32_t value)
{
    GETREG(cpu, reg) = value;
}

uint32_t t_getreg(uint32_t reg)
{
    return GETREG(cpu, reg);
}

void t_setactual(uint32_t reg, uint32_t value)
{
    cpu->regs.actual[reg] = value;
}

uint32_t t_getactual(uint32_t reg)
{
    return cpu->regs.actual[reg];
}

static uint32_t flag_bit(char c)
{
    switch( c ) {
    case 'n': case 'N': return FLAG_N;
    case 'z': case 'Z': return FLAG_Z;
    case 'c': case 'C': return FLAG_C;
    case 'v': case 'V': return FLAG_V;
    case 'i': case 'I': return FLAG_I;
    case 'f': case 'F': return FLAG_F;
    default:            return 0;
    }
}

void t_setflags(const char *flags)
{
    for( const char *p = flags; *p; p++ ) {
        uint32_t bit = flag_bit(*p);
        if( 0 == bit ) {
            continue;
        }
        if( *p >= 'A' && *p <= 'Z' ) {
            cpu->regs.actual[PC] |= bit;
        }
        else {
            cpu->regs.actual[PC] &= ~bit;
        }
    }
}

void t_setflags_bits(uint32_t nzcv)
{
    char buf[5] = "nzcv";
    static const char upper[4] = {'N', 'Z', 'C', 'V'};

    for( int i = 0; i < 4; i++ ) {
        if( nzcv & (1u << (3 - i)) ) {
            buf[i] = upper[i];
        }
    }
    t_setflags(buf);
}

const char *t_flags(void)
{
    static char buf[5];
    uint32_t psr = cpu->regs.actual[PC];

    buf[0] = (psr & FLAG_N) ? 'N' : 'n';
    buf[1] = (psr & FLAG_Z) ? 'Z' : 'z';
    buf[2] = (psr & FLAG_C) ? 'C' : 'c';
    buf[3] = (psr & FLAG_V) ? 'V' : 'v';
    buf[4] = 0;

    return buf;
}

uint32_t t_getmode(void)
{
    return GETMODE(cpu);
}

void t_set_i_flag(int on)
{
    t_setflags(on ? "I" : "i");
}

int t_get_i_flag(void)
{
    return FLAG_SET(cpu, I) ? 1 : 0;
}

uint32_t t_nextpc(void)
{
    return (cpu->pc + 4) & 0x03fffffc;
}

enum armv2_status t_exec(uint32_t instruction)
{
    return t_exec_at(CODE_ADDR, instruction);
}

enum armv2_status t_exec_at(uint32_t addr, uint32_t instruction)
{
    t_write(addr, instruction);
    return t_run(addr, 1);
}

enum armv2_status t_run(uint32_t addr, int32_t count)
{
    enum armv2_status result;

    /* The run loop increments the pc before fetching, so start one back */
    cpu->pc = (addr - 4) & 0x03ffffff;
    mute();
    result = run_armv2(cpu, &count);
    unmute();

    return result;
}

void t_context(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    vsnprintf(context, sizeof(context), fmt, args);
    va_end(args);
}

void t_clear_context(void)
{
    context[0] = 0;
}

static void record_failure(const char *file, int line, const char *fmt, ...)
{
    va_list args;
    int written;

    fail_count++;
    if( fail_len >= sizeof(fail_text) - 128 ) {
        return;
    }

    written = snprintf(fail_text + fail_len, sizeof(fail_text) - fail_len, "        %s:%d: ", file, line);
    if( written > 0 ) {
        fail_len += (size_t)written;
    }

    va_start(args, fmt);
    written = vsnprintf(fail_text + fail_len, sizeof(fail_text) - fail_len, fmt, args);
    va_end(args);
    if( written > 0 ) {
        fail_len += (size_t)written;
    }

    if( context[0] ) {
        written = snprintf(fail_text + fail_len, sizeof(fail_text) - fail_len, " [%s]", context);
        if( written > 0 ) {
            fail_len += (size_t)written;
        }
    }

    written = snprintf(fail_text + fail_len, sizeof(fail_text) - fail_len, "\n");
    if( written > 0 ) {
        fail_len += (size_t)written;
    }
}

void t_check_hex(const char *what, uint32_t got, uint32_t want, const char *file, int line)
{
    check_count++;
    if( got != want ) {
        record_failure(file, line, "%s is 0x%08x, expected 0x%08x", what, got, want);
    }
}

void t_check_str(const char *what, const char *got, const char *want, const char *file, int line)
{
    check_count++;
    if( 0 != strcmp(got, want) ) {
        record_failure(file, line, "%s are \"%s\", expected \"%s\"", what, got, want);
    }
}

void t_check_msg(int ok, const char *file, int line, const char *fmt, ...)
{
    va_list args;
    char buf[256];

    check_count++;
    if( ok ) {
        return;
    }
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    record_failure(file, line, "%s", buf);
}

int main(int argc, char *argv[])
{
    int passed = 0, failed = 0;
    int total_checks = 0;
    const char *filter = argc > 1 ? argv[1] : NULL;

    qsort(tests, num_tests, sizeof(tests[0]), compare_tests);

    printf("Running %zu tests\n\n", num_tests);

    for( size_t i = 0; i < num_tests; i++ ) {
        if( filter && NULL == strstr(tests[i].name, filter) ) {
            continue;
        }
        fail_len = 0;
        fail_text[0] = 0;
        fail_count = 0;
        check_count = 0;
        t_clear_context();

        t_reset();
        tests[i].fn();
        t_clear_context();
        total_checks += check_count;

        if( fail_count > 0 ) {
            failed++;
            printf("FAIL   %s (%d/%d checks failed)\n", tests[i].name, fail_count, check_count);
            fputs(fail_text, stdout);
        }
        else {
            passed++;
            printf("ok     %-46s %d checks\n", tests[i].name, check_count);
        }
    }

    printf("\n%d passed, %d failed (%d checks)\n", passed, failed, total_checks);

    return failed ? 1 : 0;
}
