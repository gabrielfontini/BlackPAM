# 02 — Material de estudo: das aulas ao projeto PAM

> Base: Aulas 01–09 do Prof. Roberto Krauss (Lathi & Ding, Haykin & Moher, Sklar) + enunciado `Projeto_BB_2026S2.pdf`.
> Cada seção diz **em que aula está**, a **teoria mínima** e **o que ela significa na sua bancada** (com os números do projeto).
> Os números "previstos" vêm de `matlab/simula_enlace.m` (resultados em `matlab/resultados_simulacao.txt`).

---

## 0. Mapa: aula → projeto → defesa

| Aula | Tema | Onde aparece no projeto | Pergunta típica da defesa |
|---|---|---|---|
| 01 | dB, sinais de energia/potência, impulso, **correlação** | potência do PAM, palavra de sincronismo, filtro casado = correlação | "Qual a potência do seu sinal?" |
| 02 | Série e **Transformada de Fourier**, sinc, dilatação, Parseval | espectro do pulso de 50 µs (nulos em 20 kHz), PWM como série de Fourier | "Por que a PSD tem nulos em 20, 40, 60 kHz?" |
| 03 | **Sistemas LIT**, H(f), distorção, filtros práticos | canal RC = sistema LIT, resposta ao degrau, τ | "Qual o τ previsto e o medido? Por que diferem?" |
| 04 | **ESD/PSD**, autocorrelação, $S_y = \|H\|^2 S_x$ | PSD em 5 e 10 kHz, razão entre canais | "Calcule a razão das PSDs e explique pelo RC" |
| 05 | **Amostragem**, Nyquist, aliasing, PAM, ZOH, PWM | ADC a 160 kHz, 8 amostras/símbolo, ripple do PWM, PWM como DAC | "Por que fa/2 = 80 kHz importa?" |
| 06 | PCM, **quantização**, SQNR | ADC 12 bits, LSB = 0,8 mV | "Qual o erro de quantização do seu ADC?" |
| 07 | **Códigos de linha**, M-PAM, Gray, PSD de códigos | NRZ unipolar PAM-2/PAM-4, Gray, PSD com componente DC | "Por que Gray?" |
| 08 | **ISI**, Nyquist, **diagrama de olho**, sincronismo | olho em TP3, k*, ISI no 1º zero após A, CLK separado | "Mostre k* no olho e justifique" |
| 09 | Ruído, **filtro casado**, detecção ML, **função Q**, BER | dois detectores, limiares no ponto médio, BER/SER | "Calcule um z à mão. O que significa 0 erros?" |

---

## 1. Taxas, símbolos e bits (Aulas 07 e 09)

**Definições**
- Período de símbolo $T_s$; taxa de símbolos $R_s = 1/T_s$ (símbolos/s = baud).
- M-PAM: $M = 2^k$ níveis, $k = \log_2 M$ bits/símbolo.
- Taxa bruta de bits: $R_b = k \cdot R_s$.

**No projeto**

| | PAM-2 | PAM-4 |
|---|---|---|
| $T_s$ | 50 µs | 50 µs |
| $R_s$ | 20 ksym/s | 20 ksym/s |
| $k$ | 1 | 2 |
| $R_b$ | **20 kbit/s** | **40 kbit/s** |
| payload (100 000 bits) | 100 000 símbolos = **5 s** | 50 000 símbolos = **2,5 s** |
| quadro total | 100 444 símbolos | 50 420 símbolos |

- Mesma **taxa de bits** (20 kbit/s): PAM-2 a 20 ksym/s ou **PAM-4 a 10 ksym/s** → o PAM-4 ocupa metade da banda (pulso 2× mais largo ⇒ espectro 2× mais estreito, propriedade de dilatação da Aula 02). Custo: níveis 3× mais próximos ⇒ precisa de mais SNR (Aula 09, "requer mais energia").
- **A portadora PWM de 33,333 MHz NÃO é a taxa de dados**: é só o "DAC" que gera o nível médio (§5.4).
- **Banda mínima de Nyquist** (Aula 08): $B_{min} = R_s/2$ = 10 kHz. Com pulsos retangulares (NRZ) a banda essencial (1º nulo) é $R_s$ = 20 kHz.
- **Shannon** (Aula 01): $C = B\log_2(1+SNR)$. Exemplo: B = 24,5 kHz (corte do RC) e SNR do ADC ≈ 60 dB → C ≈ 24,5k × 20 ≈ 490 kbit/s: o limite do canal 2 está muito acima dos nossos 40 kbit/s. O que limita na prática é a ISI do pulso retangular, não o ruído.

**Exercício resolvido.** PAM-4 a 20 ksym/s com payload de 100 000 bits: quantos símbolos e quanto tempo? → 100 000/2 = 50 000 símbolos × 50 µs = 2,5 s. Com treinamento (396) e início de quadro (24 símbolos): 50 420 × 50 µs = 2,521 s.

---

## 2. Sinais, potência e dB (Aula 01)

