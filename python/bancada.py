#!/usr/bin/env python3
"""bancada.py — roteiro de bancada automatizado (TDS2002B pelo USB + RX pela serial).

Cada medida = 1 comando + 1 RESET no TX. O script configura o osciloscópio,
espera o quadro, salva tela/CSV/medidas em entrega/capturas/ e anota tudo em
entrega/CADERNO_BANCADA.md (para estudar depois).

  python3 python/bancada.py osc PRESET --canal c --mod 4
  python3 python/bancada.py ensaio --canal c --mod 4 [--vref 3.297]   (log serial + olho no mesmo RESET)

PRESETS (pontas):
  clk        CH1=TP2  CH2=CLK   período/duty do CLK
  niveis     CH1=TP2  CH2=CLK   início do treinamento de níveis (ordem Gray no PAM-4) + níveis medidos
  alinhamento CH1=TP2 CH2=CLK   atraso CLK -> transição de TP2 (persistência)
  ripple     CH1=TP2  CH2=CLK   ripple do PWM no nível 1 (zoom 50 ns/div)
  olho       CH1=TP3  CH2=CLK   olho com persistência infinita
  degrau     CH1=TP2  CH2=TP3   1º pulso 0->A do treinamento: entrada x saída do canal, τ e t10-90
"""
import argparse
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
from captura_tds import TDS, ler_canal, ler_tela  # noqa: E402

CAPT = os.path.join(RAIZ, "entrega", "capturas")
CADERNO = os.path.join(RAIZ, "entrega", "CADERNO_BANCADA.md")
NOME_CANAL = {"d": "Dupont", "c": "RC16n8", "x": "RC33n", "m": "Manga", "-": "TX"}
TS = 50e-6
D_NIVEIS = 140 * TS          # disparo na 1ª borda do CLK = início do símbolo 0; níveis começam no 140

COMUM = ["HEADER OFF", "CH1:PROBE 10", "CH2:PROBE 10", "CH1:COUPLING DC", "CH2:COUPLING DC", "SELECT:CH1 ON", "SELECT:CH2 ON",
         "ACQUIRE:MODE SAMPLE", "TRIGGER:MAIN:TYPE EDGE", "TRIGGER:MAIN:EDGE:SLOPE RISE",
         "TRIGGER:MAIN:EDGE:COUPLING DC", "TRIGGER:MAIN:MODE NORMAL"]

