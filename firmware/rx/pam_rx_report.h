/*
 * pam_rx_report.h — relatório do RX (mesmo formato na placa e no PC).
 */
#ifndef PAM_RX_REPORT_H
#define PAM_RX_REPORT_H

#include "pam_rx_core.h"

/* Estado da aquisição (preenchido pela parte HAL do RX) */
typedef struct {
    const char *canal;     /* rótulo do canal (comando d/c/x/m)              */
    uint32_t edges;        /* bordas de CLK recebidas                         */
    uint32_t processed;    /* símbolos processados                            */
    uint32_t first_pos;    /* posição do DMA (0..511) na 1ª borda             */
    uint32_t discarded;    /* amostras anteriores ao 1º CLK (descartadas)     */
    uint32_t misalign;     /* bordas com contagem de amostras diferente de 8  */
    uint8_t  overrun;      /* processamento atrasou mais que o buffer         */
    uint8_t  adc_err;      /* overrun do ADC                                  */
    uint8_t  clk_lost;     /* CLK parou antes do fim do quadro                */
} pam_rx_acq_t;

void pam_rx_report(const pam_rx_t *r, const pam_rx_acq_t *q, void (*puts_fn)(const char *));

#endif /* PAM_RX_REPORT_H */