- **Energia** $E_g = \int |g|^2 dt$ (finita → sinal de energia, ex.: um pulso). **Potência** $P_g = \lim \frac{1}{T}\int_{-T/2}^{T/2} |g|^2 dt$ (finita → sinal de potência, ex.: o trem PAM infinito). $\sqrt{P_g}$ = valor RMS.
- dBm: $P_{dBm} = 10\log_{10}(P/1\,\text{mW})$.

**PAM unipolar (níveis equiprováveis), em 1 Ω:**

| | níveis (V) | média $\mu$ | $E[v^2]$ | variância $\sigma^2 = E[v^2]-\mu^2$ (potência AC) |
|---|---|---|---|---|
| PAM-2 | 0 ; 3,3 | 1,65 V | 5,445 V² | **2,7225 V²** |
| PAM-4 | 0 ; 1,1 ; 2,2 ; 3,3 | 1,65 V | 4,235 V² | **1,5125 V²** |

A parcela $\mu^2 = 2{,}7225$ V² é a **componente DC** (uma raia em f = 0 na PSD); o enunciado manda **retirar a média** antes da PSD, então a área da PSD estimada dá a variância (≈ 2,72 e ≈ 1,51 V²; o MATLAB imprime "potência AC").

**Correlação (Aula 01):** $\rho = \frac{\int g x\, dt}{\sqrt{E_g E_x}}$, $-1 \le \rho \le 1$. É a mesma ideia do **filtro casado** (produto interno entre o que chegou e o pulso esperado) e da **palavra de sincronismo** 0xD391C5A7 (padrão escolhido para ter baixa correlação com versões deslocadas de si mesma).

---

## 3. Fourier do pulso PAM (Aula 02)

**Pulso retangular** de largura $T$: $\Pi(t/T) \Leftrightarrow T\,\text{sinc}(\pi f T)$ (sinc do Lathi: $\text{sinc}(x) = \sin x / x$).
- Zeros em $f = n/T$. Com $T = T_s = 50$ µs → **nulos em 20, 40, 60 kHz**. É isso que você vê na PSD.
- **Dilatação** $g(at) \Leftrightarrow \frac{1}{|a|}G(f/a)$: pulso 2× mais curto → espectro 2× mais largo. Taxa maior = banda maior (Aula 01: "K·N pulsos/s exige K·B").
- **Translação no tempo** $g(t-t_0) \Leftrightarrow G(f)e^{-j2\pi f t_0}$: o atraso de ~0,2 µs da ISR do TX não muda $|G|$, só a fase.
- **Área** $G(0) = \int g\,dt$: valor DC; **Parseval**: energia no tempo = energia na frequência.
- **Sinal periódico** → espectro de raias em múltiplos de $f_0$ (Aula 02/05).

**O PWM como série de Fourier (Aula 02 + 05).** PA8 é uma onda retangular de período $T_p = 30$ ns, amplitude 3,3 V, duty $D = \text{CCR}/3$:
$$D_0 = 3{,}3\,D,\qquad |D_n| = 3{,}3\,D\,\left|\text{sinc}(\pi n D)\right|$$
- O termo DC $D_0$ é o **nível PAM**: 0 ; 1,1 ; 2,2 ; 3,3 V.
- As harmônicas ficam em 33,3 / 66,7 / 100 MHz…: o filtro 330 Ω/390 pF ($f_c$ = 1,24 MHz) as atenua ($|H(33{,}3\,\text{MHz})| \approx 1{,}24/33{,}3 \approx 0{,}037$). Resultado: **ripple residual ≈ 150 mVpp** em TP2 nos níveis 1 e 2 (simulado; conta rápida pela carga do C: $\Delta V \approx (3{,}3-1{,}1)\cdot 10\,\text{ns}/129\,\text{ns} \approx 0{,}17$ V). Em CCR = 0 e 3 não há ripple (sinal constante).

---

## 4. Canal = sistema LIT (Aula 03)

### 4.1 Teoria
- LIT: $y = x * h$ ⇔ $Y(f) = X(f)H(f)$. $|H|$ = ganho de cada frequência; $\angle H$ = atraso de cada frequência.
- **Sem distorção**: $|H|$ constante e fase linear ($\theta_h = -2\pi f t_d$) na banda do sinal. O RC tem $|H|$ caindo e fase não linear → **distorção linear** → **alargamento do pulso** → **ISI** (a Aula 03 diz literalmente: "distorção de canal linear… introduz ISI").
- **Paley–Wiener**: filtro ideal (corte abrupto) não é realizável; filtros práticos (como o RC) têm transição gradual.
- Atraso de grupo $t_g = -\frac{1}{2\pi}\frac{d\theta_h}{df}$; para o RC em $f \ll f_c$: $t_g \approx \tau$.

