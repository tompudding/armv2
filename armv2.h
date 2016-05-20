#include <stdint.h>
#include "hw_manager.h"
#include "common.h"

#define FP    12
#define SP    13
#define LR    14
#define PC    15
#define SP_S  16
#define LR_S  17
#define SP_I  18
#define LR_I  19
#define R8_F  20
#define R9_F  21
#define R10_F 22
#define R11_F 23
#define FP_F  24
#define SP_F  25
#define LR_F  26

#define R13_S 16
#define R14_S 17
#define R13_I 18
#define R14_I 19
#define R12_F 24
#define R13_F 25
#define R14_F 26

#define NUMREGS              (27)
#define NUM_EFFECTIVE_REGS   (16)

#define PAGE_SIZE_BITS       (12)
#define PAGE_SIZE            (1<<PAGE_SIZE_BITS)
#define PAGE_MASK            (PAGE_SIZE-1)
#define NUM_PAGE_TABLES      (1<<(26 - PAGE_SIZE_BITS))
#define WORDS_PER_PAGE       (1<<(PAGE_SIZE_BITS-2))
#define MAX_MEMORY           (1<<26)
#define HW_DEVICES_MAX       (64)
#define MAX_SYMBOLS_SIZE     (0x10000)

#define PAGEOF(addr)         ((addr)>>PAGE_SIZE_BITS)
#define INPAGE(addr)         ((addr)&PAGE_MASK)
#define WORDINPAGE(addr)     (INPAGE(addr)>>2)
#define DEREF(cpu,addr)      (cpu->page_tables[PAGEOF(addr)]->memory[WORDINPAGE(addr)])
#define SETPC(cpu,newpc)     ((cpu)->regs.actual[PC] = (((cpu)->regs.actual[PC]&0xfc000003) | ((newpc)&0x03fffffc)))
#define GETPC(cpu)           ((cpu)->regs.actual[PC]&0x03fffffc)
#define GETREG(cpu,rn)       (*(cpu)->regs.effective[(rn)])
#define GETUSERREG(cpu,rn)   ((cpu)->regs.actual[(rn)])
#define SETMODE(cpu,newmode) ((cpu)->regs.actual[PC] = (((cpu)->regs.actual[PC]&0xfffffffc) | (newmode)))
#define GETMODE(cpu)         ((cpu)->regs.actual[PC]&0x3)
#define GETPSR(cpu)          ((cpu)->regs.actual[PC]&0xfc000000)
#define SETPSR(cpu,newpsr)   ((cpu)->regs.actual[PC] = (((cpu)->regs.actual[PC]&0x03ffffff) | (newpsr)))
#define GETMODEPSR(cpu)      ((cpu)->regs.actual[PC]&0xfc000003)
#define SETFLAG(cpu,flag)    ((cpu)->regs.actual[PC] |= FLAG_##flag)
#define SETPIN(cpu,pin)      ((cpu)->pins |= PIN_##pin)
#define CLEARPIN(cpu,pin)    ((cpu)->pins &= (~(PIN_##pin)))
#define SETCPUFLAG(cpu,flag) ((cpu)->flags |= FLAG_##flag)
#define CLEARCPUFLAG(cpu,flag) ((cpu)->flags &= (~FLAG_##flag))

#define PERM_READ    4
#define PERM_WRITE   2
#define PERM_EXECUTE 1

#define FLAG_N 0x80000000
#define FLAG_Z 0x40000000
#define FLAG_C 0x20000000
#define FLAG_V 0x10000000
#define FLAG_I 0x08000000
#define FLAG_F 0x04000000

#define PC_PROTECTED_BITS   ((FLAG_I|FLAG_F|3))
#define PC_UNPROTECTED_BITS (~PC_PROTECTED_BITS)

#define PIN_F  0x00000001
#define PIN_I  0x00000002

#define SWI_BREAKPOINT 0x00beeeef

#define FLAG_SET(cpu,flag) ((cpu)->regs.actual[PC]&FLAG_##flag)
#define FLAG_CLEAR(cpu,flag) (!FLAG_SET(cpu,flag))
#define PIN_ON(cpu,pin) ((cpu)->pins&PIN_##pin)
#define PIN_OFF(cpu,pin) (!PIN_ON(cpu,pin))

#define COND_EQ 0x0
#define COND_NE 0x1
#define COND_CS 0x2
#define COND_CC 0x3
#define COND_MI 0x4
#define COND_PL 0x5
#define COND_VS 0x6
#define COND_VC 0x7
#define COND_HI 0x8
#define COND_LS 0x9
#define COND_GE 0xa
#define COND_LT 0xb
#define COND_GT 0xc
#define COND_LE 0xd
#define COND_AL 0xe
#define COND_NV 0xf

#define CONDITION_BITS(x) ((x)>>28)

#define MODE_USR 0
#define MODE_FIQ 1
#define MODE_IRQ 2
#define MODE_SUP 3

#define FLAG_INIT 1
#define FLAG_WAIT 2
#define CPU_INITIALISED(cpu) ( (((cpu)->flags)&FLAG_INIT) )
#define WAITING(cpu) ( (((cpu)->flags)&FLAG_WAIT) )

