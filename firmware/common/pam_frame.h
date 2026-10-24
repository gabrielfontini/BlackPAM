/*
 * pam_frame.h — geração do quadro PAM (PRBS-15, treinamento, início de quadro,
 * payload) e mapeamento Gray. Código SEM dependência de HAL: o mesmo arquivo é
 * usado no TX (para gerar os níveis) e no RX (para saber o que foi enviado).
 */
#ifndef PAM_FRAME_H
#define PAM_FRAME_H

#include <stdint.h>
#include "pam_config.h"

typedef enum { PAM2 = 2, PAM4 = 4 } pam_mod_t;

typedef enum {
    PAM_SEG_PULSE = 0,   /* 140 símbolos 0,0,0,A,0,0,0           */
    PAM_SEG_LEVELS,      /* 256 símbolos de calibração de níveis */
    PAM_SEG_PREAMBLE,    /* 48 bits: 16 alternados + 0xD391C5A7  */
    PAM_SEG_PAYLOAD,     /* 100 000 bits da PRBS-15              */
    PAM_SEG_END
} pam_seg_t;

/* ---------- PRBS-15: b0..b14 = 1 ; b(n+15) = b(n+14) XOR b(n) ---------- */
typedef struct { uint16_t s; } prbs15_t;     /* bit0 = b(n) ... bit14 = b(n+14) */

static inline void prbs15_reset(prbs15_t *p) { p->s = 0x7FFFu; }
static inline uint8_t prbs15_next(prbs15_t *p)
{
    uint8_t out = (uint8_t)(p->s & 1u);
    uint16_t nb = (uint16_t)(((p->s >> 14) ^ p->s) & 1u);
    p->s = (uint16_t)((p->s >> 1) | (nb << 14));
    return out;
}

/* ---------- Gray PAM-4 (Tabela 1): 00->0, 01->1, 11->2, 10->3 ---------- */
static inline uint8_t pam_bits_to_level4(uint8_t b_first, uint8_t b_second)
{
    return b_first ? (b_second ? 2u : 3u) : (b_second ? 1u : 0u);
}
static inline void pam_level4_to_bits(uint8_t level, uint8_t *b_first, uint8_t *b_second)
{
    static const uint8_t f[4] = {0, 0, 1, 1};
    static const uint8_t s[4] = {0, 1, 1, 0};
    *b_first = f[level & 3u];
    *b_second = s[level & 3u];
}

/* Nível mais alto ("A") e número de bits por símbolo */
static inline uint8_t pam_level_max(pam_mod_t m) { return (m == PAM4) ? 3u : 1u; }
static inline uint8_t pam_bits_per_sym(pam_mod_t m) { return (m == PAM4) ? 2u : 1u; }

/* Valor de TIM1_CCR1 para cada nível (Apêndice A.1, ARR = 2) */
static inline uint8_t pam_level_to_ccr(pam_mod_t m, uint8_t level)
{
    return (m == PAM4) ? level : (level ? 3u : 0u);
}

uint32_t pam_preamble_syms(pam_mod_t m);   /* 48 (PAM-2) ou 24 (PAM-4)        */
uint32_t pam_payload_syms(pam_mod_t m);    /* 100 000 ou 50 000               */
uint32_t pam_total_syms(pam_mod_t m);      /* 100 444 ou 50 420               */
uint8_t  pam_preamble_bit(uint32_t i);     /* bit i (0..47) do início do quadro */
uint8_t  pam_train_level(pam_mod_t m, uint32_t j); /* nível do símbolo j < 396 */

/* ---------- Gerador sequencial de símbolos (TX e referência do RX) ---------- */
typedef struct {
    pam_mod_t mod;
    uint32_t  idx;        /* índice do próximo símbolo                         */
    prbs15_t  prbs;
    pam_seg_t seg;        /* segmento do último símbolo gerado                 */
    uint8_t   bits[2];    /* bits carregados pelo último símbolo (preâmbulo/payload) */
    uint8_t   nbits;      /* 0 no treinamento, 1 em PAM-2, 2 em PAM-4          */
} pam_symgen_t;

void pam_symgen_init(pam_symgen_t *g, pam_mod_t mod);
/* Devolve o nível (0..M-1) do próximo símbolo, ou -1 quando o quadro terminou. */
int  pam_symgen_next(pam_symgen_t *g);

#endif /* PAM_FRAME_H */
