"""
pam_core.py — núcleo de análise do Projeto PAM em banda base (sem interface).

Porta fiel, em Python, dos scripts MATLAB da pasta ../matlab:
    le_log_rx.m          -> ler_log()
    pam_quadro.m         -> quadro()
    pam_detectores.m     -> detectores()
    pam_psd.m            -> psd_welch()
    pam_psd_teorica.m    -> psd_teorica()
    pam_parametros.m     -> parametros_canal()
    analisa_ensaio.m     -> analisar()
    compara_psd_canais.m -> comparar_psd()
    tau_osciloscopio.m   -> tau_csv()
    gera_tabela_resultados.m -> tabela()

Depende só de numpy e matplotlib (as figuras são objetos Figure, sem pyplot,
para poderem ser embutidas na interface Tk ou salvas em PNG).
"""
from __future__ import annotations

import csv
import io
import math
import os
import re
from dataclasses import dataclass, field

import numpy as np
from matplotlib.figure import Figure

# ----------------------------------------------------------------------------
# Constantes do enunciado (iguais a firmware/common/pam_config.h)
# ----------------------------------------------------------------------------
RS = 20_000                     # símbolos/s
TS = 1.0 / RS                   # 50 µs
SPS = 8                         # amostras por símbolo
FA = RS * SPS                   # 160 kHz
TK_US = 3.12 + 6.25 * np.arange(8)   # instantes das 8 amostras após a borda (µs)
N_PULSO = 140                   # 20 x (0,0,0,A,0,0,0)
N_TREINO = 396                  # 140 + 256
PSD_START_SYM = 1000            # símbolo do payload onde começa o bloco PSD
GRAY = ["00", "01", "11", "10"]
CORES = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]


# ----------------------------------------------------------------------------
# Quadro (Seção 4.2) — igual a pam_frame.c / pam_quadro.m
# ----------------------------------------------------------------------------
def prbs15(n: int) -> np.ndarray:
    """b0..b14 = 1 ; b(n+15) = b(n+14) xor b(n)."""
    b = np.empty(n, dtype=np.uint8)
    s = 0x7FFF                                   # 15 bits em 1
    for i in range(n):
        b[i] = s & 1
        nb = ((s >> 14) ^ s) & 1
        s = (s >> 1) | (nb << 14)
    return b


def bits_para_niveis(bits: np.ndarray, M: int) -> np.ndarray:
    if M == 2:
        return bits.astype(np.uint8)
    b1, b2 = bits[0::2], bits[1::2]
    gray = np.array([0, 1, 3, 2], dtype=np.uint8)   # 00->0 01->1 10->3 11->2
    return gray[2 * b1 + b2]


@dataclass
class Quadro:
    M: int
    nivel: np.ndarray          # nível de cada símbolo, na ordem de transmissão
    bits: np.ndarray           # 100 000 bits do payload
    pre_bits: np.ndarray       # 48 bits do início de quadro
    i_pre: np.ndarray          # índices (0-based) do início de quadro
    i_pay: np.ndarray          # índices (0-based) do payload


_cache_quadro: dict[int, Quadro] = {}


def quadro(M: int) -> Quadro:
    if M not in (2, 4):
        raise ValueError("M deve ser 2 ou 4")
    if M in _cache_quadro:
        return _cache_quadro[M]
    A = M - 1
    pulso = np.tile([0, 0, 0, A, 0, 0, 0], 20)
    pad = [0, 1, 0, 0, 1, 1, 0, 1] if M == 2 else [0, 1, 0, 3, 2, 3, 1, 2]
    niveis = np.tile(pad, 32)
    sw = 0xD391C5A7
    pre_bits = np.array([i & 1 for i in range(16)] + [(sw >> (31 - i)) & 1 for i in range(32)],
                        dtype=np.uint8)
    bits = prbs15(100_000)
    pre_sym = bits_para_niveis(pre_bits, M)
    pay_sym = bits_para_niveis(bits, M)
    nivel = np.concatenate([pulso, niveis, pre_sym, pay_sym]).astype(np.uint8)
    i_pre = np.arange(N_TREINO, N_TREINO + len(pre_sym))
    i_pay = np.arange(i_pre[-1] + 1, len(nivel))
    q = Quadro(M, nivel, bits, pre_bits, i_pre, i_pay)
    _cache_quadro[M] = q
    return q


# ----------------------------------------------------------------------------
# Leitura do log do RX (#BEGIN_REPORT ... #END_PSD)
# ----------------------------------------------------------------------------
@dataclass
class LogRX:
    arquivo: str
    rep: dict                  # chave=valor do relatório (números quando possível)
    train: np.ndarray          # 396 x 11 [j, nivel, a0..a7, z]
    psd: np.ndarray            # 1024 x 10 [simbolo, nivel, a0..a7]
    M: int
    completo: bool             # chegou até #END_PSD?

    @property
    def nome(self) -> str:
        return os.path.splitext(os.path.basename(self.arquivo))[0] if self.arquivo else "log"


def _num(s: str):
    tok = s.strip().split()[0] if s.strip() else ""
    try:
        return int(tok)
    except ValueError:
        try:
            return float(tok)
        except ValueError:
            return s.strip()


