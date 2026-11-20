#!/bin/bash
##estado.sh: muestra de un vistazo como va la noche de capturas
##uso: bash scripts/estado.sh          (una vez)
##     watch -n 30 bash scripts/estado.sh   (se actualiza cada 30 s, salir con Ctrl+C)

AQUI="$(dirname "$(readlink -f "$0")")"
LOGS="$AQUI/../data/listener_logs"

echo "=== $(date '+%H:%M:%S') ==="
echo
echo "--- procesos ---"
pgrep -f "scripts/listener.py" >/dev/null && echo "listener: CORRIENDO" || echo "listener: parado"
pgrep -f "scripts/guardia.sh" >/dev/null && echo "guardia:  CORRIENDO" || echo "guardia:  parado  <-- revisar"
pgrep -x openconnect >/dev/null && echo "vpn:      CORRIENDO" || echo "vpn:      parada"

echo
echo "--- red ---"
ping -c1 -W2 1.1.1.1 >/dev/null && echo "internet: OK" || echo "internet: SIN CONEXION"
for ip in 31 33 34 35; do
    ping -c1 -W2 192.168.1.$ip >/dev/null && echo "pluto .$ip: OK" || echo "pluto .$ip: no responde"
done

echo
echo "--- dead man switch ---"
minutos=$(( ($(date +%s) - $(stat -c %Y "$LOGS/.latido")) / 60 ))
echo "ultimo latido de Claude: hace $minutos min (alarma a los 40)"

echo
echo "--- ultima captura (log mas nuevo) ---"
ultimo=$(ls -t "$LOGS"/c*_*.log 2>/dev/null | head -1)
if [ -n "$ultimo" ]; then
    echo "$(basename "$ultimo")"
    grep -E "tx_gain =|terminado|error|vpn" "$ultimo" | tail -4
fi

echo
echo "--- ultimas lineas de la bitacora ---"
tail -5 "$LOGS/BITACORA.md"
