/* stm32f4xx_hal_msp.c de REFERÊNCIA do TX (equivalente ao gerado pelo CubeMX) */
#include "main.h"

void HAL_MspInit(void)
{
    __HAL_RCC_SYSCFG_CLK_ENABLE();
    __HAL_RCC_PWR_CLK_ENABLE();
}

void HAL_TIM_Base_MspInit(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM1) {
        __HAL_RCC_TIM1_CLK_ENABLE();
    } else if (htim->Instance == TIM3) {
        __HAL_RCC_TIM3_CLK_ENABLE();
        HAL_NVIC_SetPriority(TIM3_IRQn, 0, 0);     /* prioridade máxima */
        HAL_NVIC_EnableIRQ(TIM3_IRQn);
    }
}

void HAL_TIM_MspPostInit(TIM_HandleTypeDef *htim)
{
    GPIO_InitTypeDef g = {0};
    if (htim->Instance == TIM1) {
        __HAL_RCC_GPIOA_CLK_ENABLE();
        g.Pin = GPIO_PIN_8;                         /* PA8 -> TIM1_CH1 */
        g.Mode = GPIO_MODE_AF_PP;
        g.Pull = GPIO_NOPULL;
        g.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
        g.Alternate = GPIO_AF1_TIM1;
        HAL_GPIO_Init(GPIOA, &g);
    } else if (htim->Instance == TIM3) {
        __HAL_RCC_GPIOB_CLK_ENABLE();
        g.Pin = GPIO_PIN_4;                         /* PB4 -> TIM3_CH1 (CLK) */
        g.Mode = GPIO_MODE_AF_PP;
        g.Pull = GPIO_PULLDOWN;
        g.Speed = GPIO_SPEED_FREQ_HIGH;
        g.Alternate = GPIO_AF2_TIM3;
        HAL_GPIO_Init(GPIOB, &g);
    }
}
