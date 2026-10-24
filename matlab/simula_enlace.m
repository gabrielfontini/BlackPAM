%SIMULA_ENLACE  Previsão numérica de TODOS os resultados pedidos no enunciado.
%   Rode antes de ir para a bancada: você fica sabendo o que esperar
%   (tau, tempo de subida, k*, pesos, centros, limiares, margens, PSD, BER).
%   Gera figuras em ./figuras_simulacao e a tabela em resultados_simulacao.txt
%
%   O modelo usa o mesmo quadro (pam_quadro) e o mesmo algoritmo de detecção
%   (pam_detectores) do firmware. Ruído: só o do ADC (sigma ~ 1,5 LSB).

clear; close all;
here = fileparts(mfilename('fullpath'));
outdir = fullfile(here, 'figuras_simulacao');
if ~exist(outdir, 'dir'), mkdir(outdir); end
fid = fopen(fullfile(here, 'resultados_simulacao.txt'), 'w');
out = @(varargin) [fprintf(varargin{:}), fprintf(fid, varargin{:})];

canais = {'dupont', 'rc', 'rc33'};
Ms = [2 4];
Vref = 3.3;
PSD = struct();

out('==== PREVISÃO NUMÉRICA DO ENLACE PAM (Rs = 20 ksym/s, fa = 160 kHz) ====\n\n');
for c = 1:numel(canais)
    P = pam_parametros(canais{c});
    out('---- Canal: %s ----\n', P.nome);
    out('tau (conta do enunciado, (330+R2)*C2) = %.2f us ; fc = %.1f kHz\n', ...
        P.tau_nominal*1e6, P.fc_nominal/1e3);
    out('tau dominante do modelo de 2 polos (com 390 pF e Rgpio=%g Ω) = %.2f us\n', ...
        P.Rgpio, P.tau_dom*1e6);
    for M = Ms
        [a, Q, P, W] = pam_canal_sim(M, canais{c}, [], 400);
        R = pam_detectores(a, Q);

        % ---- resposta ao degrau 0 -> A na forma de onda (como no osciloscópio) ----
        % primeira subida do pulso de treinamento: símbolo 4 (índice 3)
        t = W.t; y = W.tp3;
        i1 = find(t >= 3*P.Ts, 1); i2 = find(t >= 4*P.Ts, 1) - 1;
        V0 = y(i1); Vf = max(y(i1:i2));
        tt = t(i1:i2); yy = y(i1:i2);
        t0 = 3*P.Ts + P.tlat;
        t63 = interp1u(yy, tt, V0 + 0.632*(Vf - V0));
        t10 = interp1u(yy, tt, V0 + 0.1*(Vf - V0));
        t90 = interp1u(yy, tt, V0 + 0.9*(Vf - V0));
        tau_med = t63 - t0; tr = t90 - t10;

        % ---- PSD pelo método do enunciado (8 192 amostras do payload) ----
        ip = Q.ipay(1000 + (1:1024));
        cod = reshape(a(ip, :).', [], 1);
        [S, f, info] = pam_psd(cod, Vref, 160e3);
        PSD.(sprintf('%s_%d', canais{c}, M)) = struct('S', S, 'f', f);
        S5 = interp1(f, S, 5e3); S10 = interp1(f, S, 10e3);
        S5m = mean(S(abs(f-5e3) <= 2*info.df)); S10m = mean(S(abs(f-10e3) <= 2*info.df));
        Sth = pam_psd_teorica(f, M, canais{c}, P.Vdd);

        out('\n  PAM-%d:\n', M);
        out('    degrau 0->A em TP3: V0=%.3f V, Vf=%.3f V, tau(63,2%%)=%.2f us, t10-90=%.2f us (=> tau=%.2f us)\n', ...
            V0, Vf, tau_med*1e6, tr*1e6, tr/2.197*1e6);
        out('    b_c = %.2f ; E_c = %.4g\n', R.bc, R.Ec);
        out('    p_c[k] = %s\n', mat2str(round(R.pc, 1)));
        out('    ISI no 1o zero depois de A (códigos) = %s\n', mat2str(round(R.isi_zero_apos_A, 1)));
        out('    separação por k (códigos) = %s\n', mat2str(R.sep_k));
        out('    k* = %d -> t = %.2f us ; menor separação = %d códigos = %.1f mV\n', ...
            R.kstar, R.t_kstar_us, R.sep_k(R.kstar+1), R.sep_k(R.kstar+1)*Vref/4095*1e3);
        out('    centros u = %s ; limiares u = %s\n', mat2str(round(R.cen_u, 1)), mat2str(round(R.thr_u, 1)));
        out('    centros z = %s ; limiares z = %s\n', mat2str(round(R.cen_z, 4)), mat2str(round(R.thr_z, 4)));
        out('    margem u = %d códigos (%.1f mV), par %d-%d ; margem z = %.4f, par %d-%d\n', ...
            R.marg_u, R.marg_u*Vref/4095*1e3, R.marg_u_par, R.marg_z, R.marg_z_par);
        out('    sincronismo: erros no início u=%d z=%d -> %d\n', R.pre_err_u, R.pre_err_z, R.sync_ok);
        out('    amostra única: Ne=%d BER=%.2g Ns=%d SER=%.2g\n', R.Ne_u, R.BER_u, R.Ns_u, R.SER_u);
        out('    filtro casado: Ne=%d BER=%.2g Ns=%d SER=%.2g\n', R.Ne_z, R.BER_z, R.Ns_z, R.SER_z);
        out('    PSD: S(5 kHz)=%.3g V^2/Hz (média 5 bins %.3g; teoria %.3g)\n', S5, S5m, interp1(f, Sth, 5e3));
        out('         S(10 kHz)=%.3g V^2/Hz (média 5 bins %.3g; teoria %.3g)\n', S10, S10m, interp1(f, Sth, 10e3));
        out('         %d blocos de 1024, df=%.2f Hz, registro=%.1f ms, potência AC=%.3f V^2\n', ...
            info.nblocos, info.df, info.duracao_s*1e3, info.Pmedia_V2);

        % ---- figuras ----
        fig = figure('Visible', 'off', 'Position', [100 100 1200 800]);
try, theme(fig, 'light'); catch, end
        tl = tiledlayout(fig, 2, 2, 'TileSpacing', 'compact');
        title(tl, sprintf('Simulação — %s — PAM-%d', P.nome, M), 'Interpreter', 'none');
        ax = nexttile(tl);
        nshow = 30;
        plot(ax, t*1e6, W.vin, 'k:', t*1e6, y, 'b'); xlim(ax, [0 nshow*50]);
        xlabel(ax, 't (\mus)'); ylabel(ax, 'V'); grid(ax, 'on');
        legend(ax, 'nível do TX (antes do filtro)', 'TP3'); title(ax, 'Início do treinamento (pulsos 0,0,0,A,0,0,0)');
        ax = nexttile(tl);
        plot(ax, (tt - t0)*1e6, yy, 'b', 'LineWidth', 1.2); hold(ax, 'on');
        plot(ax, (t63 - t0)*1e6, V0 + 0.632*(Vf-V0), 'ro', (t10-t0)*1e6, V0+0.1*(Vf-V0), 'ks', (t90-t0)*1e6, V0+0.9*(Vf-V0), 'ks');
        xlabel(ax, 't - t_0 (\mus)'); ylabel(ax, 'TP3 (V)'); grid(ax, 'on');
        title(ax, sprintf('Degrau 0\\rightarrowA: \\tau = %.2f \\mus, t_{10-90} = %.2f \\mus', tau_med*1e6, tr*1e6));
        ax = nexttile(tl);
        pam_olho(ax, a(ip, :), Q.nivel(ip), R, Vref, 'Olho (amostras ADC + forma contínua)', W);
        ax = nexttile(tl);
        plot(ax, f/1e3, 10*log10(S), 'b'); grid(ax, 'on'); hold(ax, 'on');
        plot(ax, f/1e3, 10*log10(Sth), 'k--', 'LineWidth', 1.2);
        xline(ax, [5 10], 'r:'); legend(ax, 'estimada (8192 amostras)', 'teoria', 'Location', 'southwest');
        ylim(ax, [-110 -30]);
        xlabel(ax, 'f (kHz)'); ylabel(ax, 'S(f) (dB V^2/Hz)'); xlim(ax, [0 80]);
        title(ax, 'PSD (Hann, 1024, 50%, fa = 160 kHz)');
        exportgraphics(fig, fullfile(outdir, sprintf('sim_%s_pam%d.png', canais{c}, M)), 'Resolution', 110);
        close(fig);
    end
    out('\n');
end

% ---- comparação de PSD entre canais e teoria ----
out('---- Razões de PSD (canal RC / Dupont) em 5 e 10 kHz ----\n');
for M = Ms
    d = PSD.(sprintf('dupont_%d', M)); r = PSD.(sprintf('rc_%d', M)); r33 = PSD.(sprintf('rc33_%d', M));
    for fx = [5e3 10e3]
        rat = interp1(d.f, r.S, fx) / interp1(d.f, d.S, fx);
        rat33 = interp1(d.f, r33.S, fx) / interp1(d.f, d.S, fx);
        Pr = pam_parametros('rc'); Pr33 = pam_parametros('rc33'); Pd = pam_parametros('dupont');
        H2 = abs(polyval(Pr.num, 1i*2*pi*fx) / polyval(Pr.den, 1i*2*pi*fx))^2 / ...
             abs(polyval(Pd.num, 1i*2*pi*fx) / polyval(Pd.den, 1i*2*pi*fx))^2;
        H233 = abs(1 / polyval(Pr33.den, 1i*2*pi*fx))^2 / abs(1 / polyval(Pd.den, 1i*2*pi*fx))^2;
        out('  PAM-%d, f = %4.1f kHz: RC16,8n/Dupont = %.3f (%.2f dB) [teoria |H|^2 = %.3f] ; RC33n/Dupont = %.3f (%.2f dB) [teoria %.3f]\n', ...
            M, fx/1e3, rat, 10*log10(rat), H2, rat33, 10*log10(rat33), H233);
    end
end
fig = figure('Visible', 'off', 'Position', [100 100 1100 450]);
try, theme(fig, 'light'); catch, end
tl = tiledlayout(fig, 1, 2);
for i = 1:2
    M = Ms(i); ax = nexttile(tl); hold(ax, 'on');
    for c = 1:numel(canais)
        s = PSD.(sprintf('%s_%d', canais{c}, M));
        plot(ax, s.f/1e3, 10*log10(s.S));
    end
    set(ax, 'ColorOrderIndex', 1);
    for c = 1:numel(canais)
        plot(ax, s.f/1e3, 10*log10(pam_psd_teorica(s.f, M, canais{c})), '--', 'HandleVisibility', 'off');
    end
    ylim(ax, [-110 -30]);
    xline(ax, [5 10], 'k:'); grid(ax, 'on'); xlim(ax, [0 80]);
    legend(ax, 'Dupont', 'RC 16,8 nF', 'RC 33 nF', 'Location', 'southwest'); xlabel(ax, 'f (kHz)'); ylabel(ax, 'dB V^2/Hz');
    title(ax, sprintf('PSD PAM-%d — mesma escala (tracejado = teoria)', M));
end
exportgraphics(fig, fullfile(outdir, 'sim_psd_comparacao.png'), 'Resolution', 110); close(fig);

% ---- curva BER x ruído (liga a Aula 09: função Q e filtro casado) ----
out('\n---- BER x ruído no canal Dupont (ruído gaussiano somado no ADC) ----\n');
sig = [150 250 350 450 550];  % LSB
fig = figure('Visible', 'off', 'Position', [100 100 900 450]); tl = tiledlayout(fig, 1, 2);
try, theme(fig, 'light'); catch, end
for M = Ms
    bu = zeros(size(sig)); bz = bu;
    for i = 1:numel(sig)
        [a, Q] = pam_canal_sim(M, 'dupont', sig(i));
        R = pam_detectores(a, Q);
        bu(i) = max(R.BER_u, 1e-6); bz(i) = max(R.BER_z, 1e-6);
        out('  PAM-%d sigma=%3d LSB (%.0f mV): BER amostra=%.2e  BER filtro=%.2e\n', M, sig(i), sig(i)*Vref/4095*1e3, R.BER_u, R.BER_z);
    end
    d = 4095/(M-1);                        % distância entre níveis (códigos)
    Pth_u = 2*(M-1)/M * qfunc_(d/2 ./ sig) / log2(M);
    Pth_z = 2*(M-1)/M * qfunc_(d/2 ./ (sig/sqrt(8))) / log2(M);
    ax = nexttile(tl);
    semilogy(ax, sig, bu, 'bo', sig, bz, 'rs', sig, Pth_u, 'b-', sig, max(Pth_z,1e-7), 'r-');
    grid(ax, 'on'); ylim(ax, [1e-6 1]); xlabel(ax, '\sigma do ruído (LSB)'); ylabel(ax, 'BER');
    legend(ax, 'amostra única (sim)', 'filtro casado (sim)', 'teoria Q(d/2\sigma)', 'teoria Q(d\surd8/2\sigma)', 'Location', 'southeast');
    title(ax, sprintf('PAM-%d (piso 1e-6 = 0 erros)', M));
end
exportgraphics(fig, fullfile(outdir, 'sim_ber_ruido.png'), 'Resolution', 110); close(fig);
fclose(fid);
fprintf('\nFiguras em %s\n', outdir);

function x = interp1u(y, t, v)
% primeiro instante em que y cruza v (subida)
i = find(y >= v, 1);
if isempty(i) || i == 1, x = NaN; return; end
x = t(i-1) + (v - y(i-1)) * (t(i) - t(i-1)) / (y(i) - y(i-1));
end

function q = qfunc_(x)
q = 0.5*erfc(x/sqrt(2));
end
