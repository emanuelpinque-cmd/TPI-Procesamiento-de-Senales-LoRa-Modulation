#!/bin/bash
##reconecta la vpn de la facultad (AnyConnect) con openconnect, sin preguntar nada
##lo usa listener.py cuando se cae la conexion con el pluto
##
##las credenciales van en vpn.env (al lado de este script), que NO se sube a github:
##   VPN_USER="usuario"
##   VPN_PASS="contraseña"
##   VPN_CERT="pin-sha256:...."   <- el fingerprint que muestra openconnect la primera vez
##                                    (reemplaza el "yes" que se escribe a mano)
##sudo: sudoers deja correr SOLO /usr/local/bin/vpn-facultad sin contraseña
##   (instalacion: ver comentario al principio de scripts/vpn-facultad y /etc/sudoers.d/vpn-facultad)

AQUI="$(dirname "$(readlink -f "$0")")"
source "$AQUI/vpn.env"

##candado: si el listener y guardia.sh quieren reconectar a la vez, solo lo hace uno
exec 9>"$AQUI/../data/listener_logs/.vpn.lock"
if ! flock -n 9; then
    echo "ya hay una reconexion de la vpn en curso, no se hace otra"
    exit 0
fi

##sudo -n: nunca pide contraseña (si falta el permiso, falla en vez de quedarse esperando)
##vpn-facultad: script de root instalado en /usr/local/bin, ver scripts/vpn-facultad
echo "$VPN_PASS" | sudo -n /usr/local/bin/vpn-facultad "$VPN_USER" "$VPN_CERT"

##la vpn pone de DNS el de la facultad (192.168.16.16), que no resuelve nombres de afuera:
##se corta internet "por nombre" (y la conexion de Claude). Si pasa, se vuelve al DNS del router
##con nmcli (no hace falta root y la vpn sigue andando, los pluto van por ip)
sleep 5
if ! timeout 8 getent hosts api.anthropic.com >/dev/null; then
    echo "el DNS de la vpn no resuelve: se vuelve al del router con nmcli"
    nmcli connection up "Wired connection 1"
fi