# cada preset: comandos, modo ('single' | 'persist' | 'run'), pontas, explicação
PRESETS = {
    "clk": dict(cmd=["CH1:SCALE 1", "CH1:POSITION -3.5", "CH2:SCALE 1", "CH2:POSITION 0.5",
                     "TRIGGER:MAIN:EDGE:SOURCE CH2", "TRIGGER:MAIN:LEVEL 1.6",
                     "HORIZONTAL:MAIN:SCALE 10E-6", "HORIZONTAL:MAIN:POSITION 40E-6"],
                modo="run", pontas="CH1 = TP2 · CH2 = CLK (PB4)",
                oque="Período e duty do CLK (previsto 50,0 µs / 20 kHz / 50 %)."),
    "niveis": dict(cmd=["CH1:SCALE 1", "CH1:POSITION -3.5", "CH2:SCALE 2", "CH2:POSITION 1",
                        "TRIGGER:MAIN:EDGE:SOURCE CH2", "TRIGGER:MAIN:LEVEL 1.6",
                        "HORIZONTAL:MAIN:SCALE 50E-6",
                        f"HORIZONTAL:MAIN:POSITION {D_NIVEIS - 0.5*TS + 250e-6:.6E}"],
                   modo="single", pontas="CH1 = TP2 · CH2 = CLK",
                   oque="Símbolos 140–149 = início do treinamento de níveis. PAM-4: 0,1,0,3,2,3,1,2,0,1 "
                        "(ordem Gray); PAM-2: 0,1,0,0,1,1,0,1,0,1. Níveis previstos 0/1,1/2,2/3,3 V."),
    "alinhamento": dict(cmd=["CH1:SCALE 1", "CH1:POSITION -3.5", "CH2:SCALE 1", "CH2:POSITION 0.5",
                             "TRIGGER:MAIN:EDGE:SOURCE CH2", "TRIGGER:MAIN:LEVEL 1.6",
                             "HORIZONTAL:MAIN:SCALE 250E-9", "HORIZONTAL:MAIN:POSITION 750E-9"],
                        modo="persist", pontas="CH1 = TP2 · CH2 = CLK",
                        oque="Atraso entre a subida do CLK e o início da transição de TP2 "
                             "(previsto 0,2–0,4 µs = latência da ISR do TIM3)."),
    "ripple": dict(cmd=["CH1:SCALE 0.05", "CH1:POSITION -22", "CH2:SCALE 2", "CH2:POSITION 1",
                        "TRIGGER:MAIN:EDGE:SOURCE CH2", "TRIGGER:MAIN:LEVEL 1.6",
                        "HORIZONTAL:MAIN:SCALE 50E-9",
                        f"HORIZONTAL:MAIN:POSITION {D_NIVEIS + 1.5*TS:.6E}"],
                   modo="single", pontas="CH1 = TP2 · CH2 = CLK",
                   oque="Ripple do PWM em TP2 no meio do símbolo 141 (nível 1). Previsto ≈ 150 mVpp."),
    "olho": dict(cmd=["CH1:SCALE 1", "CH1:POSITION -3.5", "CH2:SCALE 1", "CH2:POSITION 0",
                      "TRIGGER:MAIN:EDGE:SOURCE CH2", "TRIGGER:MAIN:LEVEL 1.6",
                      "HORIZONTAL:MAIN:SCALE 10E-6", "HORIZONTAL:MAIN:POSITION 40E-6"],
                 modo="persist", pontas="CH1 = TP3 · CH2 = CLK",
                 oque="Diagrama de olho em TP3, disparo na subida do CLK, persistência infinita. "
                      "k* = 7 ↔ 46,87 µs depois da borda."),
    "diag_clk": dict(cmd=["CH1:SCALE 2", "CH1:POSITION 0.5", "CH2:SCALE 2", "CH2:POSITION -3.5",
                          "TRIGGER:MAIN:TYPE PULSE", "TRIGGER:MAIN:PULSE:SOURCE CH2",
                          "TRIGGER:MAIN:PULSE:WIDTH:POLARITY NEGATIVE", "TRIGGER:MAIN:PULSE:WIDTH:WHEN OUTSIDE",
                          "TRIGGER:MAIN:PULSE:WIDTH:WIDTH 100E-6", "TRIGGER:MAIN:LEVEL 1.6",
                          "HORIZONTAL:MAIN:SCALE 1E-3", "HORIZONTAL:MAIN:POSITION -4E-3"],
                     modo="single", pontas="CH1 = CLK no PB4 (saída do TX) · CH2 = CLK no PA0 (entrada do RX)",
                     oque="Caça à falha de CLK: dispara só se o CLK no PA0 ficar em nível baixo > 100 µs e VOLTAR "
                          "(o fim normal do quadro não dispara). Mostra ~9 ms antes da volta: se o CH1 continuou "
                          "pulsando enquanto o CH2 parou → mau contato no fio/GND; se os dois pararam → o TX travou."),
    "degrau_zoom": dict(cmd=["CH1:SCALE 1", "CH1:POSITION -3.5", "CH2:SCALE 1", "CH2:POSITION -3.5",
                             "TRIGGER:MAIN:EDGE:SOURCE CH1", "TRIGGER:MAIN:LEVEL 1.6",
                             "HORIZONTAL:MAIN:SCALE 250E-9", "HORIZONTAL:MAIN:POSITION 750E-9"],
                        modo="single", pontas="CH1 = TP2 · CH2 = TP3",
                        oque="Zoom (250 ns/div) na 1ª subida 0→A do quadro — para canais rápidos (Dupont), "
                             "onde τ ≈ 0,1 µs não se resolve a 25 µs/div."),
    "degrau": dict(cmd=["CH1:SCALE 1", "CH1:POSITION -3.5", "CH2:SCALE 1", "CH2:POSITION -3.5",
                        "TRIGGER:MAIN:EDGE:SOURCE CH1", "TRIGGER:MAIN:LEVEL 1.6",
                        "HORIZONTAL:MAIN:SCALE 20E-6", "HORIZONTAL:MAIN:POSITION 80E-6"],
                   modo="single", pontas="CH1 = TP2 · CH2 = TP3",
                   oque="1º pulso 0→A do treinamento (A dura 1 símbolo): entrada (TP2) × saída (TP3). "
                        "τ por t63 e t10-90; resíduo no zero seguinte = ISI."),
}


