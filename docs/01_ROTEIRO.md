# 01 — Roteiro de execução (2 semanas + dia da defesa)

> Ordem igual à "Sugestão de sequência de execução" do enunciado (págs. 8–9).
> Cada etapa tem: **o que fazer → o que medir/salvar → critério de "pronto"**.
> Crie já uma pasta `entrega/` com subpastas `capturas/`, `logs/`, `prints_cubemx/`, `relatorio/`.
> **Nomeie todo arquivo com canal e modulação** (ex.: `TP3_olho_RC_PAM4.png`, `log_Dupont_PAM2_1.txt`): é exigência do checklist.

---

## Etapa 0 — Antes de tocar no hardware (≈ 2 h)

| Passo | Ação | Pronto quando |
|---|---|---|
| 0.1 | Leia `02_MATERIAL_ESTUDO.md` seções 1–3 | sabe Ts, Rs, Rb, Gray, τ |
| 0.2 | MATLAB: `cd matlab; simula_enlace` | gerou `resultados_simulacao.txt` e figuras: **é o que você deve encontrar na bancada** |
| 0.3 | `cd firmware/teste_host; make; ./sim_host 4 1` | 0 erros, k* = 7 no RC |
| 0.4 | Monte os modelos Simulink à mão (`03_SIMULINK_PASSO_A_PASSO.md`) | seu modelo dá os mesmos números do modelo de referência |

Valores que você deve ter na cabeça (previsões):

| Grandeza | Dupont | RC 16,8 nF | RC 33 nF (defesa) |
|---|---|---|---|
| τ nominal (enunciado) | 0,13 µs (330 Ω·390 pF) | **6,48 µs** | **12,74 µs** |
| τ modelo 2 polos (+390 pF, +~30 Ω do GPIO) | 0,14 µs | 7,1 µs | 13,9 µs |
| f_c = 1/(2πτ) | 1,24 MHz | 24,5 kHz | 12,5 kHz |
| t₁₀₋₉₀ = 2,197 τ | 0,3 µs | 14,2 µs (15,6 no modelo) | 28 µs |
| resíduo após 1 símbolo e^(−50/τ) | ≈ 0 | 0,05 % | 2,0 % |
| k* esperado | qualquer (empate; decide o ruído) | 7 (46,87 µs) | 7 (46,87 µs) |
| abertura PAM-4 em k* | ≈ 1,09 V | ≈ 1,08 V | ≈ 0,95 V |
| \|H(5 kHz)\|² / \|H(10 kHz)\|² | 1 / 1 | 0,95 / 0,83 | 0,84 / 0,57 |

---

## SEMANA 1

### Dia 1 — CubeMX e firmware (Etapa 1 do enunciado)
1. Crie `PAM_TX.ioc` e `PAM_RX.ioc` seguindo `04_HARDWARE_E_CUBEMX.md` §5 e §6.
2. **Prints**: Pinout e Clock Configuration (TX e RX); parâmetros TIM1, TIM3, TIM2, ADC1, DMA. → `prints_cubemx/`
3. Gere o código, copie os arquivos de `firmware/` e cole os trechos USER CODE (`firmware/INTEGRACAO.md`).
4. Compile os dois. Corrija avisos.
5. **Confira no .ioc** que nenhum pino tem duas funções (enunciado §4).

✅ Pronto: os dois projetos compilam; prints salvos.

