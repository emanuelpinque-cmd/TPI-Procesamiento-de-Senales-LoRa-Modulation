# Resumen de la noche (2026-11-20, 04:20 → 12:10)

El detalle completo, hora por hora, está en `BITACORA.md`. Los gráficos están en `graficos/`.

## Capturas buenas (todas en `data/listener_captures/192.168.1.35/` salvo C1 y C3)

| Captura | Qué es | Archivo | Para qué sirve |
|---|---|---|---|
| **C7b** ✅✅ | sweep fino .35, -34..-28 paso 0.25, N=400 | `listener_2026-11-20_08-54-26_192.168.1.35.npz` | **La mejor curva FER/SER/BER**: 5–6 puntos en cada transición |
| C7c | repetición de C7b (11:29) | `listener_2026-11-20_11-29-31_192.168.1.35.npz` | Misma forma, corrida 1.25 dB → repetibilidad (`graficos/sweep_35_C7b_vs_C7c.png`) |
| C5b | sweep .35, -42..-26 paso 0.5, N=300 | `listener_2026-11-20_07-54-37_192.168.1.35.npz` | Rango más amplio |
| **C4** ✅ | fake .35, **2 umbrales** (0.62 / 0.515), -36..0 paso 2, N=200 | `listener_fake_2026-11-20_06-51-39_192.168.1.35.npz` | Los 2 canales llegan a FER 0, 0 falsas alarmas |
| **C6** ✅ | fake .35, **1 umbral** (0.62), mismo rango | `listener_fake_2026-11-20_07-18-30_192.168.1.35.npz` | Selectivo nunca detecta (FER 0.5) → comparación con C4 |
| Promedio C4b+c+d | fake .35, 2 umbrales, fino -22..-15 paso 0.5, N=3×400 | `listener_fake_PROMEDIO3_2umbrales_fino_192.168.1.35.npz` | Transición fina del fake (ver "Hallazgo 4") |
| C1 | sweep .31, -70..-30 paso 1, N=200 | `192.168.1.31/listener_2026-11-20_04-50-34_192.168.1.31.npz` | Otro Pluto (~19 dB más de enlace que el .35) |
| C3 | fake .33, 1 umbral 0.62 | `192.168.1.33/listener_fake_2026-11-20_06-16-22_192.168.1.33.npz` | Otro Pluto, 24/26 puntos |

Las capturas malas o parciales están en `data/listener_captures/descartadas/` (no se borró nada).

## Hallazgos importantes

1. **Bug de buffers viejos (arreglado en el listener).** Después de cada `sdr.tx()`, las 4 primeras capturas
   son de la señal ANTERIOR y las 3–4 siguientes vienen vacías. El listener descartaba 3 → FER falsa de ~0.2
   con señal alta. Ahora descarta 10 (`DESCARTAR`). ⚠️ **El notebook (`capturaPluto`, celda 56) descarta solo 1**:
   las mediciones viejas de `data/pluto_captures/` pueden tener el mismo error. No lo toqué.
2. **ρ satura en ≈ 0.66 (plano) y ≈ 0.546 (selectivo).** El buffer tiene 2 tramas y ρ se normaliza con todo el buffer.
   Con `threshold = 0.67` (modo fake del listener **y celdas 71/73 del notebook**) el real **nunca** se detecta → FER 0.5.
   Con un umbral por canal (0.62 / 0.515) anda perfecto. Está explicado en la nueva sección **2.3d** del notebook.
3. **Cortes de internet = DNS de la VPN.** Cada reconexión de la VPN pone el DNS de la facultad (192.168.16.16), que no
   resuelve nombres de afuera → se cortaba Claude (el corte de las 04:47). `vpn.sh` ahora lo arregla solo con nmcli.
4. **El modo fake da puntos "todo o nada" cerca del umbral** porque se reconecta al Pluto en cada punto y cada
   conexión sale con una potencia de TX algo distinta (≈ ±1 dB). Con una sola conexión la curva es suave
   (`rho_vs_gain_35.txt`). **Propuesta (no implementada, tu decisión):** reorganizar el modo fake en 4 conexiones
   (real/fake × plano/selectivo) que recorran todas las ganancias.
5. **La forma de las curvas se repite, la posición en tx_gain se corre ~1 dB entre conexiones** (C7b vs C7c).

## Cambios en archivos (nada commiteado, nada pusheado)

- `scripts/listener.py`: parámetros por línea de comandos, `BARRIDOS_MAX`, `DESCARTAR = 10`, pasos decimales,
  `thresholdFakeSel` (2 umbrales, opcional), reintentar la misma ip después de un corte, esperar si está ocupado
  (`ESPERA_BUSY`), **seguir el barrido donde quedó** después de un corte.
- `scripts/vpn.sh` (+ `scripts/vpn-facultad`, instalado en /usr/local/bin): reconexión sin contraseña, candado, arreglo del DNS.
- Nuevos: `scripts/guardia.sh`, `alarma.sh`, `despertador.sh`, `estado.sh`, `revisar_capturas.py`.
- `notebook/LoRa_V8.ipynb`: escalas/N de 4 gráficos de la simulación (celdas 15, 17, 47) y nueva sección **2.3d**
  (celdas 75–76). Copia de antes: `LoRa_V8_antes_de_graficos.ipynb.bak`.

## Pendiente para decidir
- ¿Arreglar `capturaPluto` del notebook (descartar 10 capturas) y el `threshold = 0.67` de las celdas 71/73?
- ¿Reorganizar el modo fake (hallazgo 4)?
- ¿Commit de todo esto? (sin push hasta que lo revises)
- En los gráficos de frecuencia instantánea (celdas 7 y 11) cada símbolo hace 2 rampas: viene de `symbolChirp`.
