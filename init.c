#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <errno.h>
#include <arpa/inet.h>

#include "armv2.h"
#include "memory_map.h"

enum armv2_status init(struct armv2 *cpu, uint32_t memsize)
{
    uint32_t num_pages = 0;
    enum armv2_status retval = ARMV2STATUS_OK;

    if( NULL == cpu ) {
        LOG("%s error, NULL cpu\n",__func__);
        return ARMV2STATUS_INVALID_CPUSTATE;
    }

    //round memsize up to a full page
    memsize = (memsize + PAGE_MASK) & (~PAGE_MASK);
    if( memsize & PAGE_MASK ) {
        LOG("Page mask error\n");
        return ARMV2STATUS_VALUE_ERROR;
    }

    num_pages = memsize >> PAGE_SIZE_BITS;
    if( num_pages > NUM_PAGE_TABLES ) {
        LOG("Serious page table error, too many requested\n");
        return ARMV2STATUS_VALUE_ERROR;
    }

    if( memsize > MAX_MEMORY ) {
        LOG("%s error, request memory size(%u) too big\n", __func__, memsize);
        return ARMV2STATUS_VALUE_ERROR;
    }

    memset(cpu, 0, sizeof(struct armv2));
    /* cpu->physical_ram = malloc(memsize); */
    /* if( NULL == cpu->physical_ram ) { */
    /*     cpu->physical_ram = NULL; */
    /*     return ARMV2STATUS_MEMORY_ERROR; */
    /* } */

    cpu->physical_ram_size = memsize;
    cpu->free_ram = cpu->physical_ram_size;
    LOG("Have %u pages %u\n", num_pages, memsize);
    //memset(cpu->physical_ram, 0, memsize);

    reset_breakpoints(cpu);
    reset_watchpoints(cpu);

    //map the physical ram at 0
    //we could malloc all the page tables for it at once, but all the extra bookkeeping would
    //be annoying

    /* for(uint32_t i = 0; i < num_pages; i++) { */
    /*     struct page_info *page_info = calloc(1, sizeof(struct page_info)); */
    /*     if(NULL == page_info) { */
    /*         retval = ARMV2STATUS_MEMORY_ERROR; */
    /*         goto cleanup; */
    /*     } */

    /*     page_info->memory = cpu->physical_ram + i * WORDS_PER_PAGE; */
    /*     page_info->flags |= (PERM_READ | PERM_EXECUTE | PERM_WRITE); */

    /*     if(i == 0) { */
    /*         //the first page is never writable, we'll put the boot rom there. */
    /*         page_info->flags &= (~PERM_WRITE); */
    /*     } */
    /*     cpu->page_tables[i] = page_info; */
    /* } */

    cpu->flags = FLAG_INIT;
    //Start with the interrupt flag on so we don't get interrupts until we're ready
    cpu->regs.actual[PC] = MODE_SUP | FLAG_I;
    cpu->pins = 0;
    cpu->pc = -4; //hack because it gets incremented on the first loop

    for(uint32_t i = 0;i < NUM_EFFECTIVE_REGS; i++) {
        cpu->regs.effective[i] = &cpu->regs.actual[i];
    }

    //We start in supervisor mode bank those registers
    for(uint32_t i=13; i < 15; i++) {
        cpu->regs.effective[i] = &cpu->regs.actual[R13_S + (i - 13)];
    }

    //Set up the exception conditions
    for(uint32_t i=0;i<EXCEPT_NONE;i++) {
        cpu->exception_handlers[i].mode     = MODE_SUP;
        cpu->exception_handlers[i].pc       = i * 4;
        cpu->exception_handlers[i].flags    = FLAG_I;
        cpu->exception_handlers[i].save_reg = LR_S;
    }

    cpu->exception_handlers[EXCEPT_IRQ].mode     = MODE_IRQ;
    cpu->exception_handlers[EXCEPT_IRQ].save_reg = LR_I;
    cpu->exception_handlers[EXCEPT_FIQ].mode     = MODE_FIQ;
    cpu->exception_handlers[EXCEPT_FIQ].save_reg = LR_F;
    cpu->exception_handlers[EXCEPT_FIQ].flags   |= FLAG_F;
    cpu->exception_handlers[EXCEPT_RST].flags   |= FLAG_F;

    if( retval != ARMV2STATUS_OK ) {
        cleanup_armv2(cpu);
    }

    return retval;
}

