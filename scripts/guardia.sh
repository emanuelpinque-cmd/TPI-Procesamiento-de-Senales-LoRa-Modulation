#!/bin/bash
##guardia.sh: vigila la noche de capturas, independiente de Claude (si Claude se cae, esto sigue)
##cada minuto revisa:
##  1) internet: ping + que llegue a Claude (api.anthropic.com, por DNS y HTTPS).
##     si falla FALLOS_RED minutos seguidos -> nmcli connection up "Wired connection 1" (como mucho cada 10 min)
##  2) vpn: si hay internet pero ningun pluto responde FALLOS_VPN minutos seguidos -> scripts/vpn.sh
##  3) dead man switch: Claude toca el archivo LATIDO en cada chequeo. Si pasan mas de
##     LIMITE_RED_LATIDO minutos sin que lo toque -> nmcli connection up (por si Claude perdio la conexion
##     aunque el ping ande), y se repite cada 10 min mientras siga sin latido
##     LIMITE_LATIDO minutos sin que lo toque -> suena la alarma en el monitor (y se repite cada 5 min)
##uso: bash scripts/guardia.sh   (en segundo plano, con la salida a un log)
##para reiniciar el contador a mano:  touch data/listener_logs/.latido

AQUI="$(dirname "$(readlink -f "$0")")"
LOGS="$AQUI/../data/listener_logs"
LATIDO="$LOGS/.latido"
CONEXION="Wired connection 1"
PLUTOS="192.168.1.31 192.168.1.33 192.168.1.34 192.168.1.35"
FALLOS_RED=3          ##minutos sin internet antes de levantar la conexion
FALLOS_VPN=5          ##minutos sin plutos (con internet) antes de reconectar la vpn
LIMITE_RED_LATIDO=20  ##minutos sin noticias de Claude antes de levantar la red "por las dudas"
LIMITE_LATIDO=40      ##minutos sin noticias de Claude antes de la alarma
REPETIR_ALARMA=5      ##minutos entre alarmas mientras Claude no responda

[ -f "$LATIDO" ] || touch "$LATIDO"      ##si no existe se crea (si existe no se toca, asi no se reinicia el contador)
sinRed=0
sinVpn=0
ultimaAlarma=0
ultimoNmcli=0

##levanta la conexion cableada (no mas de una vez cada 10 min, para no cortar la vpn a cada rato)
levantarRed() {
    if [ $(( $(date +%s) - ultimoNmcli )) -lt 600 ]; then
        return
    fi
    echo "$(hora) levantando la red ($1): nmcli connection up \"$CONEXION\""
    nmcli connection up "$CONEXION"
    ultimoNmcli=$(date +%s)
    sleep 20
}

##hay internet si responde el ping Y se llega a Claude (DNS + HTTPS, cualquier respuesta HTTP sirve)
hayInternet() {
    ping -c1 -W3 1.1.1.1 >/dev/null 2>&1 || ping -c1 -W3 8.8.8.8 >/dev/null 2>&1 || return 1
    curl -s -o /dev/null -m 10 https://api.anthropic.com >/dev/null 2>&1 || return 1
    return 0
}

hora() { date '+%H:%M:%S'; }

while true; do
    ##1) internet
    if hayInternet; then
        sinRed=0
    else
        sinRed=$((sinRed+1))
        echo "$(hora) sin internet ($sinRed/$FALLOS_RED)"
        if [ $sinRed -ge $FALLOS_RED ]; then
            levantarRed "sin internet"
            sinRed=0
        fi
    fi

    ##2) vpn (solo si hay internet: sin internet no tiene sentido reconectarla)
    if [ $sinRed -eq 0 ]; then
        algunPluto=0
        for ip in $PLUTOS; do
            if ping -c1 -W3 $ip >/dev/null 2>&1; then
                algunPluto=1
                break
            fi
        done
        if [ $algunPluto -eq 1 ]; then
            sinVpn=0
        else
            sinVpn=$((sinVpn+1))
            echo "$(hora) ningun pluto responde ($sinVpn/$FALLOS_VPN)"
            if [ $sinVpn -ge $FALLOS_VPN ]; then
                echo "$(hora) reconectando la vpn"
                timeout 120 bash "$AQUI/vpn.sh" >> "$LOGS/vpn_guardia.log" 2>&1
                sinVpn=0
            fi
        fi
    fi

    ##3) dead man switch
    minutos=$(( ($(date +%s) - $(stat -c %Y "$LATIDO")) / 60 ))
    ##desde los LIMITE_RED_LATIDO minutos sin latido se levanta la red por las dudas (levantarRed lo limita a 1 cada 10 min)
    if [ $minutos -ge $LIMITE_RED_LATIDO ]; then
        levantarRed "Claude sin latido hace $minutos min"
    fi
    if [ $minutos -ge $LIMITE_LATIDO ]; then
        if [ $(( $(date +%s) - ultimaAlarma )) -ge $((REPETIR_ALARMA*60)) ]; then
            echo "$(hora) ALARMA: Claude no responde hace $minutos minutos"
            bash "$AQUI/alarma.sh" "Atención. Claude no responde hace $minutos minutos. Revisá la computadora." 3
            ultimaAlarma=$(date +%s)
        fi
    fi

    sleep 60
done
