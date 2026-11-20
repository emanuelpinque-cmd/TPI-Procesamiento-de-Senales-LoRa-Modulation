# Bitácora de capturas nocturnas (2026-11-20)

Capturas con `scripts/listener.py` corridas por Claude mientras el usuario duerme.
Las capturas malas se mueven a `data/listener_captures/descartadas/` (no se borran).
Los gráficos de cada captura revisada quedan en `data/listener_logs/graficos/`.

## Preparación (04:20–04:45)
- Permiso de sudo solo para `/usr/local/bin/vpn-facultad` (copia de `scripts/vpn-facultad`).
  `scripts/vpn.sh` lo llama con `sudo -n`. Probado: VPN cortada a mano → levantada por el script → los 4 Pluto responden.
- Los 4 Pluto (.31 .33 .34 .35) transmiten y detectan el preámbulo (ρ ≈ 0.60–0.67 con tx_gain = -20, rx_gain = 20).
- `listener.py`: se pueden pasar parámetros al correrlo (`MODO=sweep N=100 ...`) y se agregó `BARRIDOS_MAX`.
- Chequeo automático cada 30 minutos (xx:13 y xx:43, aprox.).

## Plan (se ajusta según lo que salga)
1. Prueba corta: sweep, tx_gain -80..0 paso 10, N=20 → medir tiempo y ubicar la transición.
2. Sweep fino: rango que cubra la transición, paso 2 dB, N=200, plano y selectivo.
3. Fake (50% fakes): mismo rango, paso 2 dB, N=200.
4. Si sobra tiempo: repetir 2 y 3 con N más grande en la zona de transición para curvas más suaves.

## Registro
### 04:39 — Prueba corta (sweep, -80..0 paso 10, N=20) → DESCARTADA
- FER con piso de ~0.2 a señal alta (debería ser 0). Causa: después de cada `sdr.tx()` las primeras 4 capturas
  son de la señal ANTERIOR (buffers en cola del Pluto) y las 3–4 siguientes vienen vacías (ρ = 0.03).
  El listener descartaba solo 3 → contaba ~4 vacías como "no detectado" (4/20 = 0.2).
- Arreglo: parámetro `DESCARTAR = 10` en `listener.py` (sweep y fake).
- ⚠️ Para la mañana: el notebook (`capturaPluto`, celda 56) descarta solo 1 captura. Las mediciones viejas
  de `data/pluto_captures/` y del listener anterior pueden tener el mismo piso falso. Revisar.

### 04:41 — Prueba corta repetida con DESCARTAR=10 → OK
- FER = 0 desde -50 dB (plano) y -40 dB (selectivo); 1 por debajo de -60. Transición entre -60 y -40.
- Tarda ~0.1 s por captura.

### 04:47 — Se cortó la conexión (sesión de Claude reiniciada). Red, VPN y Plutos OK al volver.
- Agregado `scripts/guardia.sh` (corre aparte de Claude): levanta la red con nmcli, reconecta la VPN y
  hace de dead man switch (alarma en el monitor si Claude no toca `.latido` en 40 min). Alarma probada: se escucha.
- `scripts/alarma.sh`: suena por el monitor MSI (HDMI 3) sin cambiar la salida por defecto.
- `vpn.sh` con candado (flock) para que listener y guardia no reconecten a la vez.

### 04:51 — C1: sweep fino, -70..-30 paso 1, N=200 (ip .31, 27 min) → BUENA
- Archivo: `192.168.1.31/listener_2026-11-20_04-50-34_192.168.1.31.npz`
- Transición muy abrupta: plano FER 1 → 0 entre -52 y -50 dB (-51: 0.895); selectivo entre -50 y -48 (-49: 0.99, -48: 0.005).
  El selectivo necesita ~2 dB más. SER = BER = FER: si se detecta el preámbulo, el payload sale perfecto.
- Con paso 1 dB la transición cae en 1 punto → hace falta paso 0.25 dB en -53..-46.
- `listener.py` ahora acepta pasos decimales (TX_PASO=0.25).

