function R = pam_detectores(a, Q)
%PAM_DETECTORES  Mesmo algoritmo do firmware (pam_rx_core.c), em MATLAB.
%   R = pam_detectores(a, Q)
%   a : matriz Nsym x 8 de códigos ADC (uma linha por símbolo, k = 0..7)
%       pode ter só as 396 linhas do treinamento (sem BER) ou o quadro inteiro
%   Q : saída de pam_quadro(M)
%
%   Seções do enunciado: 4.3 (k*), 4.5.1 (filtro casado), 4.5.2 (centros,
%   limiares, margens), 4.6 (decisão) e 4.7 (BER/SER).

M = Q.M; A = M - 1;
a = double(a);

% ---------------- 4.5.1 filtro casado ----------------
ip = Q.itrain_pulso;                       % 1..140
posA  = ip(Q.nivel(ip) == A);              % 20 símbolos A
posZ  = posA - 1;                          % último zero antes de cada A
posZ1 = posA + 1;                          % primeiro zero depois de A (ISI)
R.bc = mean(reshape(a(posZ, :), [], 1));   % média das 160 leituras
R.pc = mean(a(posA, :), 1) - R.bc;         % 8 pesos
R.Ec = sum(R.pc.^2);
R.isi_zero_apos_A = mean(a(posZ1, :), 1) - R.bc;
zf = @(x) ((x - R.bc) * R.pc.') / R.Ec;    % z = sum p_c[k] x[k] / E_c
R.z = zf(a);                               % z de todos os símbolos
R.media8 = mean(a - R.bc, 2);              % média simples (comparação)

% ---------------- 4.3 escolha de k* ----------------
il = Q.itrain_niveis;                      % 141..396
lv = Q.nivel(il);
R.sep_k = zeros(1, 8);
for k = 1:8
    s = inf;
    for l = 0:M-2
        d = min(a(il(lv == l+1), k)) - max(a(il(lv == l), k));
        s = min(s, d);
    end
    R.sep_k(k) = s;
end
[~, kk] = max(R.sep_k);                    % max devolve o 1o (menor k) em empate
R.kstar = kk - 1;                          % 0..7
R.t_kstar_us = (3.12 + 6.25*R.kstar);

% ---------------- 4.5.2 centros, limiares, margens ----------------
u = a(:, kk);
R.u = u;
R.cen_u = zeros(1, M); R.cen_z = zeros(1, M);
for l = 0:M-1
    R.cen_u(l+1) = mean(u(il(lv == l)));
    R.cen_z(l+1) = mean(R.z(il(lv == l)));
end
R.calib_ok = all(diff(R.cen_u) > 0) && all(diff(R.cen_z) > 0) && R.Ec > 0;
R.thr_u = (R.cen_u(1:end-1) + R.cen_u(2:end)) / 2;
R.thr_z = (R.cen_z(1:end-1) + R.cen_z(2:end)) / 2;
R.marg_u_pares = zeros(1, M-1); R.marg_z_pares = zeros(1, M-1);
for l = 0:M-2
    R.marg_u_pares(l+1) = min(u(il(lv == l+1))) - max(u(il(lv == l)));
    R.marg_z_pares(l+1) = min(R.z(il(lv == l+1))) - max(R.z(il(lv == l)));
end
[R.marg_u, iu] = min(R.marg_u_pares); R.marg_u_par = [iu-1 iu];
[R.marg_z, iz] = min(R.marg_z_pares); R.marg_z_par = [iz-1 iz];

% ---------------- 4.6 / 4.7 decisão e contagem ----------------
if size(a, 1) < numel(Q.nivel)
    R.tem_payload = false;
    return
end
R.tem_payload = true;
dec = @(v, thr) sum(v > thr, 2);           % nível = nº de limiares ultrapassados
lu = dec(u, R.thr_u); lz = dec(R.z, R.thr_z);

% início de quadro
ipre = Q.ipre;
R.pre_err_u = sum(niveis2bits(lu(ipre), M) ~= Q.pre_bits);
R.pre_err_z = sum(niveis2bits(lz(ipre), M) ~= Q.pre_bits);
R.sync_ok = R.pre_err_u == 0 && R.pre_err_z == 0 && R.calib_ok;

ipay = Q.ipay;
tx = Q.nivel(ipay).';
R.Ns_u = sum(lu(ipay) ~= tx);  R.Ns_z = sum(lz(ipay) ~= tx);
R.Ne_u = sum(niveis2bits(lu(ipay), M) ~= Q.bits);
R.Ne_z = sum(niveis2bits(lz(ipay), M) ~= Q.bits);
R.Nbits = numel(Q.bits);  R.Nsym = numel(ipay);
R.BER_u = R.Ne_u / R.Nbits;  R.BER_z = R.Ne_z / R.Nbits;
R.SER_u = R.Ns_u / R.Nsym;   R.SER_z = R.Ns_z / R.Nsym;
R.lu = lu; R.lz = lz;
end

function b = niveis2bits(l, M)
l = l(:).';
if M == 2
    b = l;
else
    b1 = [0 0 1 1]; b2 = [0 1 1 0];        % Gray: 0->00 1->01 2->11 3->10
    b = reshape([b1(l+1); b2(l+1)], 1, []);
end
end
