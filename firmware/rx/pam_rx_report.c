/*
 * pam_rx_report.c — relatório do RX em texto (sem HAL).
 * Usado pela placa (saída pela USART1) e pelo teste no PC (teste_host), de modo
 * que o log do simulador tem exatamente o mesmo formato do log real.
 */
#include "pam_rx_report.h"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

#define VREF_MV_NOMINAL 3300.0f  /* só para imprimir mV; use o Vref medido na análise */

static void (*s_puts)(const char *);

static void uprintf(const char *fmt, ...)
{
    char b[160];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(b, sizeof b, fmt, ap);
    va_end(ap);
    s_puts(b);
}

/* converte float em texto com 'dec' casas (sem printf de float: newlib-nano) */
static const char *ff(char buf[32], float v, int dec)
{
    static const int32_t p10[] = {1, 10, 100, 1000, 10000, 100000, 1000000};
    const char *sg = "";
    if (v < 0) { sg = "-"; v = -v; }
    int32_t ip = (int32_t)v;
    int32_t fp = (int32_t)((v - (float)ip) * (float)p10[dec] + 0.5f);
    if (fp >= p10[dec]) { ip++; fp -= p10[dec]; }
    if (ip == 0 && fp == 0) sg = "";                 /* evita "-0.000" */
    if (dec == 0) snprintf(buf, 32, "%s%ld", sg, (long)ip);
    else snprintf(buf, 32, "%s%ld.%0*ld", sg, (long)ip, dec, (long)fp);
    return buf;
}