### 05:19 — C2: fake exploratorio, -70..0 paso 2, N=200 (en curso)
- El umbral fake (0.67) es más alto: la transición puede estar en otro lado. Además en la prueba de las 04:30
  el ρ del real a tx_gain=-20 daba 0.60–0.67 (< 0.67) → puede que el real casi no se detecte. A ver.

### 05:24 — Chequeo
- Listener, guardia y VPN corriendo; internet y los 4 Plutos OK. C2 por tx_gain=-60 (≈1 punto cada 1.2 min → termina ~6:45).
- Hasta -60: FER = 0.5 (no detecta ningún real, 0 falsas alarmas), lo esperable con poca señal.
- Alarma mejorada: ahora prende los monitores (Hyprland `hl.dsp.dpms("on")`, con reintentos). Probado con las pantallas apagadas por software: funciona.

### 05:54 — Chequeo
- 05:37: se cayó la VPN (TimeoutError con .31). **El listener la reconectó solo** con vpn.sh (sudo sin contraseña OK)
  y siguió con .33. El .31 dejó guardadas 21/36 ganancias (-70..-30) en `listener_fake_2026-11-20_05-18-29_192.168.1.31.npz`.
- Hasta -30 dB (en .31) y -40 (en .33): ningún real detectado, 0 falsas alarmas.
- Por qué el real recién se detecta con mucha señal: el buffer de rx tiene 2 copias de la señal (tx cíclico,
  buffer = 2·len), y ρ se normaliza con la energía de TODO el buffer → **ρ máximo = 1/√2 ≈ 0.707**.
  El fake da ≈ 0.88·0.707 ≈ 0.62. thresholdFake = 0.67 queda en esa ventana angosta (0.62–0.707),
  así que el real recién supera el umbral cerca de tx_gain -20..0. Para la mañana: para el informe, explicar esto
  (o normalizar ρ con la energía de una ventana del largo del preámbulo, no de todo el buffer).
- Siguiente: C3 = fake fino en la zona donde empieza a detectar (según lo que dé C2), C4 = sweep -54..-45 paso 0.25 N=500.

### 06:00 — guardia.sh mejorado
- "Hay internet" ahora = ping OK **y** se llega a api.anthropic.com (DNS + HTTPS). Si falla 3 min → nmcli connection up.
- Dead man de red: desde 20 min sin latido de Claude → nmcli connection up "Wired connection 1" (máx. 1 cada 10 min).
  A los 40 min sigue la alarma.
- Latido cada 15 min (xx:07/22/37/52) además del chequeo completo de cada 30.

### 06:12 — C2 terminado (fake, -70..0 paso 2, N=200, thresholdFake=0.67) → NO INFORMATIVA (se conserva como evidencia)
- Archivo: `192.168.1.33/listener_fake_2026-11-20_05-38-49_192.168.1.33.npz`. FER = 0.5 en TODO el rango:
  con 0.67 el real casi nunca se detecta (1 de 3600), 0 falsas alarmas.
- El parcial del .31 (21/36, mismo resultado) → `descartadas/`.
- Medición de ρ en .33 (20 capturas por punto, rx_gain 20, buffer del modo fake):

  | tx_gain | real plano | fake plano | real selec | fake selec |
  |---|---|---|---|---|
  | -50 | 0.31 | 0.26 | 0.27 | 0.22 |
  | -45 | 0.46 | 0.39 | 0.39 | 0.33 |
  | -40 | 0.58 | 0.50 | 0.48 | 0.42 |
  | -30 | 0.65 | 0.57 | 0.54 | 0.47 |
  | -20..0 | 0.66 (satura) | 0.585 | 0.545 (satura) | 0.48–0.50 |

- Conclusión: 0.67 > ρ máximo del real → nunca detecta. Y **ningún umbral fijo sirve para los dos canales**:
  el real selectivo llega a 0.545, pero el fake plano llega a 0.585. Umbral bajo (≈0.52) → detecta selectivo
  pero el fake plano da falsas alarmas con señal alta. Debilidad de la detección por correlación frente a fakes.
- Plan: C3 = umbral 0.62 (separa perfecto en plano; selectivo nunca detecta), C4 = umbral 0.52 (selectivo OK,
  falsas alarmas en plano). Rango -50..0 paso 2, N=200. Después C5 = sweep -54..-45 paso 0.25, N=500.