# ---------------------------------------------------------------------------
def medir(sc, ch, tipo):
    sc.write(f"MEASUREMENT:IMMED:SOURCE {ch}")
    sc.write(f"MEASUREMENT:IMMED:TYPE {tipo}")
    v = float(sc.query("MEASUREMENT:IMMED:VALUE?"))
    return None if abs(v) > 1e30 else v


def armar(sc, p):
    sc.write("ACQUIRE:STATE STOP")
    time.sleep(0.2)
    for c in COMUM + p["cmd"]:
        sc.write(c)
    sc.write("DISPLAY:PERSISTENCE OFF")
    time.sleep(0.3)
    if p["modo"] == "persist":
        sc.write("DISPLAY:PERSISTENCE INF")
    sc.write("ACQUIRE:STOPAFTER " + ("SEQUENCE" if p["modo"] == "single" else "RUNSTOP"))
    sc.write("ACQUIRE:STATE RUN")


def esperar(sc, p, limite=600, parar=None):
    n = lambda: int(float(sc.query("ACQUIRE:NUMACQ?")))
    t0 = time.time()
    while n() == 0:
        if parar and parar():
            return 0
        if time.time() - t0 > limite:
            raise TimeoutError("nenhum disparo (o TX foi resetado? as pontas estão certas?)")
        time.sleep(0.4)
    if p["modo"] == "single":
        time.sleep(0.5)
        return 1
    if p["modo"] == "run":            # pega uma aquisição no meio do quadro
        time.sleep(1.0)
        sc.write("ACQUIRE:STATE STOP")
        return n()
    ult, tult = n(), time.time()       # persist: acumula até o quadro acabar
    while time.time() - tult < 3:
        time.sleep(0.5)
        a = n()
        if a != ult:
            ult, tult = a, time.time()
    sc.write("ACQUIRE:STATE STOP")
    return ult


def salvar(sc, nome):
    os.makedirs(CAPT, exist_ok=True)
    base = os.path.join(CAPT, nome)
    dados = {}
    for ch in ("CH1", "CH2"):
        t, v = ler_canal(sc, ch)
        dados[ch] = (t, v)
        np.savetxt(f"{base}_{ch}.csv", np.column_stack([t, v]), delimiter=",",
                   header="tempo_s,tensao_V", comments="", fmt="%.9e")
    bmp = ler_tela(sc)
    from PIL import Image
    open(base + "_tela.bmp", "wb").write(bmp)
    im = Image.open(base + "_tela.bmp")
    im.save(base + "_tela.png")
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(base + "_tela_3x.png")
    os.remove(base + "_tela.bmp")
    return base, dados


