import armv2
import pygame
import threading
import traceback
import signal

class Keyboard(armv2.Device):
    """
    A Keyboard device. The memory map looks like

    0x00 - 0x20 : bitmask of currently pressed ascii keys
    0x20 - 0xa0 : 128 byte ring buffer
    0xa0 - 0xa1 : byte indicating ringbuffer position
    """
    id = 0x41414141
    bitmask_start    = 0
    ringbuffer_start = 0x20
    ringbuffer_pos   = 0xa0

    class InterruptCodes:
        KEY_DOWN = 0
        KEY_UP   = 1

    def __init__(self, cpu):
        super(Keyboard,self).__init__(cpu)
        self.ring_buffer = [0 for i in xrange(128)]
        self.pos = 0
        self.key_state = 0
        armv2.DebugLog('keyboard keyboard keyboard!\n')

    def KeyDown(self,key):
        armv2.DebugLog('key down ' + str(key))
        self.key_state |= (1<<key)
        self.ring_buffer[self.ring_buffer[self.pos]] = key
        self.pos += 1
        if self.pos == len(self.ring_buffer):
            self.pos = 0
        self.cpu.Interrupt(self.id, self.InterruptCodes.KEY_DOWN)

    def KeyUp(self,key):
        armv2.DebugLog('key up ' + str(key))
        self.key_state &= ~(1<<key)
        self.cpu.Interrupt(self.id, self.InterruptCodes.KEY_UP)

    def readCallback(self,addr,value):
        armv2.DebugLog('keyboard reader %x %x\n' % (addr,value))
        if addr < self.ringbuffer_start:
            #It's a state request
            return (self.key_state>>(8*addr)&0xffffffff)
        elif addr < self.ringbuffer_pos:
            pos = addr - self.ringbuffer_start
            bytes = [self.ring_buffer[pos + i % len(self.ring_buffer)] for i in xrange(4)]
            return (bytes[0]) | (bytes[1]<<8) | (bytes[2]<<16) | (bytes[3]<<24)
        elif addr == ringbuffer_pos:
            return self.pos

        return 0

    def writeCallback(self,addr,value):
        armv2.DebugLog('keyboard writer %x %x\n' % (addr,value))
        return 0

class MemPassthrough(object):
    def __init__(self,cv,accessor):
        self.cv = cv
        self.accessor = accessor

    def __getitem__(self,index):
        with self.cv:
            return self.accessor.__getitem__(index)

    def __setitem__(self,index,values):
        with self.cv:
            return self.accessor.__setitem__(index,values)

    def __len__(self):
        with self.cv:
            return self.accessor.__len__()

class Machine:
    def __init__(self,cpu_size,cpu_rom):
        self.cpu          = armv2.Armv2(size = cpu_size,filename = cpu_rom)
        self.hardware     = []
        self.running      = True
        self.steps_to_run = 0
        #I'm not sure why I need a regular lock here rather than the default (A RLock), but with the default
        #I get weird deadlocks on KeyboardInterrupt
        self.cv           = threading.Condition(threading.Lock())
        self.mem          = MemPassthrough(self.cv,self.cpu.mem)
        self.memw         = MemPassthrough(self.cv,self.cpu.memw)
        self.thread       = threading.Thread(target = self.threadMain)
        self.status       = None
        self.thread.start()

    @property
    def regs(self):
        with self.cv:
            return self.cpu.regs

    @regs.setter
    def regs(self,value):
        with self.cv:
            self.cpu.regs = value

    @property
    def stepping(self):
        with self.cv:
            return self.steps_to_run != 0

    @property
    def mode(self):
        with self.cv:
            return self.cpu.mode

    @property
    def pc(self):
        with self.cv:
            return self.cpu.pc

    def threadMain(self):
        with self.cv:
            while self.running:
                while self.running and self.steps_to_run == 0:
                    self.cv.wait(1)
                if not self.running:
                    break
                self.status = self.cpu.Step(self.steps_to_run)
                self.steps_to_run = 0
                self.cv.notify()

    def Step(self,num):
        with self.cv:
            self.steps_to_run = num
            self.cv.notify()

    def StepAndWait(self,num):
        self.Step(num)
        with self.cv:
            while self.running:
                while self.running and self.steps_to_run != 0:
                    self.cv.wait(1)
                if not self.running:
                    break
                return self.status

    def AddHardware(self,device,name = None):
        with self.cv:
            self.cpu.AddHardware(device)
        self.hardware.append(device)
        if name != None:
            setattr(self,name,device)

    def Delete(self):
        with self.cv:
            self.running = False
            self.cv.notify()
        armv2.DebugLog('joining thread')
        self.thread.join()
        armv2.DebugLog('Killed')

    def Interrupt(self, hw_id, code):
        armv2.DebugLog('Interrupt from device %s with code %s' % (hw_id, code))
        #self.cpu.interrupt(hw_id, code)