### 06:20 — C3: fake, thresholdFake=0.62, -50..0 paso 2, N=200 (en curso)

### 06:25 — Pedido del usuario: probar 2 umbrales (uno por canal) + seguir con el de 1 umbral
- `listener.py`: nuevo parámetro `thresholdFakeSel` (umbral del canal selectivo en modo fake). None = un solo
  umbral, como antes. Se guarda en el .npz como `thresholdSel`. (Se hizo como parámetro y no como script
  aparte para no duplicar 300 líneas; el comportamiento por defecto no cambia.)
- Nuevo orden: C3 (1 umbral 0.62, en curso) → **C4 (2 umbrales: plano 0.62, selectivo 0.525)** → C5 sweep fino
  -54..-45 paso 0.25 N=500 → C6 (1 umbral 0.52).
- Si C4 sale bien: agregar al notebook una celda simple con los dos umbrales, después de la 2.3c (sin tocar las existentes).

### 06:24 — Chequeo
- Todo corriendo; red, VPN y 4 Plutos OK.
- C3 (umbral 0.62) va como se predijo: plano FER 0.5 → 0.01 en -36 → 0 en -34 (0 falsas alarmas);
  selectivo sigue en 0.5 (el real selectivo no llega a 0.62).

### 06:30 — Nuevas reglas del usuario
- Seguir mejorando hasta que se despierte (13–14 h). No parar por cuenta propia: si no hay más que mejorar → alarma y pedir permiso.
- **Prioridad Pluto .35** (el del usuario); los otros solo si el .35 está ocupado/caído. Pausa de ~10 min entre capturas (Plutos compartidos).
- Antes de C4: medir ρ real/fake en el .35 (en la prueba de 04:30 daba ρ más bajo: 0.60 vs 0.66) y ajustar los umbrales a ese Pluto.

### 06:47 — C3 terminado (fake, 1 umbral 0.62) → BUENA (24/26 ganancias, en .33)
- Archivo: `192.168.1.33/listener_fake_2026-11-20_06-16-22_192.168.1.33.npz` (faltan -2 y 0 dB, zona plana).
- Plano: FER 0.5 hasta -38, -36: 2 no detectados, desde -34: FER = 0. **0 falsas alarmas en todo el rango.**
- Selectivo: FER = 0.5 en todo el rango (el real selectivo satura en ρ≈0.545 < 0.62). Confirma que hace falta otro umbral.
- 06:37 cayó la VPN otra vez → reconectó solo y empezó de nuevo en .34; lo corté (redundante, ya en descartadas/).
  (Al cortarlo con Ctrl+C cayó en medio de un rx → el listener lo tomó como error y reconectó la VPN. Sin consecuencias.)

### 06:45 — Despertador
- `scripts/despertador.sh 12:30` corriendo aparte (setsid): a las 12:30 prende monitores y suena 6 tandas cada 5 min.
  Respaldo: chequeo de Claude a las 12:33. (systemd-run --user no sirve: desde ahí pactl no ve la salida HDMI.)

### Pausa de Plutos 06:47–06:57 → mientras tanto: gráficos de la simulación del notebook (pedido del usuario:
solo escalas/ejes/N, sin tocar la lógica).

### 06:50–07:10 — Gráficos de la simulación (notebook) — SOLO parámetros de las llamadas
- Backup antes de tocar: `data/listener_logs/LoRa_V8_antes_de_graficos.ipynb.bak`.
- Celda 15 (BER SF=7): N 1000→3000, SNR `arange(-12,0,1)` → `arange(-13,-4.5,0.5)` (antes sobraba -4..-1, todo 0; ahora más puntos y más suave).
- Celda 17 (BER y SER SF=4): SNR `arange(-20,10,0.5)` → `arange(-12,6.5,0.5)` (de -20 a -12 era plano en 0.5), N 1000→10000 (cola suave).
- Celda 47 (FER SF=8): `graphFER(500,8,0.5)` → `graphFER(1000,8,0.5,np.arange(-6,-2.5,0.25))` (antes -8..-5.5 todo FER=1).
- Salidas de esas 3 celdas regeneradas con el mismo tamaño de imagen que Jupyter (869×594). El resto del notebook, sin cambios.
- Observación (NO tocada): en los gráficos de frecuencia instantánea (celdas 7 y 11) cada símbolo hace 2 rampas en vez de 1.
  Viene de `symbolChirp`: fase = 2π·((s+t)%N)·t/N → la frecuencia instantánea crece como 2t/N (el doble). Para charlar.

