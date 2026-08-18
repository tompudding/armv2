/* Instruction encoders, so the tests can say what they mean rather than
 * carrying a pile of magic hex constants. Field layouts are from the ARM2
 * datasheet (VL86C010 / ARM 2 Data Sheet, section 4).
 */
#ifndef ARMV2_TESTS_ENCODE_H
#define ARMV2_TESTS_ENCODE_H

#include <stdint.h>

/* Condition codes */
#define C_EQ 0x0u
#define C_NE 0x1u
#define C_CS 0x2u
#define C_CC 0x3u
#define C_MI 0x4u
#define C_PL 0x5u
#define C_VS 0x6u
#define C_VC 0x7u
#define C_HI 0x8u
#define C_LS 0x9u
#define C_GE 0xau
#define C_LT 0xbu
#define C_GT 0xcu
#define C_LE 0xdu
#define C_AL 0xeu
#define C_NV 0xfu

/* Data processing opcodes */
#define OP_AND 0x0u
#define OP_EOR 0x1u
#define OP_SUB 0x2u
#define OP_RSB 0x3u
#define OP_ADD 0x4u
#define OP_ADC 0x5u
#define OP_SBC 0x6u
#define OP_RSC 0x7u
#define OP_TST 0x8u
#define OP_TEQ 0x9u
#define OP_CMP 0xau
#define OP_CMN 0xbu
#define OP_ORR 0xcu
#define OP_MOV 0xdu
#define OP_BIC 0xeu
#define OP_MVN 0xfu

/* Shift types */
#define SH_LSL 0x0u
#define SH_LSR 0x1u
#define SH_ASR 0x2u
#define SH_ROR 0x3u

#define R_SP 13u
#define R_LR 14u
#define R_PC 15u

/* cond 00 1 opcode S rn rd rotate imm8 -- operand 2 is imm8 ROR (2 * rotate) */
static inline uint32_t dp_imm(uint32_t cond, uint32_t opcode, uint32_t s, uint32_t rn, uint32_t rd,
                              uint32_t rotate, uint32_t imm8)
{
    return (cond << 28) | (1u << 25) | (opcode << 21) | (s << 20) | (rn << 16) | (rd << 12) |
           (rotate << 8) | imm8;
}

/* cond 00 0 opcode S rn rd shift_amount shift_type 0 rm */
static inline uint32_t dp_reg(uint32_t cond, uint32_t opcode, uint32_t s, uint32_t rn, uint32_t rd,
                              uint32_t rm, uint32_t shift_type, uint32_t shift_amount)
{
    return (cond << 28) | (opcode << 21) | (s << 20) | (rn << 16) | (rd << 12) |
           (shift_amount << 7) | (shift_type << 5) | rm;
}

/* cond 00 0 opcode S rn rd rs 0 shift_type 1 rm -- shift amount from rs */
static inline uint32_t dp_regshift(uint32_t cond, uint32_t opcode, uint32_t s, uint32_t rn, uint32_t rd,
                                   uint32_t rm, uint32_t shift_type, uint32_t rs)
{
    return (cond << 28) | (opcode << 21) | (s << 20) | (rn << 16) | (rd << 12) |
           (rs << 8) | (shift_type << 5) | 0x10u | rm;
}

/* cond 000000 A S rd rn rs 1001 rm */
static inline uint32_t mul(uint32_t cond, uint32_t accumulate, uint32_t s, uint32_t rd, uint32_t rn,
                           uint32_t rs, uint32_t rm)
{
    return (cond << 28) | (accumulate << 21) | (s << 20) | (rd << 16) | (rn << 12) |
           (rs << 8) | 0x90u | rm;
}

/* cond 00010 B 00 rn rd 00001001 rm */
static inline uint32_t swp(uint32_t cond, uint32_t byte, uint32_t rn, uint32_t rd, uint32_t rm)
{
    return (cond << 28) | 0x01000090u | (byte << 22) | (rn << 16) | (rd << 12) | rm;
}

/* cond 01 I P U B W L rn rd offset */
static inline uint32_t sdt(uint32_t cond, uint32_t is_reg, uint32_t pre, uint32_t up, uint32_t byte,
                           uint32_t writeback, uint32_t load, uint32_t rn, uint32_t rd, uint32_t offset)
{
    return (cond << 28) | (1u << 26) | (is_reg << 25) | (pre << 24) | (up << 23) | (byte << 22) |
           (writeback << 21) | (load << 20) | (rn << 16) | (rd << 12) | offset;
}

/* The register form of an ldr/str offset: shift_amount shift_type 0 rm */
static inline uint32_t sdt_offset_reg(uint32_t rm, uint32_t shift_type, uint32_t shift_amount)
{
    return (shift_amount << 7) | (shift_type << 5) | rm;
}

/* cond 100 P U S W L rn register_list */
static inline uint32_t mdt(uint32_t cond, uint32_t pre, uint32_t up, uint32_t psr, uint32_t writeback,
                           uint32_t load, uint32_t rn, uint32_t reglist)
{
    return (cond << 28) | (1u << 27) | (pre << 24) | (up << 23) | (psr << 22) | (writeback << 21) |
           (load << 20) | (rn << 16) | reglist;
}

/* cond 101 L offset24, where offset24 = (target - (pc_of_branch + 8)) / 4 */
static inline uint32_t branch(uint32_t cond, uint32_t link, uint32_t from, uint32_t to)
{
    uint32_t offset = ((to - (from + 8)) >> 2) & 0xffffffu;

    return (cond << 28) | (0x5u << 25) | (link << 24) | offset;
}

/* cond 1111 comment24 */
static inline uint32_t swi(uint32_t cond, uint32_t comment)
{
    return (cond << 28) | 0x0f000000u | (comment & 0x00ffffffu);
}

/* cond 1110 cp_opcode crn crd cp_num cp_aux 0 crm */
static inline uint32_t cdp(uint32_t cond, uint32_t cp_num, uint32_t cp_opcode, uint32_t crd,
                           uint32_t crn, uint32_t crm, uint32_t cp_aux)
{
    return (cond << 28) | 0x0e000000u | (cp_opcode << 20) | (crn << 16) | (crd << 12) |
           (cp_num << 8) | (cp_aux << 5) | crm;
}

/* cond 1110 cp_opcode L crn rd cp_num cp_aux 1 crm */
static inline uint32_t mrc_mcr(uint32_t cond, uint32_t load, uint32_t cp_num, uint32_t cp_opcode,
                               uint32_t rd, uint32_t crn, uint32_t crm, uint32_t cp_aux)
{
    return (cond << 28) | 0x0e000010u | (cp_opcode << 21) | (load << 20) | (crn << 16) | (rd << 12) |
           (cp_num << 8) | (cp_aux << 5) | crm;
}

/* Common shorthands */
#define MOV_IMM(rd, imm)        dp_imm(C_AL, OP_MOV, 0, 0, (rd), 0, (imm))
#define MOV_REG(rd, rm)         dp_reg(C_AL, OP_MOV, 0, 0, (rd), (rm), SH_LSL, 0)
#define NOP                     dp_reg(C_AL, OP_MOV, 0, 0, 0, 0, SH_LSL, 0)

#endif
