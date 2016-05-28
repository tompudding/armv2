cimport carmv2
from libc.stdint cimport uint32_t, int64_t
from libc.stdlib cimport malloc, free
import itertools
import threading
import thread

NUMREGS            = carmv2.NUMREGS
NUM_EFFECTIVE_REGS = carmv2.NUM_EFFECTIVE_REGS
MAX_26BIT          = 1<<26
SWI_BREAKPOINT     = carmv2.SWI_BREAKPOINT

class CpuExceptions:
    Reset                = carmv2.EXCEPT_RST
    UndefinedInstruction = carmv2.EXCEPT_UNDEFINED_INSTRUCTION
    SoftwareInterrupt    = carmv2.EXCEPT_SOFTWARE_INTERRUPT
    PrefetchAboprt       = carmv2.EXCEPT_PREFETCH_ABORT
    DataAbort            = carmv2.EXCEPT_DATA_ABORT
    Address              = carmv2.EXCEPT_ADDRESS
    Irq                  = carmv2.EXCEPT_IRQ
    Fiq                  = carmv2.EXCEPT_FIQ
    Breakpoint           = carmv2.EXCEPT_BREAKPOINT

class Status:
    Ok               = carmv2.ARMV2STATUS_OK
    InvalidCpuState  = carmv2.ARMV2STATUS_INVALID_CPUSTATE
    MemoryError      = carmv2.ARMV2STATUS_MEMORY_ERROR
    ValueError       = carmv2.ARMV2STATUS_VALUE_ERROR
    IoError          = carmv2.ARMV2STATUS_IO_ERROR
    Breakpoint       = carmv2.ARMV2STATUS_BREAKPOINT
    WaitForInterrupt = carmv2.ARMV2STATUS_WAIT_FOR_INTERRUPT

class Pins:
    Interrupt     = carmv2.PIN_I
    FastInterrupt = carmv2.PIN_F

def PAGEOF(addr):
    return addr>>carmv2.PAGE_SIZE_BITS

def INPAGE(addr):
    return addr&carmv2.PAGE_MASK

def WORDINPAGE(addr):
    return INPAGE(addr)>>2

class AccessError(Exception):
    pass

class Registers(object):
    mapping = {'fp' : 12,
               'sp' : 13,
               'lr' : 14,
               'pc' : 15}
    for i in xrange(NUM_EFFECTIVE_REGS):
        mapping['r%d' % i] = i

    def __init__(self,cpu):
        self.cpu = cpu

    def __getattr__(self,attr):
        try:
            index = self.mapping[attr]
        except KeyError:
            raise AttributeError()
        return self.cpu.getregs(index)

    def __setattr__(self,attr,value):
        try:
            index = self.mapping[attr]
        except KeyError:
            super(Registers,self).__setattr__(attr,value)
            return
        self.cpu.setregs(index,value)

    def __getitem__(self,index):
        if isinstance(index,slice):
            indices = index.indices(NUM_EFFECTIVE_REGS)
            return [self.cpu.getregs(i) for i in xrange(*indices)]
        return self.cpu.getregs(index)

    def __setitem__(self,index,value):
        if isinstance(index,slice):
            indices = index.indices(NUM_EFFECTIVE_REGS)
            for i in xrange(*indices):
                self.cpu.setregs(i,value[i])
            return
        return self.cpu.setregs(index,value)

    def __repr__(self):
        return repr(self[:])

class ByteMemory(object):
    def __init__(self,cpu):
        self.cpu    = cpu
        self.getter = self.cpu.getbyte
        self.setter = self.cpu.setbyte

    def __getitem__(self,index):
        if isinstance(index,slice):
            indices = index.indices(MAX_26BIT)
            indices = xrange(*indices)
        else:
            indices = (index,)
        return ''.join(chr(self.getter(index)) for index in indices)

    def __setitem__(self,index,values):
        if isinstance(index,slice):
            indices = index.indices(MAX_26BIT)
            indices = xrange(*indices)
        else:
            indices = (index,)
            values  = (values,)
        try:
            for i,v in itertools.izip_longest(indices,values):
                self.setter(i,ord(v))
        except TypeError:
            raise ValueError('Wrong values sequence length')

    def __len__(self):
        return MAX_26BIT

