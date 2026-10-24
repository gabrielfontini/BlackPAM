function [S, f, info] = pam_psd(codigos, Vref, fa)
%PAM_PSD  PSD unilateral pelo método EXATO do enunciado (passo 6 da sequência).
%   [S, f] = pam_psd(codigos, Vref, fa)
%   codigos : 8 192 códigos ADC consecutivos (0..4095)
%   Vref    : referência MEDIDA do ADC em volts (ex.: 3.297)
%   fa      : 160 000 Hz
%   S       : V^2/Hz, f : Hz (0 .. fa/2, resolução fa/1024 = 156,25 Hz)
%
%   Passos: códigos -> volts; retira a média; blocos de 1024 com 50 % de
%   sobreposição; janela de Hann; S = 2|FFT(w x)|^2 / (fa * sum(w^2)) nos bins
%   internos (sem dobrar DC e Nyquist); média das PSDs dos blocos.

if nargin < 2 || isempty(Vref), Vref = 3.3; end
if nargin < 3 || isempty(fa), fa = 160e3; end
N = 1024; hop = N/2;
x = double(codigos(:)) * Vref / 4095;   % volts
x = x - mean(x);
w = 0.5 - 0.5*cos(2*pi*(0:N-1).'/N);     % Hann periódica (= hann(N,'periodic'))
U = sum(w.^2);
nb = floor((numel(x) - N)/hop) + 1;      % 15 blocos para 8 192 amostras
P = zeros(N/2 + 1, 1);
for b = 0:nb-1
    seg = x(b*hop + (1:N)) .* w;
    X = fft(seg);
    Pb = abs(X(1:N/2+1)).^2 / (fa*U);    % bilateral
    Pb(2:end-1) = 2*Pb(2:end-1);         % unilateral: dobra só os bins internos
    P = P + Pb;
end
S = P / nb;
f = (0:N/2).' * fa / N;
info.nblocos = nb; info.df = fa/N; info.duracao_s = numel(x)/fa;
info.Pmedia_V2 = sum(S) * fa/N;          % potência AC (≈ variância de x)
info.var_x = var(x, 1);
end