### 07:00 — ρ en el .35 (`data/listener_logs/rho_fake_35.txt`)
- El .35 tiene ~10 dB menos de enlace que el .33 (transición en -30..-10 en vez de -45..-30), pero los TOPES de ρ son
  iguales: plano real 0.665 / fake 0.585; selectivo real 0.546 / fake 0.483.
- Umbrales elegidos (mitad de cada ventana): **plano 0.62, selectivo 0.515**.

### 07:03 — C4: fake 2 umbrales (0.62 / 0.515), .35, -36..0 paso 2, N=200 (en curso)

### 06:55 — Chequeo + causa de los cortes de internet ENCONTRADA
- guardia.log: "sin internet" desde 06:39 → nmcli a las 06:41 y 06:54. Internet por IP andaba; lo que fallaba era el DNS.
- journalctl/dnsmasq: cada vez que la VPN se reconecta, openconnect cambia el DNS a **192.168.16.16** (el de la facultad),
  que no resuelve nombres de afuera (api.anthropic.com, etc.). Pasó tras las reconexiones de 06:37 y 06:45.
  Muy probablemente es también la causa del corte de la sesión de Claude de las 04:47 (VPN reconectada a las 04:38).
- `nmcli connection up "Wired connection 1"` devuelve el DNS del router (192.168.100.1) y la VPN sigue andando.
- Arreglo en `vpn.sh`: después de reconectar, si `getent hosts api.anthropic.com` falla → nmcli connection up.
  El guardia sigue de respaldo (lo detecta en 3 min).
- C4 en .35 va por -30 dB (todavía FER 0.5, se espera la transición en -30..-10).

### 07:08 — C4 terminado (fake, 2 umbrales 0.62 / 0.515, .35, -36..0 paso 2, N=200, 17 min) → MUY BUENA ✅
- Archivo: `192.168.1.35/listener_fake_2026-11-20_06-51-39_192.168.1.35.npz`
- Plano: FER 0.5 hasta -22 → -20: 0.435 → -18: 0.065 → **0 desde -16**.
- Selectivo: FER 0.5 hasta -22 → -20: 0.315 → **0 desde -18**.
- **0 falsas alarmas en todo el rango y en los dos canales.** Con un umbral por canal los dos llegan a FER = 0
  (con 1 umbral, C3: el selectivo se quedaba en 0.5).
- Pausa del Pluto 07:08–07:18. Siguiente: C5 = sweep en .35 (C1 fue en .31), después C4b = C4 fino en la transición.

### 07:12 — Notebook 2.3b / 2.3c (para la mañana, NO tocado)
- `capturaPluto` (celda 56) usa el mismo buffer de 2 tramas e `identifyPreamble` normaliza igual → el mismo tope ρ ≈ 0.66.
  Con `threshold = 0.67` (celdas 71 y 73) el real nunca se detecta → la 2.3c daría FER = 0.5 en todo el rango.
- `capturaPluto` descarta 1 sola captura después de `sdr.tx()`: mismo problema de buffers viejos/vacíos que tenía el listener
  (ahí se arregló con DESCARTAR = 10). Proponer al usuario cambiar `sdr.rx()` por un for de 10.
- Para el notebook (pedido): comparar 1 umbral vs 2 umbrales en el MISMO Pluto (.35) → hace falta C6.

### 07:12 — C6: fake, 1 umbral 0.62, .35, -36..0 paso 2, N=200 (arranca 07:21, después de la pausa)
- Mismo rango y Pluto que C4: la única diferencia es el umbral del selectivo (0.62 vs 0.515).

