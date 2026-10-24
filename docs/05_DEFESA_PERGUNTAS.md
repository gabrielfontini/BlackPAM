# 05 — Defesa individual: perguntas, como responder e o que levar

> A defesa vale **4 dos 10 pontos, individual**. O professor quer ver **medidas da sua bancada**, com unidade e captura identificada. Use as respostas abaixo como **estrutura**; troque os números previstos pelos SEUS (campos `[ ]`).
> Regra de ouro: **número medido → teoria da aula → conclusão verificável.**

---

## Bloco A — Fourier/PSD e canal (2,0 pontos)

### P1. "Compare a potência espectral perto de 5 e 10 kHz nos dois canais. Calcule a razão e explique pela resposta RC medida. Informe janela, duração e resolução."
**Roteiro de resposta (1–2 min):**
1. Método: "8 192 amostras do ADC a 160 kHz (51,2 ms), convertidas com Vref medido = [ ] V, média retirada, 15 blocos de 1 024 com 50 % de sobreposição, janela de Hann, PSD unilateral em V²/Hz, resolução 156,25 Hz."
2. Valores: "Em 5 kHz: Dupont [ ] e RC [ ] V²/Hz → razão [ ] ([ ] dB). Em 10 kHz: [ ] e [ ] → razão [ ]."
3. Teoria (Aula 04): "Para sistema LIT, $S_y = |H|^2S_x$. Como os 8 192 pontos começam no mesmo símbolo do payload nos dois ensaios, os bits são os mesmos e a razão é $|H(f)|^2$."
4. Conta com o τ medido: "$|H|^2 = 1/(1+(2\pi f\tau)^2)$; com τ = [ ] µs: 5 kHz → [ ], 10 kHz → [ ]." (Previsto: ≈ 0,95 e ≈ 0,83.)
5. Conclusão: "O RC quase não mexe em 5 kHz (f ≪ f_c = 24 kHz) e tira ~17 % da potência em 10 kHz. Atenuar alta frequência = subida mais lenta = ISI."

**Perguntas de seguimento prováveis:**
- *"Por que o valor absoluto difere da teoria em 30 %?"* → variância do estimador de Welch (só ~15 médias); por isso compara-se a razão ou a média de 5 bins.
- *"Por que tem nulos em 20, 40, 60 kHz?"* → pulso retangular de 50 µs ⇒ sinc²(πfTs), zeros em n/Ts (Aula 02).
- *"Por que o PAM-4 tem um vale em 10 kHz e o PAM-2 não?"* → PRBS-15 + Gray ⇒ nível_i = 2c_i + c_(i−7) ⇒ fator 5 + 4cos(2πf·7Ts), mínimo em 10 kHz (material §6.4). Não é efeito do canal: aparece no Dupont também.
- *"E a raia em f = 0?"* → sinal unipolar tem média 1,65 V; retiramos a média antes da FFT.
- *"O que aparece acima de 60 kHz / perto de 53 kHz?"* → aliasing (fa/2 = 80 kHz, sem anti-aliasing); o ripple de 33,3 MHz dobra para ≈ 53,3 kHz.

### P2. "Estime τ por R e C, extraia do degrau capturado. Se divergir, dê uma causa física ou instrumental verificável."
1. Previsão: "(330 + 56) Ω × 16,8 nF = 6,48 µs; f_c = 24,5 kHz; t_r previsto = 2,197τ = 14,2 µs."
2. Medida: "Transição 0→3 do treinamento PAM-4 em TP3 (captura [nome]): V0 = [ ], Vf = [ ], V63 = [ ], t0 = [ ], t63 = [ ] ⇒ τ = [ ] µs. t10 = [ ], t90 = [ ] ⇒ t_r = [ ] µs ⇒ τ = t_r/2,197 = [ ] µs."
3. Divergência (previsto pelo modelo completo ≈ 7,1 µs): "O modelo de 1 polo ignora (a) o 390 pF do TX (+0,13 µs), (b) a resistência de saída do PA8 (~30 Ω × 16,8 nF ≈ +0,5 µs) e (c) a tolerância do capacitor — medi o 10 nF ∥ 6,8 nF = [ ] nF." Escolha UMA causa e mostre como verificaria (medir o capacitor; medir τ com ponta ×1 e ×10; medir só o filtro do TX no canal 1).

### P3 (ao vivo). "Troquei 16,8 nF por 33 nF. Meça tempo de subida, abertura do olho e PSD e explique."
| Grandeza | 16,8 nF (seu) | 33 nF previsto | 33 nF medido |
|---|---|---|---|
| τ | [ ] | 12,7 (1 polo) – 13,9 µs (2 polos) | |
| t₁₀₋₉₀ | [ ] | 27–28 µs | |
| resíduo em k = 7 | 0,1 % | 2,5 % (~84 mV) | |
| abertura PAM-4 em k* | ≈ 1,08 V | ≈ 0,95 V | |
| abertura PAM-2 em k* | ≈ 3,28 V | ≈ 3,07 V | |
| razão PSD 5 kHz (vs Dupont) | 0,95 | 0,84 | |
| razão PSD 10 kHz | 0,83 | 0,57 | |
| k* | 7 | 7 | |

