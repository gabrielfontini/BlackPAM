/*
 * pam_rx_core.h — processamento do RX símbolo a símbolo (SEM HAL).
 *
 * Recebe as 8 leituras a_j[0..7] de cada símbolo, na ordem em que chegaram,
 * e executa as Seções 4.3, 4.5.1, 4.5.2, 4.6 e 4.7 do enunciado:
 *   1) 140 símbolos de pulso  -> linha de base b_c, pesos p_c[k], E_c
 *   2) 256 símbolos de níveis -> k*, centros, limiares e margens dos 2 detectores
 *   3) 48 bits de início      -> confirma enquadramento (sincronismo)
 *   4) payload                -> contagem de erros de bit e de símbolo (BER/SER)
 */
#ifndef PAM_RX_CORE_H
#define PAM_RX_CORE_H

#include <stdint.h>
#include "pam_config.h"
#include "pam_frame.h"

typedef enum {
    RX_ST_PULSE = 0, RX_ST_LEVELS, RX_ST_PREAMBLE, RX_ST_PAYLOAD, RX_ST_DONE
} pam_rx_state_t;

typedef struct {
    pam_mod_t mod;
    uint8_t   M;                 /* 2 ou 4                                         */
    pam_rx_state_t st;
    pam_symgen_t ref;            /* cópia do gerador do TX (níveis/bits esperados) */
    uint32_t  j;                 /* símbolos processados                           */

    /* ---- registro bruto do treinamento (396 x 8 leituras) ---- */
    uint16_t  train_raw[PAM_TRAIN_SYMS][PAM_SPS];
    float     train_z[PAM_TRAIN_SYMS];          /* z_c,j (só nos 256 de níveis)   */

    /* ---- filtro casado (Seção 4.5.1) ---- */
    uint32_t  base_sum;          /* soma das 160 leituras do último zero antes de A */
    uint32_t  A_sum[PAM_SPS];    /* soma das 20 leituras de A em cada k             */
    float     bc;                /* linha de base (código ADC)                      */
    float     pc[PAM_SPS];       /* pesos medidos p_c[k]                            */
    float     Ec;                /* sum p_c[k]^2                                    */
    uint8_t   pulse_ok;          /* 0 se todos os p_c forem zero                    */

    /* ---- calibração (Seções 4.3 e 4.5.2) ---- */
    int32_t   sep_k[PAM_SPS];    /* menor separação entre vizinhos em cada k (ADC)  */
    uint8_t   kstar;
    float     cen_u[4], cen_z[4];/* centros dos detectores                          */
    float     thr_u[3], thr_z[3];/* limiares (1 em PAM-2, 3 em PAM-4)               */
    int32_t   marg_u;            /* margem da amostra única (códigos ADC)           */
    float     marg_z;            /* margem do filtro casado (escala z)              */
    uint8_t   marg_u_pair, marg_z_pair; /* par (l, l+1) que deu a menor margem     */
    uint8_t   calib_ok;          /* centros crescentes?                             */

    /* ---- início de quadro ---- */
    uint8_t   pre_err_u, pre_err_z;  /* bits errados nos 48 de início            */
    uint8_t   sync_ok;

    /* ---- payload ---- */
    uint32_t  pay_bits, pay_syms;
    uint32_t  bit_err_u, bit_err_z;
    uint32_t  sym_err_u, sym_err_z;

    /* ---- registros para PSD/olho ---- */
    uint16_t  psd[PAM_PSD_SAMPLES];  /* 8 192 leituras consecutivas do payload    */
    uint8_t   psd_level[PAM_PSD_SYMS]; /* nível transmitido de cada símbolo copiado */
    uint32_t  psd_n;

    /* ---- uma janela real do payload para a defesa ---- */
    uint16_t  ex_a[PAM_SPS];
    float     ex_z;
    uint32_t  ex_j;
    uint8_t   ex_level;
} pam_rx_t;

void pam_rx_init(pam_rx_t *rx, pam_mod_t mod);
/* Processa um símbolo. Devolve 1 quando o quadro inteiro já foi processado. */
int  pam_rx_symbol(pam_rx_t *rx, const uint16_t a[PAM_SPS]);

/* Saída do filtro casado para 8 leituras quaisquer (Eq. 2 do enunciado). */
float pam_rx_matched(const pam_rx_t *rx, const uint16_t a[PAM_SPS]);

#endif /* PAM_RX_CORE_H */
