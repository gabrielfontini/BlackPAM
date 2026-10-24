/*
 * main_rx.c — main de REFERÊNCIA do receptor.
 *
 * As funções MX_*_Init() reproduzem o que o CubeMX gera com a configuração de
 * docs/04_HARDWARE_E_CUBEMX.md. No seu projeto do CubeIDE copie apenas os
 * trechos "USER CODE" (ver firmware/INTEGRACAO.md).
 */
#include "main.h"
#include "pam_rx.h"

ADC_HandleTypeDef hadc1;
DMA_HandleTypeDef hdma_adc1;
TIM_HandleTypeDef htim2;
UART_HandleTypeDef huart1;

void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_ADC1_Init(void);
static void MX_TIM2_Init(void);
static void MX_USART1_UART_Init(void);

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_DMA_Init();              /* o CubeMX coloca o DMA antes do ADC */
    MX_ADC1_Init();
    MX_TIM2_Init();
    MX_USART1_UART_Init();

    /* USER CODE BEGIN 2 */
    PAM_RX_Init();
    /* USER CODE END 2 */

    while (1) {
        /* USER CODE BEGIN 3 */
        PAM_RX_Loop();
        /* USER CODE END 3 */
    }
}

/* USER CODE BEGIN 4 */
void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance == ADC1) PAM_RX_DMA_HalfOrFull();
}
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance == ADC1) PAM_RX_DMA_HalfOrFull();
}
void HAL_ADC_ErrorCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance == ADC1) PAM_RX_ADC_Error();
}
/* USER CODE END 4 */

/* ADC1: 12 bits, PCLK2/4 = 25 MHz, 15 ciclos, disparo TIM2_CC2 (subida), DMA contínuo */
static void MX_ADC1_Init(void)
{
    ADC_ChannelConfTypeDef ch = {0};

    hadc1.Instance = ADC1;
    hadc1.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
    hadc1.Init.Resolution = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode = DISABLE;
    hadc1.Init.ContinuousConvMode = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_RISING;
    hadc1.Init.ExternalTrigConv = ADC_EXTERNALTRIGCONV_T2_CC2;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion = 1;
    hadc1.Init.DMAContinuousRequests = ENABLE;
    hadc1.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
    if (HAL_ADC_Init(&hadc1) != HAL_OK) Error_Handler();

    ch.Channel = ADC_CHANNEL_1;                 /* PA1 */
    ch.Rank = 1;
    ch.SamplingTime = ADC_SAMPLETIME_15CYCLES;
    if (HAL_ADC_ConfigChannel(&hadc1, &ch) != HAL_OK) Error_Handler();
}

/* TIM2: PSC=0, ARR=624 (6,25 µs); Slave Reset por TI1FP1 (PA0, subida);
 * CH2 = PWM sem saída, modo PWM2, CCR2=312 -> borda de TIM2_CC2 a ≈ 3,12 µs */
static void MX_TIM2_Init(void)
{
    TIM_ClockConfigTypeDef clk = {0};
    TIM_SlaveConfigTypeDef slave = {0};
    TIM_MasterConfigTypeDef master = {0};
    TIM_OC_InitTypeDef oc = {0};

    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 0;
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = 624;
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    if (HAL_TIM_Base_Init(&htim2) != HAL_OK) Error_Handler();
    clk.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
    if (HAL_TIM_ConfigClockSource(&htim2, &clk) != HAL_OK) Error_Handler();
    if (HAL_TIM_PWM_Init(&htim2) != HAL_OK) Error_Handler();

    slave.SlaveMode = TIM_SLAVEMODE_RESET;
    slave.InputTrigger = TIM_TS_TI1FP1;
    slave.TriggerPolarity = TIM_TRIGGERPOLARITY_RISING;
    slave.TriggerPrescaler = TIM_TRIGGERPRESCALER_DIV1;
    slave.TriggerFilter = 3;                    /* 8 amostras a 100 MHz = 80 ns */
    if (HAL_TIM_SlaveConfigSynchro(&htim2, &slave) != HAL_OK) Error_Handler();

    master.MasterOutputTrigger = TIM_TRGO_RESET;
    master.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
    if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &master) != HAL_OK) Error_Handler();

    oc.OCMode = TIM_OCMODE_PWM2;                /* OC2REF sobe quando CNT = 312 */
    oc.Pulse = 312;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    if (HAL_TIM_PWM_ConfigChannel(&htim2, &oc, TIM_CHANNEL_2) != HAL_OK) Error_Handler();
}

static void MX_USART1_UART_Init(void)
{
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 460800;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart1) != HAL_OK) Error_Handler();
}

static void MX_DMA_Init(void)
{
    __HAL_RCC_DMA2_CLK_ENABLE();
    HAL_NVIC_SetPriority(DMA2_Stream0_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(DMA2_Stream0_IRQn);
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef g = {0};
    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_GPIOH_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
    g.Pin = GPIO_PIN_13;                        /* LED */
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &g);

    g.Pin = GPIO_PIN_0;                         /* jumper PB0: GND = PAM-4 */
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB, &g);
}