### Dia 2 — Montagem e verificação do TX (Etapas 1 e 2)
1. Monte **só o TX**: PA8 → 330 Ω → TP2, 4 × 100 pF em paralelo (400 pF, no lugar dos 390 pF) para GND. Grave o TX.
2. Osciloscópio CH1 = PB4 (CLK), CH2 = TP2. Aperte RESET do TX.
3. **Meça e salve** (`capturas/`):
   - período do CLK = **50,0 µs** (20 kHz), duty 50 %. Use os cursores. → `TX_CLK_50us.png`
   - PAM-2 (PB0 aberto): níveis em TP2 ≈ 0 e 3,3 V. → `TX_TP2_PAM2_niveis.png`
   - PAM-4 (PB0 no GND): níveis ≈ 0 / 1,1 / 2,2 / 3,3 V; registre os valores medidos de cada nível (cursores ou "Measure → Mean" com janela dentro do símbolo). → `TX_TP2_PAM4_niveis.png`
   - **Ordem Gray**: na calibração PAM-4 aparece 0,1,0,3,2,3,1,2 (dispare no início do quadro). Identifique na captura. → `TX_TP2_PAM4_gray.png`
   - TP1 (PA8 bruto): só qualitativo (pulsos de 10/20 ns não são medidos com precisão a 60 MHz de banda).
   - **Ripple** em TP2 no nível 1 (zoom ~50 ns/div): previsto ≈ 150 mVpp. → `TX_TP2_ripple_PWM.png`
   - **Alinhamento**: atraso entre a subida do CLK e o início da transição de TP2 (previsto ≈ 0,2–0,4 µs = latência da ISR). → `TX_alinhamento.png`

✅ Pronto: CLK 20 kHz, 2 e 4 níveis corretos, ordem Gray confirmada.

### Dia 3 — RX e canal 1 (Etapa 3)
1. Monte a proteção (1 kΩ + D+ + D−) e os fios Dupont de dados, CLK e GND (canal 1).
2. **Antes de ligar PA1**: §4 de `04_HARDWARE...` (GND comum, TP3 entre 0 e 3,3 V). **Meça Vref** (3V3 do RX) com o multímetro e anote.
3. Grave o RX, abra a serial do Pico (`/dev/ttyACM1`, 460800). No MATLAB: `captura_serial('/dev/ttyACM1','Dupont_PAM2','d','2')`, depois RESET no TX.
4. Confira no log: `bordas_CLK = simbolos_esperados` (100 444 / 50 420), `amostras_processadas = 8 × símbolos`, `bordas_com_contagem_errada=0`, `aquisicao_valida=1`. → isto é a prova de **8 amostras/símbolo e 160 000 amostras/s sem perdas** (checklist).
5. Argumento para os 160 000 amostras/s: o TIM2 é zerado a cada borda do CLK (50 µs medidos no osciloscópio) e dispara a cada 625 ciclos de 10 ns = 6,25 µs; a contagem `amostras = 8 × bordas` sem erro em 100 444 bordas fecha a conta (8 / 50 µs = 160 kHz). Opcional: CH1 = CLK e CH2 = TP4 com zoom podem mostrar o pequeno "degrau" de carga do capacitor de amostragem do ADC a cada 6,25 µs.

✅ Pronto: um quadro PAM-2 e um PAM-4 válidos no Dupont.

### Dia 4 — Canal 1 completo (Etapas 4, 5, 6 para o Dupont)
Para **PAM-2** e depois **PAM-4** (`2`/`4` no RX + jumper PB0 no TX):
1. **Resposta a transições**: CH1 = TP2, CH2 = TP3, dispare na subida 0→A do treinamento. → `Dupont_PAMx_TP2_TP3_degrau.png`. Meça t₁₀₋₉₀ (Measure → Rise Time).
2. **Olho no osciloscópio**: CH1 = CLK (trigger na subida), CH2 = TP3, 10 µs/div, **Display → Persist = Infinite**. Deixe acumular durante o payload. → `Dupont_PAMx_olho_osc.png`
3. **Quadro completo**: `captura_serial(..., 'Dupont_PAMx', 'd', 'x')`. Guarde o log bruto (entregável!).
4. Análise: `T = analisa_ensaio('logs/Dupont_PAM2_....txt', Vref)`. Ela imprime p_c[k], k*, centros, limiares, margens, abertura, PSD em 5/10 kHz, BER/SER e salva figuras em `matlab/resultados/`.
5. Anote na tabela (modelo em §"Tabela" abaixo).

