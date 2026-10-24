%PAM_SIMULINK_INIT  Variáveis dos dois modelos Simulink. Rode ANTES de simular.
%
%   Escolha (antes de rodar este script, no Command Window):
%     M = 4;              % 2 ou 4
%     canal = 'rc';       % 'dupont' | 'rc' (16,8 nF) | 'rc33' (33 nF)
%     sigma_ruido = 0.002;% ruído RMS no ADC, em volts
%     N_payload_sim = 2000;  % símbolos de payload simulados (o real tem 100000/50000)
%   e depois:  pam_simulink_init
%
%   Fluxo igual ao da bancada:
%     1) pam_simulink_init  -> sim('pam_enlace_simulink')   (rodada de TREINAMENTO)
%     2) calibra_simulink   -> calcula b_c, p_c, k*, centros e limiares
%     3) sim('pam_enlace_simulink') de novo                 (rodada de MEDIÇÃO/BER)

addpath(fullfile(fileparts(mfilename('fullpath')), '..', 'matlab'));

if ~exist('M', 'var'), M = 4; end
if ~exist('canal', 'var'), canal = 'rc'; end
if ~exist('sigma_ruido', 'var'), sigma_ruido = 0.002; end
if ~exist('N_payload_sim', 'var'), N_payload_sim = 2000; end
if ~exist('usar_pwm', 'var'), usar_pwm = 1; end          % só no modelo Simscape: 1 = PWM 33 MHz real, 0 = nível médio
if usar_pwm, max_step_circ = 2.5e-9; else, max_step_circ = 0.2e-6; end

P = pam_parametros(canal);
Ts   = P.Ts;            % 50 us
Tsa  = P.Tsa;           % 6,25 us
t0   = 3.125e-6;        % 1a amostra (no firmware 3,12 us; 3,125 deixa os tempos múltiplos de 0,125 us)
Vmax = 3.3;             % nível alto do TX
Vref = 3.3;             % referência do ADC
q_adc = Vref/4095;      % 1 LSB (mesma escala do enunciado: V = código*Vref/4095)

% ---------- canal (modelo A): escada RC de 2 polos ----------
num_canal = P.num;
den_canal = P.den;
fprintf('Canal: %s | tau dominante = %.2f us | den = %s\n', P.nome, P.tau_dom*1e6, mat2str(den_canal, 4));

% ---------- circuito (modelo B, Simscape) ----------
Rgpio = P.Rgpio; R1 = P.R1; C1 = P.C1; Rprot = P.Rprot; C_adc = 4e-12;
if P.C2 == 0, R2 = 0.1; C2 = 20e-12; else, R2 = P.R2; C2 = P.C2; end  % Dupont: só parasitas do fio (≈0,1 Ω, ≈20 pF)
Vf_schottky = 0.3; Ron_schottky = 0.5;

% ---------- fonte: o MESMO quadro do firmware ----------
Q = pam_quadro(M);
Nsim = 396 + numel(Q.ipre) + N_payload_sim;
Nsim = min(Nsim, numel(Q.nivel));
tt = (0:Nsim-1).' * Ts;
fonte_nivel   = [tt, Q.nivel(1:Nsim).'];
fonte_payload = [tt, double(Q.seg(1:Nsim).' == 4)];
T_sim = Nsim * Ts;
fprintf('PAM-%d: %d símbolos (%d de payload) -> T_sim = %.1f ms\n', M, Nsim, Nsim - 396 - numel(Q.ipre), T_sim*1e3);

% sequência curta para o modelo Simscape: pulso + 8 níveis da calibração
seq = [0 0 0 M-1 0 0 0, Q.nivel(141:148)];
if M == 2, ccr = 3*seq; else, ccr = seq; end              % TIM1_CCR1 (Apêndice A)
fonte_ccr = [(0:numel(ccr)-1).' * Ts, ccr.'];
T_sim_circ = numel(ccr) * Ts;

% ---------- calibração dos detectores ----------
% Sem treinamento: pulso ideal (retangular) e limiares nominais.
% Depois de uma rodada, calibra_simulink substitui por valores "medidos".
if ~exist('cal', 'var') || cal.M ~= M || ~strcmp(cal.canal, canal)
    cal.M = M; cal.canal = canal; cal.origem = 'nominal (sem treinamento)';
    cal.bc = 0;
    cal.pc = Vmax * ones(1, 8);
    cal.kstar = 7;
    cal.thr_u = ((1:M-1) - 0.5) * Vmax / (M-1);
    cal.thr_z = ((1:M-1) - 0.5) / (M-1);
end
bc = cal.bc;
pc = cal.pc;
Ec = sum(pc.^2);
hc = fliplr(pc) / Ec;              % FIR: h_c[k] = p_c[7-k] / E_c
kstar = cal.kstar;
t_kstar = t0 + kstar*Tsa;          % offset do amostrador da "amostra única"
t_fim = t0 + 7*Tsa;                % fim da janela (saída do filtro casado)
thr_u = [cal.thr_u, inf(1, 3 - numel(cal.thr_u))];
thr_z = [cal.thr_z, inf(1, 3 - numel(cal.thr_z))];

% erros de bit entre nível decidido (linha) e transmitido (coluna) — Gray
if M == 2
    tab_bits = [0 1; 1 0];
else
    g = [0 1 3 2];                 % nível -> código Gray (00,01,11,10)
    tab_bits = zeros(4);
    for i = 1:4, for j = 1:4, tab_bits(i,j) = sum(bitget(bitxor(g(i), g(j)), 1:2)); end, end
end
fprintf('Calibração em uso: %s | k* = %d | limiares u = %s V | limiares z = %s\n', ...
    cal.origem, kstar, mat2str(cal.thr_u, 3), mat2str(cal.thr_z, 3));
