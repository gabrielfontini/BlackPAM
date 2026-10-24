function T = analisa_ensaio(arquivo, Vref, salvar)
%ANALISA_ENSAIO  Análise completa de UM log do RX (uma condição canal+modulação).
%   T = analisa_ensaio('logs/PAM4_RC.txt', 3.297)
%   Vref   : tensão de referência do ADC MEDIDA no 3V3 do RX (multímetro)
%   salvar : true (padrão) grava as figuras em ./resultados/
%
%   Faz, a partir dos dados BRUTOS do log:
%     1) confere o treinamento (recalcula b_c, p_c, k*, centros, limiares,
%        margens com pam_detectores e compara com o firmware);
%     2) desenha resposta ao pulso p_c[k] e a ISI no 1º zero depois de A;
%     3) olho com as amostras do payload e linha em t_k*; abertura em volts;
%     4) PSD pelo método do enunciado + curva teórica; valores em 5 e 10 kHz;
%     5) histogramas de u e z na calibração (centros, limiares, margens);
%     6) resume BER/SER dos dois detectores (contadores do firmware).

if nargin < 2 || isempty(Vref), Vref = 3.3; warning('Use o Vref MEDIDO!'); end
if nargin < 3, salvar = true; end
D = le_log_rx(arquivo);
M = D.M; r = D.rep;
Q = pam_quadro(M);
[~, base] = fileparts(arquivo);
tk = 3.12 + 6.25*(0:7);
mV = @(c) c * Vref / 4095 * 1e3;

fprintf('\n================ %s ================\n', base);
fprintf('Modulação PAM-%d | canal: %s | aquisição válida = %d | sincronismo = %d\n', ...
    M, r.canal, r.aquisicao_valida, r.sincronismo_ok);
fprintf('Bordas de CLK = %d de %d ; amostras = %d (= 8 x %d) ; descartadas antes do CLK = %d\n', ...
    r.bordas_CLK, r.simbolos_esperados, r.amostras_processadas, r.simbolos_processados, ...
    r.amostras_descartadas_antes_CLK);

% ---------- 1) treinamento recalculado ----------
a = D.train(:, 3:10);
if any(D.train(:, 2).' ~= Q.nivel(1:396))
    warning('Níveis do treinamento no log não batem com o quadro esperado!');
end
R = pam_detectores(a, Q);
fprintf('\n-- Filtro casado (Seção 4.5.1) --\n');
fprintf('b_c = %.2f códigos (%.1f mV)\n', R.bc, mV(R.bc));
fprintf('p_c[k] = %s códigos\n', mat2str(round(R.pc, 1)));
fprintf('E_c = %.4g\n', R.Ec);
fprintf('ISI no 1º zero depois de A = %s códigos\n', mat2str(round(R.isi_zero_apos_A, 1)));
fprintf('conferência com o firmware: max|Δp_c| = %.3g, k* firmware = %d, k* MATLAB = %d\n', ...
    max(abs(R.pc - r.p_c)), r.k_estrela, R.kstar);

fprintf('\n-- Escolha de k* (Seção 4.3) --\n');
for k = 0:7
    fprintf('  k=%d  t=%5.2f us  menor separação = %5d códigos (%7.1f mV)%s\n', k, tk(k+1), ...
        R.sep_k(k+1), mV(R.sep_k(k+1)), repmat('  <== k*', 1, k == R.kstar));
end

fprintf('\n-- Centros, limiares, margens (Seção 4.5.2) --\n');
fprintf('centros u (códigos) = %s ; em V = %s\n', mat2str(round(R.cen_u, 1)), mat2str(round(R.cen_u*Vref/4095, 3)));
fprintf('limiares u (códigos) = %s ; em V = %s\n', mat2str(round(R.thr_u, 1)), mat2str(round(R.thr_u*Vref/4095, 3)));
fprintf('centros z = %s ; limiares z = %s\n', mat2str(round(R.cen_z, 4)), mat2str(round(R.thr_z, 4)));
gray = {'00', '01', '11', '10'};
fprintf('margem amostra única = %d códigos = %.1f mV (par de níveis %d-%d', R.marg_u, mV(R.marg_u), R.marg_u_par);
if M == 4, fprintf(', Gray %s/%s', gray{R.marg_u_par+1}); end
fprintf(')\nmargem filtro casado = %.4f (escala z; par %d-%d)\n', R.marg_z, R.marg_z_par);
fprintf('margem relativa (margem / distância entre centros vizinhos): u = %.2f , z = %.2f\n', ...
    R.marg_u / mean(diff(R.cen_u)), R.marg_z / mean(diff(R.cen_z)));

% ---------- 3) olho do payload ----------
ap = D.psd(:, 3:10); lp = D.psd(:, 2).';
ab = zeros(1, 8);
for k = 1:8
    s = inf;
    for l = 0:M-2
        s = min(s, min(ap(lp == l+1, k)) - max(ap(lp == l, k)));
    end
    ab(k) = s;
