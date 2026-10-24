/* stm32f4xx_it.c de REFERÊNCIA do TX — o que importa é TIM3_IRQHandler */
#include "main.h"
#include "pam_tx.h"

extern TIM_HandleTypeDef htim3;

void NMI_Handler(void) { while (1) { } }
void HardFault_Handler(void) { while (1) { } }
void MemManage_Handler(void) { while (1) { } }
void BusFault_Handler(void) { while (1) { } }
void UsageFault_Handler(void) { while (1) { } }
void SVC_Handler(void) { }
void DebugMon_Handler(void) { }
void PendSV_Handler(void) { }
void SysTick_Handler(void) { HAL_IncTick(); }

void TIM3_IRQHandler(void)
{
    /* USER CODE BEGIN TIM3_IRQn 0 */
    PAM_TX_TIM3_IRQ();          /* escreve o novo nível em TIM1_CCR1 primeiro */
    /* USER CODE END TIM3_IRQn 0 */
    HAL_TIM_IRQHandler(&htim3);
}
