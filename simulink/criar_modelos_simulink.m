%CRIAR_MODELOS_SIMULINK  Monta automaticamente os dois modelos de REFERÊNCIA.
%   Os mesmos modelos estão descritos bloco a bloco em
%   docs/03_SIMULINK_PASSO_A_PASSO.md para você montar à mão. Use este script
%   para conferir o seu modelo (abra os dois lado a lado).
%
%   Modelo A  pam_enlace_simulink.slx  — enlace completo com blocos básicos:
%             quadro -> níveis -> canal RC (LIT) -> ADC 8x -> amostra única
%             e filtro casado -> decisão -> contagem de erros
%   Modelo B  pam_circuito_simscape.slx — circuito físico (Simscape Electrical):
%             PWM 33,3 MHz -> 330 Ω/390 pF -> 56 Ω/16,8 nF -> 1 kΩ + Schottky -> ADC

here = fileparts(mfilename('fullpath'));
cd(here);
pam_simulink_init;
% callbacks: ao abrir e a cada Run o modelo roda pam_simulink_init da própria pasta
CB = 'run(fullfile(fileparts(get_param(bdroot,''FileName'')),''pam_simulink_init.m''))';

%% ===================== MODELO A =====================
mdl = 'pam_enlace_simulink';
if bdIsLoaded(mdl), close_system(mdl, 0); end
if exist(fullfile(here, [mdl '.slx']), 'file'), delete(fullfile(here, [mdl '.slx'])); end
new_system(mdl); open_system(mdl);
set_param(mdl, 'SolverType', 'Variable-step', 'Solver', 'ode23tb', 'MaxStep', '1e-6', ...
    'RelTol', '1e-4', 'StopTime', 'T_sim', 'ReturnWorkspaceOutputs', 'on');
set_param(mdl, 'PostLoadFcn', CB, 'InitFcn', CB);
B = @(nome) [mdl '/' nome];
add = @(lib, nome, pos, varargin) add_block(lib, B(nome), 'Position', pos, varargin{:});
L = @(a, b) add_line(mdl, a, b, 'autorouting', 'smart');