end
abertura_V = ab(R.kstar+1) * Vref / 4095;
fprintf('\n-- Olho (1024 símbolos do payload) --\n');
fprintf('abertura vertical em t_k* = %.2f us: %.3f V (menor entre níveis vizinhos)\n', tk(R.kstar+1), abertura_V);
fprintf('abertura por k (V) = %s\n', mat2str(round(ab*Vref/4095, 3)));

% ---------- 4) PSD ----------
cod = reshape(ap.', [], 1);
[S, f, info] = pam_psd(cod, Vref, 160e3);
canal_teo = canal_do_rotulo(r.canal);
Sth = pam_psd_teorica(f, M, canal_teo, Vref);
S5 = interp1(f, S, 5e3); S10 = interp1(f, S, 10e3);
S5m = mean(S(abs(f-5e3) <= 2*info.df)); S10m = mean(S(abs(f-10e3) <= 2*info.df));
fprintf('\n-- PSD (fa = 160 kHz, Vref = %.4f V, média retirada, Hann, N = 1024, 50%%, %d blocos) --\n', Vref, info.nblocos);
fprintf('resolução = %.2f Hz ; duração do registro = %.1f ms ; potência AC = %.4f V^2 (var = %.4f)\n', ...
    info.df, info.duracao_s*1e3, info.Pmedia_V2, info.var_x);
fprintf('S(5 kHz)  = %.3e V^2/Hz (média de 5 bins %.3e; teoria %.3e)\n', S5, S5m, interp1(f, Sth, 5e3));
fprintf('S(10 kHz) = %.3e V^2/Hz (média de 5 bins %.3e; teoria %.3e)\n', S10, S10m, interp1(f, Sth, 10e3));

% ---------- 6) BER ----------
fprintf('\n-- Contagem de erros (firmware, mesmas amostras do payload) --\n');
if isfield(r, 'amostra_unica_Ne')
    fprintf('amostra única: Ne = %d em %d bits -> BER = %.2e ; Ns = %d em %d -> SER = %.2e\n', ...
        r.amostra_unica_Ne, r.payload_bits, r.amostra_unica_Ne/r.payload_bits, ...
        r.amostra_unica_Ns, r.payload_simbolos, r.amostra_unica_Ns/r.payload_simbolos);
    fprintf('filtro casado: Ne = %d em %d bits -> BER = %.2e ; Ns = %d em %d -> SER = %.2e\n', ...
        r.filtro_casado_Ne, r.payload_bits, r.filtro_casado_Ne/r.payload_bits, ...
        r.filtro_casado_Ns, r.payload_simbolos, r.filtro_casado_Ns/r.payload_simbolos);
    if r.amostra_unica_Ne == 0
        fprintf('  -> escrever "0 erros em 100.000 bits" (BER observada = 0, NÃO prova BER física nula;\n');
        fprintf('     com 0 erros, limite superior de 95%% ~ 3/100000 = 3e-5).\n');
    end
else
    fprintf('SEM BER: quadro inválido ou sem sincronismo -> repetir o ensaio.\n');
end

% ---------- janela real para a defesa ----------
if isfield(r, 'janela_a')
    x = r.janela_a - R.bc;
    fprintf('\n-- Janela real (símbolo j = %d, nível TX = %d) --\n', r.janela_exemplo_j, r.janela_exemplo_nivel_TX);
    fprintf('  k   a[k]    x[k]=a-b_c    p_c[k]     p_c*x\n');
    for k = 1:8
        fprintf('  %d  %5d  %10.2f  %10.2f  %12.1f\n', k-1, r.janela_a(k), x(k), R.pc(k), R.pc(k)*x(k));
    end
    fprintf('  soma = %.1f ; E_c = %.1f ; z = soma/E_c = %.5f (firmware: %.5f)\n', ...
        sum(R.pc.*x), R.Ec, sum(R.pc.*x)/R.Ec, r.janela_z);
end

% ---------- figuras ----------
fig = figure('Position', [50 50 1300 850], 'Visible', ternario(salvar, 'off', 'on'));
tema_claro(fig);
tl = tiledlayout(fig, 2, 2, 'TileSpacing', 'compact');
title(tl, sprintf('%s — PAM-%d — %s', base, M, r.canal), 'Interpreter', 'none');

