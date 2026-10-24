# 04 — Hardware, montagem e configuração no CubeMX

> Tudo aqui segue a Figura 3 e o Apêndice A do enunciado. Os valores que **não** estão no enunciado (UART, jumper de modo, pull-downs, filtro do trigger) estão marcados como **[extra]**: são escolhas desta solução e você deve declará-las no relatório.

---

## 1. Lista de material

| Item | Qtd | Observação |
|---|---|---|
| BlackPill STM32F411CEU6 (cristal de 25 MHz) | 2 | marque com fita: **TX** e **RX** |
| ST-Link V2 (ou clone) | 1–2 | SWDIO, SWCLK, GND, 3V3 (só para referência) |
| Adaptador USB-serial **3,3 V** (CP2102, CH340, FT232) | 1 | **[extra]** recebe o relatório do RX (PA9/PA10) |
| Resistor 330 Ω | 1 | filtro PWM do TX |
| Capacitor 390 pF (cerâmico C0G/NP0 de preferência) | 1 | filtro PWM do TX |
| Resistor 56 Ω | 1 | canal 2 |
| Capacitor 10 nF + 6,8 nF (em paralelo = 16,8 nF) | 1+1 | canal 2 (C0G ou poliéster: X7R pode variar ±10–15 %) |
| Capacitor 33 nF | 1 | troca feita pelo professor na defesa (leve um seu para ensaiar) |
| Resistor 1 kΩ | 1 (+1 opcional) | proteção do ADC (+ perturbação opcional) |
| Diodo Schottky (ex.: BAT54S, BAT85, 1N5817) | 2 | **pedir ao professor** |
| Resistor 10 kΩ | 1 | **[extra]** pull-down externo no fio de CLK no RX (recomendado) |
| Jumper ou fio | 2 | **[extra]** PB0 → GND seleciona PAM-4 (um em cada placa) |
| Fios Dupont ~20 cm | ≥ 6 | dados, CLK, GND |
| Protoboard | 1–2 | |
| Cabo manga 200 m (bobina) | 1 | canal 3 (exploratório) |
| Osciloscópio (TDS2002B), 2 pontas **×10** | 1 | use ×10: a ponta ×1 tem ~100 pF e muda o τ |
| Multímetro | 1 | medir o 3V3 do RX (= Vref do ADC) |

---

## 2. Pinagem final

### TX (BlackPill "TX")

| Pino | Função | Liga em |
|---|---|---|
| **PA8** | TIM1_CH1 — PWM 33,333 MHz (TP1) | resistor 330 Ω |
| **PB4** | TIM3_CH1 — CLK 20 kHz | fio Dupont "CLK" → PA0 do RX |
| PA0 | botão KEY da placa (entrada, pull-up) | — (aperte para retransmitir) |
| PB0 | **[extra]** jumper de modo (entrada, pull-up) | aberto = PAM-2 ; ao GND = PAM-4 |
| PC13 | LED (aceso = transmitindo) | — |
| PA13/PA14 | SWDIO/SWCLK | ST-Link |
| GND | | GND comum com o RX |

### RX (BlackPill "RX")

| Pino | Função | Liga em |
|---|---|---|
| **PA0** | TIM2_CH1 — entrada do CLK (reset do TIM2) | fio Dupont "CLK" (e 10 kΩ para GND) |
| **PA1** | ADC1_IN1 (TP4) | saída da rede de proteção |
| PA9 | **[extra]** USART1_TX 460 800 8N1 | RX do adaptador USB-serial |
| PA10 | **[extra]** USART1_RX | TX do adaptador USB-serial |
| PB0 | **[extra]** jumper de modo | aberto = PAM-2 ; ao GND = PAM-4 |
| PC13 | LED (aceso = armado; pisca = recebendo) | — |
| PA13/PA14 | SWD | ST-Link |
| 3V3 | trilho de 3,3 V do RX | **catodo do D+** e medição de Vref |
| GND | | GND comum, anodo do D−, GND do adaptador |

> ⚠️ **Não aperte o botão KEY do RX**: ele fica em PA0, que é a entrada do CLK. Cada aperto vira uma "borda" falsa.

> ⚠️ **Não una os pinos 3V3 das duas placas.** Só os GND. Cada placa é alimentada pelo seu próprio USB (ou ST-Link).

