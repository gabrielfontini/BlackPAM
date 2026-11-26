# 06 — Ligações por pino

> Montagem real da equipe: capacitores escolhidos entre os disponíveis (sem 390 pF nem 6,8 nF) e serial por um **Raspberry Pi Pico (RP2040)** com o firmware `pico-uart-bridge`, porta **/dev/ttyACM1** (UART1 = GP4/GP5).

## BlackPill TX

| Pino | Liga em |
|---|---|
| **PA8** | resistor **330 Ω** → ponto **TP2** |
| **TP2** | **4 capacitores de 100 pF em paralelo** para o GND (= 400 pF, no lugar dos 390 pF) · fio Dupont 20 cm de **dados** → canal (ver abaixo) |
| **PB4** | fio Dupont 20 cm de **CLK** → **PA0 do RX** |
| **PB0** | fio para o **GND** = PAM-4 · solto = PAM-2 |
| **GND** | GND do RX |
| **3V3** | nada |
| **USB-C** | PC ou carregador |

Filtro do TX: τ = 330 Ω × 400 pF = **0,132 µs** (enunciado: 330 × 390 pF = 0,129 µs, diferença de +2,6 %, dentro da tolerância do capacitor).

## Canal (entre o fio de dados e o RX)

| Ensaio | Fio de dados → TP3 | TP3 → GND | Rótulo no RX |
|---|---|---|---|
| Canal 1 — Dupont | direto | nada | `d` |
| Canal 2 — RC | resistor **56 Ω** | **33 nF em série com 33 nF** = **16,5 nF** (no lugar dos 16,8 nF) | `c` |
| Defesa — 33 nF | resistor **56 Ω** | **jumper sobre um dos dois 33 nF** (sobra um só 33 nF) — ou troque o par por um 33 nF | `x` |
| Canal 3 — cabo manga | cabo de 200 m no lugar do fio Dupont | nada | `m` |

**Como ligar os dois 33 nF em série:** o primeiro vai de **TP3** até uma coluna livre (chame de **N**); o segundo vai de **N** até o **GND**. Para a defesa, um fio de N ao GND curto-circuita o segundo capacitor e o canal fica com 33 nF.

τ do canal 2 (1 polo, como no enunciado): (330 + 56) Ω × 16,5 nF = **6,37 µs** (com 16,8 nF seria 6,48 µs, −1,8 %). Pelo modelo de 2 polos (+400 pF do TX e ~30 Ω do GPIO) o previsto fica ≈ **7,0 µs**.

## BlackPill RX

| Pino | Liga em |
|---|---|
| **PA1** | ponto **TP4** |
| **TP4** | resistor **1 kΩ** → **TP3** · diodo **D−** (1N5817): anodo no GND, faixa em TP4 · diodo **D+** (1N5817): anodo em TP4, faixa no 3V3 do RX |
| **PA0** | fio de CLK vindo do **PB4 do TX** · resistor **10 kΩ** para o GND |
| **PA9** (USART1_TX) | **GP5** do Pico (UART1 RX) |
| **PA10** (USART1_RX) | **GP4** do Pico (UART1 TX) |
| **PB0** | fio para o **GND** = PAM-4 (opcional: dá para escolher pela serial) |
| **3V3** | faixa do diodo **D+** |
| **GND** | GND do TX · GND do Pico · anodo do D− · capacitores do TX e do canal · resistor 10 kΩ |
| **USB-C** | PC |

## Raspberry Pi Pico (RP2040) com `pico-uart-bridge`

| Pino do Pico | Pino físico | Liga em |
|---|---|---|
| **GP4** (UART1 TX) | 6 | **PA10 do RX** |
| **GP5** (UART1 RX) | 7 | **PA9 do RX** |
| **GND** | 8 (ou qualquer GND) | GND do RX |
| 3V3 / VSYS / VBUS | — | nada |
| **USB** | — | PC → aparece como **/dev/ttyACM1** |

A ligação é **cruzada** (TX de um no RX do outro), como em qualquer adaptador USB-serial. O `pico-uart-bridge` cria duas portas: **/dev/ttyACM0** = UART0 (GP0/GP1, não usada) e **/dev/ttyACM1** = UART1 (GP4/GP5, a nossa). O baud (460 800) é o que o PC pedir ao abrir a porta.

Nome fixo da porta (não muda se outro aparelho pegar ACM0/ACM1): `/dev/serial/by-id/usb-Raspberry_Pi_Pico_D6651C31E654822A-if02` → ttyACM1.

Gravar o firmware (uma vez): baixe `uart_bridge.uf2` em github.com/Noltari/pico-uart-bridge → Releases (v4.2); segure **BOOTSEL**, ligue o USB, solte; arraste o `.uf2` para o disco **RPI-RP2**. O Pico reinicia sozinho como ponte serial.

## Não fazer

- Não ligar o 3V3 do TX no 3V3 do RX, nem o 3V3/VSYS do Pico em nenhuma das duas. Entre as placas, só os GND se ligam.
- Não apertar o botão KEY do RX: ele está no PA0, a entrada do CLK.
- Ligar o fio do PA1 do RX só depois de ver no osciloscópio que TP3 fica entre 0 e 3,3 V.
- Não usar a /dev/ttyACM0: ela é a UART0 do Pico (GP0/GP1), onde não há nada ligado.