class WordMemory(object):
    def __init__(self,cpu):
        self.cpu    = cpu
        self.getter = self.cpu.getword
        self.setter = self.cpu.setword

    def __getitem__(self,index):
        if isinstance(index,slice):
            indices = index.indices(MAX_26BIT)
            indices = xrange(*indices)
        else:
            indices = (index,)
        if len(indices) == 1:
            return self.getter(index)
        else:
            return [self.getter(index) for index in indices]

    def __setitem__(self,index,values):
        if isinstance(index,slice):
            indices = index.indices(MAX_26BIT)
            indices = xrange(*indices)
        else:
            indices = (index,)
            values  = (values,)
        try:
            for i,v in itertools.izip_longest(indices,values):
                self.setter(i,v)
        except TypeError:
            raise ValueError('Wrong values sequence length')

    def __len__(self):
        return MAX_26BIT>>2


#cdef void readCallback(void *device,uint32_t addr, uint32_t value):


cdef class Device:
    id            = None
    readCallback  = None
    writeCallback = None
    cdef carmv2.hardware_device *cdevice

    def __cinit__(self, *args, **kwargs):
        self.cdevice = <carmv2.hardware_device*>malloc(sizeof(carmv2.hardware_device))
        self.cdevice.device_id = self.id
        self.cdevice.read_callback = <carmv2.access_callback_t>self.read;
        self.cdevice.write_callback = <carmv2.access_callback_t>self.write;
        self.cdevice.read_byte_callback = <carmv2.access_callback_t>self.read_byte;
        self.cdevice.write_byte_callback = <carmv2.access_callback_t>self.write_byte;
        self.cdevice.operation_callback = <carmv2.operation_callback_t>self.operation;
        self.cdevice.cpu = <carmv2.armv2*>args[0].cpu
        if self.cdevice == NULL:
            raise MemoryError()

    cdef uint32_t read(self,uint32_t addr, uint32_t value) nogil:
        with gil:
            if self.readCallback:
                return self.readCallback(addr,value)
            return 0

    cdef uint32_t write(self,uint32_t addr, uint32_t value) nogil:
        with gil:
            if self.writeCallback:
                return self.writeCallback(int(addr),int(value))

            return 0

    cdef uint32_t read_byte(self,uint32_t addr, uint32_t value) nogil:
        with gil:
            if self.readByteCallback:
                return self.readByteCallback(addr,value)
            return 0

    cdef uint32_t write_byte(self,uint32_t addr, uint32_t value) nogil:
        with gil:
            if self.writeByteCallback:
                return self.writeByteCallback(int(addr),int(value))

            return 0

    cdef uint32_t operation(self, uint32_t arg0, uint32_t arg1) nogil:
        with gil:
            if self.operationCallback:
                return self.operationCallback(int(arg0), int(arg1))

    def __dealloc__(self):
        if self.cdevice != NULL:
            free(self.cdevice)

    def __init__(self,cpu):
        self.cpu = cpu

    #def __del__(self):
    #    secpu.RemoveDevice(self)

    cdef carmv2.hardware_device *GetDevice(self):
        return self.cdevice

