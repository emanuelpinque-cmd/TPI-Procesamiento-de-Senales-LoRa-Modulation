# Guía de estudio — LoRa como FSCM

> Para pasar al cuaderno. Los números son los del TP: **SF = 8**, **N = 2^SF = 256**, **B = 2.5 MHz** en el Pluto.

---

## Parte 1 — Teoría

### 1. ¿Qué es LoRa?
- Modulación para **LPWAN** (redes de baja potencia y largo alcance), usada en IoT: sensores que mandan pocos datos, lejos y gastando poco.
- Es la capa física de **LoRaWAN**.
- Vangelista la describe como **FSCM** (*Frequency Shift Chirp Modulation*): cada símbolo es un **chirp** (una rampa de frecuencia) y el símbolo **corre dónde arranca la rampa**.
- Contra: la tasa es baja. Sin codificación: **R = SF · B / 2^SF**.
  - SF = 8, B = 2.5 MHz → R ≈ 78 kbit/s.

### 2. Bits → símbolo (ec. 1)
- Cada símbolo junta **SF bits**: `s = Σ w_h · 2^h`, h = 0 … SF−1 (w₀ es el bit menos significativo).
- Hay **2^SF símbolos posibles**: s ∈ {0, 1, …, N−1}.
- SF = 8 → 8 bits por símbolo, 256 símbolos.

### 3. El chirp (ecs. 2–3)
- Una muestra cada T = 1/B. El símbolo dura **Ts = N · T = 2^SF / B**.
  - SF = 8, B = 2.5 MHz → Ts = 102.4 µs.

```
c[k] = (1/√N) · exp( j2π · [(s + k) mod N] · k / N ),   k = 0 … N−1
```

- La frecuencia **crece lineal** con k: es una rampa. El símbolo `s` solo cambia **la frecuencia inicial**, de ahí *Frequency Shift*.
- El **mod N**: cuando la frecuencia llega al máximo (B), vuelve a 0.
- El **1/√N** deja cada chirp con **energía 1**. Todos los símbolos tienen la misma energía, que es lo que supone el receptor óptimo.
- **Downchirp** = conjugado del upchirp (la rampa baja). Se usa en el preámbulo.

### 4. Ortogonalidad (ecs. 4–9)
- Producto interno discreto: `⟨x, y⟩ = Σ x[k] · y*[k]`.
- Los chirps de símbolos distintos son **ortogonales**: `⟨c_i, c_q⟩ = 0` si i ≠ q, y `= 1` si i = q.
- Por eso el receptor los puede distinguir sin que se mezclen.

### 5. Receptor óptimo: dechirp + FFT (ecs. 10–16)
- Lo recibido: **r = c + w** (w = ruido blanco gaussiano complejo).
- Con símbolos equiprobables, de igual energía y **sincronismo perfecto**, el receptor óptimo proyecta r sobre los N chirps y elige el de mayor `|⟨r, c_q⟩|²`.
- **El mod desaparece:** como k es entero, `e^{j2π(s+k−N)k/N} = e^{j2π(s+k)k/N}`. Entonces
  `c[k] = (1/√N) · e^{j2π(s·k + k²)/N}`.
- Se hace en **dos pasos**:
  1. **Dechirp:** multiplicar por `e^{−j2πk²/N}`. El término k² se cancela y queda un **tono puro** `(1/√N)·e^{j2π s k/N}`.
  2. **FFT de N puntos:** el tono se convierte en un **pico en el bin s**.
- **Símbolo estimado = bin con mayor módulo** (`argmax |FFT|`).
- La FFT calcula las N proyecciones de una sola vez.

### 6. Ganancia de procesamiento
- El dechirp + FFT junta en **un solo bin** la energía de las N muestras. El ruido queda repartido en todos los bins.
- Ganancia = **N = 2^SF**, en dB: **10·log₁₀(N)**.

