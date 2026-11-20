##Deteccion del preambulo por dechirp (prueba aparte del notebook)
##
##Idea: en vez de correlacionar, se decodifica la captura en ventanas de 2^SF muestras
##(dechirp + FFT, el mismo receptor de los simbolos) y se busca el preambulo en dos pasos,
##como un receptor LoRa real:
##  1. todas las ventanas se decodifican solo como upchirp y se buscan 8 ceros seguidos
##     (los 8 upchirps del preambulo). Si no hay, se pasa directo al siguiente desfasaje.
##  2. recien cuando aparecen los 8, se aplica el dechirp inverso a las 2 ventanas siguientes
##     (los 2 downchirps). Si dan 0, ese inicio cumple; si no, se sigue buscando.
##Se prueban los 2^SF desfasajes tau (correr la captura 2^SF muestras es correrla un simbolo entero)
##y de todos los inicios que cumplen se elige el de mayor energia (suma de los picos de las 10 ventanas):
##con este chirp cada upchirp son dos mitades iguales, asi que corrido media ventana tambien cumple,
##pero sus ventanas de los bordes quedan con medio preambulo y medio pico.
##
##En la captura se puede poner un "fake" (8 upchirps sin downchirps) antes del preambulo real:
##pasa el paso 1 pero no el paso 2.

import numpy as np
import matplotlib.pyplot as plt

##---------------- Parametros a modificar ----------------
SF = 8
SNR = -5                 ##dB por muestra
BEFORE = 2780            ##donde empieza la trama real = lo que hay que encontrar
AFTER = 1000             ##silencio despues de la trama
PL = [12,32,21,5,1]      ##payload
CON_FAKE = True          ##True: agrega 8 upchirps sueltos (fake) antes de la trama real
FAKE_START = 296         ##donde empieza el fake (tiene que terminar antes de BEFORE)
MIN_UP = 8               ##de los 8 upchirps, cuantos tienen que dar 0
MIN_DOWN = 2             ##de los 2 downchirps, cuantos tienen que dar 0
SEMILLA = 7

N_UP = 8                 ##el preambulo: 8 upchirps
N_DOWN = 2               ##            + 2 downchirps (+ 1/4 de downchirp, que no llena una ventana)


##---------------- Funciones base (copiadas del notebook) ----------------
##chirp de un simbolo, dividido sqrt(N) para que tenga energia 1
def symbolChirp(SF, symbol, up):
    N = 2**SF
    sgn = 1 if up else -1
    time = np.arange(0, N, 1)
    phase = 2 * np.pi * ((symbol + time) % N) * time / N
    return np.exp(1j * sgn * phase) / np.sqrt(N)

def chirps(SF, symbols, up):
    out = np.array([], dtype=complex)
    for i in range(len(symbols)):
        out = np.concatenate((out, symbolChirp(SF, symbols[i], up)))
    return out