# ---------------------------------------------------------------------------
def analise_degrau(t1, v1, t2, v2):
    """1º pulso 0->A do treinamento (A dura 1 símbolo, depois zeros)."""
    L = []
    pre = t1 < t1[0] + 0.05 * (t1[-1] - t1[0])        # 5 % iniciais da tela = linha de base
    V01, V02 = float(np.median(v1[pre])), float(np.median(v2[pre]))
    acima = (v1 - V01 > 0.25).astype(int)              # TX comuta: TP2 sai da linha de base
    sust = np.convolve(acima, np.ones(5, int), mode='full')[4:]   # 5 amostras seguidas (ignora picos)
    i0 = int(np.argmax(sust == 5))
    t0 = t1[i0]
    rel = lambda t, a, b: (t >= t0 + a * TS) & (t < t0 + b * TS)
    rapido = (t1[-1] - t0) < 1.2 * TS
    if rapido:                                        # zoom: janela ≪ 1 símbolo
        jan = t1[-1] - t0
        rel = lambda t, a, b: (t >= t0 + a * jan) & (t < t0 + b * jan)
    Vf = float(np.mean(v1[rel(t1, 0.80, 0.95)]))      # TP2 no fim da janela/símbolo ≈ nível do TX
    salto = float(np.max(v1[(t1 >= t0) & (t1 < t0 + 0.4e-6)])) - V01
    vs = np.convolve(v2, np.ones(3 if rapido else 9) / (3 if rapido else 9), mode="same")
    s = rel(t2, 0, 1)
    tt, vv = t2[s] - t0, vs[s]
    def cruza(p):
        alvo = V02 + p * (Vf - V02)
        i = int(np.argmax(vv >= alvo))
        return tt[i] if vv[i] >= alvo else np.nan
    t10, t63, t90 = cruza(0.1), cruza(0.632), cruza(0.9)
    tau = t63
    fimA = float(np.mean(v2[rel(t2, 0.90, 0.97)]))
    L.append(f"t0 = início da transição do TX (TP2 sai da linha de base) = {t0*1e6:.2f} µs na tela")
    L.append(f"TP2: {V01:.3f} → {Vf:.3f} V; **salto instantâneo em TP2 = {salto:.2f} V "
             f"({100*salto/(Vf-V01):.0f} % do degrau)** — divisor 56/(330+56+R_GPIO) ≈ 14 % no RC; ≈ 100 % no Dupont")
    L.append(f"TP3: V0 = {V02:.3f} V, Vf (=TP2 final) = {Vf:.3f} V, no instante k* (46,9 µs após t0) = {fimA:.3f} V "
             f"({100*(fimA-V02)/(Vf-V02):.1f} % do degrau)")
    L.append(f"t10 = {t10*1e6:.2f} µs · t63 = {t63*1e6:.2f} µs · t90 = {t90*1e6:.2f} µs (medidos a partir de t0)")
    L.append(f"**τ = t63 − t0 = {tau*1e6:.2f} µs** · **t10-90 = {(t90-t10)*1e6:.2f} µs** "
             f"(→ τ = t10-90/2,197 = {(t90-t10)/2.197*1e6:.2f} µs) · f_c = 1/(2πτ) = {1/(2*np.pi*tau)/1e3:.1f} kHz")
    z = rel(t2, 1.90, 1.98)
    if z.any():
        res = float(np.mean(v2[z])) - V02
        prev = (Vf - V02) * (1 - np.exp(-TS / tau)) * np.exp(-TS / tau)
        L.append(f"ISI: resíduo em TP3 no fim do 1º zero depois de A = {res*1e3:+.0f} mV "
                 f"(previsto A·(1−e^(−Ts/τ))·e^(−Ts/τ) = {prev*1e3:.0f} mV; resolução do osciloscópio ≈ 40 mV a 1 V/div)")
    return L