| SF | N | Ganancia |
|---|---|---|
| 7 | 128 | 21 dB |
| 8 | 256 | 24 dB |
| 10 | 1024 | 30 dB |

- Por eso **LoRa funciona con SNR negativa**: la señal está por debajo del ruido en el tiempo, pero el pico de la FFT sobresale.
- **Trade-off:** más SF → más alcance (más robusto al ruido), pero cada símbolo tarda el doble → menos tasa.

### 7. Ruido y SNR
- SNR **por muestra**. El chirp tiene potencia `1/N` por muestra.
- Potencia de ruido: `σ_w² = 1 / (N · 10^(SNR/10))`.
- El ruido es complejo → se reparte entre I y Q: **σ = √(σ_w² / 2)** por componente.

### 8. Canal plano vs selectivo (sección IV)
- **Plano:** solo ruido (h = [1]).
- **Selectivo:** **h = [√0.8, √0.2]** → un camino directo y una copia más débil, retrasada 1 muestra (multicamino). Energía total 1.
- **Qué hace:** la copia retrasada, después del dechirp, cae **2 bins al costado** del símbolo. El pico pierde energía (queda 0.8) y aparece un segundo pico chico.
- **Resultado:** FSCM pierde poco, porque **cada chirp barre toda la banda** y promedia la atenuación del canal. Las curvas se corren unos dB a la derecha.

### 9. Métricas
| Métrica | Qué cuenta |
|---|---|
| **BER** (*Bit Error Rate*) | bits errados / bits enviados |
| **SER** (*Symbol Error Rate*) | símbolos errados / símbolos enviados |
| **FER** (*Frame Error Rate*) | tramas con el **preámbulo no detectado** / tramas (así lo define el profe) |

- Un símbolo errado cambia **entre 1 y SF bits** → **BER < SER**.
- Con SNR muy baja: **BER → 0.5** (los bits salen al azar) y **SER → casi 1**.

---

## Parte 2 — Detección del preámbulo (lo central del TP)

### 10. El preámbulo
- **No está en el paper** (el paper supone sincronismo perfecto). Sale del práctico.
- **8 upchirps** (símbolo 0) + **2 downchirps** + **¼ de downchirp** = **10.25 símbolos**.
  - SF = 8 → 10.25 · 256 = **2624 muestras**.
  - Energía **Ep = 10.25** (cada chirp tiene energía 1).
- **Upchirps:** sirven para detectar.
- **Downchirps:** marcan **dónde termina** el preámbulo. No se parecen a ningún símbolo del payload, que son todos upchirps.

### 11. Por qué hace falta
- En una captura real **no se sabe cuándo llega la trama**: delay de propagación, filtros del hardware, el RX empieza a grabar en cualquier momento.
- Sin saber dónde empieza la trama, no se sabe dónde cortar las ventanas de N muestras del payload.

### 12. Las 5 fases
1. **Captura:** silencio + trama + silencio, con ruido.
2. **Correlación** con el preámbulo conocido:
   `c[ℓ] = |⟨x, p_ℓ⟩| = |Σ x[n+ℓ] · p*[n]|`
   Es el **mismo producto interno** del paper, con el preámbulo corrido ℓ muestras. Es máximo cuando quedan alineados.
3. **Normalización** (Cauchy–Schwarz):
   `ρ[ℓ] = c[ℓ] / (‖x‖ · ‖p‖) = |cos θ| ∈ [0, 1]`
   - ρ = 1 → la captura es exactamente el preámbulo (a menos de una escala).
   - ρ = 0 → ortogonales.
4. **Decisión:** hay preámbulo si **max ρ > umbral**.
5. **Ubicación:** `np.correlate(..., "full")` da el índice donde **termina** el preámbulo →
   **inicio = lag − len(preámbulo) + 1**.

