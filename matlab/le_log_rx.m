function D = le_log_rx(arquivo)
%LE_LOG_RX  Lê o log serial do RX (#BEGIN_REPORT ... #END_PSD).
%   D = le_log_rx('PAM4_RC_ensaio1.txt')
%   D.rep    : struct com os campos chave=valor do relatório (números quando possível)
%   D.train  : 396 x 11  [j, nivel, a0..a7, z]
%   D.psd    : 1024 x 10 [simbolo, nivel, a0..a7]
%   D.M      : 2 ou 4
%   Se o arquivo tiver vários relatórios, usa o ÚLTIMO.

txt = fileread(arquivo);
txt = strrep(txt, sprintf('\r'), '');
ib = strfind(txt, '#BEGIN_REPORT');
if isempty(ib), error('Nenhum #BEGIN_REPORT em %s', arquivo); end
txt = txt(ib(end):end);

linhas = strsplit(txt, newline);
D.rep = struct();
modo = '';
train = []; psd = [];
for i = 1:numel(linhas)
    L = strtrim(linhas{i});
    if isempty(L), continue; end
    if startsWith(L, '#BEGIN_REPORT'), modo = 'rep'; continue; end
    if startsWith(L, '#END_REPORT'), modo = ''; continue; end
    if startsWith(L, '#BEGIN_TRAIN'), modo = 'train'; continue; end
    if startsWith(L, '#END_TRAIN'), modo = ''; continue; end
    if startsWith(L, '#BEGIN_PSD'), modo = 'psd'; continue; end
    if startsWith(L, '#END_PSD'), modo = ''; continue; end
    switch modo
        case 'rep'
            if startsWith(L, 'janela a[')
                v = sscanf(L, 'janela a[%d]=%d x[%d]=%f p_c[%d]=%f');
                D.rep.janela_a(v(1)+1) = v(2);
                D.rep.janela_x(v(1)+1) = v(4);
                continue
            end
            e = strfind(L, '=');
            if isempty(e), continue; end
            chave = L(1:e(1)-1); valor = L(e(1)+1:end);
            tok = regexp(chave, '^(\w+)\[(\d+)\]$', 'tokens', 'once');
            num = str2double(strtok(valor));
            if ~isempty(tok)
                nome = matlab.lang.makeValidName(tok{1});
                D.rep.(nome)(str2double(tok{2})+1) = num;
            else
                nome = matlab.lang.makeValidName(chave);
                if isnan(num), D.rep.(nome) = valor; else, D.rep.(nome) = num; end
            end
        case 'train'
            train(end+1, :) = sscanf(L, '%f,').'; %#ok<AGROW>
        case 'psd'
            psd(end+1, :) = sscanf(L, '%f,').'; %#ok<AGROW>
    end
end
D.train = train;
D.psd = psd;
D.M = sscanf(D.rep.modulacao, 'PAM-%d');
D.arquivo = arquivo;
end
