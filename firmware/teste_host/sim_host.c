/*
 * sim_host.c — teste do firmware NO PC, sem placa.
 *
 * Usa o MESMO pam_frame.c (TX) e pam_rx_core.c (RX) que vão para a BlackPill.
 * O canal é modelado por um polo dominante (tau) com solução exata entre as
 * amostras, + ripple residual do PWM + ruído gaussiano + quantização de 12 bits.
 *
 * Uso: ./sim_host <2|4> <canal: 0=Dupont, 1=RC 16,8 nF, 2=RC 33 nF> [sigma_mV] [ripple_mVpp] [log.txt]
 *      Com o 5o argumento grava um log no MESMO formato da serial do RX real
 *      (serve para testar matlab/analisa_ensaio.m antes de ter a placa).
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "pam_frame.h"
#include "pam_rx_core.h"
#include "pam_rx_report.h"

static FILE *s_log;
static void log_puts(const char *t) { fputs(t, s_log); }

static double gauss(void)
{
    double u1 = (rand() + 1.0) / (RAND_MAX + 2.0), u2 = (rand() + 1.0) / (RAND_MAX + 2.0);
    return sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
}

static pam_rx_t rx;   /* grande (≈ 24 kB): fora da pilha */

int main(int argc, char **argv)
{
    const pam_mod_t mod = (argc > 1 && atoi(argv[1]) == 4) ? PAM4 : PAM2;
    const int M = (int)mod;
    const int canal = (argc > 2) ? atoi(argv[2]) : 0;
    const double sigma = ((argc > 3) ? atof(argv[3]) : 2.0) * 1e-3;     /* V */
    const double ripple = ((argc > 4) ? atof(argv[4]) : 0.0) * 1e-3;    /* Vpp */
    const double Vdd = 3.3, Rgpio = 25.0, R1 = 330.0, C1 = 390e-12, R2 = 56.0;
    double C2 = 0.0;
    if (canal == 1) C2 = 16.8e-9;
    if (canal == 2) C2 = 33e-9;
    /* polo dominante da escada RC: tau ≈ (Rg+R1)(C1+C2) + R2*C2 */
    const double tau = (Rgpio + R1) * (C1 + C2) + R2 * C2;
    const double Ts = 1.0 / PAM_SYM_RATE_HZ, Tsa = Ts / PAM_SPS;
    const double t_lat = 0.25e-6;               /* atraso da ISR do TX */
    const double t0 = (double)PAM_RX_TIM2_CCR2 / PAM_TIMER_CLK_HZ;  /* 3,12 us */

    pam_symgen_t g;
    pam_symgen_init(&g, mod);
    pam_rx_init(&rx, mod);
    srand(1234);

    const double vstep = Vdd / (double)(mod - 1);
    double v = 0.0;            /* tensão no capacitor (TP3) */
    double vin_prev = 0.0;     /* nível do símbolo anterior */
    int lvl;
    while ((lvl = pam_symgen_next(&g)) >= 0) {
        const double vin = lvl * vstep;
        uint16_t a[PAM_SPS];
        /* trecho [0, t_lat): ainda o nível anterior */
        v = vin_prev + (v - vin_prev) * exp(-t_lat / tau);
        double t = t_lat;
        for (unsigned k = 0; k < PAM_SPS; k++) {
            const double tk = t0 + k * Tsa;
            v = vin + (v - vin) * exp(-(tk - t) / tau);
            t = tk;
            double vs = v + sigma * gauss() + ripple * ((double)rand() / RAND_MAX - 0.5);
            long code = lround(vs / Vdd * 4095.0);
            if (code < 0) code = 0;
            if (code > 4095) code = 4095;
            a[k] = (uint16_t)code;
        }
        v = vin + (v - vin) * exp(-(Ts - t) / tau);
        vin_prev = vin;
        pam_rx_symbol(&rx, a);
    }

    printf("PAM-%d canal=%d tau=%.2f us sigma=%.1f mV ripple=%.0f mVpp\n",
           mod, canal, tau * 1e6, sigma * 1e3, ripple * 1e3);
    printf("b_c = %.2f  E_c = %.1f  p_c =", rx.bc, rx.Ec);
    for (int k = 0; k < 8; k++) printf(" %.1f", rx.pc[k]);
    printf("\nsep_k (ADC) =");
    for (int k = 0; k < 8; k++) printf(" %d", rx.sep_k[k]);
    printf("\nk* = %u (t = %.2f us)\n", rx.kstar, (t0 + rx.kstar * Tsa) * 1e6);
    printf("centros u:"); for (int l = 0; l < M; l++) printf(" %.1f", rx.cen_u[l]);
    printf("\ncentros z:"); for (int l = 0; l < M; l++) printf(" %.4f", rx.cen_z[l]);
    printf("\nlimiares u:"); for (int l = 0; l < M - 1; l++) printf(" %.1f", rx.thr_u[l]);
    printf("\nlimiares z:"); for (int l = 0; l < M - 1; l++) printf(" %.4f", rx.thr_z[l]);
    printf("\nmargem u = %d ADC (%.1f mV) par %u-%u | margem z = %.4f par %u-%u\n",
           rx.marg_u, rx.marg_u * 3300.0 / 4095.0, rx.marg_u_pair, rx.marg_u_pair + 1,
           rx.marg_z, rx.marg_z_pair, rx.marg_z_pair + 1);
    printf("calib_ok=%u sync_ok=%u (erros inicio: u=%u z=%u)\n",
           rx.calib_ok, rx.sync_ok, rx.pre_err_u, rx.pre_err_z);
    printf("payload: %u bits, %u simbolos\n", rx.pay_bits, rx.pay_syms);
    printf("amostra unica: Ne=%u BER=%.2e Ns=%u SER=%.2e\n", rx.bit_err_u,
           rx.bit_err_u / (double)rx.pay_bits, rx.sym_err_u, rx.sym_err_u / (double)rx.pay_syms);
    printf("filtro casado: Ne=%u BER=%.2e Ns=%u SER=%.2e\n", rx.bit_err_z,
           rx.bit_err_z / (double)rx.pay_bits, rx.sym_err_z, rx.sym_err_z / (double)rx.pay_syms);
    printf("psd_n=%u\n", rx.psd_n);

    if (argc > 5) {
        static const char *nomes[] = {"Dupont_direto", "Dupont_RC_16n8", "Dupont_RC_33n"};
        pam_rx_acq_t q = {
            .canal = nomes[canal % 3], .edges = pam_total_syms(mod), .processed = pam_total_syms(mod),
            .first_pos = 37, .discarded = 1061, .misalign = 0, .overrun = 0, .adc_err = 0, .clk_lost = 0,
        };
        s_log = fopen(argv[5], "w");
        if (!s_log) { perror(argv[5]); return 1; }
        pam_rx_report(&rx, &q, log_puts);
        fclose(s_log);
        printf("log gravado em %s\n", argv[5]);
    }
    return 0;
}
