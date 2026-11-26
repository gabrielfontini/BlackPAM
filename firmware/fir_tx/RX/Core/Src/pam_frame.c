/*
 * pam_frame.c — quadro da Seção 4.2 do enunciado.
 *
 *   [140 pulso][256 níveis][48 bits de início][payload 100 000 bits PRBS-15]
 *
 * O TX chama pam_symgen_next() a cada símbolo. O RX usa uma cópia idêntica do
 * gerador para saber o nível e os bits esperados de cada símbolo.
 */
#include "pam_frame.h"

static const uint8_t k_level_pat2[PAM_TRAIN_LEVEL_LEN] = {0, 1, 0, 0, 1, 1, 0, 1};
static const uint8_t k_level_pat4[PAM_TRAIN_LEVEL_LEN] = {0, 1, 0, 3, 2, 3, 1, 2};

uint32_t pam_preamble_syms(pam_mod_t m) { return PAM_PRE_BITS / pam_bits_per_sym(m); }
uint32_t pam_payload_syms(pam_mod_t m)  { return PAM_PAYLOAD_BITS / pam_bits_per_sym(m); }
uint32_t pam_total_syms(pam_mod_t m)
{
    return PAM_TRAIN_SYMS + pam_preamble_syms(m) + pam_payload_syms(m);
}

uint8_t pam_preamble_bit(uint32_t i)
{
    if (i < PAM_PRE_ALT_BITS)
        return (uint8_t)(i & 1u);                     /* 0,1,0,1,... começa em 0 */
    i -= PAM_PRE_ALT_BITS;                            /* 0..31, MSB primeiro      */
    return (uint8_t)((PAM_SYNC_WORD >> (31u - i)) & 1u);
}

uint8_t pam_train_level(pam_mod_t m, uint32_t j)
{
    if (j < PAM_TRAIN_PULSE_SYMS)
        return ((j % PAM_TRAIN_PULSE_LEN) == 3u) ? pam_level_max(m) : 0u;
    j -= PAM_TRAIN_PULSE_SYMS;
    return (m == PAM4) ? k_level_pat4[j % PAM_TRAIN_LEVEL_LEN]
                       : k_level_pat2[j % PAM_TRAIN_LEVEL_LEN];
}

void pam_symgen_init(pam_symgen_t *g, pam_mod_t mod)
{
    g->mod = mod;
    g->idx = 0;
    g->seg = PAM_SEG_PULSE;
    g->nbits = 0;
    g->bits[0] = g->bits[1] = 0;
    prbs15_reset(&g->prbs);
}

int pam_symgen_next(pam_symgen_t *g)
{
    const uint32_t npre = pam_preamble_syms(g->mod);
    const uint32_t npay = pam_payload_syms(g->mod);
    uint32_t j = g->idx;
    uint8_t level;

    if (j < PAM_TRAIN_SYMS) {
        g->seg = (j < PAM_TRAIN_PULSE_SYMS) ? PAM_SEG_PULSE : PAM_SEG_LEVELS;
        g->nbits = 0;
        level = pam_train_level(g->mod, j);
    } else if (j < PAM_TRAIN_SYMS + npre) {
        uint32_t i = j - PAM_TRAIN_SYMS;
        g->seg = PAM_SEG_PREAMBLE;
        if (g->mod == PAM4) {
            g->bits[0] = pam_preamble_bit(2u * i);
            g->bits[1] = pam_preamble_bit(2u * i + 1u);
            g->nbits = 2;
            level = pam_bits_to_level4(g->bits[0], g->bits[1]);
        } else {
            g->bits[0] = pam_preamble_bit(i);
            g->nbits = 1;
            level = g->bits[0];
        }
    } else if (j < PAM_TRAIN_SYMS + npre + npay) {
        if (j == PAM_TRAIN_SYMS + npre)
            prbs15_reset(&g->prbs);               /* reinicia antes do payload */
        g->seg = PAM_SEG_PAYLOAD;
        if (g->mod == PAM4) {
            g->bits[0] = prbs15_next(&g->prbs);
            g->bits[1] = prbs15_next(&g->prbs);
            g->nbits = 2;
            level = pam_bits_to_level4(g->bits[0], g->bits[1]);
        } else {
            g->bits[0] = prbs15_next(&g->prbs);
            g->nbits = 1;
            level = g->bits[0];
        }
    } else {
        g->seg = PAM_SEG_END;
        g->nbits = 0;
        return -1;
    }
    g->idx++;
    return (int)level;
}
