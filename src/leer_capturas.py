##leer_capturas.py: lee las mediciones de listener_captures/ en orden (la mas vieja es la 0)
##
##uso (desde la carpeta src, con el venv):
##   python leer_capturas.py       -> lista las capturas con su numero
##   python leer_capturas.py 0     -> grafica la captura 0 (FER, SER y BER con fecha, hora e ip)
##   python leer_capturas.py -1    -> grafica la ultima
##desde el notebook:  from leer_capturas import mostrar;  mostrar(0)

import sys, os, glob
import numpy as np
import matplotlib.pyplot as plt

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listener_captures")

##lista de archivos ordenada por nombre (el nombre lleva la fecha, asi que queda por fecha)
def capturas():
    return sorted(glob.glob(os.path.join(CARPETA, "listener_*.npz")))

def listar():
    archivos = capturas()
    if len(archivos) == 0:
        print("no hay capturas en", CARPETA)
    for i in range(len(archivos)):
        d = np.load(archivos[i])
        medidos = int(np.sum(d["ip_punto"] != ""))
        ips = sorted(set(ip for ip in d["ip_punto"] if ip != ""))
        print("%3d  %s  | %s | tx_gain %d a %d dB | %d/%d puntos | N=%d | ip %s"%(
              i, os.path.basename(archivos[i]), d["fecha"], d["tx_list"][0], d["tx_list"][-1],
              medidos, len(d["tx_list"]), int(d["N"]), ", ".join(ips)))

def mostrar(i):
    archivos = capturas()
    d = np.load(archivos[i])
    tx_list = d["tx_list"]
    ips = sorted(set(ip for ip in d["ip_punto"] if ip != ""))
    medidos = int(np.sum(d["ip_punto"] != ""))

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
    fig.suptitle("Captura %d: %s | fecha %s | ip %s\nSF=%d, N=%d capturas por punto, threshold=%.2f, rx_gain=%d dB, silencio %d/%d, %d/%d puntos medidos"%(
                 i, os.path.basename(archivos[i]), d["fecha"], ", ".join(ips),
                 int(d["SF"]), int(d["N"]), float(d["threshold"]), int(d["rx_gain"]),
                 int(d["before"]), int(d["after"]), medidos, len(tx_list)), fontsize=10)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        listar()
    else:
        mostrar(int(sys.argv[1]))
