#!/bin/bash
##reconecta la vpn de la facultad (AnyConnect) con openconnect, sin preguntar nada
##lo usa listener.py cuando se cae la conexion con el pluto
##
##las credenciales van en vpn.env (al lado de este script), que NO se sube a github:
##   VPN_USER="usuario"
##   VPN_PASS="contraseña"
##   VPN_CERT="pin-sha256:...."   <- el fingerprint que muestra openconnect la primera vez
##                                    (reemplaza el "yes" que se escribe a mano)
##sudo: para que no pida la contraseña de sudo en medio de la medicion, correr el listener
##en una terminal donde ya se haya usado sudo hace poco, o configurar sudoers para openconnect

AQUI="$(dirname "$(readlink -f "$0")")"
source "$AQUI/vpn.env"

##se corta la vpn anterior si quedo colgada
sudo pkill openconnect
sleep 2

##--passwd-on-stdin: la contraseña entra por la tuberia (no se escribe a mano)
##--servercert: acepta el certificado del servidor (lo que antes era escribir "yes")
##--background: queda corriendo de fondo y el script termina
echo "$VPN_PASS" | sudo openconnect --protocol=anyconnect \
    --user="$VPN_USER" --passwd-on-stdin \
    --servercert "$VPN_CERT" \
    --background 200.16.19.5:443