def ler_log(origem: str, eh_texto: bool = False) -> LogRX:
    """Lê um log (caminho ou texto). Se houver vários relatórios, usa o ÚLTIMO."""
    if eh_texto:
        txt, arq = origem, ""
    else:
        with open(origem, "r", encoding="utf-8", errors="replace") as fh:
            txt, arq = fh.read(), origem
    txt = txt.replace("\r", "")
    ib = txt.rfind("#BEGIN_REPORT")
    if ib < 0:
        raise ValueError(f"Nenhum #BEGIN_REPORT em {arq or 'texto'}")
    txt = txt[ib:]
    rep: dict = {}
    modo = ""
    train, psd = [], []
    completo = False
    re_idx = re.compile(r"^(\w+)\[(\d+)\]$")
    re_jan = re.compile(r"janela a\[(\d+)\]=(\d+) x\[\d+\]=(-?[\d.]+) p_c\[\d+\]=(-?[\d.]+)")
    for L in txt.split("\n"):
        L = L.strip()
        if not L:
            continue
        if L.startswith("#BEGIN_REPORT"):
            modo = "rep"; continue
        if L.startswith("#END_REPORT"):
            modo = ""; continue
        if L.startswith("#BEGIN_TRAIN"):
            modo = "train"; continue
        if L.startswith("#END_TRAIN"):
            modo = ""; continue
        if L.startswith("#BEGIN_PSD"):
            modo = "psd"; continue
        if L.startswith("#END_PSD"):
            modo = ""; completo = True; break
        if modo == "rep":
            m = re_jan.match(L)
            if m:
                k = int(m.group(1))
                rep.setdefault("janela_a", [0] * 8)[k] = int(m.group(2))
                rep.setdefault("janela_x", [0.0] * 8)[k] = float(m.group(3))
                continue
            if "=" not in L:
                continue
            chave, valor = L.split("=", 1)
            mi = re_idx.match(chave)
            if mi:
                lst = rep.setdefault(mi.group(1), [])
                i = int(mi.group(2))
                while len(lst) <= i:
                    lst.append(math.nan)
                lst[i] = _num(valor)
            else:
                rep[chave] = _num(valor)
        elif modo in ("train", "psd"):
            try:
                row = [float(v) for v in L.split(",") if v != ""]
            except ValueError:
                continue
            (train if modo == "train" else psd).append(row)
    mod = str(rep.get("modulacao", "PAM-2"))
    M = int(re.findall(r"\d+", mod)[0]) if re.findall(r"\d+", mod) else 2
    return LogRX(arq, rep, np.array(train, dtype=float), np.array(psd, dtype=float), M, completo)


# ----------------------------------------------------------------------------
# Detectores (Seções 4.3, 4.5.1, 4.5.2) — mesmo algoritmo de pam_rx_core.c
# ----------------------------------------------------------------------------
@dataclass
class Detect:
    bc: float
    pc: np.ndarray
    Ec: float
    isi: np.ndarray
    z: np.ndarray
    sep_k: np.ndarray
    kstar: int
    u: np.ndarray
    cen_u: np.ndarray
    cen_z: np.ndarray
    thr_u: np.ndarray
    thr_z: np.ndarray
    marg_u: float
    marg_u_par: tuple
    marg_z: float
    marg_z_par: tuple
    calib_ok: bool
    media8: np.ndarray = field(default_factory=lambda: np.zeros(0))


def detectores(a: np.ndarray, M: int) -> Detect:
    """a: N x 8 códigos ADC (pelo menos os 396 símbolos de treinamento)."""
    q = quadro(M)
    A = M - 1
    a = np.asarray(a, dtype=float)
    nv = q.nivel[:N_TREINO]
    ip = np.arange(N_PULSO)
    posA = ip[nv[ip] == A]               # 20 símbolos A
    posZ = posA - 1                      # último zero antes de A
    posZ1 = posA + 1                     # 1º zero depois de A
    bc = a[posZ].mean()
    pc = a[posA].mean(axis=0) - bc
    Ec = float(np.sum(pc ** 2))
    isi = a[posZ1].mean(axis=0) - bc
    z = ((a - bc) @ pc) / (Ec if Ec > 0 else 1.0)

    il = np.arange(N_PULSO, N_TREINO)
    lv = nv[il]
    sep = np.zeros(8)
    for k in range(8):
        s = math.inf
        for l in range(M - 1):
            s = min(s, a[il[lv == l + 1], k].min() - a[il[lv == l], k].max())
        sep[k] = s
    kstar = int(np.argmax(sep))          # 1º máximo (menor k) em empate
    u = a[:, kstar]
    cen_u = np.array([u[il[lv == l]].mean() for l in range(M)])
    cen_z = np.array([z[il[lv == l]].mean() for l in range(M)])
    calib_ok = bool(np.all(np.diff(cen_u) > 0) and np.all(np.diff(cen_z) > 0) and Ec > 0)
    thr_u = (cen_u[:-1] + cen_u[1:]) / 2
    thr_z = (cen_z[:-1] + cen_z[1:]) / 2
    mu = [u[il[lv == l + 1]].min() - u[il[lv == l]].max() for l in range(M - 1)]
    mz = [z[il[lv == l + 1]].min() - z[il[lv == l]].max() for l in range(M - 1)]
    iu, iz = int(np.argmin(mu)), int(np.argmin(mz))
    return Detect(bc, pc, Ec, isi, z, sep, kstar, u, cen_u, cen_z, thr_u, thr_z,
                  float(mu[iu]), (iu, iu + 1), float(mz[iz]), (iz, iz + 1), calib_ok,
                  (a - bc).mean(axis=1))


