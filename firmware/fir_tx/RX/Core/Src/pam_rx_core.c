/*
 * pam_rx_core.c — ver pam_rx_core.h. Sem HAL: compila no PC (teste_host) e na
 * BlackPill. Nenhum parâmetro é alterado depois que o payload começa.
 */
#include "pam_rx_core.h"
#include <string.h>

void pam_rx_init(pam_rx_t *rx, pam_mod_t mod)
{
    memset(rx, 0, sizeof(*rx));
    rx->mod = mod;
    rx->M = (uint8_t)mod;
    rx->st = RX_ST_PULSE;
    pam_symgen_init(&rx->ref, mod);
}

float pam_rx_matched(const pam_rx_t *rx, const uint16_t a[PAM_SPS])
{
    /* z = sum_k p_c[k] * (a[k] - b_c) / E_c  -> 8 multiplicações e uma soma */
    float acc = 0.0f;
    for (uint32_t k = 0; k < PAM_SPS; k++)
        acc += rx->pc[k] * ((float)a[k] - rx->bc);
    return acc / rx->Ec;
}

static uint8_t decide(float v, const float *thr, uint8_t M)
{
    uint8_t lvl = 0;
    for (uint8_t i = 0; i + 1u < M; i++)
        if (v > thr[i]) lvl++;
    return lvl;
}

/* Erros de bit entre o nível decidido e os bits esperados do símbolo */
static uint32_t bit_errors(const pam_rx_t *rx, uint8_t lvl)
{
    if (rx->mod == PAM4) {
        uint8_t b0, b1;
        pam_level4_to_bits(lvl, &b0, &b1);
        return (uint32_t)(b0 != rx->ref.bits[0]) + (uint32_t)(b1 != rx->ref.bits[1]);
    }
    return (uint32_t)(lvl != rx->ref.bits[0]);
}

/* Fim do treinamento de pulso: b_c, p_c[k], E_c (Seção 4.5.1, passos 1 e 2) */
static void finish_pulse(pam_rx_t *rx)
{
    rx->bc = (float)rx->base_sum / (float)(PAM_TRAIN_PULSE_REPS * PAM_SPS);
    rx->Ec = 0.0f;
    rx->pulse_ok = 0;
    for (uint32_t k = 0; k < PAM_SPS; k++) {
        rx->pc[k] = (float)rx->A_sum[k] / (float)PAM_TRAIN_PULSE_REPS - rx->bc;
        rx->Ec += rx->pc[k] * rx->pc[k];
        if (rx->pc[k] != 0.0f) rx->pulse_ok = 1;
    }
    if (rx->Ec <= 0.0f) rx->Ec = 1.0f;     /* evita divisão por zero (pulse_ok=0) */
}

/* Fim da calibração de níveis: k*, centros, limiares, margens (Seção 4.5.2) */
static void finish_levels(pam_rx_t *rx)
{
    const uint8_t M = rx->M;
    const uint32_t j0 = PAM_TRAIN_PULSE_SYMS;

    /* --- k*: para cada k, menor separação min(nível l+1) - max(nível l) --- */
    int32_t best = INT32_MIN;
    for (uint32_t k = 0; k < PAM_SPS; k++) {
        int32_t mn[4] = {4096, 4096, 4096, 4096}, mx[4] = {-1, -1, -1, -1};
        for (uint32_t j = j0; j < PAM_TRAIN_SYMS; j++) {
            uint8_t l = pam_train_level(rx->mod, j);
            int32_t v = rx->train_raw[j][k];
            if (v < mn[l]) mn[l] = v;
            if (v > mx[l]) mx[l] = v;
        }
        int32_t s = INT32_MAX;
        for (uint8_t l = 0; l + 1u < M; l++) {
            int32_t d = mn[l + 1] - mx[l];
            if (d < s) s = d;
        }
        rx->sep_k[k] = s;
        if (s > best) { best = s; rx->kstar = (uint8_t)k; }   /* empate: menor k */
    }

    /* --- centros (médias) e extremos de u = a[k*] e de z --- */
    float su[4] = {0}, sz[4] = {0};
    uint32_t n[4] = {0};
    int32_t umin[4] = {4096, 4096, 4096, 4096}, umax[4] = {-1, -1, -1, -1};
    float zmin[4] = {1e30f, 1e30f, 1e30f, 1e30f}, zmax[4] = {-1e30f, -1e30f, -1e30f, -1e30f};
    for (uint32_t j = j0; j < PAM_TRAIN_SYMS; j++) {
        uint8_t l = pam_train_level(rx->mod, j);
        int32_t u = rx->train_raw[j][rx->kstar];
        float z = rx->train_z[j];
        su[l] += (float)u; sz[l] += z; n[l]++;
        if (u < umin[l]) umin[l] = u;
        if (u > umax[l]) umax[l] = u;
        if (z < zmin[l]) zmin[l] = z;
        if (z > zmax[l]) zmax[l] = z;
    }
    rx->calib_ok = 1;
    for (uint8_t l = 0; l < M; l++) {
        rx->cen_u[l] = n[l] ? su[l] / (float)n[l] : 0.0f;
        rx->cen_z[l] = n[l] ? sz[l] / (float)n[l] : 0.0f;
        if (l > 0 && (rx->cen_u[l] <= rx->cen_u[l - 1] || rx->cen_z[l] <= rx->cen_z[l - 1]))
            rx->calib_ok = 0;                   /* centros fora da ordem física */
    }
    rx->marg_u = INT32_MAX;
    rx->marg_z = 1e30f;
    for (uint8_t l = 0; l + 1u < M; l++) {
        rx->thr_u[l] = 0.5f * (rx->cen_u[l] + rx->cen_u[l + 1]);
        rx->thr_z[l] = 0.5f * (rx->cen_z[l] + rx->cen_z[l + 1]);
        int32_t mu = umin[l + 1] - umax[l];
        float mz = zmin[l + 1] - zmax[l];
        if (mu < rx->marg_u) { rx->marg_u = mu; rx->marg_u_pair = l; }
        if (mz < rx->marg_z) { rx->marg_z = mz; rx->marg_z_pair = l; }
    }
    if (!rx->pulse_ok) rx->calib_ok = 0;
}