### 07:13 — Chequeo
- Red, VPN y 4 Plutos OK. Guardia sin eventos desde 06:54 (DNS OK). C6 en pausa, arranca 07:21.
  (estado.sh dice 'listener: CORRIENDO' porque la línea del comando en espera ya contiene listener.py.)

### 07:35 — C6 terminado (fake, 1 umbral 0.62, .35, -36..0 paso 2, N=200, 17 min) → BUENA ✅
- Archivo: `192.168.1.35/listener_fake_2026-11-20_07-18-30_192.168.1.35.npz`
- Plano: igual que C4 (FER 0 desde -16). Selectivo: **FER = 0.5 en todo el rango** (nunca detecta el real). 0 falsas alarmas.

### 07:38 — Notebook: nueva sección 2.3d (pedido del usuario: "si funciona, ponlo simple")
- Celdas nuevas 75 (markdown) y 76 (código) entre la 2.3c y la 2.4. No se tocó ninguna celda existente.
- Explica el tope de ρ (tabla real/fake por canal en el .35) y grafica C6 (1 umbral) contra C4 (2 umbrales),
  un panel por canal + cuenta de falsas alarmas. Lee las capturas del listener, no usa el Pluto. Salida ya generada.
- El listener sigue funcionando con 1 umbral por defecto (`thresholdFakeSel = None`).

### 07:38 — C5: sweep en .35, -42..-26 paso 0.5, N=300 (arranca ~07:45 después de la pausa)

### 07:43 — Chequeo
- Todo OK (red, VPN, 4 Plutos, guardia sin eventos nuevos). C5 recién arrancó en .35.

### 07:53 — C5 interrumpido → relanzado (C5b)
- 07:44 cayó la VPN en el punto 2 de 33 (.35). Se reconectó sola y **el arreglo de DNS de vpn.sh funcionó**
  ("el DNS de la vpn no resuelve: se vuelve al del router con nmcli").
- Pero el listener pasaba a la SIGUIENTE ip (.31) después de reconectar. El .31 tiene ~10 dB más de enlace →
  en -42..-26 todo FER=0, curva inútil. Cortado; los parciales (.35 1/33 y .31) → descartadas/.
- Arreglo en `listener.py`: ante un error no-busy se reconecta la VPN y se **reintenta la misma ip**; recién con 2 errores
  seguidos pasa a la siguiente (`erroresSeguidos`). Así se queda en el .35 (primera de IPS).
- 07:54 — C5b: sweep .35, -42..-26 paso 0.5, N=300 (en curso).

### 08:13 — Chequeo
- Todo OK. C5b en .35: plano FER 1 → 0.63 (-32.5) → 0.017 (-32). Selectivo todavía 1 en -32. Transición plano en .35 ≈ -32.5 dB.

### 08:24 — C5b terminado (sweep, .35, -42..-26 paso 0.5, N=300, 30 min, sin cortes) → BUENA ✅
- Archivo: `192.168.1.35/listener_2026-11-20_07-54-37_192.168.1.35.npz`
- Plano: FER 1 hasta -33 → -32.5: 0.63 → -32: 0.017 → 0 desde -31.5.
- Selectivo: -30.5: 0.977 → -30: 0.32 → -29.5: 0.003 → 0 desde -29. (~2.5 dB más que el plano, como en el .31.)
- SER ≈ BER ≈ FER (en -29.5 selectivo 1 símbolo errado de más). El .35 está ~19 dB por debajo del .31 en tx_gain.
- Transición de ~1 dB: de -42 a -33 sobra. Siguiente: C7 = -34..-28 paso 0.25, N=400 (arranca ~08:34).

### 08:43 — Chequeo
- Todo OK. C7 en .35 va por -32.25. Ojo: en -32.5 plano ahora da FER 1.0 (en C5b daba 0.63) → la transición se corre
  ~0.5 dB entre corridas (deriva del enlace). Comparar curvas de distintas corridas con eso en mente.

