/*
 * pam_rx.c — parte do RX que usa a HAL: aquisição (TIM2 + ADC1 + DMA2),
 * alinhamento pela borda do CLK, verificação de perdas e relatório serial.
 * O processamento matemático está em pam_rx_core.c.
 *
 * Contagem absoluta de amostras
 * -----------------------------
 * O DMA escreve em dma_buf[512] de forma circular. Cada interrupção de meia
 * transferência ou de transferência completa soma 256 a s_blocks, então
 * s_blocks*256 = amostras já COMPLETAS (prontas para processar). A posição
 * instantânea de escrita é 512 - NDTR. Combinando as duas obtemos o índice
 * absoluto W da próxima amostra a ser escrita (função abs_written()).
 *
 * Primeira borda do CLK
 * ---------------------
 * O TIM2 já roda livre antes do CLK (dispara o ADC a cada 6,25 µs). Na 1ª borda
 * o contador é zerado; a ISR espera TIM2->CNT >= 200 (2 µs): qualquer conversão
 * disparada ANTES da borda já terminou (dura 1,08 µs) e a amostra k=0 (3,12 µs)
 * ainda não começou. W nesse instante é o índice absoluto de a_0[0]; tudo antes
 * dele é descartado (amostras anteriores ao primeiro CLK).
 *
 * Bordas seguintes
 * ----------------
 * Em cada borda n, W deve valer abs0 + 8n (ou +1 se a ISR atrasou mais que
 * 4,2 µs). Qualquer outro valor = amostra perdida/sobrando -> ensaio inválido.
 */
#include "pam_rx.h"
#include "pam_rx_report.h"
#include <string.h>
#include <stdio.h>
#include <stdarg.h>

#define FIRST_EDGE_WAIT_TICKS  200u      /* 2,00 µs a 100 MHz                     */
#define CLK_TIMEOUT_MS         5u        /* sem borda por 5 ms = fim / perda de CLK */

typedef enum { RXS_IDLE = 0, RXS_ARMED, RXS_RUN, RXS_REPORT } rxs_t;

static pam_rx_t s_rx;
static uint16_t s_dma[PAM_DMA_BUF_LEN] __attribute__((aligned(4)));

static volatile uint32_t s_blocks;        /* metades de 256 completas            */
static volatile uint32_t s_edges;         /* bordas de CLK recebidas             */
static volatile uint32_t s_abs0;          /* índice absoluto de a_0[0]           */
static volatile uint32_t s_first_pos;     /* posição do DMA (0..511) na 1ª borda */
static volatile uint32_t s_misalign;      /* bordas com contagem de amostras errada */
static volatile uint32_t s_last_edge_ms;
static volatile uint8_t  s_adc_err;
static volatile rxs_t    s_state;

static uint32_t s_next_sym;               /* próximo símbolo a processar         */
static uint8_t  s_overrun;                /* processamento atrasou > 512 amostras */
static uint8_t  s_clk_lost;
static pam_mod_t s_mod = PAM2;
static char     s_canal[16] = "nao_informado";

/* ------------------------------------------------------------------ */
/* utilidades de impressão (sem printf de float: newlib-nano)          */
/* ------------------------------------------------------------------ */
static void uputs(const char *s)
{
    HAL_UART_Transmit(&huart1, (uint8_t *)s, (uint16_t)strlen(s), HAL_MAX_DELAY);
}
static void uprintf(const char *fmt, ...)
{
    char b[160];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(b, sizeof b, fmt, ap);
    va_end(ap);
    uputs(b);
}
/* ------------------------------------------------------------------ */
/* contagem absoluta                                                   */
/* ------------------------------------------------------------------ */
static inline uint32_t abs_written_unsafe(void)
{
    uint32_t base = s_blocks * (PAM_DMA_BUF_LEN / 2u);
    uint32_t pos = (PAM_DMA_BUF_LEN - __HAL_DMA_GET_COUNTER(hadc1.DMA_Handle)) % PAM_DMA_BUF_LEN;
    uint32_t off = (pos + PAM_DMA_BUF_LEN - (base % PAM_DMA_BUF_LEN)) % PAM_DMA_BUF_LEN;
    return base + off;
}
static uint32_t abs_written(void)
{
    uint32_t pm = __get_PRIMASK();
    __disable_irq();
    uint32_t w = abs_written_unsafe();
    __set_PRIMASK(pm);
    return w;
}

