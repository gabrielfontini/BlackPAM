# Integração do firmware no projeto gerado pelo CubeMX (STM32CubeIDE)

O código está dividido em duas partes:

| Arquivo | Usa HAL? | Função |
|---|---|---|
| `common/pam_config.h` | não | todos os números do enunciado (Rs, ARR, CCR, tamanhos do quadro) |
| `common/pam_frame.h/.c` | não | PRBS-15, treinamento, início de quadro, payload, Gray |
| `tx/pam_tx.h/.c` | sim | TX: escreve TIM1_CCR1 a cada borda do CLK (ISR do TIM3) |
| `rx/pam_rx_core.h/.c` | não | RX: filtro casado, k*, centros, limiares, margens, BER/SER |
| `rx/pam_rx_report.h/.c` | não | RX: relatório em texto (mesmo formato no PC e na placa) |
| `rx/pam_rx.h/.c` | sim | RX: TIM2 + ADC + DMA, alinhamento pela borda, perdas, serial |

As partes **sem HAL** são testadas no PC: `cd teste_host && make && ./sim_host 4 1`.
A pasta `build_referencia/` compila TX e RX completos com a HAL oficial (prova de que tudo compila; os `main_*.c` de lá mostram o que o CubeMX gera).

---

## Projeto TX (`PAM_TX`)

1. Copie para `Core/Inc/`: `common/pam_config.h`, `common/pam_frame.h`, `tx/pam_tx.h`
2. Copie para `Core/Src/`: `common/pam_frame.c`, `tx/pam_tx.c`
3. `Core/Src/main.c`:

```c
/* USER CODE BEGIN Includes */
#include "pam_tx.h"
/* USER CODE END Includes */
...
  /* USER CODE BEGIN 2 */
  PAM_TX_Init();
  /* USER CODE END 2 */

  while (1)
  {
    /* USER CODE END WHILE */
    /* USER CODE BEGIN 3 */
    PAM_TX_Loop();
  }
  /* USER CODE END 3 */
```

4. `Core/Src/stm32f4xx_it.c`:

```c
/* USER CODE BEGIN Includes */
#include "pam_tx.h"
/* USER CODE END Includes */
...
void TIM3_IRQHandler(void)
{
  /* USER CODE BEGIN TIM3_IRQn 0 */
  PAM_TX_TIM3_IRQ();          /* PRIMEIRA linha: escreve o novo nível em TIM1_CCR1 */
  /* USER CODE END TIM3_IRQn 0 */
  HAL_TIM_IRQHandler(&htim3);
  ...
```

5. Build (martelo) → Run. O TX transmite 1 s depois do reset; KEY retransmite.

---

## Projeto RX (`PAM_RX`)

1. Copie para `Core/Inc/`: `pam_config.h`, `pam_frame.h`, `pam_rx.h`, `pam_rx_core.h`, `pam_rx_report.h`
2. Copie para `Core/Src/`: `pam_frame.c`, `pam_rx.c`, `pam_rx_core.c`, `pam_rx_report.c`
3. `Core/Src/main.c`:

```c
/* USER CODE BEGIN Includes */
#include "pam_rx.h"
/* USER CODE END Includes */
...
  /* USER CODE BEGIN 2 */
  PAM_RX_Init();
  /* USER CODE END 2 */

  while (1)
  {
    /* USER CODE END WHILE */
    /* USER CODE BEGIN 3 */
    PAM_RX_Loop();
  }
  /* USER CODE END 3 */
...
/* USER CODE BEGIN 4 */
void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc)
{
  if (hadc->Instance == ADC1) PAM_RX_DMA_HalfOrFull();   /* amostras 0..255 prontas   */
}
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
  if (hadc->Instance == ADC1) PAM_RX_DMA_HalfOrFull();   /* amostras 256..511 prontas */
}
void HAL_ADC_ErrorCallback(ADC_HandleTypeDef *hadc)
{
  if (hadc->Instance == ADC1) PAM_RX_ADC_Error();        /* overrun do ADC */
}
/* USER CODE END 4 */
```

4. `Core/Src/stm32f4xx_it.c`:

```c
/* USER CODE BEGIN Includes */
#include "pam_rx.h"
/* USER CODE END Includes */
...
void TIM2_IRQHandler(void)
{
  /* USER CODE BEGIN TIM2_IRQn 0 */
  PAM_RX_TIM2_IRQ();          /* conta a borda do CLK e confere 8 amostras/borda */
  /* USER CODE END TIM2_IRQn 0 */
  HAL_TIM_IRQHandler(&htim2);
  ...
```

5. Os nomes `hadc1`, `htim2`, `huart1` precisam ser os que o CubeMX gerou (padrão).
6. Build → Run. Abra o terminal serial a **460800** baud.

---

## Como o RX funciona (para explicar na defesa)

```
 CLK (PA0) ──► TIM2 reset ──► CNT=0 ──► CNT=312 (3,12 µs): TIM2_CC2 ──► ADC converte (1,08 µs)
                  │                    CNT=312+625k: k = 1..7                     │
                  │                                                               ▼
                  └─► ISR TIM2 (borda): conta bordas;                    DMA2 Stream0 → buffer[512]
                      1ª borda: espera 2 µs e anota a posição do DMA      │ meia (256) / cheia (512)
                      demais: confere W = abs0 + 8·n                      ▼
                                                                 PAM_RX_Loop(): a cada 8 amostras
                                                                 → pam_rx_symbol() → treinamento /
                                                                   calibração / início / payload
```

* **Sem interrupção por amostra**: o ADC é disparado por hardware e o DMA grava; a CPU só é avisada a cada 256 amostras (32 símbolos).
* **Descarte do pré-CLK**: o TIM2 roda livre antes do CLK (dispara conversões que não interessam). Na 1ª borda a ISR anota o índice absoluto `abs0` da próxima amostra (= `a_0[0]`); tudo antes é descartado (`amostras_descartadas_antes_CLK`).
* **Perda de amostras**: em cada borda n o número absoluto de amostras escritas deve ser `abs0 + 8n`. Qualquer diferença incrementa `bordas_com_contagem_errada` → quadro inválido.
* **Overrun do processamento**: se a CPU atrasar mais que 512 amostras, `overrun_processamento=1`.
* **Fim / perda de CLK**: 5 ms sem borda encerra o quadro; se faltar símbolo, `perda_CLK=1`.
* Os parâmetros (k*, p_c, centros, limiares) são **congelados** no fim dos 396 símbolos de treinamento, antes do início de quadro, e nunca mais mudam.

## Desafio opcional (100 ksym/s)
Troque `PAM_SYM_RATE_HZ` para `100000u` em `pam_config.h` nos dois projetos (o firmware recalcula ARR = 999 / 124 e CCR = 500 / 62). Então fa = 800 kHz: cada conversão (1,08 µs) cabe em 1,25 µs. Atenção (não testado em placa): a 100 ksym/s a amostra k = 0 sai a 0,62 µs da borda, então a espera de 2 µs da 1ª borda em `pam_rx.c` (`FIRST_EDGE_WAIT_TICKS`) **não serve**. Uma saída é iniciar o TIM2 em *Trigger Mode* (só começa a contar na 1ª borda, sem amostras antes do CLK) e trocar para *Reset Mode* dentro da ISR da 1ª borda. A verificação de 8 amostras/borda também precisa de tolerância de ±1, porque a conversão de k = 7 termina depois da borda seguinte. Justifique a taxa de aquisição e mostre `bordas_com_contagem_errada=0`.
