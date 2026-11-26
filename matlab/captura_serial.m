function arquivo = captura_serial(porta, rotulo, canal_cmd, mod_cmd)
%CAPTURA_SERIAL  Arma o RX pela serial, espera o quadro e grava o log.
%   arquivo = captura_serial('/dev/ttyACM1', 'PAM4_RC_ensaio1', 'c', '4')
%   porta     : '/dev/ttyACM1' (Pico com pico-uart-bridge, UART1 = GP4/GP5)
%               ou 'COM5' (Windows) — veja serialportlist
%   rotulo    : nome do arquivo (sem extensão) dentro de ./logs/
%   canal_cmd : 'd' Dupont, 'c' RC 16,8 nF, 'x' RC 33 nF, 'm' cabo manga
%   mod_cmd   : '2' ou '4'
%
%   Depois de "ARMADO" aparecer, aperte o RESET (ou KEY) do TX.
%   PAM-2 leva ~5 s de payload + ~3 s de impressão; PAM-4 ~2,5 s + ~3 s.

if nargin < 3, canal_cmd = 'd'; end
if nargin < 4, mod_cmd = '2'; end
od = fullfile(fileparts(mfilename('fullpath')), 'logs');
if ~exist(od, 'dir'), mkdir(od); end
arquivo = fullfile(od, [rotulo '_' datestr(now, 'yyyymmdd_HHMMSS') '.txt']); %#ok<TNOW1,DATST>

s = serialport(porta, 460800, 'Timeout', 30);
configureTerminator(s, "CR/LF");
setDTR(s, true);   % ponte USB do Pico (TinyUSB) só repassa com a porta "aberta" (DTR)
flush(s);
write(s, uint8(mod_cmd), 'uint8'); pause(0.2);
write(s, uint8(canal_cmd), 'uint8'); pause(0.2);
fid = fopen(arquivo, 'w');
c = onCleanup(@() fclose(fid));
fprintf('Aguardando o quadro... aperte RESET no TX quando aparecer #ARMADO\n');
t0 = tic;
while toc(t0) < 120
    L = readline(s);
    if isempty(L), continue; end
    fprintf(fid, '%s\n', L);
    if startsWith(L, '#ARMADO') || startsWith(L, '#BEGIN') || startsWith(L, '#END') || ...
       contains(L, 'BER') || contains(L, 'valida') || contains(L, 'sincronismo')
        fprintf('%s\n', L);
    end
    if startsWith(L, '#END_PSD'), break; end
end
clear s;
fprintf('Log gravado em %s\n', arquivo);
end
