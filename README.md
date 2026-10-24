# Projeto PAM em banda base — BlackPill STM32F411 (Telecom 2026S2, P1 prática)

Tudo que o enunciado `../Projeto_BB_2026S2.pdf` pede, já preparado: firmware TX/RX, scripts de análise, modelos Simulink, roteiro de execução e material de estudo baseado nas Aulas 01–09.

## Comece por aqui

| Ordem | Arquivo | Para quê |
|---|---|---|
| 1 | [`docs/01_ROTEIRO.md`](docs/01_ROTEIRO.md) | **roteiro dia a dia** (2 semanas + dia da defesa), o que medir e salvar, previsões |
| 2 | [`docs/02_MATERIAL_ESTUDO.md`](docs/02_MATERIAL_ESTUDO.md) | **material de estudo**: cada aula ligada ao projeto, com contas e exercícios |
| 3 | [`docs/03_SIMULINK_PASSO_A_PASSO.md`](docs/03_SIMULINK_PASSO_A_PASSO.md) | montar e simular os 2 modelos **bloco a bloco** |
| 4 | [`docs/04_HARDWARE_E_CUBEMX.md`](docs/04_HARDWARE_E_CUBEMX.md) | material, esquema, pinagem, **CubeMX passo a passo** (TX e RX), problemas comuns |
| 5 | [`firmware/INTEGRACAO.md`](firmware/INTEGRACAO.md) | onde colar o código no projeto do CubeIDE |
| 6 | [`docs/05_DEFESA_PERGUNTAS.md`](docs/05_DEFESA_PERGUNTAS.md) | perguntas da defesa individual, roteiro de resposta, troca para 33 nF |

## Estrutura

```
Projeto_PAM_BB/
├── docs/                       roteiro, estudo, Simulink, hardware/CubeMX, defesa; img/ (figuras)
├── firmware/
│   ├── common/                 pam_config.h (números do enunciado), pam_frame.c/h (PRBS-15, quadro, Gray)
│   ├── tx/                     pam_tx.c/h  (TIM1 PWM + TIM3 CLK + ISR)
│   ├── rx/                     pam_rx.c/h (TIM2+ADC+DMA, perdas, serial), pam_rx_core.c/h (detectores, BER),
│   │                           pam_rx_report.c/h (relatório)
│   ├── teste_host/             sim_host.c: roda TX+canal+RX no PC e gera logs no formato real
│   ├── build_referencia/       Makefile + main/msp/it de referência: compila TX e RX com a HAL oficial
│   └── INTEGRACAO.md
├── matlab/
│   ├── simula_enlace.m         previsão de TODOS os resultados (τ, k*, p_c, margens, PSD, BER×ruído)
│   ├── analisa_ensaio.m        análise de um log real do RX (figuras + números da defesa)
│   ├── gera_tabela_resultados.m  tabela da Seção 5.1 (Markdown + CSV)
│   ├── compara_psd_canais.m    PSD Dupont × RC, razão × |H|²  (questão 1 da defesa)
│   ├── tau_osciloscopio.m      τ e t10-90 a partir do CSV do TDS2002B
│   ├── captura_serial.m        arma o RX e grava o log
│   ├── pam_quadro.m pam_detectores.m pam_psd.m pam_psd_teorica.m pam_canal_sim.m pam_olho.m pam_parametros.m le_log_rx.m
│   ├── exemplo_logs/           logs SIMULADOS no formato real (para treinar a análise antes da placa)
│   ├── figuras_simulacao/      saída de simula_enlace.m
│   └── resultados_simulacao.txt
└── simulink/
    ├── pam_enlace_simulink.slx     modelo A (enlace completo, blocos básicos)
    ├── pam_circuito_simscape.slx   modelo B (circuito físico com PWM de 33 MHz, Simscape Electrical)
    ├── pam_simulink_init.m  calibra_simulink.m  olho_simulink.m  criar_modelos_simulink.m
    └── ref_*.png
```

## Testes já feitos (sem placa)
- `firmware/teste_host`: quadro com 100 444 (PAM-2) e 50 420 (PAM-4) símbolos, PRBS-15 de período 32 767, **0 erros** nos canais Dupont, RC 16,8 nF e RC 33 nF; com ruído, o filtro casado ganha da amostra única como prevê a teoria.
- `firmware/build_referencia`: TX (8 kB) e RX (21 kB de Flash, 30 kB de RAM) compilam **sem warnings** com arm-none-eabi-gcc + HAL F4.
- MATLAB: `analisa_ensaio` recalcula a partir dos dados brutos e bate com o firmware (Δp_c ≈ 10⁻¹³, mesmo k* e mesmo z).
- Simulink: modelo A treinado no próprio Simulink dá os mesmos p_c/k*/limiares do firmware, e as contagens de erro batem com o MATLAB (64 = 64 sob ruído forte); modelo B dá τ = 7,12 µs (previsto 7,11) e ripple de PWM ≈ 150 mVpp.

**O que NÃO foi testado:** o firmware rodando nas BlackPills reais (não há placa aqui). As partes de temporização (latência da ISR do TX, espera da 1ª borda no RX, prioridades de interrupção) seguem o RM0383/HAL, mas confirme na bancada com o osciloscópio e com `bordas_com_contagem_errada=0`.

## Uso de IA (para declarar no relatório)
Firmware, scripts MATLAB, modelos Simulink e textos desta pasta foram gerados com ajuda de IA (Claude) a partir do enunciado e das aulas. Os parâmetros vêm do enunciado; as previsões numéricas vêm de simulação; **todas as conclusões do relatório devem vir das medições da equipe**.
