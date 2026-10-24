%OLHO_SIMULINK  Olho, resposta ao degrau e PSD a partir de uma rodada do modelo A.
%   Rode depois de: out = sim('pam_enlace_simulink');

tp3 = out.tp3_log(:);  adc_v = out.adc_log(:);
dt = 0.5e-6;                                   % passo do To Workspace de TP3
fig = figure('Position', [80 80 1200 420]); try, theme(fig, 'light'); catch, end
tl = tiledlayout(fig, 1, 3);
title(tl, sprintf('Simulink — PAM-%d — %s — calibração: %s', M, canal, cal.origem), 'Interpreter', 'none');

% 1) olho "de osciloscópio": trechos de 2 Ts alinhados pela borda do CLK
ax = nexttile(tl); hold(ax, 'on');
npts = round(2*Ts/dt); ini = round(400*Ts/dt);   % pula o treinamento
for s = ini:round(Ts/dt):numel(tp3) - npts
    plot(ax, (0:npts-1)*dt*1e6, tp3(s+1:s+npts), 'Color', [0 0.3 0.8 0.15]);
end
xline(ax, (t_kstar)*1e6, 'r-', 'k*'); xline(ax, (t_kstar + Ts)*1e6, 'r-');
xlabel(ax, 't após a borda do CLK (\mus)'); ylabel(ax, 'TP3 (V)'); title(ax, 'Olho em TP3'); grid(ax, 'on');

% 2) amostras do ADC sobrepostas (o "olho" do RX)
ax = nexttile(tl); hold(ax, 'on');
n = floor(numel(adc_v)/8)*8; A8 = reshape(adc_v(1:n), 8, []).';
tk = (t0 + (0:7)*Tsa)*1e6;
plot(ax, tk, A8(400:end, :).', '.', 'Color', [0.85 0.3 0.1]);
xline(ax, t_kstar*1e6, 'r-', sprintf('k* = %d', kstar));
xlabel(ax, 't_k (\mus)'); ylabel(ax, 'ADC (V)'); title(ax, '8 amostras/símbolo'); grid(ax, 'on');

% 3) PSD pelo método do enunciado (até 8192 amostras do payload)
ax = nexttile(tl);
ip = (396 + numel(Q.ipre))*8 + 1;
x = adc_v(ip:min(end, ip + 8191));
if numel(x) >= 2048
    [S, f] = pam_psd(round(x/Vref*4095), Vref, 160e3);
    plot(ax, f/1e3, 10*log10(S), 'b', f/1e3, 10*log10(pam_psd_teorica(f, M, canal)), 'k--');
    xline(ax, [5 10], 'r:'); legend(ax, 'Simulink', 'teoria');
    xlabel(ax, 'f (kHz)'); ylabel(ax, 'dB V^2/Hz'); xlim(ax, [0 80]); grid(ax, 'on');
    title(ax, sprintf('PSD (%d amostras)', numel(x)));
end
