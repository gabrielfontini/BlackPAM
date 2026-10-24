# 03 — Simulink passo a passo (montar à mão e simular)

Dois modelos, ambos testados no MATLAB/Simulink **R2026a** sem a Communications Toolbox (só blocos básicos + Simscape Electrical):

| Modelo | Arquivo de referência | O que mostra |
|---|---|---|
| **A** — enlace completo | `simulink/pam_enlace_simulink.slx` | quadro → níveis → canal RC (sistema LIT) → ADC 8× → amostra única e filtro casado → decisão → contagem de erros. Olho, k*, ISI, PSD, BER × ruído |
| **B** — circuito físico | `simulink/pam_circuito_simscape.slx` | PWM de 33,3 MHz real → 330 Ω/390 pF → 56 Ω/16,8 nF → 1 kΩ + Schottky → ADC. Ripple do PWM, τ, efeito do 390 pF e do 33 nF |

Os modelos de referência foram gerados por `simulink/criar_modelos_simulink.m`. **Monte o seu à mão** seguindo este guia (é o que você vai precisar explicar) e use o de referência só para conferir.

Imagens dos modelos prontos: `docs/img/modelo_A_enlace.png` e `docs/img/modelo_B_circuito.png`.

---

## 0. Preparação (vale para os dois)

1. No MATLAB, vá para a pasta `Projeto_PAM_BB/simulink`.
2. Escolha a condição e carregue as variáveis:
   ```matlab
   M = 4;                 % 2 ou 4
   canal = 'rc';          % 'dupont' | 'rc' | 'rc33'
   sigma_ruido = 0.002;   % ruído RMS no ADC (V)
   N_payload_sim = 2000;  % símbolos de payload na simulação
   usar_pwm = 0;          % modelo B: 1 = PWM real (lento), 0 = nível médio
   pam_simulink_init
   ```
   `pam_simulink_init.m` cria no workspace: `Ts, Tsa, t0, Vmax, Vref, q_adc, num_canal, den_canal, fonte_nivel, fonte_payload, T_sim, bc, pc, Ec, hc, kstar, t_kstar, t_fim, thr_u, thr_z, tab_bits, sigma_ruido`, e para o modelo B `Rgpio, R1, C1, R2, C2, Rprot, C_adc, Vf_schottky, Ron_schottky, fonte_ccr, T_sim_circ, usar_pwm, max_step_circ`.
3. Ao criar o modelo: **Modeling → Model Settings → Model Properties → Callbacks → InitFcn**:
   ```matlab
   run(fullfile(fileparts(get_param(bdroot,'FileName')),'pam_simulink_init.m'))
   ```
   (cole o mesmo em **PostLoadFcn**). Assim, toda vez que você aperta **Run**, as variáveis são recalculadas com o `M`/`canal` atuais.

> Para achar um bloco: no **Library Browser** digite o nome na busca, ou clique no fundo do modelo e **digite o nome do bloco** (quick insert).

---

## 1. MODELO A — `meu_enlace.slx`

### 1.1 Configuração do solver
**Modeling → Model Settings → Solver**:

| Campo | Valor | Por quê |
|---|---|---|
| Stop time | `T_sim` | duração do quadro simulado |
| Type | Variable-step | mistura de contínuo (canal) com discreto (ADC) |
| Solver | **ode23tb** (stiff) | a escada RC tem um polo rápido (~18 ns) e outro lento (~7 µs) |
| Max step size | `1e-6` | forma de onda suave |
| Relative tolerance | `1e-4` | |

**Data Import/Export**: marque *Single simulation output* (`out`).

### 1.2 Blocos — transmissor e canal

| # | Nome sugerido | Biblioteca → bloco | Parâmetros |
|---|---|---|---|
| A1 | Fonte nivel (quadro) | Simulink/Sources → **From Workspace** | Data: `fonte_nivel` ; Sample time: `Ts` ; **Interpolate data: desmarcado** ; Form output after final data value: *Holding final value* |
| A2 | Fonte payload (0 ou 1) | Sources → **From Workspace** | Data: `fonte_payload` ; Sample time `Ts` ; sem interpolação |
| A3 | TX nivel para V | Math Operations → **Gain** | Gain: `Vmax/(M-1)` (PAM-2: 3,3 V/nível; PAM-4: 1,1 V/nível) |
| A4 | CLK 20 kHz | Sources → **Pulse Generator** | Amplitude `3.3` ; Period `Ts` ; Pulse width `50` (%) ; Phase delay `0` |
| A5 | Canal RC (LIT) | Continuous → **Transfer Fcn** | Numerator `num_canal` ; Denominator `den_canal` |
| A6 | Mux TX | Signal Routing → **Mux** | Number of inputs `3` |
| A7 | Scope CLK TX TP3 | Sinks → **Scope** | — |
| A8 | tp3_log | Sinks → **To Workspace** | Variable name `tp3_log` ; Save format **Array** ; Sample time `0.5e-6` |

