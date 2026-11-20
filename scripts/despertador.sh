#!/bin/bash
##despertador.sh: a la hora indicada prende los monitores y hace sonar la alarma en el MSI
##corre aparte de Claude (si Claude se cae, igual suena)
##uso: (setsid nohup bash scripts/despertador.sh 12:30 >> data/listener_logs/despertador.log 2>&1 < /dev/null &)
##para cancelarlo: pkill -f "^bash scripts/despertador.sh"

AQUI="$(dirname "$(readlink -f "$0")")"
HORA="${1:-12:30}"
TANDAS=6            ##cuantas veces suena (una tanda cada 5 min, durante media hora)

objetivo=$(date -d "$HORA" +%s)
if [ $objetivo -le $(date +%s) ]; then        ##si la hora ya paso hoy, es la de mañana
    objetivo=$(date -d "tomorrow $HORA" +%s)
fi
echo "$(date '+%H:%M:%S') despertador programado para $(date -d @$objetivo '+%d/%m %H:%M')"

##se espera de a 1 minuto (si la pc se suspende un rato, igual suena al volver)
while [ $(date +%s) -lt $objetivo ]; do
    sleep 60
done

for ((t=1; t<=TANDAS; t++)); do
    echo "$(date '+%H:%M:%S') sonando (tanda $t de $TANDAS)"
    bash "$AQUI/alarma.sh" "Buen día. Son las $(date '+%H y %M'). Las capturas de LoRa siguen andando. Revisá la bitácora." 4
    sleep 300
done