def analise(preset, dados, M, sc):
    """Devolve linhas de texto com as medidas do preset."""
    t1, v1 = dados["CH1"]
    t2, v2 = dados["CH2"]
    L = []
    if preset == "clk":
        f = medir(sc, "CH2", "FREQ"); T = medir(sc, "CH2", "PERIOD")
        pw = medir(sc, "CH2", "PWIDTH"); vpp = medir(sc, "CH2", "PK2PK")
        L.append(f"CLK: f = {f/1e3:.4f} kHz, T = {T*1e6:.3f} µs, largura alta = {pw*1e6:.3f} µs "
                 f"→ duty = {100*pw/T:.1f} %, Vpp = {vpp:.2f} V")
    elif preset in ("niveis", "ripple"):
        tc = t1 - t1[0]
        if preset == "niveis":
            pat = [0, 1, 0, 3, 2, 3, 1, 2, 0, 1] if M == 4 else [0, 1, 0, 0, 1, 1, 0, 1, 0, 1]
            # o 1º símbolo começa 0,5 símbolo após o início da tela; usa 20–80 % de cada símbolo
            med = []
            for i, nv in enumerate(pat):
                a = (0.5 + i + 0.2) * TS; b = (0.5 + i + 0.8) * TS
                m = (tc >= a) & (tc < b)
                if m.any():
                    med.append((nv, float(np.mean(v1[m]))))
            L.append("Símbolos 140–149 (nível esperado → média medida em TP2):")
            L.append("  " + "  ".join(f"[{nv}] {vm:.3f} V" for nv, vm in med))
            por = {}
            for nv, vm in med:
                por.setdefault(nv, []).append(vm)
            niv = {k: np.mean(v) for k, v in sorted(por.items())}
            L.append("Níveis médios: " + " · ".join(f"{k}: {v:.3f} V" for k, v in niv.items()))
            if len(niv) > 1:
                d = np.diff(list(niv.values()))
                L.append("Degraus entre níveis: " + " · ".join(f"{x:.3f} V" for x in d))
            seq = [nv for nv, _ in med]
            ok = all(abs(vm - niv[nv]) < 0.3 for nv, vm in med)
            L.append(f"Ordem conferida: {seq} → {'OK' if ok else 'CONFERIR na tela'}")
        else:
            L.append(f"Ripple em TP2: Vpp = {np.ptp(v1)*1e3:.0f} mV (min {v1.min():.3f} V, "
                     f"max {v1.max():.3f} V, média {v1.mean():.3f} V)")
    elif preset == "alinhamento":
        antes = v1[t1 < 0]
        ref = np.median(antes) if antes.size else v1[0]
        mud = np.where((t1 > 0) & (np.abs(v1 - ref) > 0.3))[0]
        if mud.size:
            L.append(f"Última aquisição: TP2 começa a mudar {t1[mud[0]]*1e6:.3f} µs após a subida do CLK")
        else:
            L.append("Última aquisição sem transição em TP2 (símbolo igual ao anterior) — use a tela "
                     "com persistência para ler o atraso.")
    elif preset in ("degrau", "degrau_zoom"):
        L += analise_degrau(t1, v1, t2, v2)
        rt = medir(sc, "CH2", "RISE") if sc else None
        if rt:
            L.append(f"Rise Time automático do osciloscópio em TP3: {rt*1e6:.2f} µs (usa min/max da tela inteira — só referência)")
    elif preset == "diag_clk":
        def bordas(t, v):
            b = np.where((v[:-1] < 1.6) & (v[1:] >= 1.6))[0]
            return t[b]
        b1, b2 = bordas(t1, v1), bordas(t2, v2)
        if len(b2) > 1:
            g = np.diff(b2); i = int(np.argmax(g))
            a, z = b2[i], b2[i + 1]
            n1 = int(np.sum((b1 > a) & (b1 < z)))
            L.append(f"No PA0 (RX) o CLK sumiu por **{(z - a)*1e3:.2f} ms** (de {a*1e3:.2f} a {z*1e3:.2f} ms na tela).")
            L.append(f"No PB4 (TX), nesse mesmo intervalo, houve **{n1} bordas** de subida "
                     f"(esperado ≈ {(z - a)/TS:.0f} se o TX continuou).")
            L.append("→ **Diagnóstico: " + ("o TX continuou transmitindo; o CLK se perdeu no caminho PB4→PA0 "
                     "(fio/contato/GND)." if n1 > 0.5 * (z - a) / TS else "o próprio TX parou de gerar o CLK "
                     "(travamento/reset do TX).") + "**")
        else:
            L.append("Não achei o intervalo sem bordas no CH2 — ver a tela.")
    elif preset == "olho":
        L.append("Persistência infinita: ver a tela. A abertura em k* sai do log do RX (ensaio).")
    return L