# ----------------------------------------------------------------------------
# Canal (pam_parametros.m) e PSD
# ----------------------------------------------------------------------------
def parametros_canal(canal: str, Rgpio: float = 30.0) -> dict:
    R1, C1 = 330.0, 390e-12
    canal = canal.lower()
    if canal == "dupont":
        R2, C2 = 0.0, 0.0
    elif canal == "rc":
        R2, C2 = 56.0, 16.8e-9
    elif canal == "rc33":
        R2, C2 = 56.0, 33e-9
    else:
        raise ValueError(canal)
    Ra = Rgpio + R1
    if C2 == 0:
        den = np.array([Ra * C1, 1.0])
        tau_nom = R1 * C1
    else:
        den = np.array([Ra * C1 * R2 * C2, Ra * C1 + R2 * C2 + Ra * C2, 1.0])
        tau_nom = (R1 + R2) * C2
    p = np.roots(den)
    return {"den": den, "tau_dom": float(max(-1 / p.real)), "tau_nominal": tau_nom,
            "fc_nominal": 1 / (2 * math.pi * tau_nom)}


def canal_do_rotulo(rot: str) -> str:
    r = str(rot).lower()
    if "33" in r:
        return "rc33"
    if "rc" in r:
        return "rc"
    return "dupont"


def H2(f: np.ndarray, den: np.ndarray) -> np.ndarray:
    return np.abs(1.0 / np.polyval(den, 1j * 2 * np.pi * np.asarray(f))) ** 2