### 08:53 — C7 interrumpido → C7b solo en .35
- 08:4x cayó la VPN en el punto 9/25 (.35, parcial guardado en `listener_2026-11-20_08-33-42_192.168.1.35.npz`).
  La VPN y el DNS se arreglaron solos. Pero al reconectar, el .35 dio **"Device or resource busy"** (compañero usándolo
  o la conexión vieja colgada) → el listener pasó al .31 (rango inútil, todo 0) → cortado, a descartadas/.
- `listener.py`: nuevo `ESPERA_BUSY = 60`: si todas las ips están ocupadas espera 60 s antes de reintentar
  (antes reintentaba enseguida y reconectaba la VPN a la primera).
- Para capturas con el rango calibrado al .35: `IPS=192.168.1.35` solo y `FALLOS_MAX=10` (hasta 10 min esperando
  que se libere antes de reconectar la VPN).
- 08:55 — C7b: sweep .35, -34..-28 paso 0.25, N=400 (en curso).

### 09:13 — Chequeo
- Todo OK. C7b en .35 sin cortes, va por -30.5 (plano ya en 0 desde -31.5; selectivo empieza a bajar: 0.975 en -30.5).

### 09:26 — C7b terminado (sweep .35, -34..-28 paso 0.25, N=400, 31 min, sin cortes) → LA MEJOR SWEEP ✅✅
- Archivo: `192.168.1.35/listener_2026-11-20_08-54-26_192.168.1.35.npz`
- Plano: 1 → -32.75: 0.963 → -32.5: 0.67 → -32.25: 0.17 → -32: 0.02 → -31.75: 0.003 → 0 desde -31.5.
- Selectivo: 1 → -30.5: 0.975 → -30.25: 0.78 → -30: 0.335 → -29.75: 0.043 → -29.5: 0.007 → 0 desde -29.25.
- SER/BER siguen a la FER (selectivo -29: SER 0.0005, BER 0.0001 → algún símbolo errado con preámbulo detectado).
- Repetible: en -32.5 C5b daba 0.63 y C7b 0.67. Parcial de C7 (9/25) → descartadas/.
- Siguiente: C4b = fake 2 umbrales fino, .35, -22..-15 paso 0.5, N=400 (arranca ~09:36).

### 09:43 — Chequeo
- Todo OK. C4b en .35 va por -20 (plano 0.435 = igual que C4; selectivo todavía 0.5 en -20, en C4 daba 0.315 → deriva ~0.5 dB).

### 09:53 — C4b cortado por la VPN y reanudado de cero; mejora: seguir el barrido donde quedó
- 09:46 cayó la VPN en el punto 6/15 de C4b. VPN + DNS arreglados solos; el .35 dio busy → esperó 60 s → siguió
  (todo como se diseñó). Pero arrancó el barrido de cero en un archivo nuevo.
- `listener.py`: si un barrido se corta a mitad, se guarda como `pendiente` y el próximo intento con la MISMA ip
  **sigue desde la ganancia donde quedó, en el mismo archivo**. Probado con un Pluto y una VPN simulados
  (corte en el punto 4 de 6 → sigue en el 4 → un solo archivo con los 6 puntos).
- C4b actual sigue con el código viejo (ya estaba cargado). Las próximas capturas usan el nuevo.

### 10:09 — C4b terminado (fake 2 umbrales, .35, -22..-15 paso 0.5, N=400) → DUDOSA ⚠️
- Archivo: `192.168.1.35/listener_fake_2026-11-20_09-47-23_192.168.1.35.npz` (15/15). Parcial del 1er intento (6/15) → descartadas/.
- No monótona: en **-19 dB 200/200 reales no detectados en los dos canales** (FER 0.5), cuando -19.5 y -18.5 dan ~0.
  Selectivo -18: 82/200 no detectados. Resto coherente con C4 (plano: -20 184, -19.5 9, 0 desde -18.5).
- Parece que en ese minuto el Pluto no transmitió o hubo interferencia (¿otro Pluto en 800 MHz?). 0 falsas alarmas igual.
- Se repite (C4c, mismos parámetros, ~10:19) para ver si los fallos caen en otros puntos (→ interferencia) o se repiten.

### 10:13 — Chequeo
- Todo OK (red, VPN, 4 Plutos, guardia sin eventos). C4c en pausa, arranca ~10:19.

