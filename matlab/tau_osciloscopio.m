function [tau, tr] = tau_osciloscopio(csv, t0_manual)
%TAU_OSCILOSCOPIO  τ e tempo de subida a partir de um CSV do TDS2002B (ou outro).
%   [tau, tr] = tau_osciloscopio('F0001CH2.CSV')
%   [tau, tr] = tau_osciloscopio('F0001CH2.CSV', t0)   % t0 em s (início da subida)
%
%   Procedimento do enunciado (págs. 10–11):
%     V0  = tensão antes da subida; Vf = tensão depois de estabilizar
%     t0  = início da subida (NÃO é o ponto de 10 %)
%     t63 = instante em que v = V0 + 0,632 (Vf - V0)  ->  τ = t63 - t0
%     tr  = t90 - t10  (≈ 2,197 τ para RC ideal)
%
%   Formato do TDS2002B: cada linha "rótulo,valor,,tempo,tensão" -> colunas 4 e 5.
%   Se o CSV tiver só 2 colunas numéricas (tempo,tensão) também funciona.

M = readmatrix(csv);
if size(M, 2) >= 5 && all(~isnan(M(10:end, 4)))
    t = M(:, 4); v = M(:, 5);
else
    M = M(:, ~all(isnan(M), 1));
    t = M(:, 1); v = M(:, 2);
end
ok = ~isnan(t) & ~isnan(v); t = t(ok); v = v(ok);
v = movmean(v, 5);                                % suaviza ruído de 8 bits

n = numel(v);
V0 = median(v(1:round(0.1*n)));                   % 10 % iniciais da tela
Vf = median(v(round(0.85*n):end));                % 15 % finais da tela
dV = Vf - V0;
cruza = @(p) t(find(v >= V0 + p*dV, 1));
if nargin < 2 || isempty(t0_manual)
    % início da subida: primeiro ponto acima de V0 + 2 % (ajuste se o ruído for grande)
    t0 = cruza(0.02);
else
    t0 = t0_manual;
end
t10 = cruza(0.10); t63 = cruza(0.632); t90 = cruza(0.90);
tau = t63 - t0; tr = t90 - t10;

fprintf('V0 = %.3f V, Vf = %.3f V, ΔV = %.3f V, V63 = %.3f V\n', V0, Vf, dV, V0 + 0.632*dV);
fprintf('t0 = %.2f us, t10 = %.2f us, t63 = %.2f us, t90 = %.2f us\n', 1e6*[t0 t10 t63 t90]);
fprintf('τ (63,2 %%) = %.2f us ; t10-90 = %.2f us ; t10-90/2,197 = %.2f us\n', tau*1e6, tr*1e6, tr/2.197*1e6);

fig = figure; try, theme(fig, 'light'); catch, end
plot(t*1e6, v, 'b'); hold on; grid on;
yline([V0, V0 + 0.1*dV, V0 + 0.632*dV, V0 + 0.9*dV, Vf], ':');
xline(1e6*[t0 t10 t63 t90], 'r:', {'t_0', 't_{10}', 't_{63}', 't_{90}'});
xlabel('t (\mus)'); ylabel('V'); title(sprintf('\\tau = %.2f \\mus, t_{10-90} = %.2f \\mus', tau*1e6, tr*1e6));
end
