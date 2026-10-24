/*
 * pam_tx.c — ver pam_tx.h e docs/04_HARDWARE_E_CUBEMX.md
 *
 * Temporização de um quadro:
 *   - antes de ligar o CLK, TIM1_CCR1 recebe o nível do símbolo 0;
 *   - TIM3 começa com CNT = 0: a saída PB4 sobe (borda do símbolo 0);
 *   - a cada atualização do TIM3 (= cada subida do CLK) a ISR escreve em
 *     TIM1_CCR1 o nível JÁ CALCULADO do novo símbolo (primeira instrução da ISR,
 *     atraso típico ≈ 0,2 µs) e só depois calcula o nível do símbolo seguinte;
 *   - ao carregar o último símbolo, TIM3_CCR1 (com preload) recebe 0: o período
 *     seguinte não tem borda de subida; na atualização seguinte o TIM3 para e
 *     PA8 volta a 0 V.
 */
#include "pam_tx.h"

static pam_symgen_t s_gen;
static volatile uint8_t s_busy;
static volatile uint32_t s_next_ccr;     /* nível do próximo símbolo, pronto     */
static volatile uint8_t s_last_loaded;   /* último símbolo já está em TIM1_CCR1  */
static pam_mod_t s_mod;

static pam_mod_t read_mode_jumper(void)
{
    /* PB0 com pull-up: jumper para GND seleciona PAM-4 */
    return (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0) == GPIO_PIN_RESET) ? PAM4 : PAM2;
}

static int32_t next_ccr(void)
{
    int lvl = pam_symgen_next(&s_gen);
    return (lvl < 0) ? -1 : (int32_t)pam_level_to_ccr(s_mod, (uint8_t)lvl);
}

void PAM_TX_Init(void)
{
    /* Valores do Apêndice A (reforçados aqui para não depender do .ioc) */
    __HAL_TIM_SET_PRESCALER(&htim1, 0);
    __HAL_TIM_SET_AUTORELOAD(&htim1, 2);
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);          /* PA8 = 0 V (CCR1 = 0)  */

    __HAL_TIM_SET_PRESCALER(&htim3, 0);
    __HAL_TIM_SET_AUTORELOAD(&htim3, PAM_TX_TIM3_ARR);
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, PAM_TX_TIM3_CCR1);
    s_busy = 0;
}

uint8_t PAM_TX_Busy(void) { return s_busy; }

void PAM_TX_StartFrame(pam_mod_t mod)
{
    if (s_busy) return;
    s_mod = mod;
    pam_symgen_init(&s_gen, mod);

    /* 1) primeiro nível no TIM1 antes de iniciar o CLK */
    int32_t c0 = next_ccr();
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, (uint32_t)c0);
    s_next_ccr = (uint32_t)next_ccr();
    s_last_loaded = 0;

    /* 2) prepara TIM3: contador em 0, CCR1 = 2500, flag de update limpa
     *    (HAL_TIM_PWM_Init gera um UG que deixaria UIF pendente)            */
    __HAL_TIM_DISABLE(&htim3);
    __HAL_TIM_SET_COUNTER(&htim3, 0);
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, PAM_TX_TIM3_CCR1);
    htim3.Instance->EGR = TIM_EGR_UG;                 /* carrega o preload     */
    __HAL_TIM_CLEAR_FLAG(&htim3, TIM_FLAG_UPDATE);
    __HAL_TIM_ENABLE_IT(&htim3, TIM_IT_UPDATE);

    s_busy = 1;
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);   /* LED aceso */

    /* 3) liga o CLK: PB4 sobe agora = início do símbolo 0 */
    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1);
}

/* Chamada como PRIMEIRA linha de TIM3_IRQHandler (stm32f4xx_it.c) */
void PAM_TX_TIM3_IRQ(void)
{
    if ((TIM3->SR & TIM_SR_UIF) == 0u) return;
    TIM3->SR = ~TIM_SR_UIF;

    if (s_last_loaded) {
        /* terminou o último símbolo: para o CLK e volta PA8 a zero */
        TIM1->CCR1 = 0;
        TIM3->DIER &= ~TIM_DIER_UIE;
        HAL_TIM_PWM_Stop(&htim3, TIM_CHANNEL_1);
        TIM3->CCR1 = PAM_TX_TIM3_CCR1;
        s_busy = 0;
        return;
    }

    TIM1->CCR1 = s_next_ccr;                 /* novo nível, alinhado à borda */

    int32_t c = next_ccr();
    if (c < 0) {
        /* o símbolo que acabou de entrar é o último: sem nova borda depois dele */
        TIM3->CCR1 = 0;                      /* vale a partir do próximo período */
        s_last_loaded = 1;
    } else {
        s_next_ccr = (uint32_t)c;
    }
}

void PAM_TX_Loop(void)
{
    static uint8_t started_after_reset = 0;
    static uint32_t t_key = 0;

    if (!started_after_reset) {
        /* depois do reset: espera 1 s (tempo de armar o RX) e transmite uma vez */
        if (HAL_GetTick() > 1000u) {
            started_after_reset = 1;
            PAM_TX_StartFrame(read_mode_jumper());
        }
        return;
    }
    if (!s_busy) {
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);       /* LED apagado */
        /* KEY (PA0, ativo em 0): nova transmissão com o modo lido em PB0 */
        if (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0) == GPIO_PIN_RESET) {
            if (t_key == 0u) t_key = HAL_GetTick();
            else if (HAL_GetTick() - t_key > 50u) {               /* debounce */
                while (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0) == GPIO_PIN_RESET) {}
                t_key = 0;
                HAL_Delay(200);
                PAM_TX_StartFrame(read_mode_jumper());
            }
        } else {
            t_key = 0;
        }
    }
}