### 13. ¿Por qué ρ y no |c|?
- |c| **depende de la amplitud** recibida. En el Pluto la amplitud cambia con las ganancias, así que un umbral fijo sobre |c| no sirve.
- ρ **no depende de la escala**: se divide por las normas.
- Contra: ρ baja con **todo lo que hay en la captura además del preámbulo** (payload, ruido, silencio con ruido), porque agrandan ‖x‖. Por eso **el umbral depende de la captura**.

### 14. Valores de ρ para recordar
| Caso | ρ sin ruido |
|---|---|
| Solo el preámbulo | 1 |
| **Fake** (8 upchirps, sin downchirps) | √(8/10.25) ≈ **0.88** |
| Preámbulo + 5 símbolos de payload | √(10.25/15.25) ≈ **0.82** |
| Captura del Pluto con 2 tramas (buffer = 2 períodos) | √(10.25/30.5) ≈ **0.58** |

- Para rechazar el fake sin ruido, el umbral tiene que estar **arriba de ≈ 0.88** (si la captura es solo preámbulo).
- **Picos laterales cada N muestras:** son los upchirps del preámbulo alineándose con upchirps corridos. El máximo verdadero es cuando se alinean los 10.25 símbolos.

### 15. ¿Por qué todo el preámbulo y no un solo chirp?
- Con **un solo chirp** aparecen picos en cada chirp del preámbulo y en símbolos del payload → no se sabe dónde empieza.
- Con **todo el preámbulo** se suma la energía de 2624 muestras (en lugar de 256) y la forma es única gracias a los downchirps.

### 16. FER vs SNR
- Con umbral fijo, la transición es **abrupta** (≈ 1 dB): de FER ≈ 1 a FER ≈ 0.
- El canal selectivo la corre a la derecha (necesita más SNR).

---

## Parte 3 — El Pluto (ADALM-Pluto)

### 17. Cómo está armada la prueba
- **TX y RX en el mismo equipo.** LO en **800 MHz**, frecuencia de muestreo **= B = 2.5 MHz**.
- **Buffer cíclico de TX:** se manda una trama y el Pluto la repite sin parar hasta `tx_destroy_buffer()`.
- **Silencio** antes y después de la trama → en la captura se ve dónde está la trama.
- **Buffer de RX = 2 períodos:** como el RX arranca en cualquier momento, grabando el doble **siempre entra una trama completa**.
- **Bug del Pluto (libiio):** solo transmitía ¼ del buffer → la trama se manda **repetida 4 veces** (`np.tile(trama, 4)`).
- **SCALE = 2¹⁰ · √N:** el √N deshace la normalización del chirp y el 2¹⁰ lo lleva al rango del DAC.
- **`rx_gain` manual (fijo):** si fuera automático compensaría los cambios de potencia y no se verían.
- **`tx_gain` hace de variable de SNR:** el SNR no se mide directamente, por eso las curvas están en función de `tx_gain`.
- Las primeras capturas después de cada `tx()` se **descartan** (pueden traer datos viejos del buffer).

### 18. Canal selectivo en el Pluto
- El canal del paper se aplica **por software** antes de transmitir (`freqSelective`). El aire agrega el canal real.

### 19. Problemas que aparecieron (y cómo se resolvieron)
- **Transmitía ¼ del buffer** → repetir la trama 4 veces.
- **El inicio detectado daba negativo** cuando el preámbulo quedaba cortado al principio de la captura → usar la otra copia de la trama (el TX es cíclico).
- **Piso de FER en 0.2** en un barrido → capturas viejas en el buffer → descartar capturas después de cada `tx()`.
- **La VPN se caía** (ConnectionReset / BrokenPipe) → pocas capturas por punto, guardar después de cada ganancia y el `listener_v2.py` que reconecta solo.

---

## Parte 4 — Preguntas frecuentes

**¿Qué diferencia hay entre FSK y FSCM?**
En FSK cada símbolo es un tono fijo. En FSCM cada símbolo es un chirp que barre toda la banda; el símbolo solo corre la frecuencia inicial. Barrer toda la banda lo hace robusto al canal selectivo.