### 4.2 RC de 1 polo (modelo do enunciado)
$$H(f) = \frac{1}{1 + j2\pi f\tau},\quad |H|^2 = \frac{1}{1+(f/f_c)^2},\quad f_c = \frac{1}{2\pi\tau},\quad h(t) = \frac{1}{\tau}e^{-t/\tau}u(t)$$
Degrau de $V_0$ a $V_f$: $v(t) = V_f + (V_0 - V_f)e^{-t/\tau}$.
- Em $t = \tau$: 63,2 % da variação. **t₁₀₋₉₀ = τ ln 9 = 2,197 τ.**
- Depois de um símbolo inteiro sobra $e^{-T_s/\tau}$ da transição: é a "memória" do canal = ISI.

| Canal | τ nominal | f_c | t₁₀₋₉₀ | resíduo após 50 µs | resíduo em k = 0 (3,12 µs) |
|---|---|---|---|---|---|
| Dupont (só 330 Ω·390 pF) | 0,13 µs | 1,24 MHz | 0,28 µs | 0 | e^(−24) ≈ 0 |
| **RC 16,8 nF**: (330+56)·16,8 n | **6,48 µs** | **24,5 kHz** | **14,2 µs** | 0,05 % | **62 %** |
| **RC 33 nF**: (330+56)·33 n | **12,74 µs** | **12,5 kHz** | **28,0 µs** | **2,0 %** | 78 % |

### 4.3 O que o modelo de 1 polo esquece (τ medido ≠ previsto)
A escada real tem dois capacitores e a resistência de saída do pino:
$$H(s) = \frac{1}{R_aC_1R_2C_2\,s^2 + (R_aC_1 + R_2C_2 + R_aC_2)\,s + 1},\quad R_a = R_{gpio}+330$$
Polo dominante: $\tau \approx R_a(C_1+C_2) + R_2C_2$.
- Só o **390 pF**: soma 330·0,39 nF = **0,13 µs**.
- **Resistência de saída do GPIO** (datasheet: $V_{OH} \ge V_{DD}-0{,}4$ V a 8 mA ⇒ até ~50 Ω; estimamos 30 Ω): soma 30·16,8 nF ≈ **0,5 µs**.
- Total previsto pelo modelo: **≈ 7,1 µs** (16,8 nF) e **≈ 13,9 µs** (33 nF).

**Causas verificáveis de diferença (pergunta 2 da defesa):**
1. Tolerância do capacitor (X7R ±10 %, ±20 %; meça com o capacímetro).
2. 390 pF do TX em paralelo efetivo (calcule: +0,13 µs).
3. Resistência de saída do pino PA8 (meça a queda de tensão de PA8 com carga, ou compare τ com e sem o 330 Ω).
4. Ponta do osciloscópio em ×1 (≈ 100 pF + 1 MΩ): use ×10 (≈ 15 pF).
5. Escolha de $t_0$ (o enunciado frisa: $t_0$ = **início** da subida, não o ponto de 10 %) e de $V_f$ (com 33 nF o nível **não estabiliza** em 50 µs: 97,9 %; use uma sequência longa de mesmo nível ou corrija: $V_f$ teórico).
6. Resolução do osciloscópio (2500 pontos na tela: em 5 µs/div, 20 ns/ponto — ok).

### 4.4 Como medir (pág. 10 do enunciado)
$V_{63} = V_0 + 0{,}632(V_f - V_0)$; $\tau = t_{63} - t_0$; $t_r = t_{90} - t_{10}$; confira $\tau \approx t_r/2{,}197$.
Exemplo do enunciado: 0,2 → 3,0 V ⇒ $V_{63}$ = 1,97 V; se chegar em 7 µs, τ = 7 µs.
Script: `tau_osciloscopio('F0001CH2.CSV')`.

---

## 5. Amostragem e conversão (Aulas 05 e 06)

### 5.1 Teorema da amostragem
Sinal limitado em B Hz é recuperável se $f_a > 2B$. Amostrar = multiplicar por um trem de impulsos ⇒ o espectro se **repete a cada $f_a$** (réplicas de $G(f)/T_a$).
**Aliasing**: componentes acima de $f_a/2$ "dobram" para baixo. Antídoto: filtro anti-aliasing antes do ADC.

### 5.2 No projeto
- $f_a = 8 R_s = 160$ kHz; **$f_a/2 = 80$ kHz** (frequência de dobramento).
- O enunciado **proíbe filtro extra** antes do ADC nos ensaios obrigatórios. Então:
  - o sinal NRZ tem lóbulos sinc acima de 80 kHz (pouca energia: ~−25 dB em relação ao começo do espectro) → dobram para dentro da faixa;
  - o **ripple do PWM** (33,333 MHz) dobra para $33\,333\,333 \bmod 160\,000 = 53\,333$ Hz, isto é, ≈ **53,3 kHz** (a fase do PWM em cada amostra tem jitter, então pode aparecer espalhado como ruído).
