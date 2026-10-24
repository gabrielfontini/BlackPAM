function Q = pam_quadro(M)
%PAM_QUADRO  Gera o quadro completo exatamente como o firmware do TX.
%   Q = pam_quadro(2) ou pam_quadro(4)
%   Q.nivel  : nível (0..M-1) de cada símbolo, na ordem de transmissão
%   Q.seg    : 1=pulso, 2=níveis, 3=início de quadro, 4=payload
%   Q.bits   : bits do payload (100 000) — b0 primeiro
%   Q.ipay   : índices (1-based) dos símbolos do payload
%   Q.ipre   : índices dos símbolos do início de quadro

if M ~= 2 && M ~= 4, error('M deve ser 2 ou 4'); end
A = M - 1;

% 1) pulso: 20 x (0,0,0,A,0,0,0)
pulso = repmat([0 0 0 A 0 0 0], 1, 20);
% 2) níveis: 32 x padrão
if M == 2, pad = [0 1 0 0 1 1 0 1]; else, pad = [0 1 0 3 2 3 1 2]; end
niveis = repmat(pad, 1, 32);
% 3) início de quadro: 16 alternados (começa em 0) + 0xD391C5A7 (MSB primeiro)
pre_bits = [repmat([0 1], 1, 8), bitget(uint32(hex2dec('D391C5A7')), 32:-1:1)];
% 4) payload: PRBS-15, b0..b14 = 1, b(n+15) = b(n+14) xor b(n)
bits = prbs15(100000);

pre_sym = bits2niveis(double(pre_bits), M);
pay_sym = bits2niveis(bits, M);

Q.M = M;
Q.nivel = [pulso, niveis, pre_sym, pay_sym];
Q.seg = [ones(1,140), 2*ones(1,256), 3*ones(1,numel(pre_sym)), 4*ones(1,numel(pay_sym))];
Q.bits = bits;
Q.pre_bits = double(pre_bits);
Q.ipre = find(Q.seg == 3);
Q.ipay = find(Q.seg == 4);
Q.itrain_pulso = 1:140;
Q.itrain_niveis = 141:396;
end

function b = prbs15(n)
b = zeros(1, n);
r = ones(1, 15);                 % janela [b(n) ... b(n+14)]
for i = 1:n
    b(i) = r(1);
    novo = xor(r(15), r(1));
    r = [r(2:end), novo];
end
end

function s = bits2niveis(b, M)
if M == 2
    s = b;
else
    b1 = b(1:2:end); b2 = b(2:2:end);
    gray = [0 1 3 2];            % índice 2*b1+b2: 00->0, 01->1, 10->3, 11->2
    s = gray(2*b1 + b2 + 1);
end
end