cdef class Armv2:
    cdef carmv2.armv2 *cpu
    cdef public regs
    cdef public mem
    cdef public memw
    cdef public memsize
    cdef public hardware

    def __cinit__(self, *args, **kwargs):
        self.cpu = <carmv2.armv2*>malloc(sizeof(carmv2.armv2))
        if self.cpu == NULL:
            raise MemoryError()

    def __dealloc__(self):
        if self.cpu != NULL:
            carmv2.cleanup_armv2(self.cpu)
            free(self.cpu)
            self.cpu = NULL

    def getregs(self,index):
        if index >= NUM_EFFECTIVE_REGS:
            raise IndexError()
        return int(self.cpu.regs.effective[index][0])

    def setregs(self,index,value):
        if index >= NUM_EFFECTIVE_REGS:
            raise IndexError()
        self.cpu.regs.effective[index][0] = value
        if index == carmv2.PC:
            self.cpu.pc = int((0xfffffffc + (value&0x3ffffffc))&0xffffffff)

    def getbyte(self,addr):
        cdef uint32_t word = self.getword(addr)
        cdef uint32_t b = (addr&3)<<3
        return (word>>b)&0xff;

    def setbyte(self,addr,value):
        cdef uint32_t word = self.getword(addr)
        cdef uint32_t b = (addr&3)<<3
        cdef uint32_t mask = 0xff<<b
        cdef uint32_t new_word = (word&(~mask)) | ((value&0xff)<<b)
        self.setword(addr,new_word)

    def getword(self,addr):
        if addr >= MAX_26BIT or addr < 0:
            #raise IndexError()
            return 0

        cdef carmv2.page_info *page = self.cpu.page_tables[PAGEOF(addr)]
        if NULL == page:
            #raise AccessError()
            return 0

        return page.memory[WORDINPAGE(addr)]

    def setword(self,addr,value):
        if addr >= MAX_26BIT:
            return 0#raise IndexError()

        cdef carmv2.page_info *page = self.cpu.page_tables[PAGEOF(addr)]
        if NULL == page:
            raise AccessError()

        page.memory[WORDINPAGE(addr)] = int(value)

    @property
    def pc(self):
        #The first thing the run loop does is add 4 to PC, so PC is effectively 4 greater than
        #it appears to be
        return self.cpu.pc + 4

    @property
    def pins(self):
        return self.cpu.pins

    @property
    def mode(self):
        return self.regs.pc&3

    def __init__(self,size,filename = None):
        cdef carmv2.armv2_status result
        cdef uint32_t mem = size
        result = carmv2.init(self.cpu,mem)
        self.regs = Registers(self)
        self.memsize = size
        self.mem  = ByteMemory(self)
        self.memw = WordMemory(self)
        self.hardware = []
        if result != carmv2.ARMV2STATUS_OK:
            raise ValueError()
        if filename != None:
            self.LoadROM(filename)

    def LoadROM(self,filename):
        result = carmv2.load_rom(self.cpu,filename)
        if result != carmv2.ARMV2STATUS_OK:
            raise ValueError()

    def Step(self,number = None):
        cdef uint32_t result
        cdef carmv2.armv2 *cpu = self.cpu
        cdef uint32_t instructions = -1 if number == None else number
        with nogil:
            result = carmv2.run_armv2(cpu, instructions)
        #right now can only return OK or BREAKPOINT, but we don't care either way...
        return result

    def AddHardware(self,Device device,name = None):
        #FIXME: Does this do reference counting properly? We need it to increment, and we need a corresponding
        #decrement somewhere else in the code
        device.cdevice.extra = <void*>device
        result = carmv2.add_hardware(self.cpu,device.cdevice)
        if result != carmv2.ARMV2STATUS_OK:
            raise ValueError()
        self.hardware.append(device)

    def Interrupt(self, hw_id, code):
        result = carmv2.interrupt(self.cpu, <uint32_t>hw_id, <uint32_t>code)
        if result != carmv2.ARMV2STATUS_OK:
            raise ValueError()

debugf = None
log_lock = threading.Lock()
def DebugLog(message):
    global debugf
    return 
    message = str(thread.get_ident()) + ' ' + message
    with log_lock:
        if debugf == None:
            debugf = open('/tmp/pyarmv2.log','wb')
        if not message.endswith('\n'):
            message += '\n'
        debugf.write(message)
        debugf.flush()
