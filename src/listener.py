##listener.py: barrido de tx_gain con el Pluto, sin depender del kernel del notebook
##mide FER, SER y BER (canal plano y selectivo) y guarda en listener_captures/ despues de CADA ganancia
##si el Pluto da error (ocupado, conexion cortada) prueba con la siguiente ip y sigue desde la misma ganancia
##
##uso: cambiar los parametros de abajo y correr con el python del venv
##   ../.venv/bin/python listener.py
##Ctrl+C para cortar: lo medido hasta ahi ya queda guardado

import os, time, datetime
import numpy as np
import adi

##---------------- Parametros ----------------
IPS = ["192.168.1.35", "192.168.1.31", "192.168.1.34", "192.168.1.32","192.168.1.33"]   ##se prueban en este orden
TX_DESDE = -60          ##tx_gain inicial (dB)
TX_HASTA = -0         ##tx_gain final (dB), incluido
TX_PASO = 1
N = 500                  ##capturas por punto
SF = 7
PL = [12,32,21,5,1]     ##payload (simbolos)
before = 2000           ##silencio antes de la trama
after = 2000            ##silencio despues de la trama
threshold = 0.3
rx_gain = 40
frec = int(800e6)
bw = int(2.5e6)
SCALE = 2**10 * np.sqrt(2**SF)
CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listener_captures")   ##src/listener_captures
RONDAS_MAX = 3          ##si fallan todas las ips esta cantidad de rondas seguidas, se corta
ESPERA = 10             ##segundos de espera entre rondas de ips

##---------------- Funciones (copiadas del notebook) ----------------
def symbolChirp(SF, symbol, up):
    N = 2**SF
    sgn = 1 if up else -1
    time = np.arange(0, N, 1)
    phase = 2 * np.pi * ((symbol + time) % N) * time / N
    return np.exp(1j * sgn * phase) / np.sqrt(N)

class Chirp:
    def __init__(self, SF, symbols, up):
        self.f = []
        for symbol in symbols:
            self.f = np.concatenate((self.f, symbolChirp(SF, symbol, up)))

