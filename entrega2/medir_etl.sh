#!/usr/bin/env bash
# Corre el ETL completo N veces desde cero (--limpiar vacía MongoDB y HDFS antes de cada una),
# con una pausa entre corridas para que el notebook se enfríe. Antes de cada corrida registra
# cuánto de los ZIP está en la caché de páginas de WSL2.
#   N=3 PAUSA=60 PREFIJO=completo_v2 ./medir_etl.sh
set -euo pipefail
cd "$(dirname "$0")"
source ~/.venvs/entrega2/bin/activate
N=${N:-3}
PAUSA=${PAUSA:-60}
PREFIJO=${PREFIJO:-completo}
for i in $(seq 1 "$N"); do
  echo "===== Corrida $i/$N ($(date -Is)) ====="
  python src/cache_residencia.py /mnt/c/Bases/XSHOO.*.zip | tail -1
  python src/etl.py --limpiar --etiqueta "${PREFIJO}_$i" 2>&1 \
    | grep -v -E 'WARNING: Using incubator|log4j2-defaults|NativeCodeLoader|default log level|setLogLevel'
  if [ "$i" -lt "$N" ]; then sleep "$PAUSA"; fi
done