---

## 3. Esquema elétrico (Figura 3 do enunciado + extras)

```
            TX (BlackPill)                       CANAL                          RX (BlackPill)
                                                                                     3V3 (RX)
                                                                                        │
                                                                                     ───┴─── D+ (catodo no 3V3)
  PA8 ──[330 Ω]──●── TP2 ──── Dupont 20 cm ──[56 Ω]──●── TP3 ──[1 kΩ]──●── TP4 ── PA1 (ADC1_IN1)
   (TP1)         │                                   │                  │
              [390 pF]                           [16,8 nF]           ───┬─── D− (anodo no GND)
                 │                              (10n ∥ 6n8)             │
  GND ───────────●──────────── Dupont GND ───────────●──────────────────●──── GND (RX)

  PB4 (CLK) ──────────────── Dupont 20 cm ─────────────────────────●──── PA0 (TIM2_CH1)
                                                                   │
                                                                [10 kΩ] [extra]
                                                                   │
                                                                  GND

  Canal 1 (Dupont direto): retire o 56 Ω (curto) e o 16,8 nF.
  Canal 2 (RC):            56 Ω em série + 16,8 nF de TP3 para GND, ANTES do 1 kΩ.
  Troca da defesa:         16,8 nF -> 33 nF (só o capacitor).

  Diodos: D+ conduz de TP4 para 3V3 (anodo em TP4, catodo no 3V3 do RX)
          D− conduz de GND para TP4 (anodo no GND, catodo em TP4)

  Adaptador USB-serial: GND—GND, RX do adaptador—PA9, TX do adaptador—PA10. NÃO ligue o VCC dele.
```

### Canal 3 (cabo manga 200 m, exploratório)

```
  TP2 ─── condutor A do cabo (200 m em bobina) ───> TP3 (sem 56 Ω/16,8 nF) -> 1 kΩ -> TP4
  GND TX ─ condutor B do cabo (200 m) ─────────── GND RX
  PB4 ──── Dupont curto 20 cm ─────────────────── PA0
  GND TX ─ Dupont curto (necessário p/ o CLK) ─── GND RX   <- retorno PARALELO: declare!
  Outros retornos paralelos: USB das duas placas no mesmo PC, terra do osciloscópio.
```
Desenhe isso no relatório e escreva: *"o ensaio representa principalmente um condutor longo de dados com referência próxima, não um enlace isolado de 200 m"*.

---

## 4. Verificações elétricas ANTES de ligar PA1

1. Placas alimentadas, **só os GND unidos**; meça 0 V entre GND TX e GND RX.
2. Meça o 3V3 do RX com multímetro → anote **Vref** (ex.: 3,297 V). Ele entra nas contas da PSD.
3. Com o TX transmitindo (aperte KEY), veja TP2 e TP3 no osciloscópio: devem ficar entre 0 e 3,3 V.
4. Só então ligue o 1 kΩ em PA1.
5. Confira em TP4 que a forma de onda é igual à de TP3 (os diodos não devem conduzir).

---

## 5. CubeMX — projeto **TX** (passo a passo)

`File → New Project → Part Number: STM32F411CEU6 → Start Project`. Salve como `PAM_TX.ioc`.

### 5.1 System Core
- **SYS → Debug: Serial Wire** (libera PB4, que no modo JTAG seria NJTRST). Timebase: SysTick.
- **RCC → High Speed Clock (HSE): Crystal/Ceramic Resonator.**

### 5.2 Clock Configuration (aba)
| Campo | Valor |
|---|---|
| Input frequency | **25** MHz |
| PLL Source Mux | HSE |
| /M | **25** |
| ×N | **200** |
| /P | **2** |
| System Clock Mux | PLLCLK → SYSCLK = **100 MHz** |
| AHB Prescaler | /1 → HCLK 100 MHz |
| APB1 Prescaler | **/2** → PCLK1 50 MHz, **APB1 Timer clocks = 100 MHz** |
| APB2 Prescaler | **/1** → PCLK2 100 MHz, APB2 Timer clocks = 100 MHz |

Confira na tela que **TIM1, TIM2 e TIM3 recebem 100 MHz** (TIM1 no APB2, TIM2/3 no APB1 ×2). Tire print desta tela (é entregável).

