/*
 * main_tx.c — main de REFERÊNCIA do transmissor.
 *
 * As funções MX_*_Init() abaixo reproduzem o que o CubeMX gera com a
 * configuração de docs/04_HARDWARE_E_CUBEMX.md. No seu projeto do CubeIDE você
 * NÃO copia este arquivo inteiro: copie apenas as linhas marcadas com
 * "USER CODE" (ver firmware/INTEGRACAO.md). Use este arquivo para comparar.
 */
#include "main.h"
#include "pam_tx.h"

TIM_HandleTypeDef htim1;
TIM_HandleTypeDef htim3;

void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_TIM1_Init(void);
static void MX_TIM3_Init(void);

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_TIM1_Init();
    MX_TIM3_Init();

    /* USER CODE BEGIN 2 */
    PAM_TX_Init();
    /* USER CODE END 2 */

    while (1) {
        /* USER CODE BEGIN 3 */
        PAM_TX_Loop();
        /* USER CODE END 3 */
    }
}

/* PA8 = TIM1_CH1: PWM modo 1, PSC=0, ARR=2 -> 33,333 MHz */
static void MX_TIM1_Init(void)
{
    TIM_ClockConfigTypeDef clk = {0};
    TIM_MasterConfigTypeDef master = {0};
    TIM_OC_InitTypeDef oc = {0};
    TIM_BreakDeadTimeConfigTypeDef bdt = {0};

    htim1.Instance = TIM1;
    htim1.Init.Prescaler = 0;
    htim1.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim1.Init.Period = 2;
    htim1.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim1.Init.RepetitionCounter = 0;
    htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    if (HAL_TIM_Base_Init(&htim1) != HAL_OK) Error_Handler();
    clk.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
    if (HAL_TIM_ConfigClockSource(&htim1, &clk) != HAL_OK) Error_Handler();
    if (HAL_TIM_PWM_Init(&htim1) != HAL_OK) Error_Handler();
    master.MasterOutputTrigger = TIM_TRGO_RESET;
    master.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
    if (HAL_TIMEx_MasterConfigSynchronization(&htim1, &master) != HAL_OK) Error_Handler();
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCNPolarity = TIM_OCNPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    oc.OCIdleState = TIM_OCIDLESTATE_RESET;
    oc.OCNIdleState = TIM_OCNIDLESTATE_RESET;
    if (HAL_TIM_PWM_ConfigChannel(&htim1, &oc, TIM_CHANNEL_1) != HAL_OK) Error_Handler();
    bdt.OffStateRunMode = TIM_OSSR_DISABLE;
    bdt.OffStateIDLEMode = TIM_OSSI_DISABLE;
    bdt.LockLevel = TIM_LOCKLEVEL_OFF;
    bdt.DeadTime = 0;
    bdt.BreakState = TIM_BREAK_DISABLE;
    bdt.BreakPolarity = TIM_BREAKPOLARITY_HIGH;
    bdt.AutomaticOutput = TIM_AUTOMATICOUTPUT_DISABLE;
    if (HAL_TIMEx_ConfigBreakDeadTime(&htim1, &bdt) != HAL_OK) Error_Handler();
    HAL_TIM_MspPostInit(&htim1);
}

/* PB4 = TIM3_CH1: PWM modo 1, PSC=0, ARR=4999, CCR1=2500 -> CLK 20 kHz */
static void MX_TIM3_Init(void)
{
    TIM_ClockConfigTypeDef clk = {0};
    TIM_MasterConfigTypeDef master = {0};
    TIM_OC_InitTypeDef oc = {0};

    htim3.Instance = TIM3;
    htim3.Init.Prescaler = 0;
    htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim3.Init.Period = 4999;
    htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    if (HAL_TIM_Base_Init(&htim3) != HAL_OK) Error_Handler();
    clk.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
    if (HAL_TIM_ConfigClockSource(&htim3, &clk) != HAL_OK) Error_Handler();
    if (HAL_TIM_PWM_Init(&htim3) != HAL_OK) Error_Handler();
    master.MasterOutputTrigger = TIM_TRGO_RESET;
    master.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
    if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &master) != HAL_OK) Error_Handler();
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 2500;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    if (HAL_TIM_PWM_ConfigChannel(&htim3, &oc, TIM_CHANNEL_1) != HAL_OK) Error_Handler();
    HAL_TIM_MspPostInit(&htim3);
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef g = {0};
    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_GPIOH_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);      /* LED apagado */
    g.Pin = GPIO_PIN_13;                                      /* LED PC13    */
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &g);

    g.Pin = GPIO_PIN_0;                                       /* KEY PA0     */
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOA, &g);

    g.Pin = GPIO_PIN_0;                                       /* jumper PB0  */
    HAL_GPIO_Init(GPIOB, &g);
}