% ---- 1. TX ----
add('simulink/Sources/From Workspace', 'Fonte nivel (quadro)', [30 40 150 70], ...
    'VariableName', 'fonte_nivel', 'SampleTime', 'Ts', 'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
add('simulink/Sources/From Workspace', 'Fonte payload (0 ou 1)', [30 420 150 450], ...
    'VariableName', 'fonte_payload', 'SampleTime', 'Ts', 'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
add('simulink/Math Operations/Gain', 'TX nivel para V', [200 40 260 70], 'Gain', 'Vmax/(M-1)');
add('simulink/Sources/Pulse Generator', 'CLK 20 kHz', [200 110 260 140], ...
    'Amplitude', '3.3', 'Period', 'Ts', 'PulseWidth', '50', 'PhaseDelay', '0');
add('simulink/Continuous/Transfer Fcn', 'Canal RC (LIT)', [310 35 450 75], ...
    'Numerator', 'num_canal', 'Denominator', 'den_canal');
add('simulink/Signal Routing/Mux', 'Mux TX', [520 30 525 130], 'Inputs', '3');
add('simulink/Sinks/Scope', 'Scope CLK TX TP3', [560 60 600 100]);
add('simulink/Sinks/To Workspace', 'tp3_log', [520 150 600 180], ...
    'VariableName', 'tp3_log', 'SaveFormat', 'Array', 'SampleTime', '0.5e-6');
L('Fonte nivel (quadro)/1', 'TX nivel para V/1');
L('TX nivel para V/1', 'Canal RC (LIT)/1');
L('CLK 20 kHz/1', 'Mux TX/1');
L('TX nivel para V/1', 'Mux TX/2');
L('Canal RC (LIT)/1', 'Mux TX/3');
L('Mux TX/1', 'Scope CLK TX TP3/1');
L('Canal RC (LIT)/1', 'tp3_log/1');

% ---- 2. ADC do RX ----
add('simulink/Discrete/Zero-Order Hold', 'ADC amostrador 160 kHz', [330 230 380 260], 'SampleTime', '[Tsa t0]');
add('simulink/Sources/Random Number', 'Ruido ADC', [330 290 380 320], ...
    'Mean', '0', 'Variance', 'sigma_ruido^2', 'Seed', '1', 'SampleTime', '[Tsa t0]');
add('simulink/Math Operations/Sum', 'Soma ruido', [420 235 440 275], 'Inputs', '++');
add('simulink/Discontinuities/Saturation', 'Faixa 0 a Vref', [470 240 520 270], 'UpperLimit', 'Vref', 'LowerLimit', '0');
add('simulink/Discontinuities/Quantizer', 'Quantizador 12 bits', [550 240 600 270], 'QuantizationInterval', 'q_adc');
add('simulink/Sinks/To Workspace', 'adc_log', [640 300 720 330], 'VariableName', 'adc_log', 'SaveFormat', 'Array');
L('Canal RC (LIT)/1', 'ADC amostrador 160 kHz/1');
L('ADC amostrador 160 kHz/1', 'Soma ruido/1');
L('Ruido ADC/1', 'Soma ruido/2');
L('Soma ruido/1', 'Faixa 0 a Vref/1');
L('Faixa 0 a Vref/1', 'Quantizador 12 bits/1');
L('Quantizador 12 bits/1', 'adc_log/1');

% ---- 3. Detector de amostra única ----
add('simulink/Discrete/Zero-Order Hold', 'Amostra unica a(k*)', [660 220 720 250], 'SampleTime', '[Ts t_kstar]');
L('Quantizador 12 bits/1', 'Amostra unica a(k*)/1');
cadeia_decisao(mdl, 'u', 'Amostra unica a(k*)/1', 'thr_u', 't_kstar', 760, 200);

% ---- 4. Filtro casado digital ----
add('simulink/Math Operations/Bias', 'x = a - b_c', [660 380 720 410], 'Bias', '-bc');
add('simulink/Discrete/Discrete FIR Filter', 'Filtro casado FIR h_c', [750 375 840 415], ...
    'Coefficients', 'hc', 'SampleTime', '-1');
add('simulink/Discrete/Zero-Order Hold', 'z no fim da janela', [870 380 930 410], 'SampleTime', '[Ts t_fim]');
add('simulink/Sinks/To Workspace', 'z_log', [970 450 1040 480], 'VariableName', 'z_log', 'SaveFormat', 'Array');
L('Quantizador 12 bits/1', 'x = a - b_c/1');
L('x = a - b_c/1', 'Filtro casado FIR h_c/1');
L('Filtro casado FIR h_c/1', 'z no fim da janela/1');
L('z no fim da janela/1', 'z_log/1');
cadeia_decisao(mdl, 'z', 'z no fim da janela/1', 'thr_z', 't_fim', 970, 360);

% nível transmitido e flag de payload amostrados nos mesmos instantes
for d = {'u', 't_kstar'; 'z', 't_fim'}.'
    s = d{1}; tt_ = d{2};
    add('simulink/Discrete/Zero-Order Hold', ['Nivel TX ' s], [200 520+80*(s=='z') 260 550+80*(s=='z')], 'SampleTime', ['[Ts ' tt_ ']']);
    add('simulink/Discrete/Zero-Order Hold', ['Payload ' s], [200 560+80*(s=='z') 260 590+80*(s=='z')], 'SampleTime', ['[Ts ' tt_ ']']);
    L('Fonte nivel (quadro)/1', ['Nivel TX ' s '/1']);
    L('Fonte payload (0 ou 1)/1', ['Payload ' s '/1']);
    L(['Nivel TX ' s '/1'], ['Erro simbolo ' s '/2']);
    L(['Nivel TX ' s '/1'], ['uint8 TX ' s '/1']);
    L(['Payload ' s '/1'], ['x payload Ns ' s '/2']);
    L(['Payload ' s '/1'], ['x payload Ne ' s '/2']);
end
add('simulink/Signal Routing/Mux', 'Mux det', [1350 140 1355 260], 'Inputs', '3');
add('simulink/Sinks/Scope', 'Scope decisoes', [1390 180 1430 220]);
L('Nivel TX u/1', 'Mux det/1'); L('Nivel decidido u/1', 'Mux det/2'); L('Nivel decidido z/1', 'Mux det/3');
annotation_text(mdl, [30 700], sprintf(['Modelo A — enlace PAM em banda base (Rs = 20 ksym/s, 8 amostras/símbolo).\n' ...
    '1) pam_simulink_init  2) out = sim(''pam_enlace_simulink'')  3) calibra_simulink  4) sim de novo  5) olho_simulink']));
Simulink.BlockDiagram.arrangeSystem(mdl);
save_system(mdl, fullfile(here, [mdl '.slx']));

%% ===================== MODELO B (Simscape) =====================
mdc = 'pam_circuito_simscape';
if bdIsLoaded(mdc), close_system(mdc, 0); end
if exist(fullfile(here, [mdc '.slx']), 'file'), delete(fullfile(here, [mdc '.slx'])); end
new_system(mdc); open_system(mdc);
set_param(mdc, 'SolverType', 'Variable-step', 'Solver', 'ode23t', 'MaxStep', 'max_step_circ', ...
    'RelTol', '1e-4', 'StopTime', 'T_sim_circ', 'ReturnWorkspaceOutputs', 'on');
set_param(mdc, 'PostLoadFcn', CB, 'InitFcn', CB);
C = @(nome) [mdc '/' nome];
ad = @(lib, nome, pos, varargin) add_block(lib, C(nome), 'Position', pos, varargin{:});
Ls = @(a, b) add_line(mdc, a, b, 'autorouting', 'smart');
ph = @(nome) get_param(C(nome), 'PortHandles');

% ---- geração do PWM igual ao TIM1 (PSC=0, ARR=2) ----
ad('simulink/Sources/From Workspace', 'TIM1_CCR1 (nivel)', [30 40 150 70], ...
    'VariableName', 'fonte_ccr', 'SampleTime', 'Ts', 'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
ad('simulink/Sources/Repeating Sequence Stair', 'CNT do TIM1 (0,1,2)', [30 110 150 140], 'OutValues', '[0 1 2]', 'tsamp', '10e-9');
ad('simulink/Logic and Bit Operations/Relational Operator', 'CNT < CCR1', [200 80 240 120], 'Operator', '<');
ad('simulink/Signal Attributes/Data Type Conversion', 'para double', [270 85 320 115], 'OutDataTypeStr', 'double');
ad('simulink/Math Operations/Gain', 'PA8 0 ou 3,3 V', [350 85 400 115], 'Gain', 'Vmax');
ad('simulink/Math Operations/Gain', 'nivel medio', [270 160 330 190], 'Gain', 'Vmax/3');
ad('simulink/Discontinuities/Saturation', 'CCR max 3', [200 160 240 190], 'UpperLimit', '3', 'LowerLimit', '0');
ad('simulink/Sources/Constant', 'usar_pwm', [350 140 400 160], 'Value', 'usar_pwm');
ad('simulink/Signal Routing/Switch', 'PWM ou media', [440 90 480 190], 'Criteria', 'u2 > Threshold', 'Threshold', '0.5');
Ls('TIM1_CCR1 (nivel)/1', 'CNT < CCR1/2');
Ls('CNT do TIM1 (0,1,2)/1', 'CNT < CCR1/1');
Ls('CNT < CCR1/1', 'para double/1');
Ls('para double/1', 'PA8 0 ou 3,3 V/1');
Ls('TIM1_CCR1 (nivel)/1', 'CCR max 3/1');
Ls('CCR max 3/1', 'nivel medio/1');
Ls('PA8 0 ou 3,3 V/1', 'PWM ou media/1');
Ls('usar_pwm/1', 'PWM ou media/2');
Ls('nivel medio/1', 'PWM ou media/3');

% ---- circuito ----
fl = 'fl_lib/Electrical/';
ad('nesl_utility/Simulink-PS Converter', 'S-PS', [510 125 540 155], 'Unit', 'V');
ad([fl 'Electrical Sources/Controlled Voltage Source'], 'Pino PA8', [570 110 610 170]);
ad([fl 'Electrical Elements/Resistor'], 'R saida GPIO', [650 60 700 90], 'R', 'Rgpio');
ad([fl 'Electrical Elements/Resistor'], 'R1 330', [740 60 790 90], 'R', 'R1');
ad([fl 'Electrical Elements/Capacitor'], 'C1 390p', [830 120 870 170], 'c', 'C1');
ad([fl 'Electrical Elements/Resistor'], 'R2 56 (canal)', [900 60 950 90], 'R', 'R2');
ad([fl 'Electrical Elements/Capacitor'], 'C2 16n8 (canal)', [990 120 1030 170], 'c', 'C2');
ad([fl 'Electrical Elements/Resistor'], 'R protecao 1k', [1060 60 1110 90], 'R', 'Rprot');
ad([fl 'Electrical Elements/Capacitor'], 'C ADC 4p', [1170 120 1210 170], 'c', 'C_adc');
ad([fl 'Electrical Elements/Diode'], 'D+ (TP4 para 3V3)', [1150 0 1200 30], 'Vf', 'Vf_schottky', 'Ron', 'Ron_schottky');
ad([fl 'Electrical Elements/Diode'], 'D- (GND para TP4)', [1240 120 1290 150], 'Vf', 'Vf_schottky', 'Ron', 'Ron_schottky');
ad([fl 'Electrical Sources/DC Voltage Source'], '3V3 do RX', [1260 -10 1290 40], 'v0', 'Vref');
ad([fl 'Electrical Elements/Electrical Reference'], 'GND', [880 260 910 290]);
ad('nesl_utility/Solver Configuration', 'Solver', [560 250 610 280]);
nomesTP = {'TP2', 'TP3', 'TP4'};
for i = 1:3
    ad([fl 'Electrical Sensors/Voltage Sensor'], ['Sensor ' nomesTP{i}], [820+170*(i-1) 320 860+170*(i-1) 370]);
    ad('nesl_utility/PS-Simulink Converter', ['PS-S ' nomesTP{i}], [830+170*(i-1) 400 860+170*(i-1) 425], 'Unit', 'V');
end
p = @(nome) ph(nome);
cn = @(h1, h2) add_line(mdc, h1, h2, 'autorouting', 'smart');
Ls('PWM ou media/1', 'S-PS/1');
cn(p('S-PS').RConn(1), p('Pino PA8').RConn(1));              % vT
cn(p('Pino PA8').LConn(1), p('R saida GPIO').LConn(1));       % + -> Rgpio
cn(p('R saida GPIO').RConn(1), p('R1 330').LConn(1));
cn(p('R1 330').RConn(1), p('C1 390p').LConn(1));              % nó TP2
cn(p('R1 330').RConn(1), p('R2 56 (canal)').LConn(1));
cn(p('R2 56 (canal)').RConn(1), p('C2 16n8 (canal)').LConn(1)); % nó TP3
cn(p('R2 56 (canal)').RConn(1), p('R protecao 1k').LConn(1));
cn(p('R protecao 1k').RConn(1), p('C ADC 4p').LConn(1));      % nó TP4
cn(p('R protecao 1k').RConn(1), p('D+ (TP4 para 3V3)').LConn(1));   % anodo D+ = TP4
cn(p('D+ (TP4 para 3V3)').RConn(1), p('3V3 do RX').LConn(1));       % catodo D+ = 3V3
cn(p('R protecao 1k').RConn(1), p('D- (GND para TP4)').RConn(1));   % catodo D- = TP4
gnd = p('GND').LConn(1);
cn(p('D- (GND para TP4)').LConn(1), gnd);                     % anodo D- = GND
cn(p('3V3 do RX').RConn(1), gnd);
cn(p('C1 390p').RConn(1), gnd);
cn(p('C2 16n8 (canal)').RConn(1), gnd);
cn(p('C ADC 4p').RConn(1), gnd);
cn(p('Pino PA8').RConn(2), gnd);                              % - da fonte
cn(p('Solver').RConn(1), gnd);
nos = {p('R1 330').RConn(1), p('R2 56 (canal)').RConn(1), p('R protecao 1k').RConn(1)};
for i = 1:3
    s = p(['Sensor ' nomesTP{i}]);
    cn(nos{i}, s.LConn(1));
    cn(s.RConn(2), gnd);
    cn(s.RConn(1), p(['PS-S ' nomesTP{i}]).LConn(1));
end
ad('simulink/Signal Routing/Mux', 'Mux TPs', [1400 380 1405 460], 'Inputs', '4');
ad('simulink/Sinks/Scope', 'Scope TP2 TP3 TP4', [1440 400 1480 440]);
ad('simulink/Sinks/To Workspace', 'circ_log', [1440 470 1520 500], 'VariableName', 'circ_log', ...
    'SaveFormat', 'Structure With Time', 'SampleTime', '5e-9');
Ls('PWM ou media/1', 'Mux TPs/1');
for i = 1:3, Ls(['PS-S ' nomesTP{i} '/1'], sprintf('Mux TPs/%d', i+1)); end
Ls('Mux TPs/1', 'Scope TP2 TP3 TP4/1');
Ls('Mux TPs/1', 'circ_log/1');
annotation_text(mdc, [30 520], sprintf(['Modelo B — circuito da Figura 3 em Simscape. Canal: variáveis R2/C2 (pam_simulink_init).\n' ...
    'usar_pwm = 1: PWM real de 33,3 MHz (passo <= 2,5 ns, lento); usar_pwm = 0: nível médio (rápido).']));
save_system(mdc, fullfile(here, [mdc '.slx']));
fprintf('\nModelos gravados em %s\n', here);

%% ---------------- funções locais ----------------
function cadeia_decisao(mdl, s, origem, thr, ~, x0, y0)
% decisor por limiares + contagem de erros de símbolo e de bit (Gray)
B = @(nome) [mdl '/' nome];
add = @(lib, nome, pos, varargin) add_block(lib, B(nome), 'Position', pos, varargin{:});
L = @(a, b) add_line(mdl, a, b, 'autorouting', 'smart');
add('simulink/Sources/Constant', ['Limiares ' s], [x0 y0+60 x0+60 y0+80], 'Value', thr);
add('simulink/Logic and Bit Operations/Relational Operator', [s ' > limiares'], [x0+90 y0 x0+120 y0+70], 'Operator', '>');
add('simulink/Signal Attributes/Data Type Conversion', ['bool2dbl ' s], [x0+150 y0+20 x0+190 y0+50], 'OutDataTypeStr', 'double');
add('simulink/Math Operations/Sum of Elements', ['Nivel decidido ' s], [x0+220 y0+20 x0+250 y0+50]);
add('simulink/Logic and Bit Operations/Relational Operator', ['Erro simbolo ' s], [x0+290 y0+20 x0+320 y0+70], 'Operator', '~=');
add('simulink/Signal Attributes/Data Type Conversion', ['dbl Ns ' s], [x0+350 y0+30 x0+390 y0+60], 'OutDataTypeStr', 'double');
add('simulink/Math Operations/Product', ['x payload Ns ' s], [x0+420 y0+30 x0+450 y0+70]);
add('simulink/Signal Attributes/Data Type Conversion', ['uint8 dec ' s], [x0+290 y0+100 x0+330 y0+130], 'OutDataTypeStr', 'uint8');
add('simulink/Signal Attributes/Data Type Conversion', ['uint8 TX ' s], [x0+290 y0+150 x0+330 y0+180], 'OutDataTypeStr', 'uint8');
add('simulink/Lookup Tables/Direct Lookup Table (n-D)', ['Erros de bit Gray ' s], [x0+360 y0+110 x0+420 y0+170], ...
    'NumberOfTableDimensions', '2', 'Table', 'tab_bits');
add('simulink/Signal Attributes/Data Type Conversion', ['dbl Ne ' s], [x0+440 y0+125 x0+480 y0+155], 'OutDataTypeStr', 'double');
add('simulink/Math Operations/Product', ['x payload Ne ' s], [x0+500 y0+120 x0+530 y0+160]);
L(origem, [s ' > limiares/1']);
L(['Limiares ' s '/1'], [s ' > limiares/2']);
L([s ' > limiares/1'], ['bool2dbl ' s '/1']);
L(['bool2dbl ' s '/1'], ['Nivel decidido ' s '/1']);
L(['Nivel decidido ' s '/1'], ['Erro simbolo ' s '/1']);
L(['Erro simbolo ' s '/1'], ['dbl Ns ' s '/1']);
L(['dbl Ns ' s '/1'], ['x payload Ns ' s '/1']);
L(['Nivel decidido ' s '/1'], ['uint8 dec ' s '/1']);
L(['uint8 dec ' s '/1'], ['Erros de bit Gray ' s '/1']);
L(['uint8 TX ' s '/1'], ['Erros de bit Gray ' s '/2']);
L(['Erros de bit Gray ' s '/1'], ['dbl Ne ' s '/1']);
L(['dbl Ne ' s '/1'], ['x payload Ne ' s '/1']);
acumulador(mdl, ['Ns ' s], ['x payload Ns ' s '/1'], x0+560, y0+20);
acumulador(mdl, ['Ne ' s], ['x payload Ne ' s '/1'], x0+560, y0+120);
end

function acumulador(mdl, nome, origem, x0, y0)
B = @(n) [mdl '/' n];
add_block('simulink/Math Operations/Sum', B(['Soma ' nome]), 'Position', [x0 y0 x0+20 y0+40], 'Inputs', '++');
add_block('simulink/Discrete/Unit Delay', B(['Atraso ' nome]), 'Position', [x0 y0+60 x0+40 y0+90], ...
    'Orientation', 'left', 'SampleTime', '-1');
add_block('simulink/Sinks/Display', B(nome), 'Position', [x0+60 y0+5 x0+140 y0+35]);
add_block('simulink/Sinks/To Workspace', B(['log ' nome]), 'Position', [x0+60 y0+45 x0+140 y0+65], ...
    'VariableName', strrep(nome, ' ', '_'), 'SaveFormat', 'Array');
add_line(mdl, origem, ['Soma ' nome '/1'], 'autorouting', 'smart');
add_line(mdl, ['Atraso ' nome '/1'], ['Soma ' nome '/2'], 'autorouting', 'smart');
add_line(mdl, ['Soma ' nome '/1'], ['Atraso ' nome '/1'], 'autorouting', 'smart');
add_line(mdl, ['Soma ' nome '/1'], [nome '/1'], 'autorouting', 'smart');
add_line(mdl, ['Soma ' nome '/1'], ['log ' nome '/1'], 'autorouting', 'smart');
end

function annotation_text(mdl, xy, txt)
a = Simulink.Annotation([mdl '/nota'], 'Position', [xy xy + [700 40]]);
a.Text = txt;
end