def makePreamble(SF):
    up = Chirp(SF,[0]*8,True).f
    down = Chirp(SF,[0]*2,False).f
    quarter = Chirp(SF,[0],False).f[:2**SF//4]
    return np.concatenate((up,down,quarter))

def sendPayload(SF, pl):
    return np.concatenate((makePreamble(SF), Chirp(SF,pl,True).f))

def addSilence(samples, before, after):
    return np.concatenate((np.zeros(before), samples, np.zeros(after)))

def bitErrors(tx, est, SF):
    return sum(((int(tx) >> h) & 1) != ((int(est) >> h) & 1) for h in range(SF))

##dechirp + fft: el simbolo es el bin con mas energia
def estimateSymbol(samples):
    n = len(samples)
    k = np.arange(n)
    return int(np.argmax(np.abs(np.fft.fft(samples * np.exp(-2j*np.pi*k**2/n)))))

##correlacion normalizada rho: devuelve (detecto, lag) con lag = indice donde TERMINA el preambulo
def identifyPreamble(x, preamble, threshold):
    rho = np.abs(np.correlate(x, preamble, mode="full")) / (np.linalg.norm(preamble)*np.linalg.norm(x))
    lag = int(np.argmax(rho))
    return rho[lag] > threshold, lag

def freqSelective(samples, h=np.array([np.sqrt(0.8),np.sqrt(0.2)])):
    return np.convolve(samples, h)[:len(samples)]

##---------------- Pluto ----------------
def conectar(ip, buffer_size):
    sdr = adi.Pluto("ip:" + ip)
    sdr.sample_rate = bw
    sdr.rx_lo = frec
    sdr.tx_lo = frec
    sdr.gain_control_mode_chan0 = "manual"
    sdr.rx_hardwaregain_chan0 = rx_gain
    sdr.rx_buffer_size = buffer_size
    sdr.rx_rf_bandwidth = bw
    sdr.tx_rf_bandwidth = bw
    sdr.tx_cyclic_buffer = True
    return sdr

def liberar(sdr):
    for f in (sdr.tx_destroy_buffer, sdr.rx_destroy_buffer):
        try:
            f()
        except Exception:
            pass

##mide un punto (una ganancia, un canal): devuelve (FER, SER, BER)
def medirPunto(sdr, tramaTx, trama, preamble):
    nSym = len(PL)
    nBits = nSym*SF
    periodo = len(tramaTx)
    sdr.tx(np.tile(tramaTx,4)*SCALE)     ##bug del pluto: solo toma 1/4 del buffer
    for j in range(3):                    ##se descartan capturas viejas
        sdr.rx()
    tramasErradas = 0
    simbolosErrados = 0
    bitsErrados = 0
    for i in range(N):
        x = sdr.rx()
        (detecto,lag) = identifyPreamble(x, preamble, threshold)
        if not detecto:
            tramasErradas += 1
            simbolosErrados += nSym
            bitsErrados += nBits
            continue
        inicio = lag - len(preamble) + 1
        if inicio < 0:                        ##cortada al principio -> copia siguiente
            inicio += periodo
        if inicio + len(trama) > len(x):      ##cortada al final -> copia anterior
            inicio -= periodo
        payload = x[inicio+len(preamble) : inicio+len(trama)]
        for k in range(nSym):
            est = estimateSymbol(payload[k*2**SF:(k+1)*2**SF])
            if est != PL[k]:
                simbolosErrados += 1
            bitsErrados += bitErrors(PL[k], est, SF)
    sdr.tx_destroy_buffer()
    return tramasErradas/N, simbolosErrados/(N*nSym), bitsErrados/(N*nBits)

##---------------- Barrido ----------------
tx_list = np.arange(TX_DESDE, TX_HASTA+1, TX_PASO)

preamble = makePreamble(SF)
trama = sendPayload(SF, PL)
tramaTx = addSilence(trama, before, after)
tramas = [tramaTx, freqSelective(tramaTx)]      ##0 = flat, 1 = selectivo
nombres = ["Flat","Freq.sel."]

FER = np.full((2,len(tx_list)), np.nan)     ##nan = punto todavia no medido
SER = np.full((2,len(tx_list)), np.nan)
BER = np.full((2,len(tx_list)), np.nan)
ip_punto = np.array([""]*len(tx_list), dtype="U20")   ##ip con la que se midio cada ganancia

os.makedirs(CARPETA, exist_ok=True)
inicioMedicion = datetime.datetime.now()
archivo = os.path.join(CARPETA, "listener_%s.npz" % inicioMedicion.strftime("%Y-%m-%d_%H-%M-%S"))

def guardar():
    np.savez(archivo, tx_list=tx_list, FER=FER, SER=SER, BER=BER, N=N, SF=SF, PL=np.array(PL),
             threshold=threshold, rx_gain=rx_gain, before=before, after=after,
             ip_punto=ip_punto, fecha=inicioMedicion.strftime("%Y-%m-%d %H:%M:%S"))

print("barrido de tx_gain:", tx_list[0], "a", tx_list[-1], "dB | N =", N, "| guardando en", archivo)

ipActual = 0
sdr = None
rondasFallidas = 0
idx = 0
try:
    while idx < len(tx_list):
        ip = IPS[ipActual]
        try:
            if sdr is None:
                print("conectando a", ip, "...")
                sdr = conectar(ip, 2*len(tramaTx))
            sdr.tx_hardwaregain_chan0 = int(tx_list[idx])
            for canal in range(2):
                (FER[canal,idx], SER[canal,idx], BER[canal,idx]) = medirPunto(sdr, tramas[canal], trama, preamble)
                print("tx_gain =", tx_list[idx], nombres[canal], "FER =", FER[canal,idx], "SER =", SER[canal,idx], "BER =", BER[canal,idx], "| ip", ip)
            ip_punto[idx] = ip
            guardar()                 ##se guarda en cada ganancia
            rondasFallidas = 0
            idx += 1
        except KeyboardInterrupt:
            raise
        except Exception as e:
            ##ocupado, conexion cortada, etc: se libera y se pasa a la siguiente ip (se repite la misma ganancia)
            print("error con", ip, "->", type(e).__name__, e)
            if sdr is not None:
                liberar(sdr)
            sdr = None
            ipActual = (ipActual + 1) % len(IPS)
            if ipActual == 0:          ##se probaron todas las ips
                rondasFallidas += 1
                if rondasFallidas >= RONDAS_MAX:
                    print("fallaron todas las ips", RONDAS_MAX, "veces seguidas, se corta")
                    break
                print("fallaron todas las ips, esperando", ESPERA, "s ...")
                time.sleep(ESPERA)
except KeyboardInterrupt:
    print("\ncortado con Ctrl+C")
finally:
    if sdr is not None:
        liberar(sdr)
    guardar()
    print("guardado en", archivo, "| puntos medidos:", int(np.sum(ip_punto != "")), "de", len(tx_list))