### 5.3 TIM1 (PWM do nível) — PA8
- **TIM1 → Clock Source: Internal Clock; Channel1: PWM Generation CH1.** (o CubeMX põe TIM1_CH1 em **PA8**; confira no pinout)
- Parameter Settings:
  - Prescaler = **0**; Counter Mode = Up; Counter Period (ARR) = **2**; auto-reload preload = Disable
  - PWM Generation Channel 1: Mode = **PWM mode 1**; Pulse = **0**; **Output compare preload = Enable**; Fast Mode = Disable; CH Polarity = High
- GPIO Settings (PA8): **Maximum output speed = Very High**.

### 5.4 TIM3 (CLK de símbolo) — PB4
- **TIM3 → Clock Source: Internal Clock; Channel1: PWM Generation CH1.** No pinout, clique em **PB4 → TIM3_CH1** (por padrão pode ir para PA6; mude para PB4).
- Parameter Settings: Prescaler = **0**; ARR = **4999**; PWM mode 1; Pulse = **2500**; Output compare preload = Enable.
- **NVIC Settings: TIM3 global interrupt = Enabled.**
- GPIO (PB4): Pull-down **[extra]**, speed High.

### 5.5 GPIO
- **PC13 → GPIO_Output** (LED), nível inicial High (LED apagado).
- **PA0 → GPIO_Input**, Pull-up (KEY).
- **PB0 → GPIO_Input**, Pull-up **[extra]** (jumper de modo).

### 5.6 NVIC (System Core → NVIC)
- TIM3 global interrupt: **Preemption Priority 0** (a mais alta). SysTick pode ficar com 15.

### 5.7 Project Manager
- Toolchain/IDE: **STM32CubeIDE**. Code Generator: "Copy only the necessary library files". **GENERATE CODE.**

---

## 6. CubeMX — projeto **RX** (passo a passo)

Novo projeto STM32F411CEU6 → `PAM_RX.ioc`. Repita **5.1** e **5.2** (Serial Wire, HSE, mesmo clock).

### 6.1 TIM2 — recebe o CLK e dispara o ADC
- **Slave Mode: Reset Mode**; **Trigger Source: TI1FP1** (o CubeMX coloca **PA0 = TIM2_CH1**).
- **Clock Source: Internal Clock.**
- **Channel2: PWM Generation No Output** (sem pino físico).
- Parameter Settings:
  - Prescaler = **0**; Counter Period = **624** (6,25 µs)
  - Trigger: Polarity = **Rising Edge**; **Trigger Filter = 3** **[extra]** (rejeita glitches < 80 ns)
  - PWM Generation Channel 2: **Mode = PWM mode 2**, **Pulse = 312**
    > Por que PWM mode 2? O sinal interno OC2REF fica em 0 enquanto CNT < 312 e sobe quando CNT = 312. A **borda de subida** de TIM2_CC2 ocorre então a ≈ 3,12 µs de cada reinício e a cada 6,25 µs depois. É essa borda que dispara o ADC. (Com "Output Compare No Output / Frozen" o sinal de disparo pode não ter borda.)
- **NVIC: TIM2 global interrupt = Enabled, Preemption Priority 0.**
- GPIO (PA0): Pull-down **[extra]**.

### 6.2 ADC1 — PA1
- **IN1** marcado (PA1 vira ADC1_IN1).
- Parameter Settings:
  - Clock Prescaler = **PCLK2 divided by 4** (25 MHz)
  - Resolution = **12 bits**; Data Alignment = Right
  - Scan Conversion Mode = Disabled; **Continuous Conversion Mode = Disabled**; Discontinuous = Disabled
  - **DMA Continuous Requests = Enabled**
  - End Of Conversion Selection = EOC flag at the end of single channel conversion
  - Number Of Conversion = 1
  - **External Trigger Conversion Source = Timer 2 Capture Compare 2 event**
  - **External Trigger Conversion Edge = Trigger detection on the rising edge**
  - Rank 1: Channel 1, **Sampling Time = 15 Cycles**
