function pam_olho(ax, a, nivel, R, Vref, titulo, W)
%PAM_OLHO  Diagrama de olho a partir das 8 amostras/símbolo do RX (+ opcional
%   a forma de onda contínua W da simulação), com a linha vertical em t_k*.
%   pam_olho(ax, a, nivel, R, Vref, titulo, W)
%   a     : Nsym x 8 códigos ADC (símbolos consecutivos)
%   nivel : nível transmitido de cada símbolo (para colorir)
%   R     : saída de pam_detectores (usa R.kstar, R.marg_u)

if nargin < 7, W = []; end
tk = 3.12 + 6.25*(0:7);                 % us
cores = lines(4);
hold(ax, 'on');
if ~isempty(W) && isfield(W, 't')
    % olho "de osciloscópio": trechos de 2 símbolos alinhados pela borda do CLK
    Ts = 50e-6; dt = W.t(2) - W.t(1);
    npts = round(2*Ts/dt);
    i0 = round(10*Ts/dt) + 1;           % pula o começo
    for s = i0:round(Ts/dt):numel(W.t) - npts
        plot(ax, (0:npts-1)*dt*1e6, W.tp3(s:s+npts-1), 'Color', [0.6 0.6 0.6 0.25]);
    end
end
% amostras do ADC (2 símbolos por traço: j e j+1)
v = double(a) * Vref / 4095;
for j = 1:size(v,1)-1
    l = nivel(j) + 1;
    plot(ax, [tk, tk+50], [v(j,:), v(j+1,:)], '.', 'Color', cores(l,:), 'MarkerSize', 6);
end
xline(ax, tk(R.kstar+1), 'r-', sprintf('k* = %d (%.2f \\mus)', R.kstar, tk(R.kstar+1)), 'LineWidth', 1.5, ...
    'LabelVerticalAlignment', 'bottom', 'LabelHorizontalAlignment', 'left');
xline(ax, tk(R.kstar+1)+50, 'r-');
xline(ax, 50, 'k:', 'borda CLK', 'LabelVerticalAlignment', 'top');
xlabel(ax, 'tempo após a borda do CLK (\mus)'); ylabel(ax, 'tensão em TP4/ADC (V)');
title(ax, titulo, 'Interpreter', 'none');
xlim(ax, [0 100]); ylim(ax, [-0.1 Vref+0.1]); grid(ax, 'on');
end
