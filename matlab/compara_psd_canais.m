function compara_psd_canais(arq_dupont, arq_rc, Vref, tau_med_us)
%COMPARA_PSD_CANAIS  Questão 1 da defesa: PSD perto de 5 e 10 kHz nos dois canais.
%   compara_psd_canais('logs/PAM2_Dupont.txt', 'logs/PAM2_RC.txt', 3.297, 7.1)
%   tau_med_us : τ medido no degrau (osciloscópio) — usado para prever |H|^2
%
%   As 8 192 amostras começam no MESMO símbolo do payload (nº 1000) nos dois
%   ensaios, logo os bits transmitidos são idênticos. A razão S_RC/S_Dupont
%   cancela a flutuação estatística da estimativa e fica ≈ |H_RC(f)|^2.

if nargin < 4, tau_med_us = NaN; end
A = le_log_rx(arq_dupont); B = le_log_rx(arq_rc);
[Sa, f, info] = pam_psd(reshape(A.psd(:, 3:10).', [], 1), Vref, 160e3);
Sb = pam_psd(reshape(B.psd(:, 3:10).', [], 1), Vref, 160e3);
P = pam_parametros('rc');
Hnom = @(ff) abs(1 ./ polyval(P.den, 1j*2*pi*ff)).^2;
Hmed = @(ff) 1 ./ (1 + (2*pi*ff*tau_med_us*1e-6).^2);
Hnom1 = @(ff) 1 ./ (1 + (2*pi*ff*6.48e-6).^2);

fprintf('\nPSD: fa = 160 kHz, Hann, N = 1024 (%.2f Hz/bin), 50%%, %d blocos, %.1f ms de registro\n', ...
    info.df, info.nblocos, info.duracao_s*1e3);
fprintf(' f (kHz) | S_Dupont (V^2/Hz) | S_RC (V^2/Hz) | razão RC/Dup | dB    | |H|^2 τ=6,48us | |H|^2 2 polos | |H|^2 τ medido\n');
for fx = [5e3 10e3]
    ia = abs(f - fx) <= 2*info.df;
    sa = mean(Sa(ia)); sb = mean(Sb(ia));
    fprintf('  %5.1f  |    %.3e      |   %.3e   |    %.3f     | %5.2f |     %.3f      |    %.3f      |    %.3f\n', ...
        fx/1e3, sa, sb, sb/sa, 10*log10(sb/sa), Hnom1(fx), Hnom(fx)/abs(1/polyval(pam_parametros('dupont').den, 1j*2*pi*fx))^2, Hmed(fx));
end
fprintf('(valores = média de 5 bins em torno da frequência)\n');

fig = figure('Position', [100 100 1000 420]);
try, theme(fig, 'light'); catch, end
tl = tiledlayout(fig, 1, 2);
ax = nexttile(tl);
plot(ax, f/1e3, 10*log10(Sa), f/1e3, 10*log10(Sb)); grid(ax, 'on'); xlim(ax, [0 80]);
xline(ax, [5 10], 'k:'); legend(ax, 'Dupont', 'RC'); xlabel(ax, 'f (kHz)'); ylabel(ax, 'dB V^2/Hz');
title(ax, sprintf('PSD PAM-%d (mesma escala)', A.M));
ax = nexttile(tl);
plot(ax, f/1e3, 10*log10(Sb./Sa), 'b'); hold(ax, 'on');
plot(ax, f/1e3, 10*log10(Hnom1(f)), 'k--', f/1e3, 10*log10(Hmed(f)), 'r--');
grid(ax, 'on'); xlim(ax, [0 40]); ylim(ax, [-15 3]); xline(ax, [5 10], 'k:');
legend(ax, 'S_{RC}/S_{Dupont} medido', '|H|^2, \tau = 6,48 \mus', sprintf('|H|^2, \\tau medido = %.2f \\mus', tau_med_us), 'Location', 'southwest');
xlabel(ax, 'f (kHz)'); ylabel(ax, 'dB'); title(ax, 'Razão das PSDs = |H_{RC}(f)|^2');
od = fullfile(fileparts(mfilename('fullpath')), 'resultados');
if ~exist(od, 'dir'), mkdir(od); end
exportgraphics(fig, fullfile(od, sprintf('psd_comparacao_PAM%d.png', A.M)), 'Resolution', 120);
end