static void clean_bitmask(uint64_t **bm) {
    if( NULL != bm && NULL != *bm ) {
        munmap(*bm, BP_BITMASK_SIZE);
        *bm = NULL;
    }
}

enum armv2_status cleanup_armv2(struct armv2 *cpu)
{
    LOG("ARMV2 cleanup\n");
    if( NULL == cpu ) {
        return ARMV2STATUS_OK;
    }
    clean_bitmask(&cpu->breakpoint_bitmask);

    for(int i = 0; i < MAX_WATCHPOINT; i++) {
        clean_bitmask(cpu->watchpoint_bitmask + i);
    }

    for( uint32_t i = 0;i < NUM_PAGE_TABLES; i++ ) {
        if(NULL != cpu->page_tables[i]) {
            free(cpu->page_tables[i]);
            cpu->page_tables[i] = NULL;
        }
    }
    return ARMV2STATUS_OK;
}

static enum armv2_status load_section( struct armv2 *cpu, uint32_t start, uint32_t end,
                                       FILE *f, ssize_t *size_out, size_t *written_out )
{
    uint32_t section_length = 0;
    ssize_t  read_bytes     = 0;
    ssize_t  size           = *size_out;
    size_t written = 0;

    if( 0 != INPAGE(start) ) {
        //We only want to start loading sections in at page boundaries
        LOG("Error starting section off page boundary\n");
        return ARMV2STATUS_INVALID_PAGE;
    }

    uint32_t page_num = PAGEOF(start);

    read_bytes = fread(&section_length, sizeof(section_length), 1, f);
    if( read_bytes != 1 ) {
        LOG("Error reading opening length\n");
        return ARMV2STATUS_IO_ERROR;
    }

    section_length = htonl( section_length );

    size -= sizeof(section_length);

    if( section_length > (end - start) ) {
        LOG("Error, section length of %08x would take us past end %08x\n", section_length, end );
        return ARMV2STATUS_IO_ERROR;
    }

    if( section_length > size ) {
        LOG("Error, not enough data for section length 0x%x (0x%zx bytes remaining)\n", section_length, size);
        return ARMV2STATUS_IO_ERROR;
    }

    size -= section_length;

    while( section_length > 0 ) {
        size_t to_read = section_length > PAGE_SIZE ? PAGE_SIZE : section_length;
        if( NULL == cpu->page_tables[page_num] ) {
            enum armv2_status result = fault(cpu, page_num * PAGE_SIZE);
            if( ARMV2STATUS_OK !=  result) {
                LOG("Error %d fauling in page %08x\n", result, page_num * PAGE_SIZE);
                return ARMV2STATUS_INVALID_PAGE;
            }
        }
        read_bytes = fread(cpu->page_tables[page_num]->memory, 1, to_read,f);

        if( read_bytes != to_read ) {
            if( read_bytes != section_length ) {
                LOG("Error %d %zd %zd %d\n",page_num, read_bytes, size, section_length);
                return ARMV2STATUS_IO_ERROR;
            }
        }
        page_num++;
        written += read_bytes;
        section_length -= to_read;
    }

    *size_out = size;
    if( written_out ) {
        *written_out = written;
    }

    return ARMV2STATUS_OK;
}

enum armv2_status load_rom(struct armv2 *cpu, const char *filename)
{
    FILE              *f          = NULL;
    enum armv2_status  retval     = ARMV2STATUS_OK;
    struct stat        st         = {0};
    if(NULL == cpu) {
        return ARMV2STATUS_OK;
    }

    if( !(cpu->flags&FLAG_INIT) ) {
        return ARMV2STATUS_INVALID_CPUSTATE;
    }

    if( 0 != stat(filename,&st) ) {
        return ARMV2STATUS_IO_ERROR;
    }

    ssize_t size = st.st_size;
    if( size < 0x28 ) {
        //28 is the bare minimum for a rom, as the vectors go up to
        //0x20, and then you need at least one instruction, and the
        //first word is the length
        return ARMV2STATUS_IO_ERROR;
    }

    f = fopen(filename,"rb");
    if( NULL == f ) {
        LOG("Error opening %s\n",filename);
        return ARMV2STATUS_IO_ERROR;
    }
    size_t written = 0;

    retval = load_section( cpu, BOOT_ROM_ADDR, TAPE_ADDR, f, &size, &written );
    if( ARMV2STATUS_OK != retval ) {
        LOG("Error loading boot rom section\n");
        goto close_file;
    }
    cpu->boot_rom.start = BOOT_ROM_ADDR;
    cpu->boot_rom.end = cpu->boot_rom.start + written;

