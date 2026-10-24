function P = pam_parametros(canal)
%PAM_PARAMETROS  Parâmetros do projeto PAM em banda base (enunciado 2026S2).
%   P = pam_parametros('dupont' | 'rc' | 'rc33')
%   Todos os valores nominais vêm do enunciado; Rgpio é uma ESTIMATIVA da
%   resistência de saída do pino PA8 (datasheet: VOH >= VDD-0,4 V a 8 mA,
%   ou seja, R <= 50 Ω). Troque pelos valores medidos na sua bancada.

if nargin < 1, canal = 'rc'; end

% ---------- taxas ----------
P.Rs   = 20e3;            % símbolos/s
P.Ts   = 1/P.Rs;          % 50 us
P.sps  = 8;               % amostras por símbolo no RX
P.fa   = P.Rs*P.sps;      % 160 kHz
P.Tsa  = 1/P.fa;          % 6,25 us
P.t0   = 312/100e6;       % 1a amostra: CCR2 = 312 -> 3,12 us
P.tk   = P.t0 + (0:7)*P.Tsa;   % instantes nominais das 8 amostras
P.tlat = 0.25e-6;         % atraso da ISR do TX entre a borda do CLK e o novo nível

% ---------- níveis ----------
P.Vdd  = 3.3;             % alimentação / Vref do ADC (MEÇA com multímetro!)
P.nbits_adc = 12;
P.adc_max = 4095;
P.sigma_adc = 1.5;        % ruído do ADC em LSB (estimativa)

% ---------- circuito (Figura 3) ----------
P.Rgpio = 30;             % Ω  (estimativa, ver acima)
P.R1    = 330;            % Ω  filtro PWM do TX
P.C1    = 390e-12;        % F
P.Rprot = 1e3;            % Ω  proteção do ADC (não entra no polo: ADC tem alta impedância)
P.fpwm  = 100e6/3;        % 33,333 MHz
switch lower(canal)
    case {'dupont','direto','1'}
        P.R2 = 0;  P.C2 = 0;        P.nome = 'Dupont direto';
    case {'rc','2','rc16'}
        P.R2 = 56; P.C2 = 16.8e-9;  P.nome = 'Dupont + RC (56 Ω, 16,8 nF)';
    case {'rc33','33'}
        P.R2 = 56; P.C2 = 33e-9;    P.nome = 'Dupont + RC (56 Ω, 33 nF)';
    otherwise
        error('canal desconhecido: %s', canal);
end
P.canal = lower(canal);

% ---------- modelo LIT do canal: escada RC de 2 polos ----------
%   Vin -[Rg+R1]- v1 (C1 p/ GND) -[R2]- v2 = TP3 (C2 p/ GND)
Ra = P.Rgpio + P.R1;
if P.C2 == 0
    % canal 1: só o filtro do TX (1 polo)
    P.A = -1/(Ra*P.C1);  P.B = 1/(Ra*P.C1);  P.C = 1;  P.D = 0;
    P.num = 1; P.den = [Ra*P.C1 1];
else
    C1 = P.C1; C2 = P.C2; R2 = P.R2;
    P.A = [-(1/(Ra*C1) + 1/(R2*C1)),  1/(R2*C1);
             1/(R2*C2),             -1/(R2*C2)];
    P.B = [1/(Ra*C1); 0];
    P.C = [0 1];  P.D = 0;     % saída = TP3
    P.num = 1;
    P.den = [Ra*C1*R2*C2, Ra*C1 + R2*C2 + Ra*C2, 1];
end
p = roots(P.den);
P.tau_dom = max(-1./real(p));             % constante de tempo dominante
P.tau_nominal = (P.R1 + P.R2)*P.C2;       % conta do enunciado: (330+56)*C2
if P.C2 == 0, P.tau_nominal = P.R1*P.C1; end
P.fc_nominal = 1/(2*pi*P.tau_nominal);
end