**¿Por qué el receptor hace dechirp y FFT en vez de comparar con los 256 chirps?**
Es lo mismo: las 256 proyecciones del receptor óptimo, desarrolladas, dan una DFT de la señal multiplicada por el downchirp. La FFT las calcula todas juntas en O(N log N).

**¿Por qué funciona con SNR negativa?**
Por la ganancia de procesamiento N: el dechirp + FFT concentra la energía del chirp en un bin, mientras el ruido se reparte en los N bins. Con SF = 8 son 24 dB de ganancia.

**¿Qué pasa si subo el SF?**
Más ganancia (+3 dB por cada SF), más alcance y robustez, pero el símbolo dura el doble y la tasa baja. Es el trade-off alcance vs velocidad.

**¿Por qué la BER es menor que la SER?**
Un símbolo errado cuenta 1 en la SER pero cambia entre 1 y SF bits. Con un error al azar cambia en promedio la mitad de los bits, así que BER ≈ SER/2.

**¿Por qué el canal selectivo afecta poco?**
Cada chirp recorre toda la banda, así que promedia la atenuación del canal. Lo que hace la copia retrasada es sacarle energía al pico (0.8) y poner un segundo pico chico a 2 bins.

**¿Qué supone el paper que no se cumple en la realidad?**
Sincronismo perfecto: que el receptor sabe dónde empieza cada símbolo. Eso es lo que resuelve el preámbulo, que no está en el paper.

**¿Para qué están los downchirps del preámbulo?**
Para marcar el final del preámbulo. Los upchirps solos se confunden con el payload (todos los símbolos son upchirps); los downchirps no se parecen a ningún símbolo.

**¿Qué es la correlación normalizada?**
El coseno del ángulo entre la captura y el preámbulo corrido (Cauchy–Schwarz). Vale entre 0 y 1 y no depende de la amplitud.

**¿Cómo se elige el umbral?**
Es un compromiso: bajo → detecta con poco SNR pero da falsas alarmas (el fake pasa); alto → rechaza el fake pero pierde tramas con ruido. Depende de lo que haya en la captura. En el opcional está la curva ROC (detección vs falsa alarma) y el barrido de umbral.

**¿Qué es una falsa alarma?**
Detectar un preámbulo donde no lo hay. Se prueba con el fake: 8 upchirps sin downchirps.

**¿Por qué el inicio detectado en el Pluto no coincide con el silencio que puse?**
Porque el RX empieza a grabar en cualquier momento del ciclo. El silencio sirve para ver la trama separada, no para conocer el retardo.

**¿Por qué el buffer de RX es el doble del período?**
Para que siempre entre una trama completa, empiece donde empiece la captura (como en una UART, que no sabe cuándo llega el bit de start).

**¿Por qué se repite la trama 4 veces?**
Por un bug de la versión de libiio: el Pluto solo transmitía la primera cuarta parte del buffer.

**¿Por qué las curvas del Pluto están en función de `tx_gain` y no de SNR?**
Porque el SNR en el receptor no se mide; se varía la potencia de transmisión. Más negativo = menos potencia = peor SNR.

**¿Por qué pocas capturas por punto?**
Por la VPN, que se cortaba a mitad de la medición. La resolución de cada punto es 1/N (con N = 10, un error mueve el FER 0.1).

**¿En qué se diferencia de LoRa real?**
LoRa real agrega sync word, corrección de CFO (corrimiento de frecuencia entre TX y RX), codificación de canal (Hamming), interleaving, código Gray, header y CRC. Acá está la capa física básica.

**¿Qué es el LMMSE del opcional?**
Un estimador alternativo (informe de la Prof. Corral Briones): toma la salida del dechirp como estimación LS y la filtra con un Wiener. En las pruebas a −1 dB acertó menos que el LS, así que queda como pendiente.

