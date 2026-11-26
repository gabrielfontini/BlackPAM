/*
 * pam_config.h — parâmetros comuns ao TX e ao RX (Projeto PAM em banda base)
 *
 * Todos os números vêm do enunciado "Projeto_BB_2026S2.pdf" (Seções 4.1–4.7 e
 * Apêndice A). Altere aqui somente se o professor mudar o enunciado.
 */
#ifndef PAM_CONFIG_H
#define PAM_CONFIG_H

#include <stdint.h>

/* ---------------- Taxas ---------------- */
#define PAM_TIMER_CLK_HZ      100000000u  /* TIM1/TIM2/TIM3 recebem 100 MHz        */
#define PAM_SYM_RATE_HZ       20000u      /* Rs = 20 ksym/s -> Ts = 50 us          */
/* Desafio opcional: troque para 100000u nos DOIS firmwares (Ts = 10 us).          */

#define PAM_SPS               8u          /* amostras por símbolo no RX            */
#define PAM_FS_HZ             (PAM_SYM_RATE_HZ * PAM_SPS)   /* 160 000 amostras/s  */

/* TIM3 (TX, CLK em PB4): ARR = 100 MHz / Rs - 1 = 4999, CCR1 = 2500 (50 %)        */
#define PAM_TX_TIM3_ARR       (PAM_TIMER_CLK_HZ / PAM_SYM_RATE_HZ - 1u)
#define PAM_TX_TIM3_CCR1      ((PAM_TX_TIM3_ARR + 1u) / 2u)

/* TIM2 (RX): ARR = 100 MHz / (8 Rs) - 1 = 624 ; CCR2 = 312 (~3,12 us)             */
#define PAM_RX_TIM2_ARR       (PAM_TIMER_CLK_HZ / PAM_FS_HZ - 1u)
#define PAM_RX_TIM2_CCR2      ((PAM_RX_TIM2_ARR + 1u) / 2u)

/* ---------------- Quadro (Seção 4.2) ---------------- */
#define PAM_TRAIN_PULSE_REPS  20u   /* 20 x (0,0,0,A,0,0,0)                         */
#define PAM_TRAIN_PULSE_LEN   7u
#define PAM_TRAIN_PULSE_SYMS  (PAM_TRAIN_PULSE_REPS * PAM_TRAIN_PULSE_LEN)   /* 140 */
#define PAM_TRAIN_LEVEL_REPS  32u   /* 32 x 8 níveis conhecidos                     */
#define PAM_TRAIN_LEVEL_LEN   8u
#define PAM_TRAIN_LEVEL_SYMS  (PAM_TRAIN_LEVEL_REPS * PAM_TRAIN_LEVEL_LEN)   /* 256 */
#define PAM_TRAIN_SYMS        (PAM_TRAIN_PULSE_SYMS + PAM_TRAIN_LEVEL_SYMS)   /* 396 */

#define PAM_PRE_ALT_BITS      16u            /* 0101...01                           */
#define PAM_SYNC_WORD         0xD391C5A7u    /* MSB primeiro                        */
#define PAM_PRE_BITS          (PAM_PRE_ALT_BITS + 32u)                        /* 48  */

#define PAM_PAYLOAD_BITS      100000u        /* PRBS-15, b0 primeiro                */

/* Tolerância de erros nos 48 bits de início de quadro para declarar sincronismo.
 * 0 = exige o padrão exato (interpretação estrita do enunciado).                  */
#define PAM_SYNC_MAX_BIT_ERR  0u

/* ---------------- Registros para o relatório ---------------- */
#define PAM_PSD_SAMPLES       8192u          /* 8 192 amostras = 16 kB             */
#define PAM_PSD_SYMS          (PAM_PSD_SAMPLES / PAM_SPS)                     /* 1024 */
#define PAM_PSD_START_SYM     1000u          /* símbolo do payload onde começa a cópia */

/* ---------------- ADC ---------------- */
#define PAM_ADC_MAX           4095u
#define PAM_DMA_BUF_LEN       512u           /* DMA circular, 2 metades de 256      */

#endif /* PAM_CONFIG_H */
