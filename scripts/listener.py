##listener.py: barridos de tx_gain con el Pluto, repetidos sin parar (o hasta DURACION_MAX)
##cada barrido se guarda en su propio archivo, dentro de una carpeta por ip:
##   data/listener_captures/192.168.1.33/listener_2026-11-18_21-30-00_192.168.1.33.npz
##un archivo tiene datos de UNA sola ip: si la ip se cuelga a mitad del barrido, queda guardado
##lo que se midio con ella y la siguiente ip arranca un archivo nuevo (no se mezclan ips)
##
##errores:
##  - ip ocupada (busy)            -> se prueba la siguiente ip
##  - fallan todas las ips FALLOS_MAX rondas seguidas, o cualquier otro error (conexion cortada, etc)
##                                  -> se ejecuta vpn.sh para reconectar la vpn y se sigue
##
##uso: cambiar los parametros de abajo y correr con el python del venv
##   .venv/bin/python scripts/listener.py      (desde la carpeta ChirpModulation)
##Ctrl+C para cortar: lo medido hasta ahi ya queda guardado

import os, time, datetime, subprocess
import numpy as np
import adi

##---------------- Parametros ----------------
IPS = ["192.168.1.35"]   ##se prueban en este orden
TX_DESDE = -80          ##tx_gain inicial (dB)
TX_HASTA = 0       ##tx_gain final (dB), incluido
TX_PASO = 0.25
N = 2000                  ##capturas por punto
SF = 7
PL = [12,32,21,5,1]     ##payload (simbolos)
before = 2000           ##silencio antes de la trama
after = 2000            ##silencio despues de la trama
threshold = 0.3
rx_gain = 40
frec = int(800e6)
bw = int(2.5e6)
SCALE = 2**10 * np.sqrt(2**SF)

DURACION_MAX = None     ##segundos que dura todo (3600 = 1 hora). None = indefinido
FALLOS_MAX = 1          ##rondas seguidas con todas las ips ocupadas antes de reconectar la vpn
ESPERA_VPN = 20         ##segundos de espera despues de reconectar la vpn
AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(AQUI, "..", "data", "listener_captures")   ##data/listener_captures
VPN_SCRIPT = os.path.join(AQUI, "vpn.sh")

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

##---------------- Errores y vpn ----------------
##busy = el pluto esta ocupado (errno 16 o el mensaje dice busy)
def esBusy(e):
    return getattr(e, "errno", None) == 16 or "busy" in str(e).lower()

def reconectarVPN():
    print(">>> reconectando la vpn con", VPN_SCRIPT)
    try:
        subprocess.run(["bash", VPN_SCRIPT], timeout=120)
    except Exception as e:
        print(">>> fallo el script de la vpn:", type(e).__name__, e)
    print(">>> esperando", ESPERA_VPN, "s ...")
    time.sleep(ESPERA_VPN)

def tiempoVencido():
    return DURACION_MAX is not None and time.time() - t0 > DURACION_MAX

##decide que hacer despues de un error: siguiente ip o reconectar la vpn
def manejarError(e):
    global ipActual, rondasFallidas
    print("error con", IPS[ipActual], "->", type(e).__name__, e)
    if esBusy(e):
        ipActual = (ipActual + 1) % len(IPS)
        if ipActual == 0:                     ##se probaron todas las ips
            rondasFallidas += 1
            print("todas las ips ocupadas (%d/%d)" % (rondasFallidas, FALLOS_MAX))
            if rondasFallidas >= FALLOS_MAX:
                reconectarVPN()
                rondasFallidas = 0
    else:
        ##conexion cortada u otro error: probablemente se cayo la vpn
        reconectarVPN()
        ipActual = (ipActual + 1) % len(IPS)

##guarda el barrido de una ip en su carpeta
def guardar(archivo, fecha, ip, FER, SER, BER):
    np.savez(archivo, tx_list=tx_list, FER=FER, SER=SER, BER=BER, N=N, SF=SF, PL=np.array(PL),
             threshold=threshold, rx_gain=rx_gain, before=before, after=after,
             ip=ip, fecha=fecha)

##---------------- Barridos ----------------
tx_list = np.arange(TX_DESDE, TX_HASTA+1, TX_PASO)
preamble = makePreamble(SF)
trama = sendPayload(SF, PL)
tramaTx = addSilence(trama, before, after)
tramas = [tramaTx, freqSelective(tramaTx)]      ##0 = flat, 1 = selectivo
nombres = ["Flat","Freq.sel."]

t0 = time.time()
ipActual = 0
rondasFallidas = 0
barridos = 0
print("barridos de tx_gain:", tx_list[0], "a", tx_list[-1], "dB | N =", N,
      "| duracion:", "indefinida" if DURACION_MAX is None else "%d s" % DURACION_MAX)

try:
    while not tiempoVencido():
        ip = IPS[ipActual]
        ##1) conectar
        try:
            print("conectando a", ip, "...")
            sdr = conectar(ip, 2*len(tramaTx))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            manejarError(e)
            continue

        ##2) un barrido completo con esta ip, en un archivo nuevo
        inicio = datetime.datetime.now()
        fecha = inicio.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.join(CARPETA, ip), exist_ok=True)
        archivo = os.path.join(CARPETA, ip, "listener_%s_%s.npz" % (inicio.strftime("%Y-%m-%d_%H-%M-%S"), ip))
        FER = np.full((2,len(tx_list)), np.nan)     ##nan = punto no medido
        SER = np.full((2,len(tx_list)), np.nan)
        BER = np.full((2,len(tx_list)), np.nan)
        medidos = 0
        try:
            for idx in range(len(tx_list)):
                if tiempoVencido():
                    break
                sdr.tx_hardwaregain_chan0 = int(tx_list[idx])
                for canal in range(2):
                    (FER[canal,idx], SER[canal,idx], BER[canal,idx]) = medirPunto(sdr, tramas[canal], trama, preamble)
                    print("tx_gain =", tx_list[idx], nombres[canal], "FER =", FER[canal,idx], "SER =", SER[canal,idx], "BER =", BER[canal,idx], "| ip", ip)
                medidos += 1
                guardar(archivo, fecha, ip, FER, SER, BER)      ##se guarda en cada ganancia
            rondasFallidas = 0
            if medidos == len(tx_list):
                barridos += 1
                print("barrido %d terminado con %s: %s" % (barridos, ip, archivo))
            else:
                print("se termino el tiempo: %s quedo con %d de %d ganancias en %s" % (ip, medidos, len(tx_list), archivo))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            ##la ip se colgo a mitad del barrido: lo medido ya esta guardado en su archivo
            if medidos > 0:
                print("progreso de", ip, "guardado:", medidos, "de", len(tx_list), "ganancias en", archivo)
            manejarError(e)
        finally:
            liberar(sdr)
except KeyboardInterrupt:
    print("\ncortado con Ctrl+C")
print("fin | barridos completos:", barridos, "| capturas en", CARPETA)