`fonte_nivel` é uma matriz `[t, nível]` com **o mesmo quadro do firmware** (140 pulso + 256 níveis + início + payload PRBS-15), gerada por `matlab/pam_quadro.m`.

`den_canal` é o denominador exato da escada RC (com o GPIO, o 330 Ω e o 390 pF do TX):
```
H(s) = 1 / ( Ra·C1·R2·C2·s² + (Ra·C1 + R2·C2 + Ra·C2)·s + 1 ),   Ra = Rgpio + 330 Ω
```
No canal Dupont fica `H(s) = 1/(Ra·C1·s + 1)` (τ ≈ 0,14 µs).

**Ligações:** A1 → A3 → A5. A4 → Mux entrada 1; A3 → Mux 2; A5 → Mux 3; Mux → A7. A5 → A8.

### 1.3 Blocos — ADC do RX (8 amostras/símbolo)

| # | Nome | Bloco | Parâmetros |
|---|---|---|---|
| A9 | ADC amostrador 160 kHz | Discrete → **Zero-Order Hold** | Sample time **`[Tsa t0]`** (período 6,25 µs, *offset* 3,125 µs) |
| A10 | Ruido ADC | Sources → **Random Number** | Mean `0` ; Variance `sigma_ruido^2` ; Seed `1` ; Sample time `[Tsa t0]` |
| A11 | Soma ruido | Math Operations → **Sum** | List of signs `++` |
| A12 | Faixa 0 a Vref | Discontinuities → **Saturation** | Upper `Vref` ; Lower `0` |
| A13 | Quantizador 12 bits | Discontinuities → **Quantizer** | Quantization interval `q_adc` (= 3,3/4095) |
| A14 | adc_log | Sinks → **To Workspace** | Variable `adc_log` ; Save format **Array** ; Sample time `-1` |

**Ligações:** A5 → A9 → A11(+). A10 → A11(+). A11 → A12 → A13 → A14.

> O par `[Tsa t0]` é o equivalente Simulink do TIM2: 1ª amostra 3,125 µs após a borda, depois a cada 6,25 µs. Como o canal começa em t = 0 junto com o 1º CLK, as amostras de índice 8j … 8j+7 pertencem ao símbolo j (k = 0 … 7).

### 1.4 Detector de AMOSTRA ÚNICA

| # | Nome | Bloco | Parâmetros |
|---|---|---|---|
| A15 | Amostra unica a(k*) | Discrete → **Zero-Order Hold** | Sample time **`[Ts t_kstar]`** (t_kstar = t0 + k*·Tsa) |
| A16 | Limiares u | Sources → **Constant** | Value `thr_u` (vetor 1×3; em PAM-2 os dois últimos são `inf`) |
| A17 | u > limiares | Logic and Bit Operations → **Relational Operator** | Operator `>` |
| A18 | bool2dbl u | Signal Attributes → **Data Type Conversion** | Output data type `double` |
| A19 | Nivel decidido u | Math Operations → **Sum of Elements** | — (soma quantos limiares foram ultrapassados = nível 0…M−1) |

**Ligações:** A13 → A15 → A17 entrada 1; A16 → A17 entrada 2; A17 → A18 → A19.

### 1.5 FILTRO CASADO digital

| # | Nome | Bloco | Parâmetros |
|---|---|---|---|
| A20 | x = a - b_c | Math Operations → **Bias** | Bias `-bc` |
| A21 | Filtro casado FIR h_c | Discrete → **Discrete FIR Filter** | Coefficients **`hc`** ; Sample time `-1` |
| A22 | z no fim da janela | Discrete → **Zero-Order Hold** | Sample time **`[Ts t_fim]`** (t_fim = t0 + 7·Tsa = 46,875 µs) |
| A23 | z_log | Sinks → **To Workspace** | `z_log`, Array |
| A24–A27 | Limiares z, z > limiares, bool2dbl z, Nivel decidido z | iguais a A16–A19 | Constant = `thr_z` |

**Ligações:** A13 → A20 → A21 → A22 → (A23 e A25 entrada 1); A24 → A25 entrada 2; A25 → A26 → A27.