- **DMA Settings → Add → ADC1**: Stream **DMA2 Stream 0**, Direction Peripheral To Memory, Priority High, **Mode = Circular**, Increment Address: Memory ✔ (Peripheral ✘), Data Width: **Half Word / Half Word**.
- NVIC: DMA2 stream0 global interrupt = Enabled, **Preemption Priority 1**. (ADC1 global interrupt pode ficar desabilitado: o firmware confere o overrun por registro.)

> Conta para a defesa: 15 ciclos de amostragem + 12 de conversão = 27 ciclos ÷ 25 MHz = **1,08 µs** < 6,25 µs entre amostras.

### 6.3 USART1 **[extra]**
- Mode: Asynchronous (PA9 TX, PA10 RX). Baud = **460800**, 8 bits, sem paridade, 1 stop. Sem interrupção.

### 6.4 GPIO
- PC13 → GPIO_Output (inicial High). PB0 → GPIO_Input, Pull-up.

### 6.5 Project Manager → STM32CubeIDE → GENERATE CODE.

### 6.6 Prints obrigatórios (entregáveis)
Pinout (TX e RX), Clock Configuration (TX e RX), parâmetros do TIM1/TIM3 (TX) e TIM2/ADC1/DMA (RX).

---

## 7. Gravação e verificação do firmware

Siga `firmware/INTEGRACAO.md` para copiar os arquivos e colar os trechos USER CODE. Depois:

1. **TX**: grave, abra o osciloscópio com CH1 = PB4 (CLK) e CH2 = TP2. Aperte RESET: depois de 1 s o LED acende e o quadro sai (PAM-2 ≈ 5 s; PAM-4 ≈ 2,5 s).
   - meça **50,0 µs** entre bordas de subida do CLK (20 kHz) e duty de 50 %;
   - no início, veja o treinamento **0,0,0,A,0,0,0** (pulso a cada 350 µs);
   - meça o atraso entre a borda do CLK e o início da transição em TP2 (esperado ≈ 0,2–0,4 µs: latência da ISR). Registre: é o "alinhamento" pedido no Apêndice A.1;
   - PAM-4: confirme os 4 níveis ≈ 0 / 1,1 / 2,2 / 3,3 V na sequência 0,1,0,3,2,3,1,2 (calibração).
2. **RX**: grave, abra um terminal serial (460800 8N1) ou `matlab/captura_serial.m`. Deve aparecer `#ARMADO PAM-x ...`.
3. Aperte RESET no TX. Em ~6 s o RX imprime `#BEGIN_REPORT ... #END_PSD`. Confira `aquisicao_valida=1`, `bordas_CLK = simbolos_esperados`, `bordas_com_contagem_errada=0`.

### Modulação e canal (comandos do RX)
| Tecla | Efeito |
|---|---|
| `2` / `4` | PAM-2 / PAM-4 (e rearma) |
| `d` / `c` / `x` / `m` | rótulo do canal: Dupont / RC 16,8 nF / RC 33 nF / manga (e rearma) |
| `r` | rearmar para um novo quadro |
| `p` | reimprimir o último relatório |

O **TX** escolhe a modulação pelo jumper PB0 **no momento da transmissão** (PB0 ao GND = PAM-4). Mantenha TX e RX na mesma modulação.

---

## 8. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| CLK a 10 kHz ou 40 kHz | APB1 timer ≠ 100 MHz | refaça a Clock Configuration |
| `bordas_com_contagem_errada > 0` | borda falsa no CLK (reset do TX, KEY do RX) | pull-down de 10 kΩ em PA0; não toque no KEY do RX; rearme e repita |
| `perda_CLK=1` | fio do CLK solto, TX resetou no meio | repita |
| `calibracao_ok=0` | centros fora de ordem: modulação diferente no TX e no RX, canal invertido, TP3 saturando | confira jumper PB0 nas duas placas |
| `sincronismo_ok=0` com BER zero no treinamento | erro nos 48 bits de início (ruído) ou quadro deslocado | repita; se persistir, olhe `inicio_quadro_erros_u/z` |
| nível 3 = 4095 sempre | 3V3 do TX > 3V3 do RX (ADC satura) | normal; registre. Os limiares continuam válidos |
| nada na serial | TX/RX do adaptador invertidos, baud errado, GND do adaptador solto | |
| ADC lê ~0 o tempo todo | PA1 sem sinal, diodo D− invertido | meça TP4 |
