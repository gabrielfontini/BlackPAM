# 07 — O que escrever em cada área USER CODE (CubeIDE)

Só escreva **entre** `/* USER CODE BEGIN x */` e `/* USER CODE END x */`. Fora dessas marcas, o CubeMX apaga tudo ao gerar o código de novo.
Áreas que não aparecem aqui ficam **vazias**.

Os arquivos `pam_*.c` e `pam_*.h` já estão em `Core/Src` e `Core/Inc` dos dois projetos (`firmware/fir_tx/TX` e `firmware/fir_tx/RX`).

---

## TX — `TX/Core/Src/main.c`

### `USER CODE BEGIN Includes`
```c
#include "pam_tx.h"
```

### `USER CODE BEGIN 2` (logo depois de `MX_TIM3_Init();`)
```c
  PAM_TX_Init();
```

### `USER CODE BEGIN 3` (dentro do `while (1)`)
```c
    PAM_TX_Loop();
```

### `USER CODE BEGIN MX_GPIO_Init_2` (final de `MX_GPIO_Init`)
```c
  /* KEY (PA0) e MODE (PB0) com pull-up: solto = 1, no GND = 0 */
  GPIO_InitStruct.Pin  = KEY_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_PULLUP;
  HAL_GPIO_Init(KEY_GPIO_Port, &GPIO_InitStruct);

  GPIO_InitStruct.Pin  = MODE_Pin;
  HAL_GPIO_Init(MODE_GPIO_Port, &GPIO_InitStruct);

  HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_SET);   /* LED apagado */
```
> Isto é necessário porque o seu `.ioc` gerou KEY e MODE como `GPIO_NOPULL`. Sem pull-up, o PB0 solto fica flutuando e o modo PAM-2/PAM-4 sai aleatório. Se preferir corrigir no `.ioc` (PA0 e PB0 → *Pull-up*), este bloco pode ficar vazio.

---

## TX — `TX/Core/Src/stm32f4xx_it.c`

### `USER CODE BEGIN Includes`
```c
#include "pam_tx.h"
```

### `USER CODE BEGIN TIM3_IRQn 0` (dentro de `TIM3_IRQHandler`, **antes** de `HAL_TIM_IRQHandler(&htim3);`)
```c
  PAM_TX_TIM3_IRQ();
```

---

## RX — `RX/Core/Src/main.c`

### `USER CODE BEGIN Includes`
```c
#include "pam_rx.h"
```

### `USER CODE BEGIN USART1_Init 2` (depois do `HAL_UART_Init`)
```c
  huart1.Init.BaudRate = 460800;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
```
> Isto é necessário porque o seu `.ioc` está em **115200** e o app espera **460800**. Se você mudar no `.ioc` (USART1 → Baud Rate = 460800), este bloco pode ficar vazio.

### `USER CODE BEGIN 2` (logo depois de `MX_USART1_UART_Init();`)
```c
  PAM_RX_Init();
```

### `USER CODE BEGIN 3` (dentro do `while (1)`)
```c
    PAM_RX_Loop();
```

### `USER CODE BEGIN 4` (depois do `SystemClock_Config` e dos `MX_..._Init`, antes de `Error_Handler`)
```c
void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc)
{
  if (hadc->Instance == ADC1) PAM_RX_DMA_HalfOrFull();   /* amostras 0..255 prontas */
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
  if (hadc->Instance == ADC1) PAM_RX_DMA_HalfOrFull();   /* amostras 256..511 prontas */
}

void HAL_ADC_ErrorCallback(ADC_HandleTypeDef *hadc)
{
  if (hadc->Instance == ADC1) PAM_RX_ADC_Error();        /* overrun do ADC */
}
```

---

## RX — `RX/Core/Src/stm32f4xx_it.c`

### `USER CODE BEGIN Includes`
```c
#include "pam_rx.h"
```

### `USER CODE BEGIN TIM2_IRQn 0` (dentro de `TIM2_IRQHandler`, **antes** de `HAL_TIM_IRQHandler(&htim2);`)
```c
  PAM_RX_TIM2_IRQ();
```

O `ADC_IRQHandler` e o `DMA2_Stream0_IRQHandler` não precisam de nada.

---

## Não precisa mudar no `.ioc`

O `PAM_TX_Init()` e o `PAM_RX_Init()` reescrevem os valores abaixo. Por isso não importa o que o CubeMX gerou para eles:

| Projeto | Valor no seu `.ioc` | O firmware coloca |
|---|---|---|
| TX | TIM1 Period = 65535 | ARR = 2 (33,3 MHz) |
| TX | TIM3 Pulse = 0 | CCR1 = 2500 |
| RX | TIM2 CH2 Pulse = 0 | CCR2 = 312 |

Opcional no RX: TIM2 → Slave Mode → **Trigger Filter = 3** (hoje está 0). Esse filtro rejeita ruído no fio do CLK.

---

## Conferir
1. Compile com o martelo (**Build**): tem que dar 0 erros.
2. TX: 1 s depois do reset o LED acende durante a transmissão (cerca de 5 s em PAM-2 e 2,5 s em PAM-4).
3. RX: o LED fica aceso esperando o CLK. No app, conecte a 460800 baud.