> **Por que FIR com `hc = fliplr(pc)/Ec`?** O enunciado define z = Σ p_c[k]·x[k] / E_c sobre as 8 amostras do símbolo. Um FIR com h[i] = p_c[7−i]/E_c calcula, a cada amostra n, Σ h[i]·x[n−i]. Quando n é a amostra k = 7 do símbolo j, x[n−i] = x_j[7−i] e a soma vira exatamente Σ p_c[k]·x_j[k]/E_c. Por isso o ZOH A22 lê o FIR **só no instante de k = 7** (t_fim). É a "FIR com pesos invertidos e saída alinhada ao fim da janela" citada no enunciado (§4.5.1).

### 1.6 Contagem de erros (igual ao firmware)

Para **cada** detector (`u` e `z`), monte:

| # | Bloco | Parâmetros / função |
|---|---|---|
| E1 | **Zero-Order Hold** "Nivel TX" | Sample time = o MESMO do detector (`[Ts t_kstar]` para u, `[Ts t_fim]` para z); entrada = A1 |
| E2 | **Zero-Order Hold** "Payload" | mesmo sample time; entrada = A2 |
| E3 | **Relational Operator** "Erro simbolo" | `~=` ; entradas: nível decidido, nível TX |
| E4 | **Data Type Conversion** | `double` |
| E5 | **Product** "x payload Ns" | E4 × E2 (só conta no payload) |
| E6 | **Sum** `++` + **Unit Delay** (orientação para a esquerda, sample time `-1`) | acumulador: saída do Sum → Unit Delay → 2ª entrada do Sum |
| E7 | **Display** "Ns u" (ou "Ns z") + **To Workspace** `Ns_u` (Array) | contagem de símbolos errados |
| E8 | 2× **Data Type Conversion** `uint8` | nível decidido e nível TX |
| E9 | Lookup Tables → **Direct Lookup Table (n-D)** "Erros de bit Gray" | Number of table dimensions `2` ; Table data `tab_bits` ; entradas: (decidido, TX) |
| E10 | **Data Type Conversion** double → **Product** × Payload → acumulador → Display "Ne u" + To Workspace `Ne_u` | contagem de bits errados |

`tab_bits(i,j)` = número de bits diferentes entre os códigos Gray dos níveis i e j. Em PAM-4 vizinhos diferem em 1 bit; níveis 0 e 3 (00 e 10) em 1 bit; 0 e 2 (00 e 11) em 2 bits.

> Por que funciona sem atraso? O nível TX vem do mesmo `From Workspace` amostrado **no mesmo instante** do detector (dentro do mesmo símbolo), então já está alinhado.

**Scope decisões** (opcional): Mux de 3 entradas com Nivel TX u, Nivel decidido u, Nivel decidido z.

### 1.7 Rodar (fluxo igual ao da bancada)

```matlab
M = 4; canal = 'rc'; sigma_ruido = 0.002; N_payload_sim = 2000;
pam_simulink_init
out = sim('meu_enlace');          % rodada 1 = TREINAMENTO (limiares nominais)
calibra_simulink                  % b_c, p_c[k], k*, centros, limiares, margens (algoritmo do firmware)
out = sim('meu_enlace');          % rodada 2 = MEDIÇÃO
[out.Ns_u(end) out.Ne_u(end) out.Ns_z(end) out.Ne_z(end)]
olho_simulink                     % olho em TP3, 8 amostras/símbolo, PSD
```

Resultado esperado (RC, PAM-4, σ = 2 mV): `p_c ≈ [1,17 2,41 2,93 3,15 3,24 3,27 3,29 3,29] V`, `k* = 7`, margem u ≈ 1085 mV, margem z ≈ 0,24, **0 erros**.

### 1.8 Experimentos para entender (e responder na defesa)

| # | Experimento | O que observar |
|---|---|---|
| S1 | `canal='dupont'` × `'rc'` × `'rc33'` (M = 4) | Scope: subida de TP3; olho fecha no início do símbolo; k* sempre 7 no RC; ISI no 1º zero após A (veja `calibra_simulink`) |
| S2 | No Scope, meça τ na subida 0→A (cursores) | ~7,1 µs (RC) e ~13 µs (33 nF) |
| S3 | `olho_simulink` com dupont/rc/rc33 | abertura em k*; com 33 nF a abertura cai ~13 % |
| S4 | PSD (3º gráfico de `olho_simulink`) | nulos em 20, 40, 60 kHz (sinc² de Ts = 50 µs); queda extra em 10 kHz no RC; vale do PAM-4 em 10 kHz |
| S5 | `sigma_ruido = 0.25` (Dupont, M = 4), N_payload_sim = 3000 | a amostra única erra (~60 símbolos), o filtro casado não: ganho de √8 de SNR em ruído branco |
| S6 | Mesmo ruído com `canal='rc33'` | o filtro casado perde quase toda a vantagem: os pesos p_c[k] dão peso às amostras do começo do símbolo, que carregam ISI do símbolo anterior. Verificado com 50 000 símbolos PAM-4 e σ = 250 LSB (≈ 0,2 V): Dupont → amostra 267 erros × filtro 0; RC 33 nF → amostra 383 × filtro 403 |
| S7 | Force `cal.kstar = 0` (sem treinar de novo) e rode no RC | a amostra única erra ~75 % dos símbolos: em 3,12 µs o nível ainda está no meio da transição (37 547 erros em 50 000 na simulação numérica) |
| S8 | `M = 2` × `M = 4` com o mesmo σ | PAM-4 tem distância entre níveis 3× menor → erra antes |