ax = nexttile(tl);
stem(ax, tk, R.pc*Vref/4095, 'filled'); hold(ax, 'on');
stem(ax, tk + 50, R.isi_zero_apos_A*Vref/4095, 'r');
xline(ax, 50, 'k:'); grid(ax, 'on');
xlabel(ax, 'tempo após a borda do CLK (\mus)'); ylabel(ax, 'V acima da linha de base');
legend(ax, 'p_c[k] (símbolo A)', '1º zero depois de A (ISI)'); title(ax, 'Pulso medido e ISI');

ax = nexttile(tl);
pam_olho(ax, ap, lp, R, Vref, sprintf('Olho: abertura em t_{k*} = %.3f V', abertura_V));

ax = nexttile(tl); hold(ax, 'on');
il = Q.itrain_niveis; lv = Q.nivel(il);
cores = lines(4);
for l = 0:M-1
    jj = il(lv == l);
    plot(ax, jj, R.u(jj)*Vref/4095, '.', 'Color', cores(l+1,:), 'MarkerSize', 8, 'DisplayName', sprintf('nível %d', l));
end
yline(ax, R.thr_u*Vref/4095, 'k--', 'LineWidth', 1.2, 'HandleVisibility', 'off');
xlabel(ax, 'símbolo j da calibração (141..396)'); ylabel(ax, sprintf('u = a[k*=%d] (V)', R.kstar));
legend(ax, 'Location', 'eastoutside');
title(ax, sprintf('Amostra única na calibração: margem %.1f mV (tracejado = limiares)', mV(R.marg_u))); grid(ax, 'on');

ax = nexttile(tl);
plot(ax, f/1e3, 10*log10(S), 'b', f/1e3, 10*log10(Sth), 'k--'); grid(ax, 'on');
xline(ax, [5 10], 'r:'); xlim(ax, [0 80]); ylim(ax, [-110 -30]);
xlabel(ax, 'f (Hz \times 10^3)'); ylabel(ax, 'S(f) (dB re 1 V^2/Hz)');
legend(ax, 'medida', sprintf('teoria (%s)', canal_teo), 'Location', 'southwest');
title(ax, sprintf('PSD: S(5k)=%.2e, S(10k)=%.2e V^2/Hz', S5, S10));

if salvar
    od = fullfile(fileparts(mfilename('fullpath')), 'resultados');
    if ~exist(od, 'dir'), mkdir(od); end
    exportgraphics(fig, fullfile(od, [base '.png']), 'Resolution', 120);
    % figura extra: z por nível
    f2 = figure('Visible', 'off', 'Position', [50 50 800 420]); tema_claro(f2); ax = axes(f2); hold(ax, 'on');
    for l = 0:M-1
        jj = il(lv == l);
        plot(ax, jj, R.z(jj), '.', 'Color', cores(l+1,:), 'MarkerSize', 8, 'DisplayName', sprintf('nível %d', l));
    end
    yline(ax, R.thr_z, 'k--', 'LineWidth', 1.2, 'HandleVisibility', 'off'); grid(ax, 'on');
    legend(ax, 'Location', 'eastoutside');
    xlabel(ax, 'símbolo j da calibração'); ylabel(ax, 'z_{c,j} (adimensional)');
    title(ax, sprintf('Filtro casado: margem %.4f (escala z)', R.marg_z));
    exportgraphics(f2, fullfile(od, [base '_z.png']), 'Resolution', 120); close(f2);
    close(fig);
    fprintf('\nFiguras gravadas em %s\n', od);
end

% ---------- saída para a tabela ----------
T.arquivo = base; T.canal = r.canal; T.M = M; T.abertura_V = abertura_V;
T.kstar = R.kstar; T.t_kstar_us = tk(R.kstar+1);
T.marg_u_mV = mV(R.marg_u); T.marg_z = R.marg_z;
T.S5 = S5; T.S10 = S10; T.S5m = S5m; T.S10m = S10m; T.f = f; T.S = S;
T.valido = r.aquisicao_valida && r.sincronismo_ok;
if isfield(r, 'amostra_unica_Ne')
    T.Ne_u = r.amostra_unica_Ne; T.Ne_z = r.filtro_casado_Ne;
    T.Ns_u = r.amostra_unica_Ns; T.Ns_z = r.filtro_casado_Ns;
    T.bits = r.payload_bits; T.syms = r.payload_simbolos;
else
    T.Ne_u = NaN; T.Ne_z = NaN; T.Ns_u = NaN; T.Ns_z = NaN; T.bits = NaN; T.syms = NaN;
end
T.R = R;
end

function c = canal_do_rotulo(rot)
rot = lower(rot);
if contains(rot, '33'), c = 'rc33';
elseif contains(rot, 'rc'), c = 'rc';
else, c = 'dupont';
end
end

function tema_claro(fig)
try, theme(fig, 'light'); catch, set(fig, 'Color', 'w'); end
end

function v = ternario(c, a, b)
if c, v = a; else, v = b; end
end
