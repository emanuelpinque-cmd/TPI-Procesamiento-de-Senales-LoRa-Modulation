##listener.py: barridos de tx_gain con el Pluto, repetidos sin parar (o hasta DURACION_MAX)
##dos modos (parametro MODO):
##   "sweep" -> FER, SER y BER con la trama completa (como la 2.3 del notebook)
##   "fake"  -> solo FER, con 50% preambulos reales y 50% fakes (como la 2.3c del notebook)
##cada barrido se guarda en su propio archivo, dentro de una carpeta por ip:
##   data/listener_captures/192.168.1.33/listener_2026-11-18_21-30-00_192.168.1.33.npz        (sweep)
##   data/listener_captures/192.168.1.33/listener_fake_2026-11-18_21-30-00_192.168.1.33.npz   (fake)
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

import os, sys, time, datetime, subprocess
import numpy as np
import adi

##---------------- Parametros ----------------
MODO = "fake"           ##"sweep" = FER, SER y BER | "fake" = solo FER con 50% fakes
IPS = ["192.168.1.35"]   ##se prueban en este orden
TX_DESDE = -80          ##tx_gain inicial (dB)
TX_HASTA = 0            ##tx_gain final (dB), incluido
TX_PASO = 1             ##paso entre ganancias (dB)
N = 200                 ##capturas por punto (en modo fake: la mitad reales, la mitad fakes)
SF = 8
PL = [12,32,21,5,1]     ##payload (simbolos)
before = 2000           ##silencio antes de la trama
after = 2000            ##silencio despues de la trama
threshold = 0.3         ##umbral del modo sweep
thresholdFake = 0.67    ##umbral del modo fake (el fake da rho ~0.88 del real, hay que separarlos)
thresholdFakeSel = None ##umbral del modo fake para el canal SELECTIVO. None = el mismo thresholdFake (un solo umbral)
                        ##hace falta porque en selectivo el rho del real satura mas bajo (~0.545) que el fake plano (~0.585)
DESCARTAR = 10          ##capturas que se tiran despues de cada sdr.tx: las 4 primeras son de la señal ANTERIOR
                        ##(buffers en cola del pluto) y 3-4 vienen vacias (hueco entre tx). Con 3 daba FER ~0.2 de piso
rx_gain = 20            ##20 = el de la 2.3b/2.3c del notebook, donde se eligio thresholdFake
frec = int(800e6)
bw = int(2.5e6)
SCALE = 2**10 * np.sqrt(2**SF)

DURACION_MAX = None     ##segundos que dura todo (3600 = 1 hora). None = indefinido
HORA_FIN = "11:30"      ##hora a la que se corta ("HH:MM", si ya paso es la de mañana). None = sin hora
BARRIDOS_MAX = None     ##barridos completos antes de cortar (1 = uno solo). None = sin limite
FALLOS_MAX = 1          ##rondas seguidas con todas las ips ocupadas antes de reconectar la vpn
ESPERA_VPN = 20         ##segundos de espera despues de reconectar la vpn
ESPERA_BUSY = 60        ##segundos de espera cuando todas las ips estan ocupadas (un compañero lo usa, o quedo
                        ##colgada la conexion vieja despues de un corte de vpn): se espera y se reintenta
AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(AQUI, "..", "data", "listener_captures")   ##data/listener_captures
VPN_SCRIPT = os.path.join(AQUI, "vpn.sh")

##los parametros de arriba se pueden cambiar al correrlo, sin tocar el archivo:
##   .venv/bin/python scripts/listener.py MODO=sweep N=100 TX_DESDE=-60 TX_PASO=2 BARRIDOS_MAX=1
##   (listas: IPS=192.168.1.33,192.168.1.35 | None: HORA_FIN=None)
for arg in sys.argv[1:]:
    (nombre, valor) = arg.split("=", 1)
    if nombre not in globals():
        raise ValueError("parametro desconocido: " + nombre)
    if nombre == "IPS":
        globals()[nombre] = valor.split(",")
    elif valor == "None":
        globals()[nombre] = None
    elif nombre in ("MODO", "HORA_FIN"):
        globals()[nombre] = valor
    else:
        globals()[nombre] = float(valor) if "." in valor else int(valor)
SCALE = 2**10 * np.sqrt(2**SF)          ##se recalcula por si cambio SF

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
def conectar(ip, buffer_size, txGain=None):
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
    if txGain is not None:
        sdr.tx_hardwaregain_chan0 = txGain
    return sdr

##OJO: con libiio v1, tx_destroy_buffer / rx_destroy_buffer NO cierran los streams
##(el tx ciclico viejo sigue vivo). Por eso se borran a mano, igual que liberarPluto del notebook
def liberar(sdr):
    for f in (sdr.tx_destroy_buffer, sdr.rx_destroy_buffer):
        try:
            f()
        except Exception:
            pass
    sdr._tx_block = None
    sdr._tx_buf_stream = None
    sdr._tx_stream = None
    sdr._rx_stream = None