    retval = load_section( cpu, SYMBOLS_ADDR, SYMBOLS_ADDR + MAX_SYMBOLS_SIZE, f, &size, NULL );
    if( ARMV2STATUS_OK != retval ) {
        LOG("Error loading boot rom symbols\n");
        goto close_file;
    }

close_file:
    fclose(f);
    return retval;
}

enum armv2_status add_hardware(struct armv2 *cpu, struct hardware_device *device)
{
    if( NULL == cpu || NULL == device || !CPU_INITIALISED(cpu) ) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    if( cpu->num_hardware_devices >= HW_DEVICES_MAX ) {
        return ARMV2STATUS_MAX_HW;
    }

    //There's space, so let's add it
    cpu->hardware_devices[cpu->num_hardware_devices++] = device;
    //initialise the interrupt address here

    return ARMV2STATUS_OK;
}

enum armv2_status map_memory(struct armv2 *cpu, uint32_t device_num, uint32_t start, uint32_t end)
{
    if( NULL == cpu || end <= start ) {
        return ARMV2STATUS_INVALID_ARGS;
    }
    if( device_num >= cpu->num_hardware_devices ) {
        return ARMV2STATUS_NO_SUCH_DEVICE;
    }
    if(NULL == cpu->hardware_devices[device_num]) {
        return ARMV2STATUS_INVALID_CPUSTATE;
    }

    uint32_t page_pos    = 0;
    uint32_t page_start  = PAGEOF(start);
    uint32_t page_end    = PAGEOF(end);
    struct hardware_mapping hw_mapping = {0};

    if(start&PAGE_MASK                  ||
       end  &PAGE_MASK                  ||
       page_start == 0                  ||
       page_end == 0                    ||
       page_start >= NUM_PAGE_TABLES    ||
       page_end >= NUM_PAGE_TABLES
       //page_start == INTERRUPT_PAGE_NUM ||
       //page_end == INTERRUPT_PAGE_NUM  ) {
        ) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    //First we need to know if all of the requested memory is available for mapping. That means
    //it must not have been mapped already, and it may not be the zero page
    for(page_pos = page_start; page_pos < page_end; page_pos++) {
        struct page_info *page;
        if( page_pos >= NUM_PAGE_TABLES ) { // || page_pos == INTERRUPT_PAGE_NUM) {
            return ARMV2STATUS_MEMORY_ERROR;
        }
        page = cpu->page_tables[page_pos];
        if( page == NULL ) {
            //That's OK, that means this page is currently completely unmapped. We can make a page just for this
            continue;
        }
        if( page->read_callback || page->write_callback ||
           page->read_byte_callback || page->write_byte_callback ) {
            return ARMV2STATUS_ALREADY_MAPPED;
        }
    }

    hw_mapping.device = cpu->hardware_devices[device_num];
    //If we get here then the entire range is free, so we can go ahead and fill it in
    for(page_pos = page_start; page_pos < page_end; page_pos++) {
        struct page_info *page = cpu->page_tables[page_pos];

        if(NULL == page) {
            //we need a new page
            page = calloc(1, sizeof(struct page_info));
            if( NULL == page ) {
                //I don't think I'm leaving anything untidied up by returning here
                return ARMV2STATUS_MEMORY_ERROR;
            }
            page->flags = (PERM_READ | PERM_EXECUTE | PERM_WRITE);
            page->memory = NULL;
            if( hw_mapping.device ) {
                page->mapped_device = hw_mapping.device;
            }
            cpu->page_tables[page_pos] = page;
        }
        //Already checked everything's OK, and we're single threaded, so this should be ok I think...

        page->read_callback       = hw_mapping.device->read_callback;
        page->write_callback      = hw_mapping.device->write_callback;
        page->read_byte_callback  = hw_mapping.device->read_byte_callback;
        page->write_byte_callback = hw_mapping.device->write_byte_callback;
    }

    if( hw_mapping.device ) {
        hw_mapping.device->mapped.start = start;
        hw_mapping.device->mapped.end = end;
    }

    hw_mapping.start = start;
    hw_mapping.end   = end;
    hw_mapping.flags = 0; //maybe use these later
    add_mapping(&(cpu->hw_mappings), &hw_mapping);

    return ARMV2STATUS_OK;
}

