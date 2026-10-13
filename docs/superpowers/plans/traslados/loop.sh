#!/usr/bin/env bash
# Reanuda el runner cuando agy se queda sin creditos: cada 30 min vuelve a intentarlo hasta que las 5 tareas esten hechas.
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
hechas() { ls logs/*.done 2>/dev/null | wc -l; }
PID_INICIAL="$(cat logs/runner.pid 2>/dev/null | tr -d '\r\n ')"
while [ "$(hechas)" -lt 5 ]; do
  if [ -n "$PID_INICIAL" ] && tasklist //FI "PID eq $PID_INICIAL" //NH 2>/dev/null | grep -q "$PID_INICIAL"; then sleep 60; continue; fi
  PID_INICIAL=""
  bash run.sh >> logs/runner.out 2>> logs/runner.err
  [ "$(hechas)" -ge 5 ] && break
  echo "$(date '+%F %T') [INFO] el runner se detuvo con $(hechas)/5 tareas; se reintenta en 30 min" >> logs/eventos.log
  sleep 1800
done