def psd_welch(codigos: np.ndarray, Vref: float, fa: float = FA, N: int = 1024):
    """Método do enunciado: códigos->V, tira média, blocos de 1024, 50 %, Hann
    periódica, unilateral (sem dobrar DC/Nyquist), média dos blocos."""
    x = np.asarray(codigos, dtype=float).ravel() * Vref / 4095.0
    x = x - x.mean()
    hop = N // 2
    w = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N) / N)
    U = np.sum(w ** 2)
    nb = (len(x) - N) // hop + 1
    P = np.zeros(N // 2 + 1)
    for b in range(nb):
        X = np.fft.rfft(x[b * hop: b * hop + N] * w)
        Pb = np.abs(X) ** 2 / (fa * U)
        Pb[1:-1] *= 2
        P += Pb
    S = P / nb
    f = np.arange(N // 2 + 1) * fa / N
    info = {"nblocos": nb, "df": fa / N, "duracao_s": len(x) / fa,
            "Pmedia_V2": float(np.sum(S) * fa / N), "var_x": float(np.var(x))}
    return S, f, info


def psd_teorica(f: np.ndarray, M: int, canal: str, Vmax: float = 3.3) -> np.ndarray:
    P = parametros_canal(canal)
    f = np.asarray(f, dtype=float)
    D = np.abs(np.exp(-1j * 2 * np.pi * np.outer(f, np.arange(8)) / FA).sum(axis=1)) ** 2 / 8
    h2 = H2(f, P["den"])
    if M == 2:
        return (2 / FA) * (Vmax / 2) ** 2 * D * h2
    return (2 / FA) * (Vmax / 3) ** 2 * 0.25 * (5 + 4 * np.cos(2 * np.pi * f * 7 * TS)) * D * h2


def media_bins(S, f, fx, df):
    return float(np.mean(S[np.abs(f - fx) <= 2 * df]))


# ----------------------------------------------------------------------------
# Análise completa de um log (analisa_ensaio.m)
# ----------------------------------------------------------------------------
@dataclass
class Resultado:
    log: LogRX
    R: Detect
    Vref: float
    texto: str
    abertura_V: float
    abertura_k_V: np.ndarray
    S: np.ndarray
    f: np.ndarray
    Sth: np.ndarray
    S5: float
    S10: float
    S5m: float
    S10m: float
    valido: bool
    avisos: list
    checks: list               # [(descrição, ok)]

    @property
    def tabela_linha(self) -> dict:
        r = self.log.rep
        d = {"canal": r.get("canal", "?"), "PAM": self.log.M, "abertura_V": self.abertura_V,
             "kstar": self.R.kstar, "t_kstar_us": float(TK_US[self.R.kstar]),
             "marg_u_mV": self.R.marg_u * self.Vref / 4095 * 1e3, "marg_z": self.R.marg_z,
             "S5": self.S5m, "S10": self.S10m}
        if "amostra_unica_Ne" in r:
            d.update(Ne_u=r["amostra_unica_Ne"], Ne_z=r["filtro_casado_Ne"],
                     Ns_u=r["amostra_unica_Ns"], Ns_z=r["filtro_casado_Ns"],
                     bits=r["payload_bits"], syms=r["payload_simbolos"])
        else:
            d.update(Ne_u=math.nan, Ne_z=math.nan, Ns_u=math.nan, Ns_z=math.nan,
                     bits=math.nan, syms=math.nan)
        return d


def _g(r, k, padrao=math.nan):
    return r.get(k, padrao)


def verificacoes(log: LogRX) -> list:
    """Critérios de aceitação do quadro (checklist do enunciado)."""
    r = log.rep
    esp = _g(r, "simbolos_esperados")
    c = [
        ("Log completo até #END_PSD", log.completo),
        (f"bordas_CLK = símbolos esperados ({_g(r,'bordas_CLK')} = {esp})", _g(r, "bordas_CLK") == esp),
        (f"amostras = 8 × símbolos ({_g(r,'amostras_processadas')} = 8 × {_g(r,'simbolos_processados')})",
         _g(r, "amostras_processadas") == 8 * _g(r, "simbolos_processados", -1)),
        ("bordas_com_contagem_errada = 0", _g(r, "bordas_com_contagem_errada") == 0),
        ("overrun_processamento = 0 e erro_ADC_overrun = 0",
         _g(r, "overrun_processamento") == 0 and _g(r, "erro_ADC_overrun") == 0),
        ("perda_CLK = 0", _g(r, "perda_CLK") == 0),
        ("aquisicao_valida = 1", _g(r, "aquisicao_valida") == 1),
        ("calibracao_ok = 1 (centros em ordem crescente)", _g(r, "calibracao_ok") == 1),
        ("sincronismo_ok = 1 (48 bits de início corretos)", _g(r, "sincronismo_ok") == 1),
    ]
    return c


def analisar(log: LogRX | str, Vref: float) -> Resultado:
    if isinstance(log, str):
        log = ler_log(log)
    M, r = log.M, log.rep
    q = quadro(M)
    avisos = []
    out = io.StringIO()
    p = lambda *a: print(*a, file=out)
    mV = lambda c: c * Vref / 4095 * 1e3

    if log.train.shape[0] != N_TREINO:
        raise ValueError(f"Treinamento com {log.train.shape[0]} linhas (esperado {N_TREINO}). Log incompleto?")
    if log.psd.shape[0] < 2:
        raise ValueError("Bloco #BEGIN_PSD vazio. Log incompleto?")

    p(f"================ {log.nome} ================")
    p(f"Modulação PAM-{M} | canal: {r.get('canal')} | aquisição válida = {r.get('aquisicao_valida')} "
      f"| sincronismo = {r.get('sincronismo_ok')}")
    p(f"Bordas de CLK = {r.get('bordas_CLK')} de {r.get('simbolos_esperados')} ; amostras = "
      f"{r.get('amostras_processadas')} (= 8 x {r.get('simbolos_processados')}) ; descartadas antes do CLK = "
      f"{r.get('amostras_descartadas_antes_CLK')}")

    a = log.train[:, 2:10]
    if np.any(log.train[:, 1].astype(int) != q.nivel[:N_TREINO]):
        avisos.append("Níveis do treinamento no log não batem com o quadro esperado!")
    R = detectores(a, M)

    p("\n-- Filtro casado (Seção 4.5.1) --")
    p(f"b_c = {R.bc:.2f} códigos ({mV(R.bc):.1f} mV)")
    p("p_c[k] = [" + " ".join(f"{v:.1f}" for v in R.pc) + "] códigos")
    p(f"E_c = {R.Ec:.4g}")
    p("ISI no 1º zero depois de A = [" + " ".join(f"{v:.1f}" for v in R.isi) + "] códigos")
    if "p_c" in r and len(r["p_c"]) == 8:
        dpc = np.max(np.abs(R.pc - np.array(r["p_c"], dtype=float)))
        p(f"conferência com o firmware: max|Δp_c| = {dpc:.3g}, k* firmware = {r.get('k_estrela')}, "
          f"k* Python = {R.kstar}")
        if r.get("k_estrela") != R.kstar:
            avisos.append("k* do firmware difere do recalculado (empate? Dupont tem k* indefinido).")

    p("\n-- Escolha de k* (Seção 4.3) --")
    for k in range(8):
        p(f"  k={k}  t={TK_US[k]:5.2f} us  menor separação = {R.sep_k[k]:5.0f} códigos "
          f"({mV(R.sep_k[k]):7.1f} mV){'  <== k*' if k == R.kstar else ''}")

    p("\n-- Centros, limiares, margens (Seção 4.5.2) --")
    p("centros u (códigos) = " + str(np.round(R.cen_u, 1).tolist()) +
      " ; em V = " + str(np.round(R.cen_u * Vref / 4095, 3).tolist()))
    p("limiares u (códigos) = " + str(np.round(R.thr_u, 1).tolist()) +
      " ; em V = " + str(np.round(R.thr_u * Vref / 4095, 3).tolist()))
    p("centros z = " + str(np.round(R.cen_z, 4).tolist()) + " ; limiares z = " + str(np.round(R.thr_z, 4).tolist()))
    par = f"par de níveis {R.marg_u_par[0]}-{R.marg_u_par[1]}"
    if M == 4:
        par += f", Gray {GRAY[R.marg_u_par[0]]}/{GRAY[R.marg_u_par[1]]}"
    p(f"margem amostra única = {R.marg_u:.0f} códigos = {mV(R.marg_u):.1f} mV ({par})")
    p(f"margem filtro casado = {R.marg_z:.4f} (escala z; par {R.marg_z_par[0]}-{R.marg_z_par[1]})")
    p(f"margem relativa (margem / distância média entre centros): u = "
      f"{R.marg_u / np.mean(np.diff(R.cen_u)):.2f} , z = {R.marg_z / np.mean(np.diff(R.cen_z)):.2f}")

    # ---- olho do payload ----
    ap = log.psd[:, 2:10]
    lp = log.psd[:, 1].astype(int)
    ab = np.zeros(8)
    for k in range(8):
        s = math.inf
        for l in range(M - 1):
            hi, lo = ap[lp == l + 1, k], ap[lp == l, k]
            if hi.size and lo.size:
                s = min(s, hi.min() - lo.max())
        ab[k] = s
    abertura_V = ab[R.kstar] * Vref / 4095
    p(f"\n-- Olho ({ap.shape[0]} símbolos do payload) --")
    p(f"abertura vertical em t_k* = {TK_US[R.kstar]:.2f} us: {abertura_V:.3f} V (menor entre níveis vizinhos)")
    p("abertura por k (V) = " + str(np.round(ab * Vref / 4095, 3).tolist()))
    # confere níveis do bloco PSD com a PRBS esperada
    i0 = q.i_pay[0] + PSD_START_SYM
    esperado = q.nivel[i0: i0 + len(lp)]
    if len(esperado) == len(lp) and np.any(esperado != lp):
        avisos.append("Níveis do bloco PSD diferem da PRBS-15 esperada.")

    # ---- PSD ----
    S, f, info = psd_welch(ap.ravel(), Vref)
    canal_teo = canal_do_rotulo(r.get("canal", ""))
    Sth = psd_teorica(f, M, canal_teo, Vref)
    S5, S10 = float(np.interp(5e3, f, S)), float(np.interp(10e3, f, S))
    S5m, S10m = media_bins(S, f, 5e3, info["df"]), media_bins(S, f, 10e3, info["df"])
    p(f"\n-- PSD (fa = 160 kHz, Vref = {Vref:.4f} V, média retirada, Hann, N = 1024, 50%, "
      f"{info['nblocos']} blocos) --")
    p(f"resolução = {info['df']:.2f} Hz ; duração do registro = {info['duracao_s'] * 1e3:.1f} ms ; "
      f"potência AC = {info['Pmedia_V2']:.4f} V^2 (var = {info['var_x']:.4f})")
    p(f"S(5 kHz)  = {S5:.3e} V^2/Hz (média de 5 bins {S5m:.3e}; teoria {np.interp(5e3, f, Sth):.3e})")
    p(f"S(10 kHz) = {S10:.3e} V^2/Hz (média de 5 bins {S10m:.3e}; teoria {np.interp(10e3, f, Sth):.3e})")

    # ---- BER ----
    p("\n-- Contagem de erros (firmware, mesmas amostras do payload) --")
    if "amostra_unica_Ne" in r:
        pb, ps = r["payload_bits"], r["payload_simbolos"]
        for nome, ne, ns in (("amostra única", r["amostra_unica_Ne"], r["amostra_unica_Ns"]),
                             ("filtro casado", r["filtro_casado_Ne"], r["filtro_casado_Ns"])):
            p(f"{nome}: Ne = {ne} em {pb} bits -> BER = {ne / pb:.2e} ; Ns = {ns} em {ps} -> SER = {ns / ps:.2e}")
        if r["amostra_unica_Ne"] == 0:
            p('  -> escrever "0 erros em 100.000 bits" (BER observada = 0, NÃO prova BER física nula;')
            p("     com 0 erros, limite superior de 95% ~ 3/100000 = 3e-5).")
    else:
        p("SEM BER: quadro inválido ou sem sincronismo -> repetir o ensaio.")

    # ---- janela real ----
    if "janela_a" in r:
        ja = np.array(r["janela_a"], dtype=float)
        x = ja - R.bc
        p(f"\n-- Janela real (símbolo j = {r.get('janela_exemplo_j')}, nível TX = "
          f"{r.get('janela_exemplo_nivel_TX')}) --")
        p("  k   a[k]    x[k]=a-b_c    p_c[k]       p_c*x")
        for k in range(8):
            p(f"  {k}  {int(ja[k]):5d}  {x[k]:10.2f}  {R.pc[k]:10.2f}  {R.pc[k] * x[k]:12.1f}")
        soma = float(np.sum(R.pc * x))
        p(f"  soma = {soma:.1f} ; E_c = {R.Ec:.1f} ; z = soma/E_c = {soma / R.Ec:.5f} "
          f"(firmware: {r.get('janela_z')})")

    checks = verificacoes(log)
    if avisos:
        p("\n-- AVISOS --")
        for av in avisos:
            p("  ! " + av)
    valido = r.get("aquisicao_valida") == 1 and r.get("sincronismo_ok") == 1
    return Resultado(log, R, Vref, out.getvalue(), abertura_V, ab * Vref / 4095, S, f, Sth,
                     S5, S10, S5m, S10m, valido, avisos, checks)


# ----------------------------------------------------------------------------
# Figuras
# ----------------------------------------------------------------------------
def figura_analise(res: Resultado, fig: Figure | None = None) -> Figure:
    fig = fig or Figure(figsize=(13, 8.5), dpi=100)
    fig.clf()
    log, R, Vref, M = res.log, res.R, res.Vref, res.log.M
    q = quadro(M)
    fig.suptitle(f"{log.nome} — PAM-{M} — {log.rep.get('canal')}")
    ax = fig.subplots(2, 2)

    # 1) pulso e ISI
    a1 = ax[0, 0]
    a1.stem(TK_US, R.pc * Vref / 4095, basefmt=" ", label="p_c[k] (símbolo A)")
    m2 = a1.stem(TK_US + 50, R.isi * Vref / 4095, linefmt="r-", markerfmt="ro", basefmt=" ",
                 label="1º zero depois de A (ISI)")
    a1.axvline(50, color="k", ls=":")
    a1.set_xlabel("tempo após a borda do CLK (µs)")
    a1.set_ylabel("V acima da linha de base")
    a1.set_title("Pulso medido e ISI")
    a1.legend(fontsize=8)
    a1.grid(True, alpha=.3)

    # 2) olho
    a2 = ax[0, 1]
    v = log.psd[:, 2:10] * Vref / 4095
    lv = log.psd[:, 1].astype(int)
    tt = np.concatenate([TK_US, TK_US + 50])
    for l in range(M):
        jj = np.where(lv[:-1] == l)[0]
        if jj.size == 0:
            continue
        yy = np.hstack([v[jj], v[jj + 1]])
        a2.plot(np.tile(tt, (len(jj), 1)).ravel(), yy.ravel(), ".", ms=2.5, color=CORES[l],
                label=f"nível {l}")
    tks = TK_US[R.kstar]
    for xx in (tks, tks + 50):
        a2.axvline(xx, color="r", lw=1.5)
    a2.text(tks + 0.5, -0.05, f"k* = {R.kstar} ({tks:.2f} µs)", color="r", fontsize=8, va="bottom")
    a2.axvline(50, color="k", ls=":")
    a2.set_xlim(0, 100)
    a2.set_ylim(-0.1, Vref + 0.1)
    a2.set_xlabel("tempo após a borda do CLK (µs)")
    a2.set_ylabel("tensão no ADC (V)")
    a2.set_title(f"Olho: abertura em t_k* = {res.abertura_V:.3f} V")
    a2.grid(True, alpha=.3)
    a2.legend(fontsize=7, loc="center right", markerscale=3)

    # 3) amostra única na calibração
    a3 = ax[1, 0]
    il = np.arange(N_PULSO, N_TREINO)
    nv = q.nivel[il]
    for l in range(M):
        jj = il[nv == l]
        a3.plot(jj, R.u[jj] * Vref / 4095, ".", color=CORES[l], ms=5, label=f"nível {l}")
    for t in R.thr_u:
        a3.axhline(t * Vref / 4095, color="k", ls="--", lw=1)
    a3.set_xlabel("símbolo j da calibração (140..395)")
    a3.set_ylabel(f"u = a[k*={R.kstar}] (V)")
    a3.set_title(f"Amostra única na calibração: margem {R.marg_u * Vref / 4095 * 1e3:.1f} mV")
    a3.legend(fontsize=7, loc="center left", bbox_to_anchor=(1, .5))
    a3.grid(True, alpha=.3)

    # 4) PSD
    a4 = ax[1, 1]
    with np.errstate(divide="ignore"):
        a4.plot(res.f / 1e3, 10 * np.log10(res.S), "b", label="medida")
        a4.plot(res.f / 1e3, 10 * np.log10(res.Sth), "k--",
                label=f"teoria ({canal_do_rotulo(log.rep.get('canal', ''))})")
    for xx in (5, 10):
        a4.axvline(xx, color="r", ls=":")
    a4.set_xlim(0, 80)
    a4.set_ylim(-110, -30)
    a4.set_xlabel("f (kHz)")
    a4.set_ylabel("S(f) (dB re 1 V²/Hz)")
    a4.set_title(f"PSD: S(5k)={res.S5:.2e}, S(10k)={res.S10:.2e} V²/Hz")
    a4.legend(fontsize=8, loc="lower left")
    a4.grid(True, alpha=.3)
    fig.tight_layout()
    return fig


def figura_z(res: Resultado, fig: Figure | None = None) -> Figure:
    fig = fig or Figure(figsize=(8, 4.2), dpi=100)
    fig.clf()
    ax = fig.add_subplot(111)
    R, M = res.R, res.log.M
    q = quadro(M)
    il = np.arange(N_PULSO, N_TREINO)
    nv = q.nivel[il]
    for l in range(M):
        jj = il[nv == l]
        ax.plot(jj, R.z[jj], ".", color=CORES[l], ms=5, label=f"nível {l}")
    for t in R.thr_z:
        ax.axhline(t, color="k", ls="--", lw=1)
    ax.set_xlabel("símbolo j da calibração")
    ax.set_ylabel("z_c,j (adimensional)")
    ax.set_title(f"Filtro casado: margem {R.marg_z:.4f} (escala z)")
    ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1, .5))
    ax.grid(True, alpha=.3)
    fig.tight_layout()
    return fig