---

## Parte 5 — Fórmulas para memorizar

```
N = 2^SF                          Ts = N / B
s = Σ w_h · 2^h                   R = SF · B / N
c[k] = (1/√N) e^{j2π[(s+k) mod N]k/N}
dechirp: d[k] = r[k] · e^{−j2πk²/N}   →   ŝ = argmax |FFT(d)|
Ganancia = 10·log10(N) dB
σ_w² = 1 / (N · 10^(SNR/10))      σ = √(σ_w²/2)
h_sel = [√0.8, √0.2]
Preámbulo: 8 up + 2 down + ¼ down = 10.25 símbolos,  Ep = 10.25
c[ℓ] = |Σ x[n+ℓ] p*[n]|           ρ = c / (‖x‖‖p‖) = |cos θ|
inicio = lag − len(p) + 1
ρ_fake = √(8/10.25) ≈ 0.88
```

---

## Parte 6 — Estudiar el código

> Lo mínimo para entender y defender el código. Los bloques salen del notebook (`notebook/LoRa_V8.ipynb`); algunos están un poco resumidos (sin los gráficos ni los prints) para que sea más fácil copiarlos. Al lado de cada línea, qué hace.

### 6.1 Chirp de un símbolo (`symbolChirp`)
```python
def symbolChirp(SF, symbol, up):
    N = 2**SF                                   # muestras por símbolo
    sgn = 1 if up else -1                       # up = rampa que sube, down = la conjugada
    time = np.arange(0, N, 1)                   # k = 0 ... N-1
    phase = 2*np.pi*((symbol + time) % N)*time/N    # fase de la ec. (3)
    return np.exp(1j*sgn*phase) / np.sqrt(N)    # /sqrt(N) -> energía 1
```
- Es **la ecuación (3)** escrita tal cual.
- `% N` es el **mod N**: la rampa vuelve a 0 al llegar al máximo.

### 6.2 Secuencia y preámbulo (`Chirp`, `makePreamble`, `sendPayload`)
```python
class Chirp:
    def __init__(self, SF, symbols, up):
        self.f = []
        for symbol in symbols:                  # un chirp por símbolo, uno atrás del otro
            self.f = np.concatenate((self.f, symbolChirp(SF, symbol, up)))
    def addNoise(self, sigma):                  # ruido gaussiano complejo (I y Q)
        n = len(self.f)
        self.f = self.f + np.random.normal(0,sigma,n) + 1j*np.random.normal(0,sigma,n)

def makePreamble(SF, noise):
    upChirps   = Chirp(SF,[0]*8,True)           # 8 upchirps (símbolo 0)
    downChirps = Chirp(SF,[0]*2,False)          # 2 downchirps
    downChirp  = Chirp(SF,[0],False)            # 1 downchirp más ...
    downChirp.f = downChirp.f[:-int(3*len(downChirp.f)/4)]   # ... del que queda 1/4
    return np.concatenate((upChirps.f, downChirps.f, downChirp.f))   # 10.25 símbolos

def sendPayload(SF, pl, noise):                 # trama = preámbulo + payload
    p = makePreamble(SF, noise)
    pl = Chirp(SF, pl, True)
    pl.addNoise(noise)
    return np.concatenate((p, pl.f))
```

### 6.3 SNR → ruido (`snrToSigma`)
```python
def snrToSigma(snr, SF):
    pn = 1/(10**(snr/10)*(2**SF))   # potencia de ruido: el chirp tiene potencia 1/2^SF por muestra
    return np.sqrt(pn/2)            # se reparte entre I y Q
```