/* ------------------------------------------------------------------ */
/* interrupções                                                         */
/* ------------------------------------------------------------------ */
void PAM_RX_DMA_HalfOrFull(void) { s_blocks++; }
void PAM_RX_ADC_Error(void) { s_adc_err = 1; }

void PAM_RX_TIM2_IRQ(void)
{
    if ((TIM2->SR & TIM_SR_TIF) == 0u) return;
    TIM2->SR = ~TIM_SR_TIF;
    if (s_state != RXS_ARMED && s_state != RXS_RUN) return;

    if (s_edges == 0u) {
        while (TIM2->CNT < FIRST_EDGE_WAIT_TICKS) { }
        s_first_pos = (PAM_DMA_BUF_LEN - __HAL_DMA_GET_COUNTER(hadc1.DMA_Handle)) % PAM_DMA_BUF_LEN;
        s_abs0 = abs_written_unsafe();
        s_state = RXS_RUN;
    } else {
        uint32_t expected = s_abs0 + PAM_SPS * s_edges;
        uint32_t w = abs_written_unsafe();
        if (w < expected || w > expected + 1u) s_misalign++;
    }
    s_edges++;
    s_last_edge_ms = HAL_GetTick();
}

/* ------------------------------------------------------------------ */
/* armar / parar                                                        */
/* ------------------------------------------------------------------ */
static void rx_stop(void)
{
    __HAL_TIM_DISABLE_IT(&htim2, TIM_IT_TRIGGER);
    HAL_TIM_PWM_Stop(&htim2, TIM_CHANNEL_2);
    HAL_ADC_Stop_DMA(&hadc1);
}

static void rx_arm(void)
{
    rx_stop();
    pam_rx_init(&s_rx, s_mod);
    s_blocks = 0; s_edges = 0; s_abs0 = 0; s_first_pos = 0; s_misalign = 0;
    s_adc_err = 0; s_next_sym = 0; s_overrun = 0; s_clk_lost = 0;

    __HAL_TIM_SET_AUTORELOAD(&htim2, PAM_RX_TIM2_ARR);            /* 624 */
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, PAM_RX_TIM2_CCR2); /* 312 */
    __HAL_TIM_SET_COUNTER(&htim2, 0);
    __HAL_ADC_CLEAR_FLAG(&hadc1, ADC_FLAG_OVR);

    s_state = RXS_ARMED;
    /* ordem do enunciado: ADC + DMA primeiro, depois TIM2 */
    HAL_ADC_Start_DMA(&hadc1, (uint32_t *)s_dma, PAM_DMA_BUF_LEN);
    __HAL_TIM_CLEAR_FLAG(&htim2, TIM_FLAG_TRIGGER);
    __HAL_TIM_ENABLE_IT(&htim2, TIM_IT_TRIGGER);
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2);

    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);       /* LED aceso */
    uprintf("\r\n#ARMADO PAM-%d canal=%s : reinicie o TX (ou aperte KEY no TX)\r\n",
            (int)s_mod, s_canal);
}