def salvar_figuras(res: Resultado, pasta: str) -> list[str]:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    os.makedirs(pasta, exist_ok=True)
    saidas = []
    for fig, suf in ((figura_analise(res), ""), (figura_z(res), "_z")):
        FigureCanvasAgg(fig)
        cam = os.path.join(pasta, f"{res.log.nome}{suf}.png")
        fig.savefig(cam, dpi=120)
        saidas.append(cam)
    return saidas


# ----------------------------------------------------------------------------
# Comparação de PSD entre canais (questão 1 da defesa)
# ----------------------------------------------------------------------------
def comparar_psd(arq_dupont: str, arq_rc: str, Vref: float, tau_med_us: float = math.nan,
                 fig: Figure | None = None):
    A, B = ler_log(arq_dupont), ler_log(arq_rc)
    Sa, f, info = psd_welch(A.psd[:, 2:10].ravel(), Vref)
    Sb, _, _ = psd_welch(B.psd[:, 2:10].ravel(), Vref)
    canal_rc = canal_do_rotulo(B.rep.get("canal", "rc"))
    if canal_rc == "dupont":
        canal_rc = "rc"
    Prc, Pdu = parametros_canal(canal_rc), parametros_canal("dupont")
    tau_nom = Prc["tau_nominal"]
    Hnom1 = lambda ff: 1 / (1 + (2 * np.pi * ff * tau_nom) ** 2)
    Hmed = lambda ff: 1 / (1 + (2 * np.pi * ff * tau_med_us * 1e-6) ** 2)
    out = io.StringIO()
    p = lambda *a: print(*a, file=out)
    if A.M != B.M:
        p(f"ATENÇÃO: modulações diferentes (PAM-{A.M} × PAM-{B.M}) — compare a mesma modulação!")
    p(f"PSD: fa = 160 kHz, Hann, N = 1024 ({info['df']:.2f} Hz/bin), 50%, {info['nblocos']} blocos, "
      f"{info['duracao_s'] * 1e3:.1f} ms de registro")
    p(f"Canal RC identificado: {canal_rc} (τ nominal 1 polo = {tau_nom * 1e6:.2f} µs)")
    p(" f (kHz) | S_Dupont (V²/Hz) | S_RC (V²/Hz) | razão RC/Dup |   dB   | |H|² 1 polo | |H|² 2 polos | |H|² τ medido")
    linhas = []
    for fx in (5e3, 10e3):
        sa, sb = media_bins(Sa, f, fx, info["df"]), media_bins(Sb, f, fx, info["df"])
        h2p = H2(fx, Prc["den"]) / H2(fx, Pdu["den"])
        hm = Hmed(fx) if not math.isnan(tau_med_us) else math.nan
        p(f"  {fx / 1e3:5.1f}  |   {sa:.3e}      |  {sb:.3e}   |    {sb / sa:.3f}     | {10 * math.log10(sb / sa):6.2f} |"
          f"    {Hnom1(fx):.3f}    |    {h2p:.3f}     |    {hm:.3f}")
        linhas.append((fx, sa, sb, sb / sa, Hnom1(fx), h2p, hm))
    p("(valores = média de 5 bins em torno da frequência)")
    p("\nLeitura: para sistema LIT, S_y = |H|² S_x. Como os dois blocos começam no mesmo símbolo")
    p("do payload (nº 1000), os bits são os mesmos e a razão das PSDs estima |H_RC(f)|².")

    fig = fig or Figure(figsize=(11, 4.4), dpi=100)
    fig.clf()
    a1, a2 = fig.subplots(1, 2)
    with np.errstate(divide="ignore"):
        a1.plot(f / 1e3, 10 * np.log10(Sa), label="Dupont")
        a1.plot(f / 1e3, 10 * np.log10(Sb), label=B.rep.get("canal", "RC"))
        a2.plot(f / 1e3, 10 * np.log10(Sb / Sa), "b", label="S_RC/S_Dupont medido")
        a2.plot(f / 1e3, 10 * np.log10(Hnom1(f)), "k--", label=f"|H|², τ = {tau_nom * 1e6:.2f} µs")
        if not math.isnan(tau_med_us):
            a2.plot(f / 1e3, 10 * np.log10(Hmed(f)), "r--", label=f"|H|², τ medido = {tau_med_us:.2f} µs")
    for a in (a1, a2):
        for xx in (5, 10):
            a.axvline(xx, color="k", ls=":")
        a.grid(True, alpha=.3)
        a.set_xlabel("f (kHz)")
    a1.set_xlim(0, 80)
    a1.set_ylabel("dB V²/Hz")
    a1.set_title(f"PSD PAM-{A.M} (mesma escala)")
    a1.legend(fontsize=8)
    a2.set_xlim(0, 40)
    a2.set_ylim(-15, 3)
    a2.set_ylabel("dB")
    a2.set_title("Razão das PSDs = |H_RC(f)|²")
    a2.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    return out.getvalue(), fig, linhas