✅ Pronto: 2 logs válidos (PAM-2, PAM-4) + capturas + figuras do Dupont.

### Dia 5 — Canal 2 (RC) completo
1. Insira **56 Ω em série** e **33 nF em série com 33 nF** (= 16,5 nF) de TP3 para GND (antes do 1 kΩ): TP3 ─[33n]─ N ─[33n]─ GND. Meça o par com o capacímetro se puder: o valor real explica diferenças no τ (nominal com 16,5 nF: 6,37 µs).
2. Repita o Dia 4 com `c` no RX.
3. **τ medido** (PAM-4, transição 0→3 do treinamento): CH1 = CLK, CH2 = TP3, 5 µs/div, trigger na borda do símbolo A.
   - V0 antes da subida, Vf no fim do símbolo, t0 = início da subida, t63 em V0 + 0,632(Vf − V0) → τ = t63 − t0.
   - t₁₀ e t₉₀ → t₁₀₋₉₀; confira τ ≈ t₁₀₋₉₀ / 2,197.
   - Melhor ainda: **Save → CSV** no TDS2002B e `tau_osciloscopio('F0001CH2.CSV')`.
   - Previsto: ≈ 6,5–7,2 µs; t₁₀₋₉₀ ≈ 14–16 µs.
4. Capture TP2 e TP3 juntos (CH1 = TP2, CH2 = TP3): mostra a entrada e a saída do canal (sistema LIT).

✅ Pronto: 2 logs válidos do RC, τ medido, capturas.

---

## SEMANA 2

### Dia 6 — PSD e comparação (Etapa 6)
1. `compara_psd_canais('logs/Dupont_PAM2...','logs/RC_PAM2...', Vref, tau_medido)` e o mesmo para PAM-4.
2. Salve as figuras `psd_comparacao_PAM2.png` / `PAM4.png` (mesma escala nos dois canais ✔).
3. Anote S(5 kHz), S(10 kHz) dos 4 casos e as razões RC/Dupont. Previsto: **≈ 0,95 em 5 kHz** e **≈ 0,82 em 10 kHz**.
4. Explique o **vale do PAM-4 em 10 kHz** (seção 6.4 do material de estudo): é da PRBS + Gray, não do canal.

### Dia 7 — Cabo manga (Etapa 7, exploratório)
1. Monte como em `04_HARDWARE...` §3 "Canal 3". **Desenhe o retorno real de GND** (foto + desenho).
2. Antes de ligar o RX: TP3 entre 0 e 3,3 V.
3. Capture forma de onda e olho em TP3; rode o quadro com `m` no RX.
4. Se `sincronismo_ok=1`: anote erros e BER. Se não: escreva **"sem sincronismo"** + a evidência (olho fechado? `inicio_quadro_erros`? `perda_CLK`?). **Não invente BER.**
5. Explique: 200 m de par comum ≈ 200 m × ~50–100 pF/m = 10–20 nF + resistência (cabo manga tem condutores finos) → efeito parecido com o RC; mais: acoplamento entre condutores e retorno compartilhado.

### Dia 8 — Ensaio da defesa ao vivo (33 nF)
Simule a troca que o professor fará:
1. Passe de 16,5 nF para 33 nF: **jumper de N ao GND** (curto-circuita um dos 33 nF) ou troque o par por um 33 nF. Rótulo `x` no RX.
2. Meça **t₁₀₋₉₀**, **abertura do olho** e **PSD** (e τ). Previstos: τ ≈ 12,7–13,9 µs; t₁₀₋₉₀ ≈ 27–28 µs; abertura PAM-4 ≈ 0,95 V (cai ~13 %); razão PSD 10 kHz ≈ 0,57.
3. Treine a explicação em 1 minuto (ver `05_DEFESA_PERGUNTAS.md`, P1–P3).
4. Cronometre: troca de capacitor + quadro + análise deve caber em ~5 min. Deixe o MATLAB aberto com os comandos prontos.