int pam_rx_symbol(pam_rx_t *rx, const uint16_t a[PAM_SPS])
{
    if (rx->st == RX_ST_DONE) return 1;

    const int lvl_tx = pam_symgen_next(&rx->ref);   /* o que o TX enviou */
    if (lvl_tx < 0) { rx->st = RX_ST_DONE; return 1; }
    const uint32_t j = rx->j++;

    switch (rx->st) {
    case RX_ST_PULSE: {
        memcpy(rx->train_raw[j], a, sizeof(uint16_t) * PAM_SPS);
        const uint32_t pos = j % PAM_TRAIN_PULSE_LEN;
        if (pos == 2u) {                       /* último zero antes de A */
            for (uint32_t k = 0; k < PAM_SPS; k++) rx->base_sum += a[k];
        } else if (pos == 3u) {                /* símbolo A */
            for (uint32_t k = 0; k < PAM_SPS; k++) rx->A_sum[k] += a[k];
        }
        if (j + 1u == PAM_TRAIN_PULSE_SYMS) {
            finish_pulse(rx);
            rx->st = RX_ST_LEVELS;
        }
        break;
    }
    case RX_ST_LEVELS:
        memcpy(rx->train_raw[j], a, sizeof(uint16_t) * PAM_SPS);
        rx->train_z[j] = pam_rx_matched(rx, a);
        if (j + 1u == PAM_TRAIN_SYMS) {
            finish_levels(rx);                 /* congela k*, pesos, centros, limiares */
            rx->st = RX_ST_PREAMBLE;
        }
        break;

    case RX_ST_PREAMBLE: {
        const uint8_t lu = decide((float)a[rx->kstar], rx->thr_u, rx->M);
        const uint8_t lz = decide(pam_rx_matched(rx, a), rx->thr_z, rx->M);
        rx->pre_err_u += (uint8_t)bit_errors(rx, lu);
        rx->pre_err_z += (uint8_t)bit_errors(rx, lz);
        if (j + 1u == PAM_TRAIN_SYMS + pam_preamble_syms(rx->mod)) {
            rx->sync_ok = (rx->pre_err_u <= PAM_SYNC_MAX_BIT_ERR) &&
                          (rx->pre_err_z <= PAM_SYNC_MAX_BIT_ERR) && rx->calib_ok;
            rx->st = RX_ST_PAYLOAD;
        }
        break;
    }
    case RX_ST_PAYLOAD: {
        const uint32_t p = rx->pay_syms;       /* índice do símbolo no payload */
        const float z = pam_rx_matched(rx, a);
        const uint8_t lu = decide((float)a[rx->kstar], rx->thr_u, rx->M);
        const uint8_t lz = decide(z, rx->thr_z, rx->M);
        rx->bit_err_u += bit_errors(rx, lu);
        rx->bit_err_z += bit_errors(rx, lz);
        rx->sym_err_u += (uint32_t)(lu != (uint8_t)lvl_tx);
        rx->sym_err_z += (uint32_t)(lz != (uint8_t)lvl_tx);
        rx->pay_bits += rx->ref.nbits;
        rx->pay_syms++;

        if (p >= PAM_PSD_START_SYM && rx->psd_n < PAM_PSD_SAMPLES) {
            memcpy(&rx->psd[rx->psd_n], a, sizeof(uint16_t) * PAM_SPS);
            rx->psd_level[rx->psd_n / PAM_SPS] = (uint8_t)lvl_tx;
            rx->psd_n += PAM_SPS;
        }
        if (p == 7u) {                          /* guarda uma janela real p/ defesa */
            memcpy(rx->ex_a, a, sizeof(rx->ex_a));
            rx->ex_z = z;
            rx->ex_j = j;
            rx->ex_level = (uint8_t)lvl_tx;
        }
        if (j + 1u == pam_total_syms(rx->mod)) rx->st = RX_ST_DONE;
        break;
    }
    default:
        break;
    }
    return rx->st == RX_ST_DONE;
}
