%CALIBRA_SIMULINK  "Treinamento" a partir da rodada do modelo pam_enlace_simulink.
%   Usa adc_log (8 amostras/símbolo gravadas pelo To Workspace) e aplica
%   EXATAMENTE o algoritmo do firmware (pam_detectores.m):
%     b_c, p_c[k], E_c  <- 140 símbolos de pulso
%     k*, centros, limiares, margens  <- 256 símbolos de níveis
%   Depois rode sim('pam_enlace_simulink') de novo para medir a BER.

if ~exist('out', 'var') && ~exist('adc_log', 'var')
    error('Rode antes: out = sim(''pam_enlace_simulink'');');
end
if exist('out', 'var') && isa(out, 'Simulink.SimulationOutput')
    adc_v = out.adc_log(:);
else
    adc_v = adc_log(:);
end
n = floor(numel(adc_v) / 8) * 8;
a_v = reshape(adc_v(1:n), 8, []).';              % 1 linha por símbolo
a = round(a_v / Vref * 4095);                    % códigos ADC, como no firmware
R = pam_detectores(a(1:396, :), Q);

cal.M = M; cal.canal = canal; cal.origem = 'treinamento simulado (calibra_simulink)';
cal.bc = R.bc * Vref / 4095;
cal.pc = R.pc * Vref / 4095;
cal.kstar = R.kstar;
cal.thr_u = R.thr_u * Vref / 4095;
cal.thr_z = R.thr_z;
fprintf('\n== Treinamento a partir do Simulink (PAM-%d, %s) ==\n', M, canal);
fprintf('b_c = %.4f V | p_c = %s V\n', cal.bc, mat2str(cal.pc, 4));
fprintf('separação por k (mV) = %s -> k* = %d (t = %.2f us)\n', ...
    mat2str(round(R.sep_k*Vref/4095*1e3, 1)), R.kstar, (t0 + R.kstar*Tsa)*1e6);
fprintf('centros u = %s V | limiares u = %s V\n', mat2str(R.cen_u*Vref/4095, 4), mat2str(cal.thr_u, 4));
fprintf('centros z = %s | limiares z = %s\n', mat2str(R.cen_z, 4), mat2str(cal.thr_z, 4));
fprintf('margem u = %.1f mV | margem z = %.4f\n', R.marg_u*Vref/4095*1e3, R.marg_z);
pam_simulink_init;      % recarrega as variáveis com a calibração nova
fprintf('Agora rode de novo: out = sim(''pam_enlace_simulink'');\n');