- **Mas o objetivo não é reconstruir o sinal!** O RX só precisa **decidir o nível** de cada símbolo. As 8 amostras/símbolo servem para escolher o instante (k*) e para o filtro casado.
- **Sample-and-hold do ADC** (Aula 05: PAM/ZOH "amostragem instantânea + prolongamento"): o capacitor interno (~4 pF) carrega por 15 ciclos (600 ns) através do 1 kΩ: $\tau \approx (1\,\text{k}+R_{ADC})\cdot 4\,\text{pF} \approx 10$–30 ns ≪ 600 ns ⇒ carga completa. Conversão total: 27 ciclos a 25 MHz = **1,08 µs** < 6,25 µs.
- **PWM como DAC** (Aula 05, aplicações: "eletrônica de potência, DAC"): PWM + passa-baixas = nível médio. É modulação por largura de pulso usada para gerar PAM.

### 5.3 Quantização (Aula 06)
- 12 bits, $L = 4096$ níveis, $\Delta = V_{ref}/4095 \approx$ **0,806 mV** (com 3,3 V).
- Erro máximo $\pm\Delta/2 = \pm 0{,}4$ mV; ruído de quantização $\sigma_q^2 = \Delta^2/12$ ⇒ $\sigma_q \approx$ **0,23 mV**.
- SQNR para senoide em fundo de escala: 6,02n + 1,76 = **74 dB** (n = 12). Na prática o ADC do F411 tem ~10–11 bits efetivos (ruído ~1–2 LSB).
- Conversão do enunciado: $V = \text{código}\cdot V_{ref}/4095$ com **$V_{ref}$ medido** (3V3 do RX).
- O próprio TX é um "quantizador" de 2 bits: o PWM só gera 4 níveis (CCR = 0…3).

---

## 6. Densidade espectral de potência (Aulas 04 e 07)

### 6.1 Teoria
- **ESD** $\Psi_g(f) = |G(f)|^2$ (sinais de energia). **PSD** $S_g(f) = \lim_{T\to\infty}|G_T(f)|^2/T$ (sinais de potência) — potência por Hz.
- **Wiener–Khinchin**: $S_g(f) = \mathcal{F}\{R_g(\tau)\}$ (a PSD é a transformada da autocorrelação).
- **Pela LIT**: $S_y(f) = |H(f)|^2 S_x(f)$. ← chave da questão 1 da defesa.
- Potência = área: $P = \int S(f)\,df$.

### 6.2 PSD de um sinal PAM (Aula 07, Lathi §7.2)
Trem de pulsos $p(t)$ com amplitudes $a_k$ a cada $T_s$:
$$S_y(f) = \frac{|P(f)|^2}{T_s}\left(R_0 + 2\sum_{n\ge1} R_n\cos(2\pi n f T_s)\right),\quad R_n = E[a_k a_{k+n}]$$
- Formato do pulso → $|P(f)|^2$ (sinc² para NRZ). Correlação entre símbolos → termo entre parênteses.
- **Unipolar** (on-off, Aula 07): média ≠ 0 ⇒ além da parte contínua há **raias** (DC e em múltiplos de $R_s$, onde o sinc² não zera). Para NRZ as raias em $nR_s$ caem nos zeros do sinc, sobra só a **DC** — que retiramos.
- Parte contínua, unilateral, NRZ com níveis independentes:
$$S(f) = 2\sigma^2 T_s\,\text{sinc}^2(\pi f T_s)$$

### 6.3 Números do projeto (unilateral, sem DC, amostrado a 160 kHz)

| | S(5 kHz) (V²/Hz) | S(10 kHz) (V²/Hz) |
|---|---|---|
| PAM-2 Dupont | 2,21·10⁻⁴ | 1,12·10⁻⁴ |
| PAM-2 RC 16,8 nF | 2,11·10⁻⁴ | 9,3·10⁻⁵ |
| PAM-2 RC 33 nF | 1,86·10⁻⁴ | 6,4·10⁻⁵ |
| PAM-4 Dupont | 1,23·10⁻⁴ | **1,24·10⁻⁵** (vale, §6.4) |
| PAM-4 RC 16,8 nF | 1,17·10⁻⁴ | 1,04·10⁻⁵ |
| PAM-4 RC 33 nF | 1,03·10⁻⁴ | 7,1·10⁻⁶ |

**Razão RC/Dupont = |H(f)|²** (mesmos bits nos dois canais, ver §6.5):

| f | modelo 1 polo τ = 6,48 µs | modelo 2 polos (τ ≈ 7,1 µs) | simulado | 33 nF (2 polos) |
|---|---|---|---|---|
| 5 kHz | 0,960 (−0,18 dB) | 0,952 (−0,21 dB) | 0,946 | 0,841 (−0,75 dB) |
| 10 kHz | 0,858 (−0,67 dB) | 0,834 (−0,79 dB) | 0,813 | 0,569 (−2,45 dB) |

Interpretação: o RC é um passa-baixas; perto de 5 kHz ($f \ll f_c$) quase não atenua; em 10 kHz já tira ~17 % da potência; com 33 nF ($f_c$ = 12,5 kHz) tira ~43 %. Atenuar as altas frequências = subida mais lenta no tempo = ISI (dualidade tempo–frequência, Aula 02).