/* ------------------------------------------------------------------ */
/* processamento: grupos de 8 amostras por borda, por metades de 256     */
/* ------------------------------------------------------------------ */
static void rx_process(void)
{
    const uint32_t total = pam_total_syms(s_mod);
    const uint32_t avail = s_blocks * (PAM_DMA_BUF_LEN / 2u);
    const uint32_t edges = s_edges;
    uint16_t a[PAM_SPS];

    while (s_next_sym < edges && s_next_sym < total) {
        const uint32_t s = s_abs0 + PAM_SPS * s_next_sym;
        if (s + PAM_SPS > avail) break;                 /* metade ainda não completou */
        for (uint32_t k = 0; k < PAM_SPS; k++) a[k] = s_dma[(s + k) % PAM_DMA_BUF_LEN];
        if (abs_written() >= s + PAM_DMA_BUF_LEN) s_overrun = 1; /* foi sobrescrito */
        pam_rx_symbol(&s_rx, a);
        s_next_sym++;
        if ((s_next_sym & 0x3FFu) == 0u) HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13);
    }
}

/* ------------------------------------------------------------------ */
/* relatório                                                            */
/* ------------------------------------------------------------------ */
static void rx_report(void)
{
    pam_rx_acq_t q = {
        .canal = s_canal, .edges = s_edges, .processed = s_next_sym,
        .first_pos = s_first_pos, .discarded = s_abs0, .misalign = s_misalign,
        .overrun = s_overrun, .adc_err = s_adc_err, .clk_lost = s_clk_lost,
    };
    pam_rx_report(&s_rx, &q, uputs);
}

/* ------------------------------------------------------------------ */
/* comandos pela serial                                                 */
/* ------------------------------------------------------------------ */
static void rx_command(void)
{
    if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE)) __HAL_UART_CLEAR_OREFLAG(&huart1);
    if (!__HAL_UART_GET_FLAG(&huart1, UART_FLAG_RXNE)) return;
    char c = (char)(huart1.Instance->DR & 0xFFu);
    switch (c) {
    case '2': s_mod = PAM2; rx_arm(); break;
    case '4': s_mod = PAM4; rx_arm(); break;
    case 'd': strcpy(s_canal, "Dupont_direto"); rx_arm(); break;
    case 'c': strcpy(s_canal, "Dupont_RC_16n8"); rx_arm(); break;
    case 'x': strcpy(s_canal, "Dupont_RC_33n"); rx_arm(); break;
    case 'm': strcpy(s_canal, "cabo_manga_200m"); rx_arm(); break;
    case 'r': rx_arm(); break;
    case 'p': if (s_state == RXS_REPORT) rx_report(); break;
    case '?':
        uputs("\r\nComandos: 2/4 = modulacao | d=Dupont c=RC16,8n x=RC33n m=manga | r=rearmar | p=reimprimir\r\n");
        break;
    default: break;
    }
}

/* ------------------------------------------------------------------ */
void PAM_RX_Init(void)
{
    s_mod = (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0) == GPIO_PIN_RESET) ? PAM4 : PAM2;
    uputs("\r\n=== RX PAM banda base - BlackPill F411 ===\r\n");
    uputs("Comandos: 2/4 = modulacao | d=Dupont c=RC16,8n x=RC33n m=manga | r=rearmar | p=reimprimir\r\n");
    rx_arm();
}

void PAM_RX_Loop(void)
{
    rx_command();

    if (s_state == RXS_RUN) {
        if (ADC1->SR & ADC_SR_OVR) s_adc_err = 1;
        rx_process();
        const uint32_t total = pam_total_syms(s_mod);
        if (s_next_sym >= total) {
            rx_stop();
            s_state = RXS_REPORT;
        } else if (HAL_GetTick() - s_last_edge_ms > CLK_TIMEOUT_MS) {
            rx_process();                       /* esvazia o que ainda dá */
            if (s_next_sym < total) {
                s_clk_lost = 1;
                rx_stop();
                s_state = RXS_REPORT;
            }
        }
        if (s_state == RXS_REPORT) {
            HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
            rx_report();
            uputs("#FIM. Envie 'r' para rearmar (ou d/c/x/m, 2/4), 'p' para reimprimir.\r\n");
        }
    }
}
