import armv2
import bisect
from typing import List

registerNames = [("r%d" % i) for i in range(13)] + ["sp", "lr", "pc"]
shiftTypes = ["LSL", "LSR", "ASR", "ROR"]


def OperandShift(self, bits, type_flag):
    rm = registerNames[bits & 0xF]
    shift_type = shiftTypes[(bits >> 5) & 0x3]
    if type_flag:
        # shift amount is a register
        shift_val = None
        shift = registerNames[(bits >> 8) & 0xF]
    else:
        shift_val = (bits >> 7) & 0x1F
        shift = "#%d" % (shift_val)
    if shift_type == "ROR" and type_flag == 0 and shift_val == 0:
        return [rm, "RRX"]
    elif shift_val == 0:
        return [rm]
    else:
        # shift is nonzero
        return [rm, shift_type + " " + shift]


def RegisterList(bits):
    runs = []
    on = None
    for i in range(16):
        if on == None and (bits >> i) & 1:
            on = i
        elif on != None and not ((bits >> i) & 1):
            runs.append((on, i))
            on = None
    if on:
        runs.append((on, 16))
    regs = []
    for start, end in runs:
        if end - start <= 2:
            for r in range(start, end):
                regs.append(registerNames[r])
        else:
            regs.append("%s - %s" % (registerNames[start], registerNames[end - 1]))
    return ["{" + ",".join(regs) + "}"]


class Instruction(object):
    conditions = [
        "EQ",
        "NE",
        "CS",
        "CC",
        "MI",
        "PL",
        "VS",
        "VC",
        "HI",
        "LS",
        "GE",
        "LT",
        "GT",
        "LE",
        "",
        "NV",
    ]
    mneumonic = "UNK"
    args: List[str] = []
    sets_lr = False

    def __init__(self, addr, word, cpu):
        self.addr = addr
        self.word = word

    def ToString(self):
        mneumonic = self.mneumonic + self.conditions[(self.word >> 28) & 0xF]
        return "%4s %s" % (mneumonic.ljust(4), ", ".join(self.args))


class ALUInstruction(Instruction):
    opcodes = [
        "AND",
        "EOR",
        "SUB",
        "RSB",
        "ADD",
        "ADC",
        "SBC",
        "RSC",
        "TST",
        "TEQ",
        "CMP",
        "CMN",
        "ORR",
        "MOV",
        "BIC",
        "MVN",
    ]

    class OpCodes:
        AND = 0x0
        EOR = 0x1
        SUB = 0x2
        RSB = 0x3
        ADD = 0x4
        ADC = 0x5
        SBC = 0x6
        RSC = 0x7
        TST = 0x8
        TEQ = 0x9
        CMP = 0xA
        CMN = 0xB
        ORR = 0xC
        MOV = 0xD
        BIC = 0xE
        MVN = 0xF

    ALU_TYPE_IMM = 0x02000000

    def __init__(self, addr, word, cpu):
        super(ALUInstruction, self).__init__(addr, word, cpu)
        opcode = (word >> 21) & 0xF
        rn = (word >> 16) & 0xF
        rd = (word >> 12) & 0xF
        self.mneumonic = self.opcodes[opcode]
        op1 = registerNames[rn]
        rd = registerNames[rd]
        if word & self.ALU_TYPE_IMM:
            right_rotate = (word >> 7) & 0x1E
            if right_rotate != 0:
                val = (((word & 0xFF) << (32 - right_rotate)) | ((word & 0xFF) >> right_rotate)) & 0xFFFFFFFF
            else:
                val = word & 0xFF
            op2 = ["#0x%x" % val]
        else:
            op2 = OperandShift(addr, word & 0xFFF, word & 0x10)
        if opcode in [self.OpCodes.MOV, self.OpCodes.MVN]:
            self.args = [rd] + op2
        else:
            self.args = [rd, op1] + op2
        if opcode in [self.OpCodes.TST, self.OpCodes.TEQ, self.OpCodes.CMP, self.OpCodes.CMN]:
            # These don't set rd
            self.args = self.args[1:]