### 6.4 O vale do PAM-4 em 10 kHz (só vai entender quem fez a conta!)
A PRBS-15 obedece $b_{n+15} = b_{n+14}\oplus b_n$. Daí (álgebra de sequências-m): $b_n \oplus b_{n+1} = b_{n-14}$.
Com o Gray do enunciado, o nível de um par $(b_1, b_2)$ é $\ell = 2b_1 + (b_1 \oplus b_2)$ (verifique: 00→0, 01→1, 11→2, 10→3). Para o par $i$: $b_1 = b_{2i}$ e $b_1\oplus b_2 = b_{2i}\oplus b_{2i+1} = b_{2i-14} = b_1$ do par $i-7$. Logo
$$\ell_i = 2c_i + c_{i-7}$$
— os níveis PAM-4 **não são independentes**: o símbolo i "lembra" o símbolo i−7. Pela fórmula da §6.2 ($R_0 \propto 5$, $R_{\pm7} \propto 2$):
$$S_{PAM4}(f) \propto \big(5 + 4\cos(2\pi f\cdot 7T_s)\big)\,\text{sinc}^2(\pi f T_s)$$
- Picos (fator 9/5) em $f = m R_s/7$ = 0; 2,86; 5,71; 8,57 kHz…
- **Vales (fator 1/5) em $f = (2m+1)R_s/14$** = 1,43; 4,29; 7,14; **10,0 kHz**…
- Em 5 kHz o cosseno vale 0 ⇒ valor médio.

Por isso a PSD do PAM-4 mostra uma "ondulação" com período de 2,857 kHz e um **vale fundo em 10 kHz** — **não é efeito do canal** (aparece nos dois canais) e some na razão RC/Dupont. A PRBS isolada (PAM-2) é branca.

### 6.5 Método de estimação (enunciado, passo 6)
1. 8 192 amostras consecutivas do payload (a partir do símbolo 1000) → volts com $V_{ref}$ medido.
2. Retira a média (tira a raia DC).
3. Blocos de N = 1024 com 50 % de sobreposição ⇒ **15 blocos**.
4. Janela de Hann $w$; periodograma $S[f] = 2|\text{FFT}(wx)|^2/(f_a\sum w^2)$ nos bins internos (DC e Nyquist não são dobrados).
5. Média dos 15 periodogramas (método de **Welch**).

| Grandeza | Valor |
|---|---|
| $f_a$ | 160 000 Hz |
| resolução $\Delta f = f_a/N$ | **156,25 Hz** |
| duração do registro | 8192/160 000 = **51,2 ms** |
| duração de cada bloco | 6,4 ms |
| largura do lóbulo da Hann | ±2 bins (±312 Hz) |
| faixa | 0 – 80 kHz |

**Variância do estimador:** cada bin é média de ~15 periodogramas ⇒ incerteza de **±25–35 %** no valor absoluto de um bin isolado (vimos 2,81·10⁻⁴ contra 2,21·10⁻⁴ de teoria em 5 kHz). Duas saídas:
- reportar a média de 5 bins em torno de 5/10 kHz (o `analisa_ensaio` imprime as duas);
- para comparar canais, usar a **razão**: as 8 192 amostras começam no **mesmo símbolo 1000** do payload nos dois ensaios ⇒ os bits são idênticos ⇒ a flutuação estatística se cancela e a razão fica ≈ |H|² com ~2 % de erro.

A **FFT do osciloscópio** é só apoio visual (o enunciado diz isso): curta, sem média, em dBV.

---

## 7. Códigos de linha e PAM (Aula 07)

- Nosso sinal é **NRZ unipolar (on-off)**: 0 → 0 V, 1 → 3,3 V (PAM-2), largura completa.
  - Vantagens: simples, menor banda que RZ/Manchester (1º nulo em $R_s$).
  - Desvantagens (Aula 07): **componente DC** (não passa por acoplamento AC/transformador), longas sequências iguais não têm transições (não dá para extrair relógio do próprio sinal) → **por isso o CLK vai em fio separado** (Aula 08, sincronismo por "sinal de sincronização separado / relógio piloto"). A PRBS-15 tem sequências de até 15 bits iguais (o início do payload tem 15 "1"s!).
  - Requer o dobro da potência do polar para a mesma distância (Aula 07).
- **M-PAM**: constelação unidimensional; PAM-4 com distância $d$ = 1,1 V entre vizinhos (vs. 3,3 V no PAM-2).
- **Gray** (00, 01, 11, 10): vizinhos diferem em **1 bit**. O erro mais provável (confundir vizinhos) custa 1 bit ⇒ $BER \approx SER/\log_2 M = SER/2$. Sem Gray (00,01,10,11), confundir 1↔2 (01↔10) custaria 2 bits.
- **Manchester / AMI / Miller** (Aula 07): não usados, mas compare: Manchester tem DC nulo e transição em todo bit (auto-sincronismo) ao custo do dobro da banda.