##mide un punto (una ganancia, un canal): devuelve (FER, SER, BER)
def medirPunto(sdr, tramaTx, trama, preamble):
    nSym = len(PL)
    nBits = nSym*SF
    periodo = len(tramaTx)
    sdr.tx(np.tile(tramaTx,4)*SCALE)     ##bug del pluto: solo toma 1/4 del buffer
    for j in range(DESCARTAR):            ##se descartan capturas viejas
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

##modo fake: mide un punto (una ganancia, un canal) con N/2 reales y N/2 fakes
##como cambia la señal, se reconecta para cada una (por lo de libiio v1, ver liberar)
##devuelve (FER, noDetectados, falsasAlarmas)
def medirPuntoFake(ip, txGain, señales, preamble, umbral):
    global sdr
    detecciones = [0, 0]                  ##0 = reales detectados, 1 = fakes detectados
    for k in range(2):
        tramaTx = señales[k]
        sdr = conectar(ip, 2*len(tramaTx), txGain)
        sdr.tx(np.tile(tramaTx,4)*SCALE)  ##bug del pluto: solo toma 1/4 del buffer
        for j in range(DESCARTAR):        ##se descartan capturas viejas
            sdr.rx()
        for i in range(N//2):
            (detecto,_) = identifyPreamble(sdr.rx(), preamble, umbral)
            if detecto:
                detecciones[k] += 1
        liberar(sdr)
        sdr = None
    noDetectados = N//2 - detecciones[0]
    falsasAlarmas = detecciones[1]
    return (noDetectados + falsasAlarmas)/N, noDetectados, falsasAlarmas

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

##instante en que se corta por HORA_FIN (None = sin hora)
def calcularFin():
    if HORA_FIN is None:
        return None
    ahora = datetime.datetime.now()
    (h, m) = HORA_FIN.split(":")
    fin = ahora.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    if fin <= ahora:                          ##ya paso hoy: es la de mañana
        fin += datetime.timedelta(days=1)
    return fin.timestamp()

def tiempoVencido():
    if DURACION_MAX is not None and time.time() - t0 > DURACION_MAX:
        return True
    return tFin is not None and time.time() > tFin

##decide que hacer despues de un error: siguiente ip o reconectar la vpn
def manejarError(e):
    global ipActual, rondasFallidas, erroresSeguidos
    print("error con", IPS[ipActual], "->", type(e).__name__, e)
    if esBusy(e):
        ipActual = (ipActual + 1) % len(IPS)
        if ipActual == 0:                     ##se probaron todas las ips
            rondasFallidas += 1
            print("todas las ips ocupadas (%d/%d), esperando %d s ..." % (rondasFallidas, FALLOS_MAX, ESPERA_BUSY))
            time.sleep(ESPERA_BUSY)
            if rondasFallidas >= FALLOS_MAX:
                reconectarVPN()
                rondasFallidas = 0
    else:
        ##conexion cortada u otro error: probablemente se cayo la vpn -> se reconecta y se REINTENTA la misma ip
        ##(la primera de IPS es la preferida). Recien si falla 2 veces seguidas se pasa a la siguiente
        reconectarVPN()
        erroresSeguidos += 1
        if erroresSeguidos >= 2:
            ipActual = (ipActual + 1) % len(IPS)
            erroresSeguidos = 0

##guarda el barrido de una ip en su carpeta
def guardar(archivo, fecha, ip, FER, SER, BER):
    np.savez(archivo, modo="sweep", tx_list=tx_list, FER=FER, SER=SER, BER=BER, N=N, SF=SF, PL=np.array(PL),
             threshold=threshold, rx_gain=rx_gain, before=before, after=after,
             ip=ip, fecha=fecha)

##modo fake: en vez de SER y BER guarda los no detectados y las falsas alarmas
def guardarFake(archivo, fecha, ip, FER, noDetectados, falsasAlarmas):
    np.savez(archivo, modo="fake", tx_list=tx_list, FER=FER, noDetectados=noDetectados, falsasAlarmas=falsasAlarmas,
             N=N, SF=SF, threshold=thresholdFake, thresholdSel=umbralesFake[1], rx_gain=rx_gain, before=before, after=after,
             ip=ip, fecha=fecha)

##---------------- Barridos ----------------
tx_list = np.round(np.arange(TX_DESDE, TX_HASTA+TX_PASO/2, TX_PASO), 2)   ##TX_PASO puede ser 0.25 (el pluto acepta pasos de 0.25 dB)
preamble = makePreamble(SF)
trama = sendPayload(SF, PL)
tramaTx = addSilence(trama, before, after)
tramas = [tramaTx, freqSelective(tramaTx)]      ##0 = flat, 1 = selectivo
nombres = ["Flat","Freq.sel."]
##modo fake: señalesFake[canal] = [preambulo real, fake], con silencio y por el canal
fake = Chirp(SF,[0]*8,True).f
realTx = addSilence(preamble, before, after)
fakeTx = addSilence(fake, before, after)
señalesFake = [[realTx, fakeTx], [freqSelective(realTx), freqSelective(fakeTx)]]
umbralesFake = [thresholdFake, thresholdFake if thresholdFakeSel is None else thresholdFakeSel]   ##0 = flat, 1 = selectivo
if MODO not in ("sweep", "fake"):
    raise ValueError("MODO tiene que ser 'sweep' o 'fake'")
sdr = None

t0 = time.time()
tFin = calcularFin()
ipActual = 0
rondasFallidas = 0
erroresSeguidos = 0     ##errores seguidos (no busy) con la misma ip
pendiente = None        ##barrido cortado a mitad: (ip, archivo, fecha, FER, SER, BER, medidos)
barridos = 0
print("parametros:", " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "los del archivo")
print("modo", MODO, "| barridos de tx_gain:", tx_list[0], "a", tx_list[-1], "dB | N =", N,
      "| duracion:", "indefinida" if DURACION_MAX is None else "%d s" % DURACION_MAX,
      "| se corta:", "nunca" if tFin is None else datetime.datetime.fromtimestamp(tFin).strftime("%d/%m %H:%M"))

try:
    while not tiempoVencido() and (BARRIDOS_MAX is None or barridos < BARRIDOS_MAX):
        ip = IPS[ipActual]
        ##1) conectar (en modo fake se conecta dentro de medirPuntoFake, una vez por señal)
        try:
            if MODO == "sweep":
                print("conectando a", ip, "...")
                sdr = conectar(ip, 2*len(tramaTx))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            manejarError(e)
            continue

        ##2) un barrido con esta ip. Si el anterior con la MISMA ip quedo cortado (se cayo la vpn),
        ##   se sigue desde la ganancia donde quedo, en el mismo archivo. Si no, archivo nuevo
        if pendiente is not None and pendiente[0] == ip:
            (_, archivo, fecha, FER, SER, BER, medidos) = pendiente
            print("se sigue el barrido cortado de", ip, "desde la ganancia", medidos+1, "de", len(tx_list))
        else:
            inicio = datetime.datetime.now()
            fecha = inicio.strftime("%Y-%m-%d %H:%M:%S")
            os.makedirs(os.path.join(CARPETA, ip), exist_ok=True)
            prefijo = "listener_fake" if MODO == "fake" else "listener"
            archivo = os.path.join(CARPETA, ip, "%s_%s_%s.npz" % (prefijo, inicio.strftime("%Y-%m-%d_%H-%M-%S"), ip))
            FER = np.full((2,len(tx_list)), np.nan)     ##nan = punto no medido
            SER = np.full((2,len(tx_list)), np.nan)     ##en modo fake: no detectados
            BER = np.full((2,len(tx_list)), np.nan)     ##en modo fake: falsas alarmas
            medidos = 0
        pendiente = None
        try:
            for idx in range(medidos, len(tx_list)):
                if tiempoVencido():
                    break
                erroresSeguidos = 0                   ##esta ip anda: se reinicia la cuenta de errores
                if MODO == "sweep":
                    sdr.tx_hardwaregain_chan0 = float(tx_list[idx])
                    for canal in range(2):
                        (FER[canal,idx], SER[canal,idx], BER[canal,idx]) = medirPunto(sdr, tramas[canal], trama, preamble)
                        print("tx_gain =", tx_list[idx], nombres[canal], "FER =", FER[canal,idx], "SER =", SER[canal,idx], "BER =", BER[canal,idx], "| ip", ip)
                    medidos += 1
                    guardar(archivo, fecha, ip, FER, SER, BER)      ##se guarda en cada ganancia
                else:
                    for canal in range(2):
                        (FER[canal,idx], SER[canal,idx], BER[canal,idx]) = medirPuntoFake(ip, float(tx_list[idx]), señalesFake[canal], preamble, umbralesFake[canal])
                        print("tx_gain =", tx_list[idx], nombres[canal], "FER =", FER[canal,idx], "| no detectados =", int(SER[canal,idx]), "| falsas alarmas =", int(BER[canal,idx]), "| ip", ip)
                    medidos += 1
                    guardarFake(archivo, fecha, ip, FER, SER, BER)  ##se guarda en cada ganancia
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
                pendiente = (ip, archivo, fecha, FER, SER, BER, medidos)   ##para seguirlo despues
            manejarError(e)
        finally:
            if sdr is not None:
                liberar(sdr)
                sdr = None
except KeyboardInterrupt:
    print("\ncortado con Ctrl+C")
print("fin | barridos completos:", barridos, "| capturas en", CARPETA)