void pam_rx_report(const pam_rx_t *r, const pam_rx_acq_t *q, void (*puts_fn)(const char *))
{
    char b1[32], b2[32], b3[32];
    s_puts = puts_fn;
    const uint8_t M = r->M;
    const uint32_t total = pam_total_syms(r->mod);
    const float mv = VREF_MV_NOMINAL / 4095.0f;
    const uint8_t valid = (q->processed == total) && !q->misalign && !q->overrun &&
                          !q->adc_err && !q->clk_lost;

    uprintf("\r\n#BEGIN_REPORT\r\n");
    uprintf("modulacao=PAM-%d\r\ncanal=%s\r\n", (int)M, q->canal);
    uprintf("Rs_sym_s=%lu\r\nfa_amostras_s=%lu\r\n", (unsigned long)PAM_SYM_RATE_HZ,
            (unsigned long)PAM_FS_HZ);
    uprintf("bordas_CLK=%lu\r\nsimbolos_esperados=%lu\r\nsimbolos_processados=%lu\r\n",
            (unsigned long)q->edges, (unsigned long)total, (unsigned long)q->processed);
    uprintf("amostras_processadas=%lu\r\nposicao_DMA_1a_borda=%lu\r\namostras_descartadas_antes_CLK=%lu\r\n",
            (unsigned long)(q->processed * PAM_SPS), (unsigned long)q->first_pos, (unsigned long)q->discarded);
    uprintf("bordas_com_contagem_errada=%lu\r\noverrun_processamento=%u\r\nerro_ADC_overrun=%u\r\nperda_CLK=%u\r\n",
            (unsigned long)q->misalign, q->overrun, q->adc_err, q->clk_lost);
    uprintf("aquisicao_valida=%u\r\n", valid);

    uprintf("b_c=%s\r\nE_c=%s\r\n", ff(b1, r->bc, 2), ff(b2, r->Ec, 1));
    for (unsigned k = 0; k < PAM_SPS; k++) uprintf("p_c[%u]=%s\r\n", k, ff(b1, r->pc[k], 2));
    /* ISI: média do 1º zero depois de A, menos b_c, em cada k */
    for (unsigned k = 0; k < PAM_SPS; k++) {
        uint32_t s = 0;
        for (uint32_t rep = 0; rep < PAM_TRAIN_PULSE_REPS; rep++)
            s += r->train_raw[rep * PAM_TRAIN_PULSE_LEN + 4u][k];
        uprintf("ISI_zero_apos_A[%u]=%s\r\n", k, ff(b1, (float)s / PAM_TRAIN_PULSE_REPS - r->bc, 2));
    }
    for (unsigned k = 0; k < PAM_SPS; k++)
        uprintf("separacao_k[%u]=%ld\r\n", k, (long)r->sep_k[k]);
    uprintf("k_estrela=%u\r\nt_k_estrela_us=%s\r\n", r->kstar,
            ff(b1, 1e6f * ((float)PAM_RX_TIM2_CCR2 + r->kstar * (PAM_RX_TIM2_ARR + 1u)) / PAM_TIMER_CLK_HZ, 2));
    for (int l = 0; l < M; l++)
        uprintf("centro_u[%d]=%s\r\ncentro_z[%d]=%s\r\n", l, ff(b1, r->cen_u[l], 2), l, ff(b2, r->cen_z[l], 5));
    for (int l = 0; l + 1 < M; l++)
        uprintf("limiar_u[%d]=%s\r\nlimiar_z[%d]=%s\r\n", l, ff(b1, r->thr_u[l], 2), l, ff(b2, r->thr_z[l], 5));
    uprintf("margem_u_ADC=%ld\r\nmargem_u_mV_nominal=%s\r\nmargem_u_par=%u-%u\r\n", (long)r->marg_u,
            ff(b1, r->marg_u * mv, 1), r->marg_u_pair, r->marg_u_pair + 1);
    uprintf("margem_z=%s\r\nmargem_z_par=%u-%u\r\ncalibracao_ok=%u\r\n", ff(b1, r->marg_z, 5),
            r->marg_z_pair, r->marg_z_pair + 1, r->calib_ok);

    /* média simples m_j (pesos iguais) de um símbolo de cada nível */
    for (int l = 0; l < M; l++) {
        for (uint32_t j = PAM_TRAIN_PULSE_SYMS; j < PAM_TRAIN_SYMS; j++) {
            if (pam_train_level(r->mod, j) != l) continue;
            float m = 0.0f;
            for (unsigned k = 0; k < PAM_SPS; k++) m += (float)r->train_raw[j][k] - r->bc;
            uprintf("media8_nivel[%d]=%s (simbolo j=%lu, z=%s)\r\n", l, ff(b1, m / PAM_SPS, 2),
                    (unsigned long)j, ff(b2, r->train_z[j], 5));
            break;
        }
    }

    uprintf("inicio_quadro_erros_u=%u\r\ninicio_quadro_erros_z=%u\r\nsincronismo_ok=%u\r\n",
            r->pre_err_u, r->pre_err_z, r->sync_ok);
    uprintf("payload_bits=%lu\r\npayload_simbolos=%lu\r\n", (unsigned long)r->pay_bits,
            (unsigned long)r->pay_syms);
    if (valid && r->sync_ok) {
        uprintf("amostra_unica_Ne=%lu\r\namostra_unica_Ns=%lu\r\n", (unsigned long)r->bit_err_u,
                (unsigned long)r->sym_err_u);
        uprintf("filtro_casado_Ne=%lu\r\nfiltro_casado_Ns=%lu\r\n", (unsigned long)r->bit_err_z,
                (unsigned long)r->sym_err_z);
        uprintf("BER_amostra=%lu/%lu\r\nBER_filtro=%lu/%lu\r\nSER_amostra=%lu/%lu\r\nSER_filtro=%lu/%lu\r\n",
                (unsigned long)r->bit_err_u, (unsigned long)r->pay_bits,
                (unsigned long)r->bit_err_z, (unsigned long)r->pay_bits,
                (unsigned long)r->sym_err_u, (unsigned long)r->pay_syms,
                (unsigned long)r->sym_err_z, (unsigned long)r->pay_syms);
    } else {
        uprintf("BER=NAO_ATRIBUIDA (quadro invalido ou sem sincronismo: repita o ensaio)\r\n");
    }

    /* uma janela real para a conta à mão da defesa */
    uprintf("janela_exemplo_j=%lu\r\njanela_exemplo_nivel_TX=%u\r\n", (unsigned long)r->ex_j, r->ex_level);
    for (unsigned k = 0; k < PAM_SPS; k++)
        uprintf("janela a[%u]=%u x[%u]=%s p_c[%u]=%s\r\n", k, r->ex_a[k], k,
                ff(b1, (float)r->ex_a[k] - r->bc, 2), k, ff(b2, r->pc[k], 2));
    uprintf("janela_z=%s\r\n", ff(b3, r->ex_z, 5));
    uprintf("#END_REPORT\r\n");

    /* ---- dados brutos: treinamento (396 x 8) ---- */
    uprintf("#BEGIN_TRAIN j,nivel,a0,a1,a2,a3,a4,a5,a6,a7,z\r\n");
    for (uint32_t j = 0; j < PAM_TRAIN_SYMS; j++) {
        const uint16_t *a = r->train_raw[j];
        uprintf("%lu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%s\r\n", (unsigned long)j, pam_train_level(r->mod, j),
                a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7],
                ff(b1, (j >= PAM_TRAIN_PULSE_SYMS) ? r->train_z[j] : 0.0f, 5));
    }
    uprintf("#END_TRAIN\r\n");

    /* ---- 8 192 amostras consecutivas do payload (PSD e olho) ---- */
    uprintf("#BEGIN_PSD simbolo,nivel,a0,a1,a2,a3,a4,a5,a6,a7\r\n");
    for (uint32_t i = 0; i < r->psd_n / PAM_SPS; i++) {
        const uint16_t *a = &r->psd[i * PAM_SPS];
        uprintf("%lu,%u,%u,%u,%u,%u,%u,%u,%u,%u\r\n", (unsigned long)(PAM_PSD_START_SYM + i),
                r->psd_level[i], a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]);
    }
    uprintf("#END_PSD\r\n");
}
