##leer_capturas.py: lee las capturas del listener (data/listener_captures/<ip>/*.npz) ordenadas por fecha
##
##uso (desde la carpeta ChirpModulation, con el python del venv):
##   python scripts/leer_capturas.py                    -> lista todas las capturas con su numero
##   python scripts/leer_capturas.py 0                  -> grafica la captura 0 (FER, SER y BER con fecha, hora e ip)
##   python scripts/leer_capturas.py -1                 -> grafica la ultima
##   python scripts/leer_capturas.py 192.168.1.33       -> lista solo las de esa ip
##   python scripts/leer_capturas.py 192.168.1.33 0     -> grafica la captura 0 de esa ip
##desde el notebook (carpeta notebook/):  import sys; sys.path.append("../scripts"); from leer_capturas import mostrar; mostrar(0)

import sys, os, glob
import numpy as np
import matplotlib.pyplot as plt

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "listener_captures")

##archivos ordenados por fecha (el nombre empieza con la fecha). ip=None -> todas las ips
def capturas(ip=None):
    carpeta = "*" if ip is None else ip
    archivos = glob.glob(os.path.join(CARPETA, carpeta, "listener_*.npz"))
    return sorted(archivos, key=os.path.basename)

def listar(ip=None):
    archivos = capturas(ip)
    if len(archivos) == 0:
        print("no hay capturas en", CARPETA if ip is None else os.path.join(CARPETA, ip))
    for i in range(len(archivos)):
        d = np.load(archivos[i])
        medidos = int(np.sum(~np.isnan(d["FER"][0])))
        print("%3d  %s | ip %s | tx_gain %d a %d dB | %d/%d ganancias | N=%d"%(
              i, d["fecha"], d["ip"], d["tx_list"][0], d["tx_list"][-1], medidos, len(d["tx_list"]), int(d["N"])))

def mostrar(i, ip=None):
    archivos = capturas(ip)
    d = np.load(archivos[i])
    tx_list = d["tx_list"]
    medidos = int(np.sum(~np.isnan(d["FER"][0])))

    fig, ax = plt.subplots(1, 3, figsize=(16,5))
    for k, nombre in enumerate(["FER","SER","BER"]):
        valores = d[nombre]
        ax[k].semilogy(tx_list, valores[0], marker="s", label="Flat")
        ax[k].semilogy(tx_list, valores[1], marker="d", label="Freq.sel.")
        ax[k].set_xlabel("tx_gain (dB)")
        ax[k].set_ylabel(nombre)
        ax[k].set_title(nombre)
        ax[k].legend()
    ##datos de la medicion arriba de los graficos
    fig.suptitle("Captura %d | fecha %s | ip %s | %s\nSF=%d, N=%d capturas por punto, threshold=%.2f, rx_gain=%d dB, silencio %d/%d, %d/%d ganancias medidas"%(
                 i, d["fecha"], d["ip"], os.path.basename(archivos[i]),
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
