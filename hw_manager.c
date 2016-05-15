#include "armv2.h"
#include <stdio.h>
#include <stdarg.h>
#include "hw_manager.h"

uint32_t time_data[2] = {0x203b2836,0xb8b0a7b6};

static enum armv2_status device_operation(armv2_t *cpu, uint32_t device_num, uint32_t arg0, uint32_t arg1, uint32_t *result) {
    hardware_device_t *device = cpu->hardware_devices[device_num];
    if(NULL == cpu || NULL == result) {
        return ARMV2STATUS_INVALID_ARGS;
    }
    if(device_num >= cpu->num_hardware_devices) {
        return ARMV2STATUS_NO_SUCH_DEVICE;
    }
    if(NULL == cpu->hardware_devices[device_num]) {
        return ARMV2STATUS_INVALID_CPUSTATE;
    }

    if(NULL == device->operation_callback) {
        return ARMV2STATUS_DEVICE_ERROR;
    }
    *result = device->operation_callback(device->extra, arg0, arg1);

    return ARMV2STATUS_OK;
}

enum armv2_status HwManagerDataOperation(armv2_t *cpu, uint32_t crm, uint32_t aux, uint32_t crd, uint32_t crn, uint32_t opcode) {
    if(NULL == cpu               ||
       crd >= HW_MANAGER_NUMREGS ||
       crm >= HW_MANAGER_NUMREGS ||
       crn >= HW_MANAGER_NUMREGS ||
       aux >= HW_MANAGER_NUMREGS) {
        return ARMV2STATUS_INVALID_ARGS;
    }
    switch((hw_manager_opcode_t)opcode) {
    case NUM_DEVICES:
        /* put the current number of devices in to cr0 */
        cpu->hardware_manager.regs[crd] = cpu->num_hardware_devices;
        return ARMV2STATUS_OK;
    case MAP_MEMORY:
        /* Assign hardware device stored in crd the memory from crm up to crn. Store error code in aux */
        {
            uint32_t device_num  = cpu->hardware_manager.regs[crd];
            uint32_t mem_start   = cpu->hardware_manager.regs[crn];
            uint32_t mem_end     = cpu->hardware_manager.regs[crm];
            enum armv2_status result = map_memory(cpu,device_num,mem_start,mem_end);
            //FIXME: set aux here on error
            return result;
        }
    case GET_DEVICE_ID:
        /* Get the device id of a given device and store it in CR0 */
        /* FIXME: store the result in a chosen register rather than just using cr0 */
        {
            uint32_t device_num = cpu->hardware_manager.regs[crd];
            if(device_num >= cpu->num_hardware_devices) {
                return ARMV2STATUS_NO_SUCH_DEVICE;
            }
            hardware_device_t *device = cpu->hardware_devices[device_num];
            if(NULL == device) {
                return ARMV2STATUS_NO_SUCH_DEVICE;
            }
            cpu->hardware_manager.regs[0] = device->device_id;
            return ARMV2STATUS_OK;
        }
    case INTERRUPT_DATA:
        /* put the interrupt device into cr0 and the interrupt code into cr1 */
        cpu->hardware_manager.regs[0] = cpu->hardware_manager.last_interrupt_id;
        cpu->hardware_manager.regs[1] = cpu->hardware_manager.last_interrupt_code;
        return ARMV2STATUS_OK;

    case WAIT_FOR_INTERRUPT:
        //LOG("Wait for interrupt! %d %d\n",FLAG_CLEAR(cpu,I),FLAG_CLEAR(cpu,F));
        if(FLAG_CLEAR(cpu,I) && FLAG_CLEAR(cpu,F)) {
            //only start a wait if we're not already in an interrupt
            SETCPUFLAG(cpu,WAIT);
        }
        return ARMV2STATUS_OK;

    case GETTIME:
        cpu->hardware_manager.regs[0] = time_data[0] ^ 0x41414141;
        cpu->hardware_manager.regs[1] = time_data[1] ^ 0xc1c2c3c4;
        return ARMV2STATUS_OK;

    case DEVICE_OPERATION: {
        uint32_t device_num  = cpu->hardware_manager.regs[crd];
        uint32_t arg0        = cpu->hardware_manager.regs[crn];
        uint32_t arg1        = cpu->hardware_manager.regs[crm];
        uint32_t result_word = 0;
        enum armv2_status result = device_operation(cpu,device_num,arg0,arg1, &result_word);
        //FIXME: set aux here on error
        if(ARMV2STATUS_OK == result) {
            cpu->hardware_manager.regs[crd] = result_word;
        }
        return result;
    }


    default:
        return ARMV2STATUS_UNKNOWN_OPCODE;
    }
    return ARMV2STATUS_UNIVERSE_BROKEN;
}

enum armv2_status HwManagerRegisterTransfer(armv2_t *cpu, uint32_t crm, uint32_t aux, uint32_t rd, uint32_t crn, uint32_t opcode) {
    int load = opcode&1;
    opcode >>= 1;
    if(NULL == cpu) {
        return ARMV2STATUS_INVALID_ARGS;
    }
    if(crn >= HW_MANAGER_NUMREGS) {
        return ARMV2STATUS_INVALID_ARGS;
    }

    switch((hw_register_opcode_t)opcode) {
    case MOV_REGISTER:
        /* Move to / from a coprocessor register */
        if(load) {
            uint32_t value = cpu->hardware_manager.regs[crn];
            if(rd == 15) {
                //only set the flags
                SETPSR(cpu,value);
            }
            else {
                GETREG(cpu,rd) = value;
            }
        }
        else {
            cpu->hardware_manager.regs[crn] = GETREG(cpu,rd);
        }
        return ARMV2STATUS_OK;
    default:
        return ARMV2STATUS_UNKNOWN_OPCODE;
    }
    return ARMV2STATUS_UNIVERSE_BROKEN;
}