### 10:39 — C4c terminado (repetición de C4b) → también con puntos anómalos, en OTROS lugares
- Archivo: `192.168.1.35/listener_fake_2026-11-20_10-18-20_192.168.1.35.npz` (15/15)
- Plano: -20 191, -19.5 17, -19 8, -18.5 0, **-18 40**, 0 desde -17.5. Selectivo: -19.5 14, **-19 200, -18.5 187, -18 83**, -17.5 1, 0 desde -17.
- C4b falló en -19 (los dos) y -18 (selec); C4c en -19..-18 (selec) y -18 (plano) → los fallos se mueven entre corridas:
  **interferencia intermitente** (varios minutos), muy probablemente compañeros transmitiendo en 800 MHz a esta hora.
  Las capturas de madrugada (C4, C6, C7b) salieron limpias. 0 falsas alarmas siempre.
- Plan: C4d (3ra corrida igual, ~10:49) y curva combinada = **mediana por punto** de C4b, C4c y C4d
  (un punto arruinado en una sola corrida no mueve la mediana).

### 10:43 — Chequeo
- Todo OK. C4d en pausa, arranca ~10:49.

### 11:10 — C4d terminado + promedio de las 3 corridas finas (C4b, C4c, C4d)
- C4d: `listener_fake_2026-11-20_10-49-07_192.168.1.35.npz`. Otra vez fallos en -19.5..-18 (plano -19: 200, -18.5: 189; selec -18: 89).
- Ya no parece interferencia al azar: los fallos caen SIEMPRE en -19.5..-18. Explicación: el umbral 0.62 está pegado al
  techo de ρ del real (0.665), donde ρ(tx_gain) se aplana → una deriva chica del enlace (décimas de dB) cruza el umbral, y como
  ρ casi no varía entre capturas seguidas, cada punto sale "todo o nada". En el sweep (umbral 0.3, zona empinada) no pasa.
- Promedio (N = 1200): `listener_fake_PROMEDIO3_2umbrales_fino_192.168.1.35.npz`, gráfico `graficos/fake_2umbrales_PROMEDIO3_35.png`.
  Plano: -20 0.479, -19.5 0.137, **-19 0.340**, -18.5 0.158, -18 0.058, 0 desde -17.5. Selec: -19.5 0.221, **-19 0.347**, -18.5 0.157, -18 0.212, ~0 desde -17.5.
  0 falsas alarmas en 3600 fakes.
- El pico en -19 en los dos canales sugiere que el atenuador de TX no es monótono ahí. Diagnóstico (~11:20): ρ del real vs
  tx_gain -21..-17 paso 0.25, ida y vuelta en una conexión (separa ganancia de deriva) → `rho_vs_gain_35.txt`.

### 11:13 — Chequeo
- Todo OK. Diagnóstico de ρ vs tx_gain en pausa, arranca ~11:17.

### 11:20 — Diagnóstico ρ vs tx_gain (.35, una sola conexión, ida y vuelta) → `rho_vs_gain_35.txt`
- ρ del real crece parejo (0.590 en -21 → 0.629 en -17), ida y vuelta iguales → no hay deriva en esos minutos.
  En -19 hay un escaloncito del atenuador (0.6104 vs 0.6114 en -19.25), igual en las 2 pasadas, pero mínimo.
- Con UNA conexión el real cruza 0.62 recién en ≈ -18.1 dB; en las corridas fake se detectaba desde -19.5.
  → **La causa de los puntos "todo o nada" es que el modo fake se reconecta al Pluto en cada punto** (por libiio v1
  al cambiar de señal) y cada conexión nueva sale con una potencia de TX algo distinta (≈ ±1 dB). Cerca del umbral eso
  decide todo el punto. El sweep usa una sola conexión → curvas suaves.
- **Propuesta para el usuario (NO implementada, es un cambio grande):** reorganizar el modo fake en 4 conexiones
  (real/fake × plano/selectivo), cada una recorriendo todas las ganancias. Curvas suaves como el sweep.
- 11:20 — C7c: repetición de C7b (sweep .35, -34..-28 paso 0.25, N=400) para ver repetibilidad (arranca ~11:29).