enum armv2_status add_mapping(struct hardware_mapping **head, struct hardware_mapping *item)
{
    if( NULL == head ) {
        return ARMV2STATUS_INVALID_ARGS;
    }
    item->next = *head;
    *head = item;
    return ARMV2STATUS_OK;
}

enum armv2_status interrupt(struct armv2 *cpu, uint32_t hw_id, uint32_t code)
{
    if( NULL == cpu || !CPU_INITIALISED(cpu) ) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    //TODO: some kind of interrupt queue, for now drop interrupts that happen while we're doing this
    if( PIN_OFF(cpu,I) && FLAG_CLEAR(cpu,I) ) {
        cpu->hardware_manager.last_interrupt_id = hw_id;
        cpu->hardware_manager.last_interrupt_code = code;
        SETPIN(cpu,I);
    }

    return ARMV2STATUS_OK;
}

enum armv2_status set_breakpoint(struct armv2 *cpu, uint32_t addr)
{
    if( NULL == cpu || !CPU_INITIALISED(cpu) || NULL == cpu->breakpoint_bitmask ) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    SET_BREAKPOINT(cpu, addr);

    return ARMV2STATUS_OK;
}

enum armv2_status unset_breakpoint(struct armv2 *cpu, uint32_t addr)
{
    if( NULL == cpu || !CPU_INITIALISED(cpu) || NULL == cpu->breakpoint_bitmask ) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    CLEAR_BREAKPOINT(cpu, addr);

    return ARMV2STATUS_OK;
}

enum armv2_status set_watchpoint(struct armv2 *cpu, enum watchpoint_type type, uint32_t addr)
{
    if( NULL == cpu || !CPU_INITIALISED(cpu) || NULL == cpu->breakpoint_bitmask ) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    switch( type ) {
    case READ_WATCHPOINT:
        SET_READ_WATCHPOINT(cpu, addr);
        break;

    case WRITE_WATCHPOINT:
        SET_WRITE_WATCHPOINT(cpu, addr);
        break;

    case ACCESS_WATCHPOINT:
        SET_READ_WATCHPOINT(cpu, addr);
        SET_WRITE_WATCHPOINT(cpu, addr);
        break;
    }

    return ARMV2STATUS_OK;
}

enum armv2_status unset_watchpoint(struct armv2 *cpu, enum watchpoint_type type, uint32_t addr)
{
    if( NULL == cpu || !CPU_INITIALISED(cpu) || NULL == cpu->breakpoint_bitmask ) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    switch( type ) {
    case READ_WATCHPOINT:
        CLEAR_READ_WATCHPOINT(cpu, addr);
        break;

    case WRITE_WATCHPOINT:
        CLEAR_WRITE_WATCHPOINT(cpu, addr);
        break;

    case ACCESS_WATCHPOINT:
        CLEAR_READ_WATCHPOINT(cpu, addr);
        CLEAR_WRITE_WATCHPOINT(cpu, addr);
        break;
    }

    return ARMV2STATUS_OK;
}


enum armv2_status reset_breakpoints(struct armv2 *cpu)
{
    clean_bitmask(&cpu->breakpoint_bitmask);
    //We want a bit for every addressable word, i.e one every 32 bits
    cpu->breakpoint_bitmask = mmap(NULL, BP_BITMASK_SIZE, PROT_READ | PROT_WRITE,
                                   MAP_ANONYMOUS | MAP_SHARED, -1, 0);
    if( MAP_FAILED == cpu->breakpoint_bitmask ) {
        cpu->breakpoint_bitmask = NULL;
        return ARMV2STATUS_MEMORY_ERROR;
    }

    return ARMV2STATUS_OK;
}
enum armv2_status reset_watchpoints(struct armv2 *cpu)
{
    //Do the same thing for watchpoint masks
    for(int i = 0; i < MAX_WATCHPOINT; i++) {
        clean_bitmask(cpu->watchpoint_bitmask + i);
        cpu->watchpoint_bitmask[i] = mmap(NULL, BP_BITMASK_SIZE, PROT_READ | PROT_WRITE,
                                          MAP_ANONYMOUS | MAP_SHARED, -1, 0);
        if( MAP_FAILED == cpu->watchpoint_bitmask[i] ) {
            cpu->watchpoint_bitmask[i] = NULL;
            goto cleanup;
        }
    }

    return ARMV2STATUS_OK;
cleanup:
    for(int i = 0; i < MAX_WATCHPOINT; i++) {
        clean_bitmask(cpu->watchpoint_bitmask + i);
    }

    return ARMV2STATUS_MEMORY_ERROR;
}