### 6.4 Receptor: dechirp + FFT (`chirpDown`, `estimateSymbol`)
```python
def chirpDown(self):
    time = np.arange(0, self.lenght, 1)
    d = self.samples * np.exp(-2j*np.pi*(time**2)/self.lenght)   # dechirp: queda un tono puro
    return np.fft.fft(d) / np.sqrt(self.lenght)                  # FFT: el tono es un pico

def estimateSymbol(self):
    fft = self.chirpDown()
    return int(np.argmax(np.abs(fft)))     # símbolo = bin con más energía
```
- Son **las ecuaciones (15) y (16)** del paper: multiplicar por el downchirp y hacer la DFT.

### 6.5 Canal selectivo (`freqSelective`)
```python
def freqSelective(self, h=np.array([np.sqrt(0.8), np.sqrt(0.2)])):
    self.samples = np.convolve(self.samples, h)[:self.lenght]   # convolución con h, mismo largo
```

### 6.6 Detección del preámbulo (`identifyPreamble`) ← lo central
```python
def identifyPreamble(self, preamble, threshold):
    rho = np.correlate(self.samples, preamble, mode="full") / (np.linalg.norm(preamble)*np.linalg.norm(self.samples))
    lag = np.argmax(np.abs(rho))              # dónde se parece más
    if np.abs(rho[lag]) > threshold:          # decisión con umbral
        return True, lag                      # lag = índice donde TERMINA el preámbulo
    else:
        return False, math.nan
```
- `np.correlate(x, p, "full")` → **fase 2** (la correlación: producto interno con el preámbulo corrido).
- dividir por `norm(p)·norm(x)` → **fase 3** (ρ = |cos θ|, entre 0 y 1).
- `> threshold` → **fase 4** (decisión).
- **Fase 5** (fuera de la función): `inicio = lag - len(preamble) + 1`.

### 6.7 Realinear y decodificar el payload (`fixPreamble`, `decodeSymbols`) — opcional
```python
def fixPreamble(self, preamble, threshold):
    (correct, lag) = self.identifyPreamble(preamble, threshold)
    if correct:
        self.samples = np.roll(self.samples, -1-lag+len(preamble))   # rota: el preámbulo queda al inicio
    return correct

##dentro de decodeSymbols:
payload = self.samples[len(preamble):]          # lo que viene después del preámbulo
nSymbols = int(len(payload)/(2**SF))
for i in range(nSymbols):                       # una ventana de 2^SF muestras por símbolo
    window = Sampling(payload[i*2**SF:(i+1)*2**SF])
    symbols[i] = window.estimateSymbol()
```
- `-1-lag+len(preamble)` = −inicio: rotar para atrás hasta que el preámbulo quede en la muestra 0.
- `np.roll` sirve porque el Pluto repite la trama en loop (la captura es circular).

### 6.8 Métricas en simulación (`getSER`, `getBER`, `getFER`)
```python
def getSER(N, SF, send, noise, sel=False):
    errors = 0
    for i in range(N):
        (tx, est) = sendOneSymbol(SF, send, noise, sel)   # manda un símbolo por el canal
        if tx != est:
            errors += 1
    return errors/N                                       # símbolos errados / N

def getBER(N, SF, send, noise, sel=False):
    errors = 0
    for i in range(N):
        (tx, est) = sendOneSymbol(SF, send, noise, sel)
        errors += bitErrors(tx, est, SF)                  # cuántos bits cambiaron
    return errors/(N*SF)                                  # bits errados / bits enviados

def getFER(N, SF, noise, threshold, sel=False):
    errors = 0
    p = makePreamble(SF, 0.0)                             # referencia sin ruido
    for i in range(N):
        c = Sampling(makePreamble(SF, noise))             # preámbulo con ruido
        (correct, _) = c.identifyPreamble(p, threshold)
        if not correct:
            errors += 1                                   # preámbulo no encontrado
    return errors/N
```