### Dia 9 — Opcionais (só se sobrar tempo)
- **Perturbação PRBS-7** (Fig. 5): só com o desenho conferido pelo professor.
- **100 ksym/s** (bônus): ver `firmware/INTEGRACAO.md`.
- **PAM-4 a 10 ksym/s** (mesma Rb de 20 kbit/s do PAM-2): troque `PAM_SYM_RATE_HZ` para 10000 (ARR TIM3 = 9999, TIM2 = 1249).

### Dia 10 — Relatório e entrega
Use o checklist do enunciado (pág. 8) e:

**Tabela (Seção 5.1)** — `gera_tabela_resultados({...4 logs...}, Vref, [NaN NaN tau tau])` gera a tabela em Markdown + CSV.

| Canal | PAM | Abertura (V) | τ (µs) | Erros amostra; BER | Erros filtro; BER |
|---|---|---|---|---|---|
| Dupont | 2 | | — | | |
| Dupont | 4 | | — | | |
| RC | 2 | | | | |
| RC | 4 | | | | |
| Cabo manga | 2 | | | (ou "sem sincronismo") | |
| Cabo manga | 4 | | | | |

**Estrutura do relatório curto (4–6 páginas):**
1. Objetivo e arquitetura (Fig. 1 do enunciado + pinagem real).
2. Montagem real (esquema desenhado, fotos, valores medidos dos componentes, Vref).
3. Verificação do TX (CLK, níveis, Gray, ripple, alinhamento).
4. Verificação do RX (8 amostras/símbolo, 160 kS/s, perdas = 0).
5. Canais: degrau, τ previsto × medido e causas da diferença; olhos com k*; ISI no 1º zero depois de A.
6. PSD: método (fa, Vref, média retirada, N = 1024, Hann, 50 %, 15 blocos, 156,25 Hz, 51,2 ms), figuras na mesma escala, valores em 5/10 kHz e razões × |H|².
7. Detectores: p_c[k], k*, centros, limiares, margens (em suas unidades), conta à mão de um z, BER/SER, conclusão por canal.
8. Cabo manga (exploratório) com retorno de GND desenhado.
9. **Uso de IA**: diga onde foi usada (geração do firmware base, scripts MATLAB, modelos Simulink, material de estudo), o que veio do enunciado (todos os parâmetros) e o que depende das medições da equipe (todas as conclusões numéricas).

---

## Dia da defesa (100 min no total, ~40 min por equipe)

**Leve pronto**: as duas placas gravadas e testadas, montagem do canal 2 na protoboard (capacitor fácil de trocar), notebook com MATLAB aberto em `matlab/`, os logs e figuras, o relatório impresso/aberto, capacitor de 33 nF de reserva.

**Sequência sugerida (~40 min):**

| min | Ação | Quem fala |
|---|---|---|
| 0–3 | Liga tudo; mostra CLK 50 µs e TP2 PAM-4 no osciloscópio | integrante A |
| 3–8 | Quadro PAM-4 no RC ao vivo → log → `analisa_ensaio` → tabela | integrante B |
| 8–13 | Olho com persistência + linha de k*; explica a escolha de k* pelos dados | B |
| 13–18 | Professor troca 16,8 → 33 nF; mede t₁₀₋₉₀, olho, PSD | **cada um registra** |
| 18–30 | Perguntas individuais Fourier/PSD/canal (A) e amostragem/filtro/olho/BER (B) | individual |
| 30–40 | Alterações pedidas pelo professor, síntese | ambos |

**Comandos prontos no MATLAB:**
```matlab
Vref = 3.297;                                       % o SEU valor medido
f = captura_serial('/dev/ttyACM1','RC33_PAM4','x','4');   % depois RESET no TX
T = analisa_ensaio(f, Vref);
compara_psd_canais('logs/<Dupont_PAM4>.txt', f, Vref, 13);
tau_osciloscopio('F0002CH2.CSV');                   % CSV salvo no pendrive do TDS
```