# ----------------------------------------------------------------------------
# τ a partir do CSV do osciloscópio (tau_osciloscopio.m)
# ----------------------------------------------------------------------------
def ler_csv_osc(caminho: str):
    """TDS2002B: 'rótulo,valor,,tempo,tensão' (colunas 4 e 5). Também aceita 2 colunas."""
    t, v = [], []
    with open(caminho, "r", encoding="utf-8", errors="replace") as fh:
        for row in csv.reader(fh):
            nums = []
            for c in row:
                try:
                    nums.append(float(c))
                except ValueError:
                    nums.append(None)
            if len(nums) >= 5 and nums[3] is not None and nums[4] is not None:
                t.append(nums[3]); v.append(nums[4])
            else:
                vals = [x for x in nums if x is not None]
                if len(vals) == 2 and len(row) <= 3:
                    t.append(vals[0]); v.append(vals[1])
    return np.array(t), np.array(v)


def _movmean(v, n=5):
    h = n // 2
    c = np.concatenate([[0], np.cumsum(v)])
    i = np.arange(len(v))
    lo, hi = np.maximum(0, i - h), np.minimum(len(v), i + h + 1)
    return (c[hi] - c[lo]) / (hi - lo)


def tau_csv(caminho: str, t0_manual: float | None = None, fig: Figure | None = None):
    t, v = ler_csv_osc(caminho)
    if len(t) < 20:
        raise ValueError("CSV sem dados de tempo/tensão reconhecíveis.")
    v = _movmean(v, 5)
    n = len(v)
    V0 = float(np.median(v[: round(0.1 * n)]))
    Vf = float(np.median(v[round(0.85 * n) - 1:]))
    dV = Vf - V0

    def cruza(pct):
        idx = np.where(v >= V0 + pct * dV)[0] if dV > 0 else np.where(v <= V0 + pct * dV)[0]
        return float(t[idx[0]]) if idx.size else math.nan

    t0 = cruza(0.02) if t0_manual is None else t0_manual
    t10, t63, t90 = cruza(0.10), cruza(0.632), cruza(0.90)
    tau, tr = t63 - t0, t90 - t10
    txt = (f"V0 = {V0:.3f} V, Vf = {Vf:.3f} V, ΔV = {dV:.3f} V, V63 = {V0 + 0.632 * dV:.3f} V\n"
           f"t0 = {t0 * 1e6:.2f} us, t10 = {t10 * 1e6:.2f} us, t63 = {t63 * 1e6:.2f} us, t90 = {t90 * 1e6:.2f} us\n"
           f"τ (63,2 %) = {tau * 1e6:.2f} us ; t10-90 = {tr * 1e6:.2f} us ; t10-90/2,197 = {tr / 2.197 * 1e6:.2f} us\n"
           f"f_c = 1/(2πτ) = {1 / (2 * math.pi * tau) / 1e3:.2f} kHz\n")
    fig = fig or Figure(figsize=(8, 4.5), dpi=100)
    fig.clf()
    ax = fig.add_subplot(111)
    ax.plot(t * 1e6, v, "b")
    for yy in (V0, V0 + .1 * dV, V0 + .632 * dV, V0 + .9 * dV, Vf):
        ax.axhline(yy, color="gray", ls=":")
    for xx, lab in ((t0, "t0"), (t10, "t10"), (t63, "t63"), (t90, "t90")):
        ax.axvline(xx * 1e6, color="r", ls=":")
        ax.text(xx * 1e6, Vf, lab, color="r", fontsize=8)
    ax.set_xlabel("t (µs)")
    ax.set_ylabel("V")
    ax.set_title(f"τ = {tau * 1e6:.2f} µs, t10-90 = {tr * 1e6:.2f} µs")
    ax.grid(True, alpha=.3)
    fig.tight_layout()
    return tau * 1e6, tr * 1e6, txt, fig