---

## 8. ISI, critério de Nyquist e diagrama de olho (Aula 08)

### 8.1 ISI
"Um símbolo interfere no instante de decisão do seguinte" — **distorção determinística**, não ruído. Causas: banda limitada, $|H|$ não plano, fase não linear, multipercurso. Cabos longos = passa-baixas dispersivo (Aula 08, "Modelo elétrico de um cabo metálico").

**Critério de Nyquist para ISI nula**: o pulso recebido deve valer 0 nos instantes $\pm nT_s$ de decisão. Pulso sinc (banda $R_s/2$), cosseno levantado com roll-off $r$: banda $(1+r)R_s/2$.
**No projeto**: o pulso recebido é um "retângulo filtrado pelo RC" = subida exponencial. Ele **não** satisfaz Nyquist exatamente, mas se $T_s \gg \tau$ o resíduo em k = 7 é desprezível.

### 8.2 ISI medida pelo treinamento
O 1º zero depois de A ainda carrega a cauda do pulso. Previsões (códigos ADC acima de $b_c$, PAM-4 RC 16,8 nF):

| k | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| tempo (µs) | 3,12 | 9,37 | 15,62 | 21,87 | 28,12 | 34,37 | 40,62 | 46,87 |
| $p_c[k]$ (símbolo A) | 1351 | 2956 | 3622 | 3898 | 4013 | 4060 | 4081 | 4089 |
| 1º zero após A (ISI) | 2739 | 1137 | 471 | 195 | 80 | 34 | 13 | 5 |

Note que $p_c[k] + \text{ISI}[k] \approx 4095$: o que "falta" subir no símbolo A é o que "falta" descer no zero seguinte (linearidade!). Com 33 nF a ISI em k = 7 sobe para ~137 códigos (110 mV).

### 8.3 Diagrama de olho
Sobreposição de trechos do sinal alinhados pelo CLK (osciloscópio com persistência infinita; ou as amostras do RX no computador).
- **Abertura vertical** = margem contra ruído (maior ⇒ menor BER).
- **Abertura horizontal** = tolerância a erro de instante (jitter).
- Fechamento por ruído, ISI, jitter, distorção.
- Regra prática: amostrar no ponto de **maior abertura vertical** — no nosso caso o RX **escolhe isso pelos dados** (§8.4), e o olho só **mostra** a escolha.

### 8.4 Escolha de k* (§4.3 do enunciado)
Para cada k, com os 256 símbolos de calibração separados por nível:
$$d_{k,\ell} = \min(a[k]\mid \ell+1) - \max(a[k]\mid \ell),\qquad s_k = \min_\ell d_{k,\ell},\qquad k^* = \arg\max_k s_k \ (\text{empate: menor } k)$$
- $d < 0$ ⇒ as faixas dos níveis se cruzam (olho fechado naquele instante).
- RC previsto (PAM-4): $s_k$ = −2294, −157, 730, 1097, 1251, 1313, 1337, **1350** ⇒ **k* = 7 (46,87 µs)**, separação 1350 códigos = **1,09 V**.
- Dupont: todos os $s_k$ ≈ iguais (o sinal já estabilizou em 3 µs): k* sai do **ruído** (pode ser qualquer um). Diga isso na defesa!
- Em PAM-4, identifique nos seus dados o par mais próximo (`margem_u_par`) e os bits Gray dele. Na simulação: Dupont → par 1–2 (01/11, decidido pelo ruído); RC → par **2–3 (11/10)**, porque o nível 3 vindo de 0 é o que menos chega ao final do símbolo e o nível 2 vindo de 3 é o que fica mais alto. Na bancada, níveis reais não equidistantes do PWM e a saturação do ADC em 4095 também pesam.

---

## 9. Ruído, detecção e filtro casado (Aula 09)

### 9.1 Modelo de decisão
Saída do amostrador: $z = a_i + n_0$, $n_0 \sim \mathcal{N}(0,\sigma^2)$ (ruído térmico, gaussiano pelo teorema do limite central; branco ⇒ PSD plana).
**Máxima verossimilhança** com símbolos equiprováveis e PDFs simétricas ⇒ **limiar no ponto médio** entre centros: $\gamma = (a_1+a_2)/2$. É exatamente o que o enunciado manda: limiar = média dos centros vizinhos.

### 9.2 Função Q e probabilidade de erro
$Q(x) = \frac{1}{\sqrt{2\pi}}\int_x^\infty e^{-y^2/2}dy$; para $x>2$: $Q(x)\approx \frac{e^{-x^2/2}}{x\sqrt{2\pi}}$.

| x | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Q(x) | 0,159 | 2,28·10⁻² | 1,35·10⁻³ | 3,17·10⁻⁵ | 2,87·10⁻⁷ | 9,9·10⁻¹⁰ |

