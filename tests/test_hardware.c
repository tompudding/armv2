/* Hardware devices mapped into the address space.
 *
 * A device supplies read and write callbacks and gets a range of the address
 * space assigned to it, so that loads and stores in that range turn into calls
 * rather than memory accesses. Offsets handed to the callbacks are relative to
 * the start of the device's mapping, not to the page.
 */
#include <string.h>

#include "harness.h"
#include "encode.h"
#include "hw_manager.h"

#define HW_ADDR      0x00010000u
#define HW_PAGES     2
#define HW_END       (HW_ADDR + HW_PAGES * PAGE_SIZE)
#define DEVICE_ID    0x5eedfaceu

struct fake_device {
    uint32_t words[8];
    uint32_t last_offset;
    uint32_t last_value;
    int      word_reads, word_writes, byte_reads, byte_writes;
};

static struct fake_device state;
static struct hardware_device device;

static uint32_t fake_read(void *extra, uint32_t offset, uint32_t value)
{
    struct fake_device *dev = extra;

    (void)value;
    dev->last_offset = offset;
    dev->word_reads++;

    return 0xd0000000u | offset;
}

static uint32_t fake_write(void *extra, uint32_t offset, uint32_t value)
{
    struct fake_device *dev = extra;

    dev->last_offset = offset;
    dev->last_value = value;
    dev->word_writes++;

    return 0;
}

static uint32_t fake_read_byte(void *extra, uint32_t offset, uint32_t value)
{
    struct fake_device *dev = extra;

    (void)value;
    dev->last_offset = offset;
    dev->byte_reads++;

    return 0xb0 | (offset & 0xf);
}

static uint32_t fake_write_byte(void *extra, uint32_t offset, uint32_t value)
{
    struct fake_device *dev = extra;

    dev->last_offset = offset;
    dev->last_value = value;
    dev->byte_writes++;

    return 0;
}

/* Attach the device without mapping it anywhere. The runner has already reset
 * the cpu, which zeroes the hardware tables, so this runs per test. */
static void make_device(void)
{
    memset(&state, 0, sizeof(state));
    memset(&device, 0, sizeof(device));

    device.device_id           = DEVICE_ID;
    device.read_callback       = fake_read;
    device.write_callback      = fake_write;
    device.read_byte_callback  = fake_read_byte;
    device.write_byte_callback = fake_write_byte;
    device.extra               = &state;

    CHECK_MSG(ARMV2STATUS_OK == add_hardware(cpu, &device), "could not attach the device");
}

/* ...and give it HW_ADDR upwards */
static void attach_device(void)
{
    make_device();
    CHECK_MSG(ARMV2STATUS_OK == map_memory(cpu, 0, HW_ADDR, HW_END), "could not map the device");
}

TEST(device_word_read_calls_the_device)
{
    attach_device();
    t_setreg(1, HW_ADDR);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));       /* ldr r0, [r1] */

    CHECK_REG(0, 0xd0000000);
    CHECK_HEX("word reads", (uint32_t)state.word_reads, 1);
    CHECK_HEX("offset", state.last_offset, 0);
}

TEST(device_word_write_calls_the_device)
{
    attach_device();
    t_setreg(0, 0x12345678);
    t_setreg(1, HW_ADDR);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 8));       /* str r0, [r1, #8] */

    CHECK_HEX("word writes", (uint32_t)state.word_writes, 1);
    CHECK_HEX("offset", state.last_offset, 8);
    CHECK_HEX("value", state.last_value, 0x12345678);
}

TEST(device_byte_access_uses_the_byte_callbacks)
{
    attach_device();
    t_setreg(1, HW_ADDR);

    t_exec(sdt(C_AL, 0, 1, 1, 1, 0, 1, 1, 0, 5));       /* ldrb r0, [r1, #5] */
    CHECK_REG(0, 0xb5);
    CHECK_HEX("byte reads", (uint32_t)state.byte_reads, 1);
    CHECK_HEX("offset", state.last_offset, 5);

    t_setreg(0, 0x000000ab);
    t_exec(sdt(C_AL, 0, 1, 1, 1, 0, 0, 1, 0, 6));       /* strb r0, [r1, #6] */
    CHECK_HEX("byte writes", (uint32_t)state.byte_writes, 1);
    CHECK_HEX("offset", state.last_offset, 6);
    CHECK_HEX("value", state.last_value, 0xab);
    /* the word callbacks must not be dragged into a byte access */
    CHECK_HEX("word writes", (uint32_t)state.word_writes, 0);
}

/* The offset is measured from the start of the device's mapping, so a device
 * covering several pages sees one flat range */
TEST(device_offsets_are_relative_to_the_mapping)
{
    attach_device();
    t_setreg(1, HW_ADDR + PAGE_SIZE + 0x20);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));       /* ldr r0, [r1] */

    CHECK_HEX("offset", state.last_offset, PAGE_SIZE + 0x20);
    CHECK_REG(0, 0xd0000000 | (PAGE_SIZE + 0x20));
}