enum armv2_exception {
    EXCEPT_RST                   = 0,
    EXCEPT_UNDEFINED_INSTRUCTION = 1,
    EXCEPT_SOFTWARE_INTERRUPT    = 2,
    EXCEPT_PREFETCH_ABORT        = 3,
    EXCEPT_DATA_ABORT            = 4,
    EXCEPT_ADDRESS               = 5,
    EXCEPT_IRQ                   = 6,
    EXCEPT_FIQ                   = 7,
    EXCEPT_NONE                  = 8,
    EXCEPT_BREAKPOINT            = 9,
    EXCEPT_MAX,
};

struct exception_handler {
    uint32_t mode;
    uint32_t pc;
    uint32_t flags;
    uint32_t save_reg;
};

struct regs {
    uint32_t  actual[NUMREGS];
    uint32_t *effective[NUM_EFFECTIVE_REGS];
};

typedef uint32_t (*access_callback_t)(void *extra, uint32_t addr, uint32_t value);
typedef uint32_t (*operation_callback_t)(void *extra, uint32_t arg0, uint32_t arg1);

struct page_info {
    uint32_t          *memory;
    void              *mapped_device;
    access_callback_t  read_callback;
    access_callback_t  write_callback;
    access_callback_t  read_byte_callback;
    access_callback_t  write_byte_callback;
    uint32_t           flags;
};

struct armv2_t;

struct hardware_device {
    uint32_t device_id;
    uint32_t interrupt_flag_addr;
    access_callback_t read_callback;
    access_callback_t write_callback;
    access_callback_t read_byte_callback;
    access_callback_t write_byte_callback;
    operation_callback_t operation_callback;
    struct armv2_t *cpu;
    void *extra;
};

struct hardware_mapping {
    struct hardware_device *device;
    struct hardware_mapping *next;
    uint32_t start;
    uint32_t end;
    uint32_t flags;
};

struct armv2 {
    struct regs               regs; //storage for all the registers
    uint32_t                 *physical_ram;
    uint32_t                  physical_ram_size;
    uint32_t                  num_hardware_devices;
    struct page_info         *page_tables[NUM_PAGE_TABLES];
    struct exception_handler  exception_handlers[EXCEPT_MAX];
    struct hardware_device   *hardware_devices[HW_DEVICES_MAX];
    hw_manager_t              hardware_manager;
    struct hardware_mapping  *hw_mappings;
    //the pc is broken out for efficiency, when needed accessed r15 is updated from them
    uint32_t                  pc;
    //the flags are about the processor(like initialised), not part of it
    uint32_t                  flags;
    //simulating hardware pins:
    uint32_t                  pins;
};

typedef enum armv2_exception (*instruction_handler_t)(struct armv2 *cpu,uint32_t instruction);
enum armv2_status init(struct armv2 *cpu, uint32_t memsize);
enum armv2_status load_rom(struct armv2 *cpu, const char *filename);
enum armv2_status cleanup_armv2(struct armv2 *cpu);
enum armv2_status run_armv2(struct armv2 *cpu, int32_t instructions);
enum armv2_status add_hardware(struct armv2 *cpu, struct hardware_device *device);
enum armv2_status map_memory(struct armv2 *cpu, uint32_t device_num, uint32_t start, uint32_t end);
enum armv2_status add_mapping(struct hardware_mapping **head, struct hardware_mapping *item);
enum armv2_status interrupt(struct armv2 *cpu, uint32_t hw_id, uint32_t code);

//instruction handlers
enum armv2_exception ALUInstruction                         (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception MultiplyInstruction                    (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception SwapInstruction                        (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception SingleDataTransferInstruction          (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception BranchInstruction                      (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception MultiDataTransferInstruction           (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception SoftwareInterruptInstruction           (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception CoprocessorDataTransferInstruction     (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception CoprocessorRegisterTransferInstruction (struct armv2 *cpu,uint32_t instruction);
enum armv2_exception CoprocessorDataOperationInstruction    (struct armv2 *cpu,uint32_t instruction);

#define COPROCESSOR_HW_MANAGER (1)
#define COPROCESSOR_MMU        (2)
#define COPROCESSOR_INTERRUPT_CONTROLLER (3)

typedef enum armv2_status (*coprocessor_data_operation_t)(struct armv2*,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);

enum armv2_status HwManagerDataOperation       (struct armv2 *cpu, uint32_t crm, uint32_t aux, uint32_t crd, uint32_t crn, uint32_t opcode);
enum armv2_status HwManagerRegisterTransfer    (struct armv2 *cpu, uint32_t crm, uint32_t aux, uint32_t crd, uint32_t crn, uint32_t opcode);

enum armv2_status MmuDataOperation             (struct armv2 *cpu, uint32_t crm, uint32_t aux, uint32_t crd, uint32_t crn, uint32_t opcode);
enum armv2_status MmuRegisterTransfer          (struct armv2 *cpu, uint32_t crm, uint32_t aux, uint32_t crd, uint32_t crn, uint32_t opcode);

enum armv2_status InterruptControllerOperation (struct armv2 *cpu, uint32_t crm, uint32_t aux, uint32_t crd, uint32_t crn, uint32_t opcode);
enum armv2_status InterruptControllerTransfer  (struct armv2 *cpu, uint32_t crm, uint32_t aux, uint32_t crd, uint32_t crn, uint32_t opcode);

void flog(char* fmt, ...);

#define LOG(...) printf(__VA_ARGS__)
//#define LOG(...) flog(__VA_ARGS__)
//#define LOG(...)