def caderno(titulo, p, nome, n_acq, linhas, extra=None):
    novo = not os.path.exists(CADERNO)
    with open(CADERNO, "a", encoding="utf-8") as f:
        if novo:
            f.write("# Caderno de bancada — Projeto PAM em banda base\n\n"
                    "Gerado por `python/bancada.py`. Capturas em `entrega/capturas/`, logs em "
                    "`entrega/logs/`, figuras do RX em `entrega/figuras/`.\n\n")
        f.write(f"## {titulo}  ·  {datetime.now():%d/%m/%Y %H:%M}\n\n")
        f.write(f"- **Pontas:** {p['pontas']}\n- **O que é:** {p['oque']}\n")
        f.write(f"- **Aquisições:** {n_acq}\n\n")
        if os.path.exists(os.path.join(CAPT, f"{nome}_tela_3x.png")) and n_acq:
            f.write(f"![{nome}](capturas/{nome}_tela_3x.png)\n\n")
        for L in linhas:
            f.write(f"- {L}\n")
        f.write(f"\nArquivos: `capturas/{nome}_tela.png`, `{nome}_CH1.csv`, `{nome}_CH2.csv`\n\n")
        if extra:
            f.write(extra + "\n\n")


def nome_arquivo(preset, canal, M):
    c = NOME_CANAL[canal]
    if preset in ("clk", "alinhamento"):
        return f"TX_{preset}" if preset == "alinhamento" else "TX_CLK_50us"
    if preset in ("niveis", "ripple"):
        return f"TX_TP2_PAM{M}_{'niveis_gray' if preset == 'niveis' else 'ripple_PWM'}"
    if preset == "olho":
        return f"{c}_PAM{M}_olho_osc"
    if preset == "diag_clk":
        return f"{c}_PAM{M}_diag_CLK"
    return f"{c}_PAM{M}_TP2_TP3_degrau" + ("_zoom" if preset == "degrau_zoom" else "")


def rodar_osc(preset, canal, M, nome=None, antes_de_esperar=None, parar=None):
    p = PRESETS[preset]
    nome = nome or nome_arquivo(preset, canal, M)
    sc = TDS()
    if antes_de_esperar:          # 1º o RX (pode levar alguns s), SÓ DEPOIS o osciloscópio:
        antes_de_esperar()        # assim, quando o osciloscópio mostrar "Ready", o RX já está armado
    armar(sc, p)
    print(f"[osc] {preset} armado ({p['pontas']}).", flush=True)
    print(">>> APERTE RESET NO TX <<<", flush=True)
    n = esperar(sc, p, parar=parar)
    if n == 0:
        sc.write("ACQUIRE:STATE STOP")
        sc.write("TRIGGER:MAIN:TYPE EDGE")
        sc.close()
        L = ["**Nenhuma falha de CLK no PA0 durante o quadro** (o disparo de pulso baixo > 100 µs não ocorreu)."]
        print("[osc]", L[0])
        return p, nome, 0, L
    while preset in ("degrau", "degrau_zoom"):          # disparo falso (ponta encostando)? rearma
        _, v1 = ler_canal(sc, "CH1")
        _, v2 = ler_canal(sc, "CH2")
        if np.ptp(v1) > 2.0 and np.ptp(v2) > 1.0:
            break
        print("[osc] disparo falso (sem degrau em TP2/TP3) — rearmando. ESPERE ~10 s (o quadro atual terminar) e aperte RESET de novo", flush=True)
        armar(sc, p)
        n = esperar(sc, p)
    base, dados = salvar(sc, nome)
    linhas = analise(preset, dados, M, sc)
    sc.write("DISPLAY:PERSISTENCE OFF")
    sc.close()
    print(f"[osc] {n} aquisições → {base}_tela.png")
    for L in linhas:
        print("   ", L)
    return p, nome, n, linhas