- Binário com distância $d$: $P_b = Q\!\left(\frac{d}{2\sigma}\right)$ (antipodal da Aula 09: $Q(A/\sigma)$, com $d = 2A$).
- M-PAM: $P_s = \frac{2(M-1)}{M}Q\!\left(\frac{d}{2\sigma}\right)$; com Gray $P_b \approx P_s/\log_2M$.

**Na bancada**: ruído do ADC ≈ 1–2 LSB (≈ 1–2 mV). PAM-4: $d/2$ = 0,55 V ⇒ $d/2\sigma \approx 300$ ⇒ $Q(300)$ ≈ 0. **Espere 0 erros** nos canais 1 e 2. Erros só aparecem com interferência forte (perturbação PRBS-7), ISI que feche o olho, ou falha de sincronismo/montagem.

### 9.3 Filtro casado
Filtro linear que **maximiza a SNR** no instante de decisão para um pulso conhecido em ruído branco: $h(t) = s(T-t)$ (pulso espelhado e atrasado). SNR máxima $= 2E/N_0$: depende da **energia** do pulso, não da forma.
Versão discreta com 8 amostras (nosso firmware):
$$z = \frac{\sum_{k=0}^{7}p_c[k]\,x[k]}{E_c},\qquad x[k] = a[k]-b_c,\qquad E_c = \sum p_c[k]^2$$
- É uma **correlação** (produto interno) entre o símbolo recebido e o pulso medido (Aula 01/09).
- Por que dividir por $E_c$? Normaliza: se o símbolo recebido for igual ao pulso A, $z = 1$. Em PAM-4 sem ISI: $z \approx \ell/3$ (0; 0,33; 0,67; 1). É **adimensional** — por isso a margem do filtro não se compara em volts com a da amostra única.
- **Desigualdade de Cauchy–Schwarz**: entre todos os pesos $w$, a razão $(\sum w\cdot p)^2/(\sigma^2\sum w^2)$ é máxima para $w \propto p$ ⇒ ganho de SNR em relação à melhor amostra única $= E_c/p_c[k^*]^2$:
  - Dupont: $p_c$ todos iguais ⇒ ganho **8 (9 dB)** = média de 8 amostras ($\sigma/\sqrt8$).
  - RC 16,8 nF: $1{,}048\cdot10^8/4089^2 \approx 6{,}3$ (8 dB).
- **Limitação diante de ISI** (o enunciado pede que você reconheça): o filtro casado é ótimo para **um pulso isolado + ruído branco**. Ele dá peso às amostras do começo do símbolo, que no RC carregam o **símbolo anterior**. Resultado previsto (PAM-4 RC): margem relativa da amostra única 0,99 × do filtro 0,72; com 33 nF e ruído de 0,2 V o filtro erra tanto quanto a amostra única (403 × 383 símbolos), enquanto no Dupont ele erra 0 × 267. **Margem maior não garante BER menor** e vice-versa: conclua com as contagens.
- O "detector" ótimo com ISI seria um **equalizador** (Aula 09: "filtro equalizador… necessário apenas quando a ISI distorce") ou detecção de sequência — fora do escopo.

### 9.4 Média simples $m_j$
$m_j = \frac18\sum x_j[k]$ = filtro com pesos iguais (casado só para pulso retangular). O enunciado pede registrar em um símbolo de cada nível (o relatório do RX imprime `media8_nivel[...]`). No RC ela fica **abaixo** do nível (o começo do símbolo ainda está subindo): ex. nível 3 após um 0 → média ≈ 3515 em vez de ~4090.

### 9.5 BER, SER e significado estatístico
$$\widehat{BER} = \frac{N_e}{100\,000},\qquad \widehat{SER} = \frac{N_s}{N_{sym}}\ (N_{sym} = 100\,000 \text{ ou } 50\,000)$$
- **0 erros em 100 000 bits** ⇒ "BER observada = 0", **não** BER física nula. Com 0 erros, o limite superior de 95 % de confiança é ≈ $3/N$ = **3·10⁻⁵** ("regra dos três": $(1-p)^N = 0{,}05 \Rightarrow p \approx 3/N$). Para afirmar BER < 10⁻⁹ seriam precisos ~3·10⁹ bits sem erro (~42 h a 20 kbit/s).
- **Erro de bit ≠ falha de sincronismo**: com sincronismo perdido o quadro inteiro desliza (BER ≈ 0,5, sem sentido) — por isso o RX confere os 48 bits de início e, se falharem, **não atribui BER** (`BER=NAO_ATRIBUIDA`). Perda de CLK, amostra faltando ou overrun ⇒ quadro inválido, repetir.
- Treinamento e os 48 bits iniciais **não entram** na BER (estariam "viciando" a estatística com símbolos conhecidos usados para calibrar).

---

