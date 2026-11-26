#!/usr/bin/env python3
"""Captura do Tektronix TDS2002B pelo USB traseiro (USBTMC), direto no Linux.

Salva, para cada canal ligado na tela: CSV (tempo_s,tensao_V) com a escala real
(já considera a atenuação 10X/1X configurada no menu do canal), um PNG com os
dois canais e a imagem da tela do osciloscópio (BMP -> PNG), útil para o olho
com persistência.

Uso:
    python3 python/captura_tds.py Dupont_PAM4_TP2_TP3_degrau
    python3 python/captura_tds.py TP3_olho_RC_PAM4 --sem-parar   # não congela a aquisição
    python3 python/captura_tds.py teste --sem-tela               # só dados (mais rápido)

Pré-requisitos:
  * No osciloscópio: Utility -> Options -> Rear USB Port -> Computer.
  * /dev/usbtmc0 com permissão:  sudo chmod 666 /dev/usbtmc0
"""
import argparse
import fcntl
import glob
import os
import struct
import sys
import time
from datetime import datetime

import numpy as np

USBTMC_IOCTL_SET_TIMEOUT = 0x40045B0A  # _IOW(91, 10, __u32)
USBTMC_IOCTL_CLEAR = 0x5B02            # _IO(91, 2)


class TDS:
    def __init__(self, dev=None, timeout_ms=10000):
        if dev is None:
            devs = sorted(glob.glob("/dev/usbtmc*"))
            if not devs:
                sys.exit("Nenhum /dev/usbtmc* encontrado. O cabo está ligado e "
                         "'Rear USB Port' = Computer? Veja 'lsusb | grep -i 0699'.")
            dev = devs[0]
        try:
            self.fd = os.open(dev, os.O_RDWR)
        except PermissionError:
            sys.exit(f"Sem permissão em {dev}. Rode:  sudo chmod 666 {dev}")
        self.dev = dev
        self.set_timeout(timeout_ms)
        try:
            fcntl.ioctl(self.fd, USBTMC_IOCTL_CLEAR)
        except OSError:
            pass

    def set_timeout(self, ms):
        fcntl.ioctl(self.fd, USBTMC_IOCTL_SET_TIMEOUT, struct.pack("I", ms))

    def write(self, cmd):
        os.write(self.fd, (cmd + "\n").encode())

    def read_raw(self, n=1 << 20):
        return os.read(self.fd, n)

    def query(self, cmd):
        self.write(cmd)
        return self.read_raw().decode(errors="replace").strip()

    def close(self):
        os.close(self.fd)


def ler_canal(sc, ch):
    sc.write(f"DATA:SOURCE {ch}")
    sc.write("DATA:ENCDG RIBINARY")
    sc.write("DATA:WIDTH 1")
    sc.write("DATA:START 1")
    sc.write("DATA:STOP 2500")
    pre = {k: float(sc.query(f"WFMPRE:{k}?"))
           for k in ("XINCR", "XZERO", "PT_OFF", "YMULT", "YZERO", "YOFF")}
    sc.write("CURVE?")
    raw = b""
    while True:
        raw += sc.read_raw()
        if raw.startswith(b"#"):
            nd = int(raw[1:2])
            nbytes = int(raw[2:2 + nd])
            if len(raw) >= 2 + nd + nbytes:
                dados = raw[2 + nd:2 + nd + nbytes]
                break
        elif len(raw) > 16:
            raise RuntimeError(f"Resposta inesperada do CURVE?: {raw[:40]!r}")
    cod = np.frombuffer(dados, dtype=np.int8).astype(float)
    v = (cod - pre["YOFF"]) * pre["YMULT"] + pre["YZERO"]
    t = pre["XZERO"] + pre["XINCR"] * (np.arange(len(v)) - pre["PT_OFF"])
    return t, v


def ler_tela(sc):
    sc.set_timeout(30000)
    sc.write("HARDCOPY:FORMAT BMP")
    sc.write("HARDCOPY:LAYOUT PORTRAIT")
    sc.write("HARDCOPY START")
    img = b""
    t0 = time.time()
    while time.time() - t0 < 40:
        img += sc.read_raw()
        if len(img) >= 6 and img[:2] == b"BM":
            tam = struct.unpack("<I", img[2:6])[0]
            if len(img) >= tam:
                return img[:tam]
    raise RuntimeError("Imagem da tela incompleta")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nome", help="ex.: Dupont_PAM4_TP2_TP3_degrau")
    ap.add_argument("--dir", default="entrega/osciloscopio")
    ap.add_argument("--sem-tela", action="store_true", help="não baixa a imagem da tela")
    ap.add_argument("--sem-parar", action="store_true", help="não congela (RUN/STOP) durante a leitura")
    ap.add_argument("--dev", default=None)
    a = ap.parse_args()

    os.makedirs(a.dir, exist_ok=True)
    base = os.path.join(a.dir, a.nome)
    sc = TDS(a.dev)
    sc.write("HEADER OFF")
    print("Conectado:", sc.query("*IDN?"), f"({sc.dev})")

    rodando = sc.query("ACQUIRE:STATE?").strip() in ("1", "RUN")
    if rodando and not a.sem_parar:
        sc.write("ACQUIRE:STATE STOP")
        time.sleep(0.3)

    canais = {}
    try:
        for ch in ("CH1", "CH2"):
            if sc.query(f"SELECT:{ch}?").strip() not in ("1", "ON"):
                continue
            t, v = ler_canal(sc, ch)
            canais[ch] = (t, v)
            np.savetxt(f"{base}_{ch}.csv", np.column_stack([t, v]), delimiter=",",
                       header="tempo_s,tensao_V", comments="", fmt="%.9e")
            print(f"{ch}: {len(v)} pts, min {v.min():.3f} V, max {v.max():.3f} V, "
                  f"média {v.mean():.3f} V, dt {t[1]-t[0]:.3e} s -> {base}_{ch}.csv")

        if not a.sem_tela:
            try:
                bmp = ler_tela(sc)
                with open(f"{base}_tela.bmp", "wb") as f:
                    f.write(bmp)
                try:
                    from PIL import Image
                    Image.open(f"{base}_tela.bmp").save(f"{base}_tela.png")
                    os.remove(f"{base}_tela.bmp")
                    print(f"Tela -> {base}_tela.png")
                except ImportError:
                    print(f"Tela -> {base}_tela.bmp")
            except Exception as e:  # tela é opcional; os dados já foram salvos
                print("Aviso: não consegui baixar a tela:", e)
    finally:
        if rodando and not a.sem_parar:
            sc.write("ACQUIRE:STATE RUN")
        sc.close()

    if canais:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 4.5))
        for ch, (t, v) in canais.items():
            ax.plot(t * 1e6, v, lw=0.9, label=ch)
        ax.set_xlabel("tempo (µs)")
        ax.set_ylabel("tensão (V)")
        ax.set_title(f"{a.nome}  ({datetime.now():%d/%m/%Y %H:%M})")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(f"{base}_dados.png", dpi=150)
        print(f"Gráfico -> {base}_dados.png")


if __name__ == "__main__":
    main()