##8 upchirps + 2 downchirps + 1/4 de downchirp
def makePreamble(SF):
    N = 2**SF
    up = chirps(SF, [0]*8, True)
    down = chirps(SF, [0]*2, False)
    cuarto = symbolChirp(SF, 0, False)[:N//4]
    return np.concatenate((up, down, cuarto))

def sendPayload(SF, pl):
    return np.concatenate((makePreamble(SF), chirps(SF, pl, True)))

def snrToSigma(snr, SF):
    pn = 1/(10**(snr/10)*(2**SF))
    return np.sqrt(pn/2)

def addNoise(samples, sigma):
    n = len(samples)
    return samples + np.random.normal(0,sigma,n) + 1j*np.random.normal(0,sigma,n)

##receptor de un simbolo: dechirp + FFT, el simbolo es el bin de mayor modulo
def estimateSymbol(window):
    N = len(window)
    time = np.arange(0, N, 1)
    d = window * np.exp(-2j * np.pi * (time ** 2) / N)
    return int(np.argmax(np.abs(np.fft.fft(d))))

##lo mismo para los downchirps: se multiplica por un upchirp (dechirp inverso), un downchirp da bin 0
def estimateSymbolDown(window):
    N = len(window)
    time = np.arange(0, N, 1)
    d = window * np.exp(2j * np.pi * (time ** 2) / N)
    return int(np.argmax(np.abs(np.fft.fft(d))))

def bitErrors(a, b, SF):
    errores = 0
    for h in range(SF):
        if ((a >> h) & 1) != ((b >> h) & 1):
            errores = errores + 1
    return errores


##---------------- El algoritmo ----------------
##decodifica x como upchirps en ventanas de 2^SF muestras desde la muestra 0 (como decodeSymbols)
def decodeUp(x, SF):
    N = 2**SF
    nWin = len(x) // N
    simbolos = [0]*nWin
    for w in range(nWin):                          ##for (int w = 0; w < nWin; w++)
        simbolos[w] = estimateSymbol(x[w*N:(w+1)*N])
    return simbolos

##decodifica como downchirp solo las ventanas pedidas (x ya corrido tau muestras)
def decodeDown(x, SF, ventanas):
    N = 2**SF
    simbolos = []
    for i in range(len(ventanas)):
        w = ventanas[i]
        simbolos.append(estimateSymbolDown(x[w*N:(w+1)*N]))
    return simbolos

##dechirp de varias ventanas a la vez (una fila por ventana): devuelve |FFT| de cada fila
##sgn = -1: dechirp normal (upchirps) | sgn = +1: dechirp inverso (downchirps)
def dechirpWindows(ventanas, SF, sgn):
    N = 2**SF
    time = np.arange(0, N, 1)
    return np.abs(np.fft.fft(ventanas*np.exp(sgn*2j*np.pi*(time**2)/N), axis=1))

##busqueda en dos pasos. Devuelve (encontrado, inicio, eventos)
##eventos = cada vez que aparecieron los 8 upchirps: (tau, ventana, simbolos down, cumple, energia)
def detectTwoSteps(x, SF, minUp, minDown):
    N = 2**SF
    eventos = []
    mejorInicio = -1
    mejorEnergia = 0
    for tau in range(N):                           ##for (int tau = 0; tau < N; tau++)
        nWin = (len(x) - tau)//N
        ventanas = x[tau:tau+nWin*N].reshape(nWin, N)   ##descarta las primeras tau muestras
        fftUp = dechirpWindows(ventanas, SF, -1)   ##paso 1: todo como upchirp
        up = np.argmax(fftUp, axis=1)
        for w in range(nWin - N_UP - N_DOWN + 1):
            ceros = 0
            for i in range(N_UP):
                if up[w+i] == 0:
                    ceros = ceros + 1
            if ceros < minUp:
                continue                           ##no estan los 8 upchirps: siguiente ventana
            ##paso 2: recien ahora, dechirp inverso a las 2 ventanas siguientes
            fftDown = dechirpWindows(ventanas[w+N_UP:w+N_UP+N_DOWN], SF, 1)
            down = np.argmax(fftDown, axis=1)
            cerosDown = 0
            for i in range(N_DOWN):
                if down[i] == 0:
                    cerosDown = cerosDown + 1
            cumple = cerosDown >= minDown
            ##energia = suma de los picos de las 10 ventanas
            energia = np.sum(np.max(fftUp[w:w+N_UP], axis=1)) + np.sum(np.max(fftDown, axis=1))
            eventos.append((tau, w, [int(down[0]), int(down[1])], cumple, energia))
            if cumple and energia > mejorEnergia:
                mejorEnergia = energia
                mejorInicio = tau + w*N
    return mejorInicio >= 0, mejorInicio, eventos


##---------------- Prueba ----------------
np.random.seed(SEMILLA)
N = 2**SF
trama = sendPayload(SF, PL)
x = np.zeros(BEFORE + len(trama) + AFTER, dtype=complex)
x[BEFORE:BEFORE+len(trama)] = trama
if CON_FAKE:
    x[FAKE_START:FAKE_START+N_UP*N] = chirps(SF, [0]*N_UP, True)
x = addNoise(x, snrToSigma(SNR, SF))

(encontrado, inicio, eventos) = detectTwoSteps(x, SF, MIN_UP, MIN_DOWN)
for k in range(len(eventos)):
    (t, w, down, cumple, energia) = eventos[k]
    if not cumple:
        print("tau = %3d, ventana %2d: 8 upchirps en 0 -> downchirps = %s -> no son downchirps"%(t, w, down))
    else:
        print("tau = %3d, ventana %2d: 8 upchirps en 0 -> downchirps = %s -> cumple, energía = %.1f%s"
              %(t, w, down, energia, "  <- ELEGIDO" if t + w*N == inicio else ""))
if encontrado:
    print("encontrado: inicio = %d (real = %d)"%(inicio, BEFORE))
else:
    print("NO encontró el preámbulo (bajar MIN_UP / MIN_DOWN o subir el SNR)")

##comparacion con la correlacion del notebook (identifyPreamble)
preamble = makePreamble(SF)
rho = np.abs(np.correlate(x, preamble, mode="full"))/(np.linalg.norm(preamble)*np.linalg.norm(x))
print("correlación -> inicio = %d | máximo |ρ| = %.2f"%(int(np.argmax(rho)) - len(preamble) + 1, rho.max()))

##barrido completo de tau (solo para graficar): racha mas larga de ceros y BER del preambulo
rachaTau = np.zeros(N)
berTau = np.zeros(N)
tauReal = BEFORE % N                               ##con este tau las ventanas quedan alineadas
ventanaReal = (BEFORE - tauReal) // N              ##ventana donde empieza el preambulo
for t in range(N):
    up = decodeUp(x[t:], SF)
    racha = 0
    for w in range(len(up)):
        if up[w] == 0:
            racha = racha + 1
            rachaTau[t] = max(rachaTau[t], racha)
        else:
            racha = 0
    down = decodeDown(x[t:], SF, [ventanaReal+N_UP, ventanaReal+N_UP+1])
    bits = 0
    for i in range(N_UP):
        bits = bits + bitErrors(up[ventanaReal+i], 0, SF)
    for i in range(N_DOWN):
        bits = bits + bitErrors(down[i], 0, SF)
    berTau[t] = bits/((N_UP+N_DOWN)*SF)


##---------------- Graficos ----------------
VERDE = "#b9e4b0"
ROJO = "#f4b6b0"

##dibuja una fila de casilleros con los simbolos decodificados como upchirp (los 0 en verde).
##marcas = lista de (ventana, simbolos down, estado): borde alrededor de los 10 simbolos del preambulo
##estado: "elegido" (rojo), "cumple" (azul punteado: cumple pero con menos energia) o "no" (naranja punteado:
##los downchirps no dieron 0). Las 2 ventanas de downchirps se muestran con ↓
def drawRow(ax, fila, simbolos, etiqueta, marcas=[], fondo="white"):
    textos = []
    colores = []
    for w in range(len(simbolos)):
        textos.append(str(simbolos[w]))
        colores.append(VERDE if simbolos[w] == 0 else fondo)
    for k in range(len(marcas)):
        (w, down, estado) = marcas[k]
        for i in range(N_DOWN):
            if w+N_UP+i < len(simbolos):
                textos[w+N_UP+i] = str(down[i]) + "↓"
                colores[w+N_UP+i] = VERDE if down[i] == 0 else ROJO
    for w in range(len(simbolos)):                 ##for (int w = 0; w < simbolos.length; w++)
        ax.add_patch(plt.Rectangle((w, -fila-0.9), 0.92, 0.8, facecolor=colores[w], edgecolor="#999999", linewidth=0.6))
        ax.text(w+0.46, -fila-0.5, textos[w], ha="center", va="center", fontsize=8)
    bordes = {"elegido":("tab:red","-"), "cumple":("tab:blue","--"), "no":("tab:orange","--")}
    for k in range(len(marcas)):
        (w, down, estado) = marcas[k]
        (color, estilo) = bordes[estado]
        ax.add_patch(plt.Rectangle((w-0.06, -fila-0.98), N_UP+N_DOWN+0.04, 0.96, fill=False, edgecolor=color, linewidth=2.2, linestyle=estilo))
    ax.text(-0.4, -fila-0.5, etiqueta, ha="right", va="center", fontsize=9)

##---- Figura 1: el algoritmo paso a paso ----
##filas: los primeros intentos y cada tau donde aparecieron los 8 upchirps
filasTau = [0, 1]
for k in range(len(eventos)):
    if eventos[k][0] not in filasTau:
        filasTau.append(eventos[k][0])

nCol = len(decodeUp(x, SF))
fig, ax = plt.subplots(figsize=(16, 0.62*(2*len(filasTau)+2) + 1.2))
fila = 0
drawRow(ax, fila, [0]*(N_UP+N_DOWN), "patrón (preámbulo teórico)", marcas=[(0, [0]*N_DOWN, "elegido")], fondo="#fde9d9")
fila = fila + 1.4
for k in range(len(filasTau)):
    t = filasTau[k]
    if k > 0 and t > filasTau[k-1] + 1:
        ax.text(nCol/2, -fila-0.5, "⋮   (τ = %d ... %d: no hay 8 ceros seguidos)"%(filasTau[k-1]+1, t-1), ha="center", va="center", fontsize=10)
        fila = fila + 1
    marcas = []
    etiqueta = "τ = %d  sin 8 ceros seguidos"%t
    for j in range(len(eventos)):
        (tj, w, down, cumple, energia) = eventos[j]
        if tj != t:
            continue
        if not cumple:
            marcas.append((w, down, "no"))
            etiqueta = "τ = %d  8 up ✔ · 2 down ✘"%t
        elif t + w*N == inicio:
            marcas.append((w, down, "elegido"))
            etiqueta = "τ = %d  cumple · energía %.0f ← ELEGIDO"%(t, energia)
        else:
            marcas.append((w, down, "cumple"))
            etiqueta = "τ = %d  cumple · energía %.0f"%(t, energia)
    drawRow(ax, fila, decodeUp(x[t:], SF), etiqueta, marcas=marcas)
    fila = fila + 1

ax.set_xlim(-9, nCol+0.2)                          ##lugar a la izquierda para las etiquetas
ax.set_ylim(-fila-0.3, 0.3)
ax.axis("off")
if encontrado:
    resumen = "de los τ que cumplen se elige el de mayor energía: el preámbulo empieza en la muestra %d (real = %d)"%(inicio, BEFORE)
else:
    resumen = "ningún τ cumple: no se encontró el preámbulo"
ax.set_title("Búsqueda en dos pasos (SNR = %d dB%s): cada fila es la captura decodificada como upchirp desde la muestra τ\n%s"
             %(SNR, ", con fake" if CON_FAKE else "", resumen), fontsize=11)
fig.text(0.01, 0.01, "verde = 0 · ↓ = ventana decodificada como downchirp · naranja = 8 upchirps pero los downchirps no dan 0 · azul = cumple con menos energía · rojo = elegido",
         fontsize=8.5, color="#444444")
plt.tight_layout()
plt.show()

##---- Figura 2: el barrido completo de tau ----
fig, ax = plt.subplots(2, 1, figsize=(12, 7.5))

##racha mas larga de ceros (upchirps) para cada tau, y donde se probaron los downchirps
ax[0].plot(rachaTau, linewidth=1, label="racha más larga de ceros")
ax[0].axhline(MIN_UP, color="tab:gray", linestyle="--", label="8 upchirps")
yaEtiquetado = []
for k in range(len(eventos)):
    (t, w, down, cumple, energia) = eventos[k]
    if not cumple:
        (marca, color, nombre) = ("X", "tab:orange", "downchirps ✘")
    elif t + w*N == inicio:
        (marca, color, nombre) = ("o", "tab:red", "cumple, elegido (mayor energía)")
    else:
        (marca, color, nombre) = ("o", "tab:blue", "cumple, menos energía")
    ax[0].plot(t, N_UP, marca, color=color, markersize=10, label=nombre if nombre not in yaEtiquetado else None)
    yaEtiquetado.append(nombre)
ax[0].axvline(tauReal, color="tab:green", linestyle=":", label="tau real = %d"%tauReal)
ax[0].set_xlabel("desfasaje tau (muestras)"); ax[0].set_ylabel("ventanas seguidas en 0")
ax[0].set_title("Paso 1 para cada tau: racha de upchirps en 0 (el paso 2 solo se hace donde llega a 8)")
ax[0].set_ylim(0, N_UP+N_DOWN+0.5)
ax[0].legend(loc="upper left", fontsize=8)

##BER de las ventanas del preambulo para cada tau: ¿sirve para buscar "grueso a fino"?
ax[1].plot(berTau, linewidth=1)
ax[1].axvline(tauReal, color="tab:green", linestyle=":", label="tau real = %d"%tauReal)
ax[1].set_xlabel("desfasaje tau (muestras)"); ax[1].set_ylabel("BER del preámbulo")
ax[1].set_title("BER de los símbolos del preámbulo según tau: no baja de a poco hacia el tau real (no sirve buscar grueso a fino)")
ax[1].legend(loc="upper right")

plt.tight_layout()
plt.show()
