# LoRa como Frequency Shift Chirp Modulation (FSCM)

Trabajo práctico de **Procesamiento de Señales** (UNC · FCEFyN). Modulación y demodulación LoRa con SF configurable, **detección del preámbulo** y medición de BER, SER y FER en simulación y con el ADALM-Pluto.

| Métrica | Qué cuenta |
|---|---|
| **BER** | bits errados / bits enviados |
| **SER** | símbolos errados / símbolos enviados |
| **FER** | tramas con el preámbulo no detectado / tramas enviadas |

## Estructura
```
ChirpModulation/
├── notebook/
│   └── LoRa_V8.ipynb          ← notebook principal (Parte 1 simulación, Parte 2 Pluto, Parte 3 opcional)
├── scripts/
│   ├── listener.py            ← barridos de tx_gain con el Pluto sin el notebook (cambia de IP y reconecta la VPN)
│   ├── leer_capturas.py       ← lista y grafica las capturas del listener
│   ├── vpn.sh                 ← reconecta la VPN (openconnect / AnyConnect)
│   └── vpn.env.example        ← plantilla de credenciales (copiar como vpn.env, que no se sube)
├── data/
│   ├── pluto_captures/        ← mediciones guardadas desde el notebook (2.3)
│   ├── listener_captures/     ← mediciones del listener, una carpeta por IP
│   └── listener_v1_captures/  ← mediciones de la primera versión del listener
└── docs/
    └── GUIA_ESTUDIO.md        ← teoría, preguntas frecuentes y guía del código
```

## Uso
```bash
python -m venv .venv
.venv/bin/pip install numpy matplotlib pyadi-iio jupyter

# notebook: abrir notebook/LoRa_V8.ipynb con el kernel del .venv

# mediciones con el Pluto (desde ChirpModulation/, Pluto conectado por la VPN)
.venv/bin/python scripts/listener.py
.venv/bin/python scripts/leer_capturas.py        # lista las capturas
.venv/bin/python scripts/leer_capturas.py 0      # grafica la captura 0
```

## Referencias
1. L. Vangelista, "Frequency Shift Chirp Modulation: The LoRa Modulation," *IEEE Signal Processing Letters*, vol. 24, no. 12, pp. 1818–1821, 2017.
2. G. Corral Briones, informe sobre el estimador LMMSE (cátedra).