class MultiplyInstruction(Instruction):
    MUL_TYPE_MLA = 0x00200000

    def __init__(self, addr, word, cpu):
        super(MultiplyInstruction, self).__init__(addr, word, cpu)
        rm = word & 0xF
        rn = (word >> 12) & 0xF
        rs = (word >> 8) & 0xF
        rd = (word >> 16) & 0xF
        self.args = [registerNames[rd], registerNames[rm], registerNames[rs]]
        if word & self.MUL_TYPE_MLA:
            self.mneumonic = "MLA"
            self.args.append(registerNames[rn])
        else:
            self.mneumonic = "MUL"


class SwapInstruction(Instruction):
    LOAD_BYTE = 0x00400000

    def __init__(self, addr, word, cpu):
        super(SwapInstruction, self).__init__(addr, word, cpu)
        rm = word & 0xF
        rd = (word >> 12) & 0xF
        rn = (word >> 16) & 0xF
        if word & self.LOAD_BYTE:
            self.mneumonic = "SWPB"
        else:
            self.mneumonic = "SWP"
        self.args = [registerNames[rd], registerNames[rm], "[%s]" % registerNames[rn]]


class SingleDataTransferInstruction(Instruction):
    SDT_REGISTER = 0x02000000
    SDT_WRITE_BACK = 0x00200000
    SDT_PREINDEX = 0x01000000
    SDT_LDR = 0x00100000
    SDT_OFFSET_ADD = 0x00800000
    SDT_LOAD_BYTE = 0x00400000

    def __init__(self, addr, word, cpu):
        super(SingleDataTransferInstruction, self).__init__(addr, word, cpu)
        rd = (word >> 12) & 0xF
        rn = (word >> 16) & 0xF
        rd = registerNames[rd]
        if not word & self.SDT_REGISTER:
            offset = word & 0xFFF
            if not word & self.SDT_OFFSET_ADD:
                offset *= -1
            op2 = ["#0x%x" % offset]
        else:
            op2 = OperandShift(addr, word & 0xFFF, 0)
            # FIXME, incorporate the negativeness
        if word & self.SDT_LDR:
            self.mneumonic = "LDR"
        else:
            self.mneumonic = "STR"
        if word & self.SDT_LOAD_BYTE:
            self.mneumonic += "B"
        if word & self.SDT_WRITE_BACK:
            rd += "!"

        if rn == 0xF and not word & self.SDT_REGISTER:
            pos = addr + 8 + offset
            try:
                val = cpu.memw[addr + 8 + offset]
            except:
                val = 0
            self.args = [rd] + ["=0x%x" % val]
            return

        rn = registerNames[rn]
        op2.insert(0, rn)

        op2[0] = "[" + op2[0]
        if word & self.SDT_PREINDEX:
            op2[-1] = op2[-1] + "]"
        else:
            op2[0] = op2[0] + "]"
        self.args = [rd] + op2


class BranchInstruction(Instruction):
    def __init__(self, addr, word, cpu, symbols):
        super(BranchInstruction, self).__init__(addr, word, cpu)
        if (word >> 24) & 1:
            self.sets_lr = True
            self.mneumonic = "BL"
        else:
            self.mneumonic = "B"
        offset = (word & 0xFFFFFF) << 2
        target = (addr + offset + 8) & 0xFFFFFF
        if symbols is None:
            sym_addr = sym_name = None
            index = 0
        else:
            sym_name, offset = symbols.get_symbol_and_offset(target)

        if offset == 0:
            arg = "0x%x(%s)" % (target, sym_name)
        elif sym_name and offset < 0x1000:  # any more and it's probably not really in that symbol
            arg = "0x%x(%s + 0x%x)" % (target, sym_name, offset)
        else:
            arg = "#0x%x" % target
        self.args = [arg]


