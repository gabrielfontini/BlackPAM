function [a, Q, P, W] = pam_canal_sim(M, canal, sigma_lsb, nwave)
%PAM_CANAL_SIM  Simula TX -> canal RC -> ADC do RX e devolve as 8 amostras/símbolo.
%   [a, Q, P, W] = pam_canal_sim(M, canal, sigma_lsb, nwave)
%   M         : 2 ou 4
%   canal     : 'dupont' | 'rc' | 'rc33'
%   sigma_lsb : desvio-padrão do ruído no ADC em LSB (padrão: P.sigma_adc)
%   nwave     : nº de símbolos iniciais para a forma de onda contínua (W)
%   a : Nsym x 8 códigos ADC ; W.t, W.vin, W.tp3 : forma de onda (passo 0,1 us)
%
%   Solução EXATA do modelo de estado da escada RC entre instantes de amostra
%   (entrada constante por trechos): x(t+dt) = Ad x + Bd u.

P = pam_parametros(canal);
if nargin < 3 || isempty(sigma_lsb), sigma_lsb = P.sigma_adc; end
if nargin < 4, nwave = 0; end
Q = pam_quadro(M);
vin = Q.nivel * P.Vdd / (M - 1);          % PAM-2: 0/3,3 V ; PAM-4: 0/1,1/2,2/3,3 V
N = numel(vin);

A = P.A; B = P.B; C = P.C; n = size(A, 1);
disc = @(dt) deal(expm(A*dt), A \ (expm(A*dt) - eye(n)) * B);
[Ad1, Bd1] = disc(P.tlat);                % borda do CLK -> TX muda de nível
[Ad2, Bd2] = disc(P.t0 - P.tlat);         % -> amostra k = 0
[Ad3, Bd3] = disc(P.Tsa);                 % entre amostras
[Ad4, Bd4] = disc(P.Ts - P.tk(end));      % k = 7 -> próxima borda

x = zeros(n, 1);
v = zeros(N, 8);
uold = 0;
for j = 1:N
    u = vin(j);
    x = Ad1*x + Bd1*uold;
    x = Ad2*x + Bd2*u;   v(j,1) = C*x;
    for k = 2:8
        x = Ad3*x + Bd3*u; v(j,k) = C*x;
    end
    x = Ad4*x + Bd4*u;
    uold = u;
end
rng(1);
a = round(v / P.Vdd * P.adc_max + sigma_lsb*randn(size(v)));
a = min(max(a, 0), P.adc_max);

W = struct();
if nwave > 0
    dt = 0.1e-6;
    t = (0:round(nwave*P.Ts/dt)-1).' * dt;
    js = floor((t - P.tlat) / P.Ts) + 1;  % símbolo vigente (com o atraso do TX)
    js(js < 1) = 1;
    uin = vin(js).';
    uin(t < P.tlat) = 0;
    sys = ss(A, B, C, 0);
    W.t = t; W.vin = uin; W.tp3 = lsim(sys, uin, t);
    W.nivel = Q.nivel(1:nwave);
end
end