# ----------------------------------------------------------------------------
# Tabela da Seção 5.1
# ----------------------------------------------------------------------------
def tabela(arquivos: list[str], Vref: float, taus_us: list[float] | None = None,
           csv_saida: str | None = None) -> str:
    taus_us = taus_us or [math.nan] * len(arquivos)
    md = ["| Canal | PAM | Abertura (V) | τ (µs) | k* (t) | Erros amostra; BER | Erros filtro; BER |",
          "|---|---|---|---|---|---|---|"]
    linhas_csv = []
    for arq, tau in zip(arquivos, taus_us):
        res = analisar(arq, Vref)
        d = res.tabela_linha
        if res.valido and not math.isnan(d["Ne_u"]):
            su = f"{d['Ne_u']}; {d['Ne_u'] / d['bits']:.2g}"
            sz = f"{d['Ne_z']}; {d['Ne_z'] / d['bits']:.2g}"
        else:
            su = sz = "sem sincronismo"
        taus = "—" if math.isnan(tau) else f"{tau:.2f}"
        md.append(f"| {d['canal']} | {d['PAM']} | {d['abertura_V']:.3f} | {taus} | {d['kstar']} "
                  f"({d['t_kstar_us']:.2f} µs) | {su} | {sz} |")
        bits, syms = d["bits"], d["syms"]
        linhas_csv.append([d["canal"], d["PAM"], f"{d['abertura_V']:.4f}", f"{tau:.3f}", d["kstar"],
                           f"{d['t_kstar_us']:.2f}", d["Ne_u"], d["Ne_u"] / bits, d["Ne_z"], d["Ne_z"] / bits,
                           d["Ns_u"], d["Ns_u"] / syms, d["Ns_z"], d["Ns_z"] / syms,
                           f"{d['marg_u_mV']:.1f}", f"{d['marg_z']:.5f}", f"{d['S5']:.4e}", f"{d['S10']:.4e}"])
    if csv_saida:
        os.makedirs(os.path.dirname(os.path.abspath(csv_saida)), exist_ok=True)
        with open(csv_saida, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["canal", "PAM", "abertura_V", "tau_us", "kstar", "t_kstar_us", "Ne_amostra",
                        "BER_amostra", "Ne_filtro", "BER_filtro", "Ns_amostra", "SER_amostra", "Ns_filtro",
                        "SER_filtro", "margem_u_mV", "margem_z", "S5k_V2Hz", "S10k_V2Hz"])
            w.writerows(linhas_csv)
    return "\n".join(md)