## 10. Sincronismo (Aula 08)
Três métodos: (1) relógio mestre comum; (2) **sinal de sincronização separado (relógio piloto)** ← nosso CLK em fio próprio; (3) autossincronização (extrair do próprio sinal, ex. Manchester). Nosso RX: a borda do CLK **zera o TIM2** (Slave Reset) ⇒ as 8 amostras ficam presas à borda; os cristais diferentes de TX e RX não acumulam erro porque o reset acontece a cada símbolo. O enquadramento (onde começa o payload) é confirmado pela palavra 0xD391C5A7.

---

## 11. Resumo de fórmulas (cola mental)

| Grandeza | Fórmula | Valor no projeto |
|---|---|---|
| Taxa de bits | $R_b = R_s\log_2 M$ | 20 / 40 kbit/s |
| τ RC | $(R_{TX}+R)C$ | 6,48 µs (16,8 nF) ; 12,74 µs (33 nF) |
| corte | $f_c = 1/(2\pi\tau)$ | 24,5 kHz ; 12,5 kHz |
| subida | $t_r = 2{,}197\tau$ | 14,2 µs ; 28 µs |
| atenuação de potência | $\|H\|^2 = 1/(1+(f/f_c)^2)$ | 0,96 / 0,86 (5/10 kHz, 16,8 nF) |
| PSD NRZ | $2\sigma^2T_s\text{sinc}^2(\pi fT_s)$ | nulos em 20, 40, 60 kHz |
| saída LIT | $S_y = \|H\|^2S_x$ | razão de PSDs = $\|H\|^2$ |
| resolução PSD | $f_a/N$ | 156,25 Hz |
| LSB | $V_{ref}/4095$ | 0,806 mV |
| instantes de amostra | $3{,}12 + 6{,}25k$ µs | k* = 7 → 46,87 µs |
| filtro casado | $z = \sum p_c x/E_c$ | z(A) ≈ 1 |
| ganho do casado | $E_c/p_c[k^*]^2$ | 8 (Dupont) ; ~6 (RC) |
| erro M-PAM | $\frac{2(M-1)}{M}Q(d/2\sigma)$ | ≈ 0 com σ ≈ 1 mV |
| limite 95 % com 0 erros | $3/N$ | 3·10⁻⁵ |

---

## 12. Exercícios aplicados (com resposta)

1. **Calcule τ, f_c e t_r para 33 nF.** τ = 386 × 33 n = 12,74 µs; f_c = 12,5 kHz; t_r = 28,0 µs. Com o 390 pF e ~30 Ω do pino: ≈ 13,9 µs.
2. **Quanto do degrau sobra no fim do símbolo com 33 nF?** $e^{-50/12{,}74} = 1{,}98\,\%$ → num degrau de 3,3 V, 65 mV de ISI em t = 50 µs (em k = 7, 46,87 µs: 2,5 % = 84 mV).
3. **Razão da PSD em 10 kHz com 33 nF (1 polo)?** $1/(1+(10/12{,}5)^2) = 0{,}61$ (−2,1 dB). Com 2 polos: 0,57.
4. **Por que o PAM-4 tem PSD menor que o PAM-2?** Variância 1,51 × 2,72 V² (os níveis intermediários têm menos potência AC). A forma (sinc²) é a mesma porque $T_s$ é o mesmo.
5. **Se dobrar $R_s$ para 40 ksym/s no RC 16,8 nF, o que acontece?** $T_s$ = 25 µs, amostras a cada 3,125 µs; k = 7 fica em ≈ 23,4 µs e o resíduo da transição é $e^{-23{,}4/7{,}1} \approx 3{,}7\,\%$ (≈ 120 mV num degrau de 3,3 V) ⇒ o olho fecha bastante; o 1º nulo da PSD vai para 40 kHz.
6. **A 100 ksym/s (desafio) no Dupont, qual a fa?** 800 kHz; 1,25 µs entre amostras > 1,08 µs de conversão ⇒ cabe, por pouco.
7. **Calcule z à mão** com $p_c$ = [1369 2971 3631 3904 4015 4063 4080 4088], $b_c$ = 1,35 e a = [3187 3721 3942 4038 4069 4084 4089 4095]: $x = a - 1{,}35$; $\sum p_c x = 1{,}1181\cdot10^8$; $E_c = 1{,}0511\cdot10^8$ ⇒ **z = 1,064** (> 0,881 ⇒ nível 3 ✔). (Janela real do log simulado `SIMULADO_PAM4_RC16n8.txt`.)
8. **Margem u de 1345 códigos com Vref = 3,297 V em volts?** 1345 × 3,297/4095 = 1,083 V.
9. **O RX contou 3 erros em 100 000 bits PAM-4. SER?** Se cada erro foi entre vizinhos (Gray) ⇒ 3 símbolos errados ⇒ SER = 3/50 000 = 6·10⁻⁵; BER = 3·10⁻⁵.
10. **Por que não dá para escolher o limiar olhando o olho?** O enunciado exige a regra objetiva (média dos centros) e congelar antes do payload, para não "ajustar" o detector aos dados que serão contados (viés).