/* Unaligned word accesses to a device abort before the device sees anything */
TEST(device_unaligned_word_access_aborts)
{
    attach_device();
    t_setreg(1, HW_ADDR + 2);

    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 1, 1, 0, 0));       /* ldr r0, [r1] */

    CHECK_HEX("exception vector", t_nextpc(), g_vector_table[EXCEPT_DATA_ABORT]);
    CHECK_HEX("word reads", (uint32_t)state.word_reads, 0);
}

TEST(device_is_reachable_by_ldm_and_stm)
{
    attach_device();
    t_setreg(0, 0x11111111);
    t_setreg(2, 0x22222222);
    t_setreg(1, HW_ADDR);

    /* stmia r1, {r0, r2} */
    t_exec(mdt(C_AL, 0, 1, 0, 0, 0, 1, (1u << 0) | (1u << 2)));

    CHECK_HEX("word writes", (uint32_t)state.word_writes, 2);
    CHECK_HEX("offset", state.last_offset, 4);
    CHECK_HEX("value", state.last_value, 0x22222222);

    /* ldmia r1, {r3, r4} */
    t_exec(mdt(C_AL, 0, 1, 0, 0, 1, 1, (1u << 3) | (1u << 4)));
    CHECK_REG(3, 0xd0000000);
    CHECK_REG(4, 0xd0000004);
}

/* The hardware manager coprocessor is how the boot rom finds its devices */
TEST(hardware_manager_sees_the_device)
{
    attach_device();

    /* cdp p1, NUM_DEVICES, cr0, cr0, cr0 ; mrc r0, cr0 */
    t_exec(cdp(C_AL, 1, NUM_DEVICES, 0, 0, 0, 0));
    t_exec(mrc_mcr(C_AL, 1, 1, 0, 0, 0, 0, 0));
    CHECK_REG(0, 1);

    /* device 0's id: put 0 in cr0, ask, read cr0 back */
    t_setreg(1, 0);
    t_exec(mrc_mcr(C_AL, 0, 1, 0, 1, 0, 0, 0));        /* mcr r1 -> cr0 */
    t_exec(cdp(C_AL, 1, GET_DEVICE_ID, 0, 0, 0, 0));
    t_exec(mrc_mcr(C_AL, 1, 1, 0, 2, 0, 0, 0));        /* mrc cr0 -> r2 */
    CHECK_REG(2, DEVICE_ID);
}

/* Mapping is exclusive: a second device cannot take the same range */
TEST(mapping_the_same_range_twice_fails)
{
    static struct hardware_device second;

    attach_device();
    memset(&second, 0, sizeof(second));
    second.device_id      = 0x1234;
    second.read_callback  = fake_read;
    second.write_callback = fake_write;
    second.extra          = &state;

    CHECK_MSG(ARMV2STATUS_OK == add_hardware(cpu, &second), "could not attach the second device");
    CHECK_MSG(ARMV2STATUS_ALREADY_MAPPED == map_memory(cpu, 1, HW_ADDR, HW_END),
              "mapping an already mapped range should be refused");
}

TEST(mapping_rejects_bad_ranges)
{
    attach_device();

    CHECK_MSG(ARMV2STATUS_INVALID_ARGS == map_memory(cpu, 0, HW_ADDR + 1, HW_END),
              "an unaligned start should be refused");
    CHECK_MSG(ARMV2STATUS_INVALID_ARGS == map_memory(cpu, 0, 0, PAGE_SIZE),
              "page zero should never be handed to a device");
    CHECK_MSG(ARMV2STATUS_NO_SUCH_DEVICE == map_memory(cpu, 4, HW_ADDR, HW_END),
              "a device number that does not exist should be refused");
}

/* A device may only be given address space that nothing has touched yet. That
 * is what keeps mapped_device set on every device page, and with it the
 * mapping relative offsets the callbacks are handed. */
TEST(mapping_over_an_existing_page_is_refused)
{
    make_device();

    /* something touches the second page of the range first */
    t_write(HW_ADDR + PAGE_SIZE, 0x99999999);

    CHECK_MSG(ARMV2STATUS_ALREADY_MAPPED == map_memory(cpu, 0, HW_ADDR, HW_END),
              "mapping over a page that already exists should be refused");

    /* and the refusal left nothing half done: the first page of the range is
     * still ordinary memory that the device knows nothing about */
    t_setreg(0, 0x12345678);
    t_setreg(1, HW_ADDR);
    t_exec(sdt(C_AL, 0, 1, 1, 0, 0, 0, 1, 0, 0));       /* str r0, [r1] */

    CHECK_HEX("word writes", (uint32_t)state.word_writes, 0);
    CHECK_MEM(HW_ADDR, 0x12345678);
}