class MultiDataTransferInstruction(Instruction):
    MDT_LDM = 0x00100000
    MDT_WRITE_BACK = 0x00200000
    MDT_HAT = 0x00400000
    MDT_OFFSET_ADD = 0x00800000
    MDT_PREINDEX = 0x01000000

    def __init__(self, addr, word, cpu):
        super(MultiDataTransferInstruction, self).__init__(addr, word, cpu)
        if word & self.MDT_LDM:
            self.mneumonic = "LDM"
        else:
            self.mneumonic = "STM"
        if word & self.MDT_OFFSET_ADD:
            self.mneumonic += "I"
        else:
            self.mneumonic += "D"
        if word & self.MDT_PREINDEX:
            self.mneumonic += "B"
        else:
            self.mneumonic += "A"
        rn = registerNames[(word >> 16) & 0xF] + "!" if word & self.MDT_WRITE_BACK else ""
        self.args = [rn] + RegisterList(word & 0xFFFF)
        # shorthands for push and pop...
        if rn == "sp!":
            if self.mneumonic == "LDMIA":
                self.mneumonic = "POP"
                self.args = self.args[1:]
            elif self.mneumonic == "STMDB":
                self.mneumonic = "PUSH"
                self.args = self.args[1:]


class SoftwareInterruptInstruction(Instruction):
    mneumonic = "SWI"

    def __init__(self, addr, word, cpu):
        super(SoftwareInterruptInstruction, self).__init__(addr, word, cpu)
        self.args = ["#0x%x" % (word & 0xFFFFFF)]


class CoprocessorDataTransferInstruction(Instruction):
    pass


class CoprocessorInstruction(Instruction):
    mneumonic = ""

    def __init__(self, addr, word, cpu):
        super(CoprocessorInstruction, self).__init__(addr, word, cpu)
        self.crm = (word >> 0) & 0xF
        self.aux = (word >> 5) & 0xF
        self.proc_num = (word >> 8) & 0xF
        self.crd = (word >> 12) & 0xF
        self.crn = (word >> 16) & 0xF
        self.opcode = (word >> 20) & 0xF
        self.args = ["%x" % self.proc_num, "#%x" % self.opcode] + [
            ("CR%d") % n for n in (self.crd, self.crn, self.crm)
        ]


class CoprocessorRegisterTransferInstruction(CoprocessorInstruction):
    mneumonic = "MCR"

    def __init__(self, addr, word, cpu):
        super(CoprocessorRegisterTransferInstruction, self).__init__(addr, word, cpu)
        if self.opcode & 1:
            self.mneumonic = "MRC"
        self.args = ["%x" % self.proc_num, "#%x" % self.opcode, "R%d" % self.crd] + [
            ("CR%d") % n for n in (self.crn, self.crm)
        ]


class CoprocessorDataOperationInstruction(CoprocessorInstruction):
    mneumonic = "CDP"


def InstructionFactory(addr, word, cpu=None, symbols=None):
    tag = (word >> 26) & 3
    handler = None
    if tag == 0:
        if (word & 0x0FC000F0) == 0x00000090:
            handler = MultiplyInstruction
        elif (word & 0x0FB00FF0) == 0x01000090:
            handler = SwapInstruction
        else:
            handler = ALUInstruction
    elif tag == 1:
        handler = SingleDataTransferInstruction
    elif tag == 2:
        if word & 0x02000000:
            return BranchInstruction(addr, word, cpu, symbols)
        else:
            handler = MultiDataTransferInstruction
    else:
        if (word & 0x0F000000) == 0x0F000000:
            handler = SoftwareInterruptInstruction
        elif (word & 0x02000000) == 0:
            handler = CoprocessorDataTransferInstruction
        elif word & 0x10:
            handler = CoprocessorRegisterTransferInstruction
        else:
            handler = CoprocessorDataOperationInstruction
    return handler(addr, word, cpu)


def Disassemble(cpu, breakpoints, start, end, symbols):
    for addr in range(start, end, 4):
        if addr in breakpoints:
            word = breakpoints[addr]
        elif (addr & 3) == 0:
            word = cpu.memw[addr]
        else:
            word = 0
            for byte in ((ord(cpu.mem[addr + i]) << ((3 - i) * 8)) for i in range(4)):
                word |= byte
        yield InstructionFactory(addr, word, cpu, symbols)


def sets_lr(word):
    instruction = InstructionFactory(0, word)
    return instruction.sets_lr
