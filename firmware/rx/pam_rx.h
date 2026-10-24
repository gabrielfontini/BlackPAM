/*
 * pam_rx.h — firmware do RECEPTOR (BlackPill STM32F411CEU6)
 *
 *  PA0  = TIM2_CH1  entrada do CLK (Slave Reset Mode, TI1FP1, borda de subida)
 *  PA1  = ADC1_IN1  sinal protegido (1 kΩ + 2 Schottky) = TP4
 *  TIM2_CH2 = PWM sem saída (modo PWM2, CCR2 = 312) -> dispara o ADC (TIM2_CC2)
 *  ADC1 -> DMA2 Stream0 Channel0, circular, 512 x 16 bits
 *  PA9  = USART1_TX  (460 800 8N1) -> adaptador USB-serial -> PC
 *  PA10 = USART1_RX  comandos: '2' = PAM-2, '4' = PAM-4, 'r' = rearmar
 *  PB0  = entrada com pull-up: aberto = PAM-2 ; ligado ao GND = PAM-4
 *  PC13 = LED (aceso = armado esperando CLK; pisca = recebendo)
 */
#ifndef PAM_RX_H
#define PAM_RX_H

#include "main.h"
#include "pam_rx_core.h"

extern ADC_HandleTypeDef hadc1;
extern TIM_HandleTypeDef htim2;
extern UART_HandleTypeDef huart1;

void PAM_RX_Init(void);           /* chamar uma vez depois dos MX_..._Init()    */
void PAM_RX_Loop(void);           /* chamar no while(1) do main                  */
void PAM_RX_TIM2_IRQ(void);       /* chamar no início de TIM2_IRQHandler         */
void PAM_RX_DMA_HalfOrFull(void); /* chamado pelos callbacks do ADC (meia/cheia) */
void PAM_RX_ADC_Error(void);      /* chamado por HAL_ADC_ErrorCallback           */

#endif /* PAM_RX_H */