### 1.9 (Extra didático) PRBS-15 com blocos
Para ver o gerador da Eq. (1) com blocos: 15 **Unit Delay** em cadeia (sample time `Ts`, condição inicial `1` em todos), um **Logical Operator XOR** entre a saída do 1º atraso (b_n) e a do último (b_{n+14}), realimentando a entrada da cadeia. A saída b_n reproduz `pam_quadro(2).bits`: 1111111111111110101010101010100110011001…

---

## 2. MODELO B — `meu_circuito.slx` (Simscape Electrical)

### 2.1 Solver
Variable-step, **ode23t**; Max step size **`max_step_circ`** (2,5 ns com PWM real; 0,2 µs com nível médio); Rel. tol `1e-4`; Stop time `T_sim_circ` (15 símbolos = 750 µs: pulso 0,0,0,A,0,0,0 + 8 níveis da calibração).

### 2.2 Geração do PWM igual ao TIM1 (PSC = 0, ARR = 2)

| # | Nome | Bloco | Parâmetros |
|---|---|---|---|
| B1 | TIM1_CCR1 (nivel) | Sources → **From Workspace** | `fonte_ccr` ; Sample time `Ts` ; sem interpolação |
| B2 | CNT do TIM1 (0,1,2) | Sources → **Repeating Sequence Stair** | Vector of output values `[0 1 2]` ; Sample time `10e-9` (100 MHz) |
| B3 | CNT < CCR1 | **Relational Operator** | `<` ; entrada 1 = CNT (B2), entrada 2 = CCR (B1) |
| B4 | para double | **Data Type Conversion** | double |
| B5 | PA8 0 ou 3,3 V | **Gain** | `Vmax` |
| B6 | CCR max 3 | **Saturation** | Upper 3, Lower 0 |
| B7 | nivel medio | **Gain** | `Vmax/3` |
| B8 | usar_pwm | **Constant** | `usar_pwm` |
| B9 | PWM ou media | Signal Routing → **Switch** | Criteria `u2 > Threshold`, Threshold `0.5`; entrada 1 = B5, 2 = B8, 3 = B7 |

> PWM modo 1: saída alta enquanto CNT < CCR1. CNT = 0,1,2 (30 ns). CCR1 = 0 → sempre 0 V; 1 → 1/3 do tempo (1,1 V médio); 2 → 2/3 (2,2 V); 3 → sempre alto (3,3 V). É o "DAC por PWM" da aula de amostragem (PWM → filtro passa-baixas).

### 2.3 Circuito (biblioteca **Simscape → Foundation Library → Electrical**)

| # | Nome | Bloco | Parâmetro |
|---|---|---|---|
| C1 | S-PS | Simscape → Utilities → **Simulink-PS Converter** | Output signal unit `V` |
| C2 | Pino PA8 | Electrical Sources → **Controlled Voltage Source** | — |
| C3 | R saida GPIO | Electrical Elements → **Resistor** | `Rgpio` (≈ 30 Ω, estimativa) |
| C4 | R1 330 | Resistor | `R1` |
| C5 | C1 390p | **Capacitor** | `C1` |
| C6 | R2 56 (canal) | Resistor | `R2` |
| C7 | C2 16n8 (canal) | Capacitor | `C2` (no Dupont o init usa 0,1 Ω / 20 pF = parasitas do fio) |
| C8 | R protecao 1k | Resistor | `Rprot` |
| C9 | C ADC 4p | Capacitor | `C_adc` (capacitor de amostragem do ADC, ordem de grandeza) |
| C10 | D+ (TP4 para 3V3) | Electrical Elements → **Diode** | Forward voltage `Vf_schottky` (0,3 V), On resistance `Ron_schottky` |
| C11 | D- (GND para TP4) | **Diode** | idem |
| C12 | 3V3 do RX | Electrical Sources → **DC Voltage Source** | `Vref` |
| C13 | GND | Electrical Elements → **Electrical Reference** | — |
| C14 | Solver | Simscape → Utilities → **Solver Configuration** | padrão |
| C15–C17 | Sensor TP2/TP3/TP4 | Electrical Sensors → **Voltage Sensor** | — |
| C18–C20 | PS-S TP2/TP3/TP4 | Utilities → **PS-Simulink Converter** | Output signal unit `V` |
| C21 | Mux TPs (4 entradas) + **Scope** + **To Workspace** `circ_log` | | To Workspace: *Structure With Time*, Sample time `5e-9` |