**Fala:** "C dobrou ⇒ τ dobrou ⇒ f_c caiu à metade (12,5 kHz) ⇒ em 10 kHz a potência cai para ~0,6 do Dupont. No tempo, a subida não termina em 50 µs: sobram ~2 % do degrau, que viram ISI no símbolo seguinte e fecham o olho em ~13 %. Ainda dá 0 erros porque a abertura (~0,95 V) é ≫ ruído (~1 mV); o capacitor de 33 nF é didático, não o modelo de 300 m."

---

## Bloco B — Amostragem, filtro casado, olho e BER (2,0 pontos)

### P4. "Mostre as 8 amostras por símbolo e justifique k*."
1. "O CLK zera o TIM2; o evento TIM2_CC2 em 312 ciclos (3,12 µs) dispara o ADC; depois a cada 625 ciclos (6,25 µs): t_k = 3,12 + 6,25k µs, 8 por símbolo, 160 kS/s. O relatório mostra [100 444] bordas e [803 552] amostras = 8 × bordas, 0 bordas com contagem errada."
2. "Com os 256 símbolos de calibração calculei, para cada k, a menor separação entre níveis vizinhos: [lista]. A maior é em k = [7] ⇒ t = [46,87] µs, separação [ ] códigos = [ ] V."
3. No olho: "a linha vertical em 46,87 µs; o olho está aberto ali e fechado em k = 0 (3,12 µs), onde a separação é negativa (−2294 códigos previsto): o nível ainda está subindo."
4. PAM-4: "o par mais próximo é [2–3], bits Gray [11/10]."
5. Dupont: "todos os k empatam (o sinal estabiliza em < 1 µs); k* sai do ruído — qualquer k serviria."

### P5. "Mostre os 8 coeficientes e calcule um z à mão."
Leve a janela do relatório (`janela a[k] x[k] p_c[k]`) **impressa**. Monte a tabela:

| k | a[k] | x = a − b_c | p_c[k] | p_c·x |
|---|---|---|---|---|
| 0…7 | | | | |
| | | | **Σ =** | |

"E_c = Σp_c² = [ ]; z = Σ/E_c = [ ]; limiares z = [ ] ⇒ nível [ ] ⇒ bits Gray [ ]."
Comparação de margens: "amostra única [ ] mV (em volts), filtro [ ] (escala z, adimensional; z = 1 é o pulso A). Não se comparam números de unidades diferentes; compara-se a **margem relativa** (margem/distância entre centros): u = [0,99], z = [0,72]."
"No RC o filtro casado tem margem menor porque os pesos grandes de k = 3…7 são bons, mas k = 0…2 carregam ISI do símbolo anterior. Ele é ótimo contra ruído branco para pulso isolado, não contra ISI."

### P6. "O que significa N_e erros em 100 000 bits? 0 erros prova BER nula?"
- "BER observada = N_e/100 000. Com 0 erros escrevo '0 erros em 100.000 bits'. Isso só limita a BER: com 95 % de confiança BER < 3/100 000 = 3·10⁻⁵."
- "Pela teoria (Aula 09): d/2σ ≈ 0,55 V / 1 mV ≈ 500 ⇒ Q(500) ≈ 0 ⇒ era esperado 0 erro."
- "Erro de bit ≠ falha de sincronismo: se os 48 bits de início não batem ou falta amostra/CLK, o quadro é inválido e não recebe BER — eu repeti o ensaio."
- Gray: "cada erro de vizinho custa 1 bit ⇒ N_e ≈ N_s em PAM-4 ⇒ BER ≈ SER/2."

### P7. Prováveis "alterações feitas pelo professor"
| Alteração | O que muda | O que dizer |
|---|---|---|
| Troca 16,8 → 33 nF | τ, olho, PSD (P3) | refazer treinamento (k*, p_c, limiares) |
| Desliga o fio de CLK no meio | `perda_CLK=1`, quadro inválido | sem BER; sincronismo assistido depende do CLK |
| Inverte TP2/GND ou tira o GND comum | níveis errados, calibração inválida | `calibracao_ok=0`; não há referência comum |
| Pede PAM-2 × PAM-4 | margens 3× menores no PAM-4 | mesmo Rs ⇒ mesma banda; PAM-4 dobra Rb mas exige mais SNR |
| "Qual k* sem RC?" | empate | ver P4 |
| "Mude o limiar à mão" | não pode | parâmetros congelados antes do payload (evita viés) |
| Pergunta sobre aliasing | fa/2 = 80 kHz | ripple PWM → 53,3 kHz; NRZ tem lóbulos acima de 80 kHz |

---

## Kit do dia (imprimir)
- [ ] Tabela de resultados preenchida (4 linhas obrigatórias + manga)
- [ ] Para cada condição: p_c[k], k*, separações, centros, limiares, margens (saída do `analisa_ensaio`)
- [ ] Uma janela real (a[k], x[k], p_c[k]) para a conta à mão — **cada integrante faz a sua**
- [ ] Capturas: CLK 50 µs, níveis TP2, Gray, degrau TP2/TP3 nos dois canais, olhos com k*, PSDs na mesma escala
- [ ] Previsões do 33 nF (tabela da P3) com espaço para os medidos
- [ ] Vref medido
- [ ] Desenho do retorno de GND do cabo manga
- [ ] Este arquivo e o `02_MATERIAL_ESTUDO.md` §11 (resumo de fórmulas)
