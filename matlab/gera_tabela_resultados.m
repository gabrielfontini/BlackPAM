function gera_tabela_resultados(arquivos, Vref, tau_us)
%GERA_TABELA_RESULTADOS  Monta a tabela da Seção 5.1 a partir dos logs do RX.
%   gera_tabela_resultados({'logs/PAM2_Dupont.txt','logs/PAM4_Dupont.txt', ...
%                           'logs/PAM2_RC.txt','logs/PAM4_RC.txt'}, 3.297, [NaN NaN 7.1 7.1])
%   tau_us : τ medido no osciloscópio para cada linha (NaN quando não se aplica)
%   Imprime em Markdown e grava resultados/tabela_resultados.csv

if nargin < 3, tau_us = nan(1, numel(arquivos)); end
fprintf('\n| Canal | PAM | Abertura (V) | τ (µs) | k* (t) | Erros amostra; BER | Erros filtro; BER |\n');
fprintf('|---|---|---|---|---|---|---|\n');
od = fullfile(fileparts(mfilename('fullpath')), 'resultados');
if ~exist(od, 'dir'), mkdir(od); end
fid = fopen(fullfile(od, 'tabela_resultados.csv'), 'w');
fprintf(fid, 'canal,PAM,abertura_V,tau_us,kstar,t_kstar_us,Ne_amostra,BER_amostra,Ne_filtro,BER_filtro,Ns_amostra,SER_amostra,Ns_filtro,SER_filtro\n');
for i = 1:numel(arquivos)
    T = analisa_ensaio(arquivos{i}, Vref, true);
    if T.valido && ~isnan(T.Ne_u)
        su = sprintf('%d; %.2g', T.Ne_u, T.Ne_u/T.bits);
        sz = sprintf('%d; %.2g', T.Ne_z, T.Ne_z/T.bits);
    else
        su = 'sem sincronismo'; sz = 'sem sincronismo';
    end
    fprintf('| %s | %d | %.3f | %s | %d (%.2f µs) | %s | %s |\n', T.canal, T.M, T.abertura_V, ...
        num2str(tau_us(i), '%.2f'), T.kstar, T.t_kstar_us, su, sz);
    fprintf(fid, '%s,%d,%.4f,%.3f,%d,%.2f,%g,%g,%g,%g,%g,%g,%g,%g\n', T.canal, T.M, T.abertura_V, tau_us(i), ...
        T.kstar, T.t_kstar_us, T.Ne_u, T.Ne_u/T.bits, T.Ne_z, T.Ne_z/T.bits, T.Ns_u, T.Ns_u/T.syms, T.Ns_z, T.Ns_z/T.syms);
end
fclose(fid);
fprintf('\nCSV gravado em %s\n', fullfile(od, 'tabela_resultados.csv'));
end