### 6.9 Pluto: configuración (2.1)
```python
sdr = adi.Pluto(ip)
sdr.sample_rate = bw                      # frecuencia de muestreo = B
sdr.rx_lo = frec                          # LO de RX y TX en 800 MHz
sdr.tx_lo = frec
sdr.gain_control_mode_chan0 = "manual"    # ganancia fija (sin AGC)
sdr.rx_hardwaregain_chan0 = rx_gain
sdr.rx_buffer_size = 2*len(tramaTx)       # 2 períodos: siempre entra una trama completa
sdr.tx_hardwaregain_chan0 = tx_gain
sdr.tx_cyclic_buffer = True               # repite la trama sin parar
```

### 6.10 Pluto: transmitir, capturar y medir (2.2 y 2.3)
```python
sdr.tx(np.tile(tramaTx,4)*SCALE)    # x4 por el bug del Pluto (solo manda 1/4)
sdr.rx()                            # se descarta la primera captura
x = sdr.rx()                        # la captura que se analiza

(detecto, lag) = Sampling(x).identifyPreamble(preamble, threshold)
if not detecto:
    tramasErradas += 1              # FER: no se encontró la trama ...
    simbolosErrados += nSym         # ... y se pierde todo el payload
    bitsErrados += nBits
else:
    inicio = lag - len(preamble) + 1
    if inicio < 0:                        # trama cortada al principio -> copia siguiente
        inicio = inicio + periodo
    if inicio + len(trama) > len(x):      # trama cortada al final -> copia anterior
        inicio = inicio - periodo
    payload = x[inicio+len(preamble) : inicio+len(trama)]
    for k in range(nSym):                 # cada símbolo con dechirp + FFT
        est = Sampling(payload[k*2**SF:(k+1)*2**SF]).estimateSymbol()
        if est != PL[k]:
            simbolosErrados += 1
        bitsErrados += bitErrors(PL[k], est, SF)
```

### 6.11 El listener (`scripts/listener.py`), en palabras
1. Prueba conectarse a una IP de la lista.
2. Hace un barrido de `tx_gain` y guarda **después de cada ganancia** en `data/listener_captures/<ip>/`.
3. Si la IP está **ocupada** (busy) → prueba la siguiente IP.
4. Si fallan **todas** varias veces, o hay otro error (conexión cortada) → corre `vpn.sh` para reconectar la VPN.
5. Cada archivo tiene datos de **una sola IP**: si una se cuelga, lo medido queda guardado y la siguiente empieza un archivo nuevo.
6. Repite barridos hasta `DURACION_MAX` (o para siempre con `None`).

### 6.12 Preguntas sobre el código
**¿Por qué `np.correlate` y no un `for`?** Hace la misma suma (producto interno en cada corrimiento) pero mucho más rápido.

**¿Por qué el índice de `np.correlate` es el final del preámbulo?** Con `mode="full"` el índice cuenta desde que el preámbulo empieza a solaparse con la captura; el solapamiento completo termina `len(p) − 1` muestras después. Por eso `inicio = lag − len(p) + 1`.

**¿Por qué `np.roll` en `fixPreamble`?** La captura es circular (TX cíclico): rotar es mover el inicio de la trama a la muestra 0 sin perder muestras.

**¿Por qué `/np.sqrt(N)` en el chirp y en la FFT?** En el chirp, para que tenga energía 1. En la FFT, para que el pico valga 1 sin ruido (es el 1/√N de la ec. 16).

**¿Por qué `SCALE = 2**10 * np.sqrt(2**SF)`?** El √N deshace la normalización (las muestras valen 1/√N, muy chicas) y el 2¹⁰ lleva la señal al rango del DAC del Pluto.

**¿Qué es `periodo`?** El largo de silencio + trama + silencio: lo que el TX repite. La captura dura 2 períodos.

---

## Referencias
1. L. Vangelista, "Frequency Shift Chirp Modulation: The LoRa Modulation," *IEEE Signal Processing Letters*, vol. 24, no. 12, pp. 1818–1821, 2017.
2. G. Corral Briones, informe sobre el estimador LMMSE (cátedra).
