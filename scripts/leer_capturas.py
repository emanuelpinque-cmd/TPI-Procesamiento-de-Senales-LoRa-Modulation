##leer_capturas.py: lee las capturas del listener (data/listener_captures/<ip>/*.npz) ordenadas por fecha
##
##uso (desde la carpeta ChirpModulation, con el python del venv):
##   python scripts/leer_capturas.py                    -> lista todas las capturas con su numero
##   python scripts/leer_capturas.py 0                  -> grafica la captura 0 (FER, SER y BER con fecha, hora e ip)
##                                                         si es del modo fake: FER, no detectados y falsas alarmas
##   python scripts/leer_capturas.py -1                 -> grafica la ultima
##   python scripts/leer_capturas.py 192.168.1.33       -> lista solo las de esa ip
##   python scripts/leer_capturas.py 192.168.1.33 0     -> grafica la captura 0 de esa ip
##desde el notebook (carpeta notebook/):  import sys; sys.path.append("../scripts"); from leer_capturas import mostrar; mostrar(0)

import sys, os, glob
import numpy as np
import matplotlib.pyplot as plt

##modo de la captura: "sweep" (FER, SER, BER) o "fake" (FER con 50% fakes). Las viejas no lo guardan: son sweep
def modo(d):
    return str(d["modo"]) if "modo" in d else "sweep"

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "listener_captures")

##archivos ordenados por fecha (el nombre empieza con la fecha). ip=None -> todas las ips
def capturas(ip=None):
    carpeta = "*" if ip is None else ip
    archivos = glob.glob(os.path.join(CARPETA, carpeta, "listener_*.npz"))
    ##el nombre sin "fake_" empieza con la fecha: asi quedan mezcladas sweep y fake por fecha
    return sorted(archivos, key=lambda a: os.path.basename(a).replace("listener_fake_","listener_"))

def listar(ip=None):
    archivos = capturas(ip)
    if len(archivos) == 0:
        print("no hay capturas en", CARPETA if ip is None else os.path.join(CARPETA, ip))
    for i in range(len(archivos)):
        d = np.load(archivos[i])
        medidos = int(np.sum(~np.isnan(d["FER"][0])))
        print("%3d  %s | %-5s | ip %s | tx_gain %d a %d dB | %d/%d ganancias | N=%d"%(
              i, d["fecha"], modo(d), d["ip"], d["tx_list"][0], d["tx_list"][-1], medidos, len(d["tx_list"]), int(d["N"])))

def mostrar(i, ip=None):
    archivos = capturas(ip)
    d = np.load(archivos[i])
    tx_list = d["tx_list"]
    medidos = int(np.sum(~np.isnan(d["FER"][0])))

    fig, ax = plt.subplots(1, 3, figsize=(16,5))
    if modo(d) == "fake":
        ##FER en escala log; no detectados y falsas alarmas son cantidades (de N/2 cada una)
        nombres = ["FER","noDetectados","falsasAlarmas"]
        titulos = ["FER (no detectados + falsas alarmas) / N","Reales no detectados (de N/2)","Fakes detectados = falsas alarmas (de N/2)"]
    else:
        nombres = ["FER","SER","BER"]
        titulos = nombres
    for k in range(3):
        valores = d[nombres[k]]
        graficar = ax[k].semilogy if k == 0 or modo(d) == "sweep" else ax[k].plot
        graficar(tx_list, valores[0], marker="s", label="Flat")
        graficar(tx_list, valores[1], marker="d", label="Freq.sel.")
        ax[k].set_xlabel("tx_gain (dB)")
        ax[k].set_ylabel(nombres[k])
        ax[k].set_title(titulos[k])
        ax[k].legend()
    ##datos de la medicion arriba de los graficos
    fig.suptitle("Captura %d (%s) | fecha %s | ip %s | %s\nSF=%d, N=%d capturas por punto, threshold=%.2f, rx_gain=%d dB, silencio %d/%d, %d/%d ganancias medidas"%(
                 i, modo(d), d["fecha"], d["ip"], os.path.basename(archivos[i]),
                 int(d["SF"]), int(d["N"]), float(d["threshold"]), int(d["rx_gain"]),
                 int(d["before"]), int(d["after"]), medidos, len(tx_list)), fontsize=10)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    args = sys.argv[1:]
    ip = None
    if len(args) > 0 and "." in args[0]:      ##el primer argumento es una ip
        ip = args.pop(0)
    if len(args) == 0:
        listar(ip)
    else:
        mostrar(int(args[0]), ip)
