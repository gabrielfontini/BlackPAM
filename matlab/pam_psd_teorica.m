function S = pam_psd_teorica(f, M, canal, Vmax)
%PAM_PSD_TEORICA  PSD unilateral teórica (V^2/Hz) das amostras do ADC, sem DC.
%   S = pam_psd_teorica(f, M, canal, Vmax)
%
%   Modelo: níveis retangulares (NRZ) de duração Ts amostrados 8x por símbolo,
%   filtrados pelo canal H(f) e com a correlação criada pela PRBS-15:
%
%   PAM-2: bits da PRBS-15 ~ brancos  ->  S = (2/fa) s2 D(f) |H|^2
%          s2 = variância dos níveis = (Vmax/2)^2
%   PAM-4: com b(n+15) = b(n+14) xor b(n) vale b(n) xor b(n+1) = b(n-14).
%          Com o Gray do enunciado, nível_i = 2 c_i + c_(i-7), c_i = 1o bit do
%          par i. Logo |2 + exp(-j 2 pi f 7 Ts)|^2 = 5 + 4 cos(2 pi f 7 Ts):
%          vales em f = (2m+1) Rs/14 (… 7,14 kHz, 10 kHz …) e picos em m Rs/7.
%          S = (2/fa) (Vmax/3)^2 (1/4) (5 + 4 cos(14 pi f / Rs)) D(f) |H|^2
%
%   D(f) = |sum_{k=0}^{7} exp(-j 2 pi f k / fa)|^2 / 8   (pulso de 8 amostras)

if nargin < 4, Vmax = 3.3; end
P = pam_parametros(canal);
fa = P.fa; Ts = P.Ts;
f = f(:);
D = abs(sum(exp(-1j*2*pi*f*(0:7)/fa), 2)).^2 / 8;
H2 = abs(1 ./ polyval(P.den, 1j*2*pi*f)).^2;
if M == 2
    S = (2/fa) * (Vmax/2)^2 * D .* H2;
else
    S = (2/fa) * (Vmax/3)^2 * 0.25 * (5 + 4*cos(2*pi*f*7*Ts)) .* D .* H2;
end
end
