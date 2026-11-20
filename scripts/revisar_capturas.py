##revisar_capturas.py: resumen en texto + un PNG por captura (en data/listener_logs/graficos/), sin abrir ventanas
##uso: .venv/bin/python scripts/revisar_capturas.py data/listener_captures/<ip>/archivo.npz [...]
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SALIDA = "/home/emanuelp/Projects/Python/LoRa-Tp/ChirpModulation/data/listener_logs/graficos"
os.makedirs(SALIDA, exist_ok=True)

for archivo in sys.argv[1:]:
    d = np.load(archivo)
    modo = str(d["modo"]) if "modo" in d else "sweep"
    tx = d["tx_list"]
    FER = d["FER"]
    medidos = int(np.sum(~np.isnan(FER[0])))
    nombres = ["FER", "noDetectados", "falsasAlarmas"] if modo == "fake" else ["FER", "SER", "BER"]
    print("==", os.path.basename(archivo), "| modo", modo, "| ip", d["ip"], "| N", int(d["N"]), "|", medidos, "/", len(tx), "ganancias")
    for k in range(2):
        fila = " ".join("%g:%.3f" % (tx[i], FER[k, i]) for i in range(len(tx)) if not np.isnan(FER[k, i]))
        print("   FER", ["plano", "selec"][k], fila)
    if modo == "fake":
        for k in range(2):
            print("   noDet/falsas", ["plano", "selec"][k],
                  " ".join("%g:%d/%d" % (tx[i], d["noDetectados"][k, i], d["falsasAlarmas"][k, i]) for i in range(len(tx)) if not np.isnan(FER[k, i])))
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for k in range(3):
        v = d[nombres[k]]
        log = k == 0 or modo == "sweep"
        for c, (m, lab) in enumerate([("s", "Flat"), ("d", "Freq.sel.")]):
            y = np.where(v[c] > 0, v[c], np.nan) if log else v[c]
            (ax[k].semilogy if log else ax[k].plot)(tx, y, marker=m, label=lab)
        ax[k].set_title(nombres[k]); ax[k].set_xlabel("tx_gain (dB)"); ax[k].grid(True, which="both", alpha=0.3); ax[k].legend()
    fig.suptitle("%s | %s | ip %s | N=%d | %d/%d ganancias" % (os.path.basename(archivo), modo, d["ip"], int(d["N"]), medidos, len(tx)), fontsize=10)
    plt.tight_layout()
    png = os.path.join(SALIDA, os.path.basename(archivo).replace(".npz", ".png"))
    plt.savefig(png, dpi=90)
    plt.close(fig)
    print("   ->", png)