### 11:43 — Chequeo
- Todo OK. C7c va por -31.5: plano 0.9775 (en C7b a -31.5 ya era 0) → la curva entera está corrida ~0.75–1 dB respecto de C7b.
  Coincide con la explicación de las 11:20: cada conexión nueva al Pluto sale con una potencia de TX algo distinta.
  La FORMA de la curva se repite; la posición absoluta en tx_gain varía ~1 dB entre conexiones.

### 12:04 — C7c terminado (repetición de C7b) → BUENA ✅
- `listener_2026-11-20_11-29-31_192.168.1.35.npz` (25/25, sin cortes). Misma forma que C7b, corrida +1.25 dB
  (plano: -31.25 0.69, -31 0.14, -30.75 0.02; selectivo: -29 0.69, -28.75 0.23, -28.5 0.043).
  Separación plano–selectivo ≈ 2.5 dB en las dos. Gráfico: `graficos/sweep_35_C7b_vs_C7c.png`.
- 12:10 — Resumen de la noche en `data/listener_logs/RESUMEN_NOCHE.md`. Pluto .35 libre para los compañeros
  hasta que el usuario decida los pendientes (despertador 12:30).

### 12:13 — Chequeo
- Todo OK (red, VPN, 4 Plutos). Sin captura en curso a propósito: lo que queda por mejorar necesita decisión del usuario
  (ver RESUMEN_NOCHE.md → Pendiente). El despertador de las 12:30 lo despierta en 17 min, así que no se lo despierta antes.

### 12:19 — FIN (autorizado por el usuario)
- Cancelados los chequeos de cada 15 y 30 min y el despertador de respaldo. Detenidos guardia.sh y despertador.sh.
- Listener parado (no había captura en curso). La VPN queda conectada.
- Nada commiteado ni pusheado. Pendientes de decisión en RESUMEN_NOCHE.md.

### Tarde — Figuras para la presentación (pedido del usuario)
- Notebook: nueva sección **2.3e** (celdas 77–80, antes de la 2.4): sweep FER/SER/BER del .35 (C7b) y repetibilidad
  (C7b vs C7c). Cada figura lee su .npz y pone fecha, hora, ip, SF, N, umbral, rx_gain y paso en el título.
- 2.3d (celda 76): el título ahora incluye ip, rx_gain y fecha/hora de las dos capturas.
- Celda 17 (BER/SER SF=4): había 2 puntos que subían en la cola (1–2 errores, ruido estadístico) → N 10000→30000 y
  SNR hasta 5 dB. Verificado: ninguna curva sube.
- Respaldo de antes: `LoRa_V8_antes_de_figuras_pluto.ipynb.bak`. Cambiaron solo las celdas 17 y 76, más las nuevas 77–80.
- Copias PNG en `data/listener_logs/presentacion/`.

### 20/11 tarde — Notebook listo para exponer
- `capturePluto` descarta 10 capturas (`discard`): se fue el piso falso de FER de la "captura god".
- 2.3 medida de nuevo en el .35 (rx_gain 40, -54..-44 paso 0.5, N = 100 en 5 conexiones por punto):
  `pluto_sweep_2026-11-20_14-46_192.168.1.35_SF8.npz`. Plano 0 desde -50, selectivo desde -47.5.
- 2.3b medida en el .35 con umbral 0.62 (-64..0 paso 2, N = 40): `pluto_fake_2026-11-20_15-38_192.168.1.35_SF8.npz`.
  Por símbolos funciona desde -44 dB, correlación desde -18 dB → ~26 dB a favor de símbolos; 0 falsas alarmas.
- `identifyPreambleWithSymbols` reescrita sin continue/break/lambda (cada muestra como inicio); idéntica a la anterior
  en 384 detecciones y 60 registros de búsqueda.
- Refactorización: todas las variables y funciones del notebook en inglés (comentarios y textos siguen en español).
  Verificado: 44 celdas sin Pluto corren sin errores; las del Pluto probadas con un Pluto simulado y después con el real.
- Salidas regeneradas en todo el notebook ("Run All"), incluida la 2.2 con el Pluto.