def iniciar_rx(canal, mod, vref, porta=None):
    """Arma o RX pela serial (pam_app capturar) em paralelo. Devolve (proc, saida, evento_armado)."""
    cmd = [sys.executable, "-u", os.path.join(AQUI, "pam_app.py"), "capturar", "--mod", str(mod),
           "--canal", canal, "--vref", str(vref), "--timeout", "600"]
    if porta:
        cmd += ["--porta", porta]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=AQUI)
    saida, armado = [], threading.Event()

    def ler():
        for L in proc.stdout:
            saida.append(L.rstrip())
            if L.lstrip().startswith("#ARMADO"):      # resposta do RX (não a mensagem do pam_app)
                armado.set()
    threading.Thread(target=ler, daemon=True).start()
    return proc, saida, armado


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("osc", help="um preset do osciloscópio (+ log do RX no mesmo RESET)")
    o.add_argument("preset", choices=list(PRESETS))
    e = sub.add_parser("ensaio", help="= osc olho: log do RX + olho no mesmo RESET")
    for q in (o, e):
        q.add_argument("--canal", required=True, choices=["d", "c", "x", "m"], help="canal MONTADO")
        q.add_argument("--mod", type=int, required=True, choices=[2, 4], help="PAM do jumper PB0 do TX")
        q.add_argument("--vref", type=float, default=3.3)
        q.add_argument("--porta", default=None)
        q.add_argument("--sem-rx", action="store_true")
        q.add_argument("--nome", default=None)
    a = ap.parse_args()
    preset = "olho" if a.cmd == "ensaio" else a.preset

    proc = saida = armado = None
    if not a.sem_rx:
        proc, saida, armado = iniciar_rx(a.canal, a.mod, a.vref, a.porta)

    def esperar_rx():
        if armado is None:
            return
        if not armado.wait(20):
            print("[rx] não vi #ARMADO em 20 s — saída até agora:\n" + "\n".join(saida[-15:]))
            proc.kill()
            raise SystemExit(1)
        print(f"[rx] RX armado: {[L for L in saida if L.lstrip().startswith('#ARMADO')][-1]}", flush=True)

    parar = (lambda: proc.poll() is not None) if (proc and preset == "diag_clk") else None
    p, nome, n, linhas = rodar_osc(preset, a.canal, a.mod, a.nome, antes_de_esperar=esperar_rx, parar=parar)
    extra = ""
    if proc:
        try:
            proc.wait(timeout=660)
        except subprocess.TimeoutExpired:
            proc.kill()
            print("[rx] RX não mandou o relatório em 180 s")
        txt = "\n".join(saida)
        log = re.search(r"log gravado em (.+\.txt)", txt)
        figs = re.findall(r"figura: (.+\.png)", txt)
        resumo = [L for L in saida if re.search(r"k\*|abertura|BER|SER|válida|sincron|\[OK\]|\[FALHOU\]|"
                                                 r"S\(|margem|Bordas|ERRO", L, re.I)]
        print("[rx]\n" + "\n".join(resumo[:60]))
        if log:
            linhas.append(f"Log do RX: `{os.path.relpath(log.group(1), os.path.dirname(CADERNO))}`")
            linhas += [f"RX: {L.strip()}" for L in saida if re.search(r"válida|BER", L)][:4]
        else:
            linhas.append("RX: **sem log** (não recebeu o relatório)")
        for fg in figs:
            extra += f"![{os.path.basename(fg)}]({os.path.relpath(fg, os.path.dirname(CADERNO))})\n\n"
        extra += "<details><summary>Saída completa do RX</summary>\n\n```\n" + txt + "\n```\n</details>"
    tit = f"{nome.replace('_', ' ')} — canal {NOME_CANAL[a.canal]}, TX em PAM-{a.mod}"
    caderno(tit, p, nome, n, linhas, extra or None)


if __name__ == "__main__":
    main()
