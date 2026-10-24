/* stm32f4xx_it.c de REFERÊNCIA do RX — o que importa: TIM2 e DMA2_Stream0 */
#include "main.h"
#include "pam_rx.h"

extern DMA_HandleTypeDef hdma_adc1;
extern TIM_HandleTypeDef htim2;

void NMI_Handler(void) { while (1) { } }
void HardFault_Handler(void) { while (1) { } }
void MemManage_Handler(void) { while (1) { } }
void BusFault_Handler(void) { while (1) { } }
void UsageFault_Handler(void) { while (1) { } }
void SVC_Handler(void) { }
void DebugMon_Handler(void) { }
void PendSV_Handler(void) { }
void SysTick_Handler(void) { HAL_IncTick(); }

void TIM2_IRQHandler(void)
{
    /* USER CODE BEGIN TIM2_IRQn 0 */
    PAM_RX_TIM2_IRQ();          /* conta a borda do CLK e confere as amostras */
    /* USER CODE END TIM2_IRQn 0 */
    HAL_TIM_IRQHandler(&htim2);
}

void DMA2_Stream0_IRQHandler(void)
{
    HAL_DMA_IRQHandler(&hdma_adc1);  /* chama HAL_ADC_ConvHalfCplt/ConvCplt */
}
