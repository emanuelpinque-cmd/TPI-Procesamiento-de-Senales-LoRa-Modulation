#!/bin/bash
##alarma por los parlantes del monitor MSI MAG 275 (salida HDMI 3), para despertar al usuario
##uso: bash scripts/alarma.sh "mensaje" [repeticiones]
##   suena la alarma + dice el mensaje en voz alta, REPETICIONES veces (por defecto 5)
##   no cambia la salida de audio por defecto (los auriculares siguen siendo la principal)

MENSAJE="${1:-Alarma de las capturas LoRa}"
REPETICIONES="${2:-5}"
MONITOR="alsa_output.pci-0000_01_00.1.hdmi-stereo-extra2"   ##pactl list short sinks
SONIDO="/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
VOLUMEN=65536   ##volumen del sonido (65536 = 100% del volumen del monitor, que esta en 40%)

##se prenden las pantallas si estaban apagadas por software (Hyprland, sintaxis lua de la 0.56)
##se reintenta porque si el apagado todavia estaba en curso, el "on" se pierde
for ((k=1; k<=5; k++)); do
    hyprctl dispatch 'hl.dsp.dpms("on")' >/dev/null 2>&1
    sleep 2
    if ! hyprctl monitors 2>/dev/null | grep -q "dpmsStatus: 0"; then
        break
    fi
done

##el monitor puede estar suspendido o en mute: se lo despierta sin tocar su volumen
pactl set-sink-mute "$MONITOR" 0

for ((i=1; i<=REPETICIONES; i++)); do
    paplay --device="$MONITOR" --volume=$VOLUMEN "$SONIDO"
    espeak-ng -v es -s 140 --stdout "$MENSAJE" | paplay --device="$MONITOR" --volume=$VOLUMEN
    sleep 1
done
