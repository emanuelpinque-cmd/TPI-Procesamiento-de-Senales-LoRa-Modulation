# LoRa como Frequency Shift Chirp Modulation (FSCM)

Trabajo práctico de **Procesamiento de Señales** (UNC · FCEFyN). Modulación y demodulación LoRa con SF configurable, **detección del preámbulo** y medición de BER, SER y FER en simulación y con el ADALM-Pluto.

## Estructura
| Ruta | Qué es |
|---|---|
| `src/LoRa_V8.ipynb` | Notebook principal: Parte 1 simulación, Parte 2 SDR (Pluto), Parte 3 opcional |
| `src/listener.py` | Barrido de `tx_gain` con el Pluto sin depender del notebook; guarda en `src/listener_captures/` después de cada ganancia y cambia de IP si el equipo falla |
| `src/leer_capturas.py` | Lista y grafica las capturas del listener (`python leer_capturas.py 0`) |
| `src/pluto_captures/` | Mediciones guardadas desde el notebook |

## Uso
```bash
python -m venv .venv
.venv/bin/pip install numpy matplotlib pyadi-iio jupyter
.venv/bin/python src/listener.py          # medir (Pluto conectado)
.venv/bin/python src/leer_capturas.py     # listar capturas
.venv/bin/python src/leer_capturas.py 0   # graficar la captura 0
```

## Referencias
1. L. Vangelista, "Frequency Shift Chirp Modulation: The LoRa Modulation," *IEEE Signal Processing Letters*, vol. 24, no. 12, 2017.
