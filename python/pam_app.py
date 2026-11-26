#!/usr/bin/env python3
"""
pam_app.py — app de bancada do Projeto PAM em banda base.

  python3 pam_app.py                 -> interface gráfica (Tk)
  python3 pam_app.py portas          -> lista as portas seriais
  python3 pam_app.py capturar --porta /dev/ttyACM1 --mod 4 --canal c --vref 3.297
  python3 pam_app.py capturar --simular --mod 4 --canal c        (sem placa)
  python3 pam_app.py analisar LOG.txt --vref 3.297
  python3 pam_app.py comparar DUPONT.txt RC.txt --vref 3.297 --tau 7.1
  python3 pam_app.py tau F0001CH2.CSV
  python3 pam_app.py tabela L1.txt L2.txt L3.txt L4.txt --vref 3.297 --tau nan,nan,7.1,7.1

A serial chega por um Raspberry Pi Pico (RP2040) com o firmware pico-uart-bridge:
ele cria /dev/ttyACM0 = UART0 (GP0/GP1, sem uso) e /dev/ttyACM1 = UART1
(GP4 TX -> PA10 do RX, GP5 RX <- PA9 do RX). Sem --porta, usa /dev/ttyACM1.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import queue
import re
import sys
import threading
import time
from datetime import datetime

import pam_core as core

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PASTA_ENTREGA = os.path.join(RAIZ, "entrega")
CFG_ARQ = os.path.join(os.path.expanduser("~"), ".config", "pam_app.json")
BAUD = 460800
PORTA_PADRAO = "/dev/ttyACM1"  # pico-uart-bridge: UART1 = GP4/GP5

CANAIS = {  # tecla -> (rótulo do firmware, nome curto p/ arquivo, descrição)
    "d": ("Dupont_direto", "Dupont", "Canal 1 — Dupont direto"),
    "c": ("Dupont_RC_16n8", "RC16n8", "Canal 2 — RC 56 Ω + 16,8 nF"),
    "x": ("Dupont_RC_33n", "RC33n", "Defesa — RC 56 Ω + 33 nF"),
    "m": ("cabo_manga_200m", "Manga", "Canal 3 — cabo manga 200 m"),
}


# ----------------------------------------------------------------------------
# configuração persistente
# ----------------------------------------------------------------------------
def cfg_ler() -> dict:
    try:
        with open(CFG_ARQ, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def cfg_gravar(d: dict):
    try:
        os.makedirs(os.path.dirname(CFG_ARQ), exist_ok=True)
        with open(CFG_ARQ, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=1)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# serial real e serial simulada
# ----------------------------------------------------------------------------
def listar_portas() -> list[tuple[str, str]]:
    try:
        from serial.tools import list_ports
        ps = [p for p in list_ports.comports()
              if p.hwid != "n/a" or "USB" in p.device or "ACM" in p.device or p.device.upper().startswith("COM")]
        return [(p.device, f"{p.device} — {p.description}") for p in ps]
    except Exception:
        return [(p, p) for p in sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))]


def porta_padrao(ps: list[tuple[str, str]]) -> str:
    """UART1 do Pico (interface if02 do pico-uart-bridge), achada pelo nome fixo
    em /dev/serial/by-id — o número ttyACMx muda se o Pico for replugado com a
    porta aberta. Sem Pico: /dev/ttyACM1 se existir; senão a primeira da lista."""
    devs = [dev for dev, _ in ps]
    for link in sorted(glob.glob("/dev/serial/by-id/usb-Raspberry_Pi_Pico_*-if02")):
        real = os.path.realpath(link)
        if real in devs:
            return real
    return PORTA_PADRAO if PORTA_PADRAO in devs else devs[0]


def abrir_serial(porta: str):
    import serial
    s = serial.Serial()
    s.port = porta
    s.baudrate = BAUD
    s.bytesize, s.parity, s.stopbits = 8, "N", 1
    s.timeout = 0.05
    # DTR ativo: a ponte USB do Pico (TinyUSB) usa o DTR para saber que a porta
    # está aberta e só então repassa os dados da UART para o PC.
    s.dtr = True
    s.rts = False
    s.open()
    s.reset_input_buffer()
    return s


class SerialSimulada:
    """Imita o RX: responde aos comandos e, ~2 s depois de armado, 'recebe' um
    quadro (reproduz um dos logs SIMULADOS de matlab/exemplo_logs)."""

    def __init__(self):
        self._buf = bytearray()
        self._lock = threading.Lock()
        self.M, self.canal = 2, "nao_informado"
        self._timer = None
        self.is_open = True
        self._put("\r\n=== RX PAM banda base - BlackPill F411 (SIMULADO) ===\r\n"
                  "Comandos: 2/4 = modulacao | d=Dupont c=RC16,8n x=RC33n m=manga | r=rearmar | p=reimprimir\r\n")
        self._armar()
        self._ultimo = None

    def _put(self, s: str):
        with self._lock:
            self._buf += s.encode()

    def _armar(self):
        if self._timer:
            self._timer.cancel()
        self._put(f"\r\n#ARMADO PAM-{self.M} canal={self.canal} : reinicie o TX (ou aperte KEY no TX)\r\n")
        self._timer = threading.Timer(2.5, self._quadro)
        self._timer.daemon = True
        self._timer.start()

    def _arquivo(self):
        base = os.path.join(RAIZ, "matlab", "exemplo_logs")
        c = core.canal_do_rotulo(self.canal)
        nome = {"dupont": "Dupont", "rc": "RC16n8", "rc33": "RC33n"}[c]
        f = os.path.join(base, f"SIMULADO_PAM{self.M}_{nome}.txt")
        if not os.path.exists(f):
            f = os.path.join(base, f"SIMULADO_PAM{self.M}_RC16n8.txt")
        return f

    def _quadro(self):
        with open(self._arquivo(), encoding="utf-8") as fh:
            txt = fh.read().replace("\r", "")
        txt = txt.replace("canal=Dupont_RC_16n8", f"canal={self.canal}") \
                 .replace("canal=Dupont_direto", f"canal={self.canal}") \
                 .replace("canal=Dupont_RC_33n", f"canal={self.canal}")
        self._ultimo = txt
        linhas = txt.split("\n")
        # ~46 kB/s como a 460 800 baud: manda em pedaços
        for i in range(0, len(linhas), 60):
            self._put("\r\n".join(linhas[i:i + 60]) + "\r\n")
            time.sleep(0.03)
        self._put("#FIM. Envie 'r' para rearmar (ou d/c/x/m, 2/4), 'p' para reimprimir.\r\n")

    # interface parecida com pyserial
    @property
    def in_waiting(self):
        return len(self._buf)

    def read(self, n=1):
        time.sleep(0.01)
        with self._lock:
            d = bytes(self._buf[:n])
            del self._buf[:n]
        return d

    def write(self, data: bytes):
        for ch in data.decode(errors="ignore"):
            if ch in "24":
                self.M = int(ch); self._armar()
            elif ch in CANAIS:
                self.canal = CANAIS[ch][0]; self._armar()
            elif ch == "r":
                self._armar()
            elif ch == "p" and self._ultimo:
                self._put(self._ultimo)
            elif ch == "?":
                self._put("\r\nComandos: 2/4 = modulacao | d=Dupont c=RC16,8n x=RC33n m=manga | r=rearmar | p=reimprimir\r\n")
        return len(data)

    def close(self):
        self.is_open = False
        if self._timer:
            self._timer.cancel()


# ----------------------------------------------------------------------------
# leitor de linhas + montagem do log (usado pela GUI e pela CLI)
# ----------------------------------------------------------------------------
class Capturador:
    """Thread que lê a serial, separa linhas e junta o relatório
    (#BEGIN_REPORT ... #END_PSD). Eventos vão para uma fila:
       ('linha', texto) | ('armado', texto) | ('inicio', None) |
       ('progresso', n_linhas) | ('relatorio', texto_completo) | ('erro', msg)"""

    def __init__(self, ser, fila: queue.Queue):
        self.ser, self.fila = ser, fila
        self._parar = threading.Event()
        self._acum: list[str] | None = None
        self.t = threading.Thread(target=self._loop, daemon=True)
        self.t.start()

    def enviar(self, texto: str, pausa=0.2):
        def _w():
            for ch in texto:
                try:
                    self.ser.write(ch.encode())
                except Exception as e:  # noqa: BLE001
                    self.fila.put(("erro", f"falha ao escrever: {e}"))
                    return
                time.sleep(pausa)
        threading.Thread(target=_w, daemon=True).start()

    def parar(self):
        self._parar.set()
        try:
            self.ser.close()
        except Exception:
            pass

    def _linha(self, L: str):
        if L.startswith("#BEGIN_REPORT"):
            self._acum = [L]
            self.fila.put(("inicio", None))
            return
        if self._acum is not None:
            self._acum.append(L)
            if len(self._acum) % 100 == 0:
                self.fila.put(("progresso", len(self._acum)))
            if L.startswith("#END_PSD"):
                self.fila.put(("relatorio", "\n".join(self._acum) + "\n"))
                self._acum = None
            elif not (L[:1].isdigit()):
                self.fila.put(("linha", L))
            return
        if L.startswith("#ARMADO"):
            self.fila.put(("armado", L))
        self.fila.put(("linha", L))

    def _loop(self):
        resto = b""
        while not self._parar.is_set():
            try:
                n = self.ser.in_waiting
                d = self.ser.read(n if n else 1)
            except Exception as e:  # noqa: BLE001
                if not self._parar.is_set():
                    self.fila.put(("erro", f"serial: {e}"))
                return
            if not d:
                continue
            resto += d
            while b"\n" in resto:
                ln, resto = resto.split(b"\n", 1)
                L = ln.decode("ascii", errors="replace").rstrip("\r").strip()
                if L:
                    self._linha(L)


def confere_config(texto: str, mod: str, canal: str) -> str | None:
    """Compara o que o RX diz (linha #ARMADO ou relatório) com o pedido.
    Devolve uma mensagem de erro se o RX estiver em outra PAM/canal, senão None.
    (11/11/2026: TX em PAM-2 e RX em PAM-4 → sem sincronismo → BER não atribuída.)"""
    m = re.search(r"PAM-(\d)", texto)
    c = re.search(r"canal=(\S+)", texto)
    erros = []
    if m and m.group(1) != mod:
        erros.append(f"RX está em PAM-{m.group(1)}, mas você pediu PAM-{mod}")
    esperado = CANAIS[canal][0]
    # no #ARMADO o canal pode aparecer "nao_informado" por um instante (chega antes da letra do canal)
    aceitos = {esperado, "nao_informado"} if texto.lstrip().startswith("#ARMADO") else {esperado}
    if c and c.group(1) not in aceitos:
        erros.append(f"RX está com canal={c.group(1)}, mas você pediu {esperado}")
    if not erros:
        return None
    return ("!!! CONFIGURAÇÃO ERRADA NO RX: " + "; ".join(erros) +
            ". O RX não recebeu os comandos (fio GP4→PA10?) ou foi resetado. "
            "NÃO aperte RESET no RX — só no TX. Rearme e confira o #ARMADO.")


def nome_log(rotulo: str) -> str:
    return f"{rotulo}_{datetime.now():%Y%m%d_%H%M%S}.txt"


def gravar_log(texto: str, pasta: str, rotulo: str) -> str:
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome_log(rotulo))
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(texto)
    return caminho


# ----------------------------------------------------------------------------
# linha de comando
# ----------------------------------------------------------------------------
def _floats(s: str | None, n: int):
    if not s:
        return [math.nan] * n
    v = [float(x) if x.strip().lower() not in ("nan", "-", "") else math.nan for x in s.split(",")]
    return (v + [math.nan] * n)[:n]


def cli(argv: list[str]):
    ap = argparse.ArgumentParser(prog="pam_app.py", description="App de bancada do Projeto PAM")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("portas", help="lista portas seriais")
    c = sub.add_parser("capturar", help="arma o RX, espera o quadro e grava o log")
    c.add_argument("--porta", default=None)
    c.add_argument("--mod", choices=["2", "4"], default="2")
    c.add_argument("--canal", choices=list(CANAIS), default="d")
    c.add_argument("--rotulo", default=None)
    c.add_argument("--vref", type=float, default=None, help="se dado, analisa logo depois")
    c.add_argument("--pasta", default=os.path.join(PASTA_ENTREGA, "logs"))
    c.add_argument("--simular", action="store_true", help="sem placa: reproduz um log de exemplo")
    c.add_argument("--timeout", type=float, default=120)
    a = sub.add_parser("analisar", help="análise completa de um log")
    a.add_argument("log")
    a.add_argument("--vref", type=float, required=True)
    a.add_argument("--figuras", default=os.path.join(PASTA_ENTREGA, "figuras"))
    p = sub.add_parser("comparar", help="PSD Dupont × RC e razão × |H|²")
    p.add_argument("dupont")
    p.add_argument("rc")
    p.add_argument("--vref", type=float, required=True)
    p.add_argument("--tau", type=float, default=math.nan, help="τ medido (µs)")
    p.add_argument("--figuras", default=os.path.join(PASTA_ENTREGA, "figuras"))
    t = sub.add_parser("tau", help="τ e t10-90 do CSV do osciloscópio")
    t.add_argument("csv")
    t.add_argument("--t0", type=float, default=None, help="início da subida em s (opcional)")
    t.add_argument("--figuras", default=os.path.join(PASTA_ENTREGA, "figuras"))
    b = sub.add_parser("tabela", help="tabela da Seção 5.1")
    b.add_argument("logs", nargs="+")
    b.add_argument("--vref", type=float, required=True)
    b.add_argument("--tau", default=None, help="lista separada por vírgula, ex.: nan,nan,7.1,7.1")
    b.add_argument("--csv", default=os.path.join(PASTA_ENTREGA, "tabela_resultados.csv"))
    args = ap.parse_args(argv)

    from matplotlib.backends.backend_agg import FigureCanvasAgg

    def salvar(fig, pasta, nome):
        os.makedirs(pasta, exist_ok=True)
        FigureCanvasAgg(fig)
        cam = os.path.join(pasta, nome)
        fig.savefig(cam, dpi=120)
        return cam

    if args.cmd == "portas":
        ps = listar_portas()
        print("\n".join(d for _, d in ps) if ps else "Nenhuma porta encontrada (o Pico está no USB?)")
    elif args.cmd == "capturar":
        if args.simular:
            ser = SerialSimulada()
        else:
            if not args.porta:
                ps = listar_portas()
                if not ps:
                    sys.exit("Nenhuma porta serial. Use --porta ou --simular.")
                args.porta = porta_padrao(ps)
            ser = abrir_serial(args.porta)
        rot = args.rotulo or f"{CANAIS[args.canal][1]}_PAM{args.mod}"
        fila: queue.Queue = queue.Queue()
        cap = Capturador(ser, fila)
        time.sleep(0.3)
        cap.enviar(args.mod + args.canal)
        print("Aguardando... quando aparecer #ARMADO, aperte RESET no TX.")
        t0 = time.time()
        caminho = None
        while time.time() - t0 < args.timeout:
            try:
                ev, val = fila.get(timeout=0.5)
            except queue.Empty:
                continue
            if ev == "linha":
                print(val)
            elif ev == "armado":
                aviso = confere_config(val, args.mod, args.canal)
                if aviso:
                    print(aviso)
            elif ev == "inicio":
                print(">> recebendo relatório...")
            elif ev == "relatorio":
                caminho = gravar_log(val, args.pasta, rot)
                print(f">> log gravado em {caminho}")
                cab = "\n".join(L for L in val.splitlines()[:4] if L.startswith(("modulacao", "canal")))
                aviso = confere_config(cab, args.mod, args.canal)
                if aviso:
                    print(aviso)
                break
            elif ev == "erro":
                print("ERRO:", val)
                break
        cap.parar()
        if caminho and args.vref:
            res = core.analisar(caminho, args.vref)
            print(res.texto)
            for txt, ok in res.checks:
                print(("  [OK] " if ok else "  [FALHOU] ") + txt)
            for c_ in core.salvar_figuras(res, os.path.join(PASTA_ENTREGA, "figuras")):
                print("figura:", c_)
    elif args.cmd == "analisar":
        res = core.analisar(args.log, args.vref)
        print(res.texto)
        for txt, ok in res.checks:
            print(("  [OK] " if ok else "  [FALHOU] ") + txt)
        for c_ in core.salvar_figuras(res, args.figuras):
            print("figura:", c_)
    elif args.cmd == "comparar":
        txt, fig, _ = core.comparar_psd(args.dupont, args.rc, args.vref, args.tau)
        print(txt)
        M = core.ler_log(args.dupont).M
        print("figura:", salvar(fig, args.figuras, f"psd_comparacao_PAM{M}.png"))
    elif args.cmd == "tau":
        tau, tr, txt, fig = core.tau_csv(args.csv, args.t0)
        print(txt)
        nome = os.path.splitext(os.path.basename(args.csv))[0]
        print("figura:", salvar(fig, args.figuras, f"tau_{nome}.png"))
    elif args.cmd == "tabela":
        md = core.tabela(args.logs, args.vref, _floats(args.tau, len(args.logs)), args.csv)
        print(md)
        print("CSV:", args.csv)


# ----------------------------------------------------------------------------
# interface gráfica
# ----------------------------------------------------------------------------
def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure

    cfg = cfg_ler()
    root = tk.Tk()
    root.title("PAM banda base — bancada")
    root.geometry("1400x880")
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    MONO = ("DejaVu Sans Mono", 9)

    # ---------- barra superior ----------
    topo = ttk.Frame(root, padding=6)
    topo.pack(fill="x")
    ttk.Label(topo, text="Vref medido (V):").pack(side="left")
    v_vref = tk.StringVar(value=str(cfg.get("vref", "3.300")))
    ttk.Entry(topo, textvariable=v_vref, width=8).pack(side="left", padx=(2, 12))
    ttk.Label(topo, text="Pasta de entrega:").pack(side="left")
    v_pasta = tk.StringVar(value=cfg.get("pasta", PASTA_ENTREGA))
    ttk.Entry(topo, textvariable=v_pasta, width=60).pack(side="left", padx=2)
    ttk.Button(topo, text="…", width=3,
               command=lambda: v_pasta.set(filedialog.askdirectory(initialdir=v_pasta.get()) or v_pasta.get())
               ).pack(side="left")
    ttk.Label(topo, text="   (meça o 3V3 do RX com o multímetro — entra em todas as contas em volts)",
              foreground="#666").pack(side="left")

    def vref() -> float:
        try:
            v = float(v_vref.get().replace(",", "."))
            if not 2.5 < v < 3.7:
                raise ValueError
            return v
        except ValueError:
            messagebox.showerror("Vref", "Vref inválido (esperado ~3,3 V).")
            raise

    def pasta(sub: str) -> str:
        return os.path.join(v_pasta.get(), sub)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    def aba_com_figura(titulo: str, figsize):
        fr = ttk.Frame(nb)
        nb.add(fr, text=titulo)
        pw = ttk.PanedWindow(fr, orient="horizontal")
        pw.pack(fill="both", expand=True)
        esq = ttk.Frame(pw, padding=6)
        dir_ = ttk.Frame(pw)
        pw.add(esq, weight=1)
        pw.add(dir_, weight=3)
        fig = Figure(figsize=figsize, dpi=90)
        cv = FigureCanvasTkAgg(fig, master=dir_)
        NavigationToolbar2Tk(cv, dir_).update()
        cv.get_tk_widget().pack(fill="both", expand=True)
        return fr, esq, fig, cv

    # =====================================================================
    # Aba 1 — Serial / captura
    # =====================================================================
    f1 = ttk.Frame(nb, padding=8)
    nb.add(f1, text="1 · Serial / captura")
    lin1 = ttk.Frame(f1)
    lin1.pack(fill="x")
    ttk.Label(lin1, text="Porta:").pack(side="left")
    v_porta = tk.StringVar(value=cfg.get("porta", ""))
    cb_porta = ttk.Combobox(lin1, textvariable=v_porta, width=45)
    cb_porta.pack(side="left", padx=4)

    def atualizar_portas():
        ps = listar_portas()
        cb_porta["values"] = [d for _, d in ps]
        if ps and not v_porta.get():
            v_porta.set(dict(ps)[porta_padrao(ps)])
    ttk.Button(lin1, text="↻ atualizar", command=atualizar_portas).pack(side="left")
    v_sim = tk.BooleanVar(value=False)
    ttk.Checkbutton(lin1, text="modo demonstração (sem placa)", variable=v_sim).pack(side="left", padx=12)
    bt_con = ttk.Button(lin1, text="Conectar")
    bt_con.pack(side="left", padx=4)
    ttk.Label(lin1, text=f"{BAUD} baud, 8N1").pack(side="left", padx=8)

    lin2 = ttk.Frame(f1)
    lin2.pack(fill="x", pady=6)
    gm = ttk.LabelFrame(lin2, text="Modulação (igual ao jumper PB0 do TX!)", padding=4)
    gm.pack(side="left", padx=(0, 8))
    v_mod = tk.StringVar(value=cfg.get("mod", "2"))
    for m in ("2", "4"):
        ttk.Radiobutton(gm, text=f"PAM-{m}", value=m, variable=v_mod).pack(side="left", padx=4)
    gc = ttk.LabelFrame(lin2, text="Canal montado na protoboard", padding=4)
    gc.pack(side="left", padx=8)
    v_canal = tk.StringVar(value=cfg.get("canal", "d"))
    for k, (_, _, desc) in CANAIS.items():
        ttk.Radiobutton(gc, text=f"{k}: {desc}", value=k, variable=v_canal).pack(anchor="w")
    gb = ttk.LabelFrame(lin2, text="Comandos", padding=4)
    gb.pack(side="left", padx=8, fill="y")
    v_rot = tk.StringVar()
    ttk.Label(gb, text="Rótulo do arquivo:").grid(row=0, column=0, sticky="w")
    ttk.Entry(gb, textvariable=v_rot, width=22).grid(row=0, column=1, columnspan=3, sticky="w")
    bt_armar = ttk.Button(gb, text="▶ ARMAR (envia modulação + canal)")
    bt_armar.grid(row=1, column=0, columnspan=4, sticky="we", pady=4)
    for i, (t, ch) in enumerate((("r rearmar", "r"), ("p reimprimir", "p"), ("? ajuda", "?"))):
        ttk.Button(gb, text=t, command=lambda c=ch: enviar(c)).grid(row=2, column=i, padx=2)
    v_auto = tk.BooleanVar(value=True)
    ttk.Checkbutton(gb, text="analisar automaticamente ao terminar", variable=v_auto).grid(
        row=3, column=0, columnspan=4, sticky="w")

    def rot_padrao(*_):
        v_rot.set(f"{CANAIS[v_canal.get()][1]}_PAM{v_mod.get()}")
    v_mod.trace_add("write", rot_padrao)
    v_canal.trace_add("write", rot_padrao)
    rot_padrao()

    status = tk.Label(f1, text="DESCONECTADO", font=("DejaVu Sans", 15, "bold"), bg="#ddd", fg="#333",
                      anchor="w", padx=10, pady=8)
    status.pack(fill="x", pady=4)
    term = ScrolledText(f1, font=MONO, height=20, bg="#111", fg="#ddd", insertbackground="#ddd")
    term.pack(fill="both", expand=True)
    ttk.Label(f1, foreground="#555", text=(
        "Fluxo: Conectar → escolher modulação e canal → ARMAR → quando aparecer #ARMADO, apertar RESET no TX → "
        "~6 s (PAM-2) / ~3 s (PAM-4) de quadro + ~3 s de relatório → o log é salvo em <pasta>/logs e analisado.")
    ).pack(anchor="w", pady=(4, 0))

    st = {"cap": None, "fila": queue.Queue()}

    def set_status(txt, bg, fg="white"):
        status.configure(text=txt, bg=bg, fg=fg)

    def term_add(s):
        term.insert("end", s + "\n")
        term.see("end")

    def enviar(texto):
        if not st["cap"]:
            messagebox.showwarning("Serial", "Conecte primeiro.")
            return
        st["cap"].enviar(texto)
        term_add(f">>> enviado: {texto!r}")

    def conectar():
        if st["cap"]:
            st["cap"].parar()
            st["cap"] = None
            bt_con.configure(text="Conectar")
            set_status("DESCONECTADO", "#ddd", "#333")
            return
        try:
            if v_sim.get():
                ser = SerialSimulada()
                nome = "SIMULADA"
            else:
                nome = v_porta.get().split(" — ")[0].strip()
                if not nome:
                    messagebox.showerror("Serial", "Escolha a porta (Pico: /dev/ttyACM1).")
                    return
                ser = abrir_serial(nome)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "Permission" in msg or "ermiss" in msg:
                msg += ("\n\nNo Linux: sudo usermod -aG dialout $USER  (depois saia e entre na sessão).")
            messagebox.showerror("Serial", msg)
            return
        st["cap"] = Capturador(ser, st["fila"])
        bt_con.configure(text="Desconectar")
        set_status(f"CONECTADO em {nome} — clique em ARMAR", "#2a6db0")
        guardar_cfg()

    def armar():
        enviar(v_mod.get() + v_canal.get())

    bt_con.configure(command=conectar)
    bt_armar.configure(command=armar)

    def processar_fila():
        try:
            while True:
                ev, val = st["fila"].get_nowait()
                if ev == "linha":
                    term_add(val)
                elif ev == "armado":
                    aviso = confere_config(val, v_mod.get(), v_canal.get())
                    if aviso:
                        term_add(aviso)
                        set_status("RX COM PAM/CANAL ERRADO — NÃO resete o TX, clique Armar de novo", "#b3261e")
                    else:
                        set_status("ARMADO — aperte RESET (ou KEY) no TX agora", "#c47f00")
                elif ev == "inicio":
                    set_status("RECEBENDO RELATÓRIO…", "#6a3fb5")
                elif ev == "progresso":
                    set_status(f"RECEBENDO RELATÓRIO… {val} linhas (~1520)", "#6a3fb5")
                elif ev == "relatorio":
                    cam = gravar_log(val, pasta("logs"), v_rot.get() or "log")
                    term_add(f">>> LOG GRAVADO: {cam}")
                    cab = "\n".join(L for L in val.splitlines()[:4] if L.startswith(("modulacao", "canal")))
                    aviso_cfg = confere_config(cab, v_mod.get(), v_canal.get())
                    if aviso_cfg:
                        term_add(aviso_cfg)
                    log = core.ler_log(val, eh_texto=True)
                    log.arquivo = cam
                    ok = all(o for _, o in core.verificacoes(log))
                    set_status(("QUADRO VÁLIDO ✔ " if ok else "QUADRO COM PROBLEMA ✘ (veja a análise) ")
                               + os.path.basename(cam), "#2e8b3d" if ok else "#b3261e")
                    if v_auto.get():
                        try:
                            analisar_log(cam)
                            nb.select(f2)
                        except Exception as e:  # noqa: BLE001
                            term_add(f"!!! análise falhou: {e}")
                elif ev == "erro":
                    term_add("!!! " + val)
                    set_status("ERRO NA SERIAL — " + val, "#b3261e")
        except queue.Empty:
            pass
        root.after(60, processar_fila)

    # =====================================================================
    # Aba 2 — análise de um ensaio
    # =====================================================================
    f2, e2, fig2, cv2 = aba_com_figura("2 · Análise do ensaio", (11, 7.5))
    bar2 = ttk.Frame(e2)
    bar2.pack(fill="x")
    lbl2 = ttk.Label(e2, text="(nenhum log)", foreground="#555", wraplength=380)
    st2: dict = {"res": None}

    def analisar_log(cam=None):
        cam = cam or filedialog.askopenfilename(initialdir=pasta("logs") if os.path.isdir(pasta("logs")) else RAIZ,
                                                filetypes=[("logs", "*.txt"), ("todos", "*")])
        if not cam:
            return
        res = core.analisar(cam, vref())
        st2["res"] = res
        lbl2.configure(text=cam)
        for w in chk.winfo_children():
            w.destroy()
        for txt, ok in res.checks:
            tk.Label(chk, text=("✔ " if ok else "✘ ") + txt, fg="#2e8b3d" if ok else "#b3261e",
                     anchor="w", justify="left").pack(fill="x")
        txt2.delete("1.0", "end")
        txt2.insert("end", res.texto)
        core.figura_analise(res, fig2)
        cv2.draw()

    def salvar_figs():
        if st2["res"]:
            cams = core.salvar_figuras(st2["res"], pasta("figuras"))
            messagebox.showinfo("Figuras", "\n".join(cams))

    def ver_z():
        if not st2["res"]:
            return
        w = tk.Toplevel(root)
        w.title("Filtro casado — z na calibração")
        fz = Figure(figsize=(8, 4.2), dpi=90)
        core.figura_z(st2["res"], fz)
        c = FigureCanvasTkAgg(fz, master=w)
        c.draw()
        c.get_tk_widget().pack(fill="both", expand=True)

    ttk.Button(bar2, text="Abrir log…", command=analisar_log).pack(side="left")
    ttk.Button(bar2, text="Salvar figuras", command=salvar_figs).pack(side="left", padx=4)
    ttk.Button(bar2, text="Gráfico z", command=ver_z).pack(side="left")
    lbl2.pack(fill="x", pady=4)
    chk = ttk.LabelFrame(e2, text="Critérios do quadro", padding=4)
    chk.pack(fill="x")
    txt2 = ScrolledText(e2, font=MONO, width=60, wrap="none")
    txt2.pack(fill="both", expand=True, pady=4)

    # =====================================================================
    # Aba 3 — comparação de PSD
    # =====================================================================
    f3, e3, fig3, cv3 = aba_com_figura("3 · PSD Dupont × RC", (11, 4.6))
    v_ldu, v_lrc, v_tau3 = tk.StringVar(), tk.StringVar(), tk.StringVar(value=cfg.get("tau", ""))

    def escolher(var):
        c = filedialog.askopenfilename(initialdir=pasta("logs") if os.path.isdir(pasta("logs")) else RAIZ,
                                       filetypes=[("logs", "*.txt")])
        if c:
            var.set(c)
    for i, (rot, var) in enumerate((("Log Dupont:", v_ldu), ("Log RC:", v_lrc))):
        ttk.Label(e3, text=rot).grid(row=i, column=0, sticky="w")
        ttk.Entry(e3, textvariable=var, width=40).grid(row=i, column=1, sticky="we")
        ttk.Button(e3, text="…", width=3, command=lambda v=var: escolher(v)).grid(row=i, column=2)
    ttk.Label(e3, text="τ medido (µs):").grid(row=2, column=0, sticky="w")
    ttk.Entry(e3, textvariable=v_tau3, width=10).grid(row=2, column=1, sticky="w")
    txt3 = ScrolledText(e3, font=MONO, width=60, height=20)

    def comparar():
        tau = float(v_tau3.get().replace(",", ".")) if v_tau3.get().strip() else math.nan
        t, _, _ = core.comparar_psd(v_ldu.get(), v_lrc.get(), vref(), tau, fig3)
        cv3.draw()
        txt3.delete("1.0", "end")
        txt3.insert("end", t)

    def salvar3():
        os.makedirs(pasta("figuras"), exist_ok=True)
        M = core.ler_log(v_ldu.get()).M
        cam = os.path.join(pasta("figuras"), f"psd_comparacao_PAM{M}.png")
        fig3.savefig(cam, dpi=120)
        messagebox.showinfo("Figura", cam)
    ttk.Button(e3, text="Comparar", command=comparar).grid(row=3, column=0, pady=6, sticky="w")
    ttk.Button(e3, text="Salvar figura", command=salvar3).grid(row=3, column=1, sticky="w")
    txt3.grid(row=4, column=0, columnspan=3, sticky="nsew")
    e3.rowconfigure(4, weight=1)
    e3.columnconfigure(1, weight=1)

    # =====================================================================
    # Aba 4 — τ do osciloscópio
    # =====================================================================
    f4, e4, fig4, cv4 = aba_com_figura("4 · τ do osciloscópio", (9, 5))
    v_csv, v_t0 = tk.StringVar(), tk.StringVar()
    ttk.Label(e4, text="CSV do TDS2002B (Save → CSV no pendrive):").grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Entry(e4, textvariable=v_csv, width=40).grid(row=1, column=0, columnspan=2, sticky="we")
    ttk.Button(e4, text="…", width=3, command=lambda: v_csv.set(
        filedialog.askopenfilename(filetypes=[("CSV", "*.csv *.CSV"), ("todos", "*")]) or v_csv.get())
    ).grid(row=1, column=2)
    ttk.Label(e4, text="t0 manual (µs, opcional):").grid(row=2, column=0, sticky="w")
    ttk.Entry(e4, textvariable=v_t0, width=10).grid(row=2, column=1, sticky="w")
    txt4 = ScrolledText(e4, font=MONO, width=60, height=14)
    st4 = {"tau": None}

    def medir_tau():
        t0 = float(v_t0.get().replace(",", ".")) * 1e-6 if v_t0.get().strip() else None
        tau, tr, t, _ = core.tau_csv(v_csv.get(), t0, fig4)
        st4["tau"] = tau
        cv4.draw()
        txt4.delete("1.0", "end")
        txt4.insert("end", t)

    def usar_tau():
        if st4["tau"]:
            v_tau3.set(f"{st4['tau']:.2f}")
            cfg["tau"] = v_tau3.get()
            messagebox.showinfo("τ", f"τ = {st4['tau']:.2f} µs copiado para a aba 3.")
    ttk.Button(e4, text="Calcular τ", command=medir_tau).grid(row=3, column=0, pady=6, sticky="w")
    ttk.Button(e4, text="Usar este τ na aba 3", command=usar_tau).grid(row=3, column=1, sticky="w")
    txt4.grid(row=4, column=0, columnspan=3, sticky="nsew")
    ttk.Label(e4, foreground="#555", wraplength=420, justify="left", text=(
        "Captura: CH1 = CLK, CH2 = TP3, 5 µs/div, trigger na subida do CLK no símbolo A do treinamento "
        "(0→A). Enquadre: um pouco de nível baixo antes e o patamar alto no fim da tela "
        "(o script usa os 10 % iniciais como V0 e os 15 % finais como Vf).")).grid(row=5, column=0, columnspan=3,
                                                                                  sticky="w")
    e4.rowconfigure(4, weight=1)
    e4.columnconfigure(1, weight=1)

    # =====================================================================
    # Aba 5 — tabela da Seção 5.1
    # =====================================================================
    f5 = ttk.Frame(nb, padding=8)
    nb.add(f5, text="5 · Tabela de resultados")
    ttk.Label(f5, text="Adicione os logs (um por condição). Selecione uma linha para editar o τ (µs).").pack(anchor="w")
    tv = ttk.Treeview(f5, columns=("log", "tau"), show="headings", height=8)
    tv.heading("log", text="log")
    tv.heading("tau", text="τ (µs)")
    tv.column("log", width=900)
    tv.column("tau", width=100)
    tv.pack(fill="x")
    b5 = ttk.Frame(f5)
    b5.pack(fill="x", pady=4)
    v_tau5 = tk.StringVar()

    def add_logs():
        for c in filedialog.askopenfilenames(initialdir=pasta("logs") if os.path.isdir(pasta("logs")) else RAIZ,
                                             filetypes=[("logs", "*.txt")]):
            tv.insert("", "end", values=(c, "—"))

    def set_tau():
        for it in tv.selection():
            tv.set(it, "tau", v_tau5.get() or "—")

    def gerar():
        arqs = [tv.item(i)["values"][0] for i in tv.get_children()]
        taus = []
        for i in tv.get_children():
            s = str(tv.item(i)["values"][1]).replace(",", ".")
            try:
                taus.append(float(s))
            except ValueError:
                taus.append(math.nan)
        csvp = os.path.join(v_pasta.get(), "tabela_resultados.csv")
        md = core.tabela(arqs, vref(), taus, csvp)
        txt5.delete("1.0", "end")
        txt5.insert("end", md + f"\n\nCSV gravado em {csvp}\n")

    ttk.Button(b5, text="Adicionar logs…", command=add_logs).pack(side="left")
    ttk.Button(b5, text="Remover", command=lambda: [tv.delete(i) for i in tv.selection()]).pack(side="left", padx=4)
    ttk.Label(b5, text="τ:").pack(side="left", padx=(12, 2))
    ttk.Entry(b5, textvariable=v_tau5, width=8).pack(side="left")
    ttk.Button(b5, text="Aplicar τ à seleção", command=set_tau).pack(side="left", padx=4)
    ttk.Button(b5, text="Gerar tabela (Markdown + CSV)", command=gerar).pack(side="left", padx=12)

    def copiar():
        root.clipboard_clear()
        root.clipboard_append(txt5.get("1.0", "end"))
    ttk.Button(b5, text="Copiar", command=copiar).pack(side="left")
    txt5 = ScrolledText(f5, font=MONO, height=14)
    txt5.pack(fill="both", expand=True)

    # ---------- erros nas callbacks viram caixa de diálogo ----------
    def erro_cb(exc, val, tb):
        if isinstance(val, ValueError) and str(val) == "":
            return
        messagebox.showerror("Erro", f"{exc.__name__}: {val}")
    root.report_callback_exception = erro_cb

    def guardar_cfg():
        cfg.update(vref=v_vref.get(), pasta=v_pasta.get(), porta=v_porta.get(),
                   mod=v_mod.get(), canal=v_canal.get(), tau=v_tau3.get())
        cfg_gravar(cfg)

    def fechar():
        guardar_cfg()
        if st["cap"]:
            st["cap"].parar()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", fechar)

    atualizar_portas()
    processar_fila()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli(sys.argv[1:])
    else:
        gui()
