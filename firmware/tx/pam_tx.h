/*
 * pam_tx.h — firmware do TRANSMISSOR (BlackPill STM32F411CEU6)
 *
 *  PA8  = TIM1_CH1  PWM 33,333 MHz (PSC=0, ARR=2)  -> 330 Ω / 390 pF -> TP2
 *  PB4  = TIM3_CH1  CLK de símbolo 20 kHz (PSC=0, ARR=4999, CCR1=2500)
 *  PB0  = entrada com pull-up: aberto = PAM-2 ; ligado ao GND = PAM-4
 *  PA0  = botão KEY da BlackPill: pressionar = transmitir o quadro de novo
 *  PC13 = LED (aceso durante a transmissão)
 */
#ifndef PAM_TX_H
#define PAM_TX_H

#include "main.h"
#include "pam_frame.h"

extern TIM_HandleTypeDef htim1;
extern TIM_HandleTypeDef htim3;

void PAM_TX_Init(void);               /* chamar uma vez depois dos MX_..._Init() */
void PAM_TX_StartFrame(pam_mod_t mod);/* transmite o quadro completo uma vez      */
uint8_t PAM_TX_Busy(void);
void PAM_TX_Loop(void);               /* chamar no while(1) do main               */
void PAM_TX_TIM3_IRQ(void);           /* chamar no início de TIM3_IRQHandler      */

#endif /* PAM_TX_H */