**Ligações elétricas** (portas: Resistor/Capacitor têm + e −; Diode: **anodo (+) à esquerda, catodo (−) à direita**; Controlled Voltage Source: + em cima, − embaixo, entrada de sinal ao lado; Voltage Sensor: + e − e a saída V):

```
B9 ─► C1 ─► entrada de sinal de C2
C2(+) ─ C3 ─ C4 ─●─ TP2 ─ C6 ─●─ TP3 ─ C8 ─●─ TP4
                 C5           C7           ├─ C9 ─ GND
                 │            │            ├─ anodo C10 ; catodo C10 ─ C12(+) ; C12(−) ─ GND
                GND          GND           └─ catodo C11 ; anodo C11 ─ GND
C2(−) ─ GND ; C14 ─ GND ; C13 = GND
Sensores: (+) no nó TP2/TP3/TP4, (−) no GND, V ─► PS-S ─► Mux (entradas 2,3,4); B9 ─► Mux entrada 1
```

### 2.4 Rodar
```matlab
M = 4; canal = 'rc'; usar_pwm = 0; pam_simulink_init
o = sim('meu_circuito');                       % ~20 s (nível médio)
y = o.circ_log.signals.values; t = o.circ_log.time;
plot(t*1e6, y(:,2:4)); legend TP2 TP3 TP4; xlabel('t (\mus)')
```
Com `usar_pwm = 1` (PWM real de 33 MHz) a simulação leva ~30–60 s; dê zoom de 300 ns num símbolo de nível 1.

### 2.5 Experimentos com o modelo B

| # | Experimento | Resultado esperado (verificado) |
|---|---|---|
| P1 | `canal='dupont'`, `usar_pwm=1`: ripple em TP2 no nível 1 e 2 | ≈ **150 mVpp** em TP2; ≈ 90 mVpp em TP4 (o 1 kΩ + 4 pF filtra um pouco) |
| P2 | `canal='rc'`, `usar_pwm=0`: τ em TP3 na subida 0→A | **≈ 7,1 µs** (o modelo de 1 polo do enunciado dá 6,48 µs: a diferença é o 390 pF + R do GPIO) |
| P3 | Troque `C2` por 33 nF (`canal='rc33'`) | τ ≈ 13,9 µs; o nível não chega ao final em 50 µs (ISI) |
| P4 | `Rgpio = 0` (edite depois do init) | τ volta para perto de (330+56)·16,8 nF = 6,48 µs + 330·0,39 nF |
| P5 | Depois do init, faça `Vref = 2.8` (simula um 3V3 do RX mais baixo) | D+ passa a conduzir quando TP4 > 2,8 + 0,3 = 3,1 V: veja TP4 grampeado perto de 3,1 V enquanto TP3 vai a 3,3 V (é isso que a proteção faz) |
| P6 | Aliasing do ripple (conta, não simulação) | PWM a 33,333 MHz amostrado a 160 kHz: 33 333 333 / 160 000 = 208,33 → o resíduo dobraria para 0,333·160 kHz ≈ **53,3 kHz**. Na prática a fase do PWM em cada amostra também varia (jitter de ±10 ns da borda do CLK ≈ 1/3 do período do PWM), então ele tende a aparecer como ruído espalhado. Procure algo perto de 53 kHz na PSD real |

---

## 3. Conferência rápida com os modelos de referência

```matlab
cd simulink
criar_modelos_simulink          % (re)gera pam_enlace_simulink.slx e pam_circuito_simscape.slx
open_system('pam_enlace_simulink'); open_system('meu_enlace')   % compare lado a lado
```
Se o seu modelo der números diferentes do de referência com as mesmas variáveis, confira: sample times com offset (`[Tsa t0]`, `[Ts t_kstar]`, `[Ts t_fim]`), *Interpolate data* desmarcado, coeficientes `hc` (não `pc`), e o solver stiff.
