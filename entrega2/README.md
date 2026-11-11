# Entrega 2: buscador híbrido de metadatos FITS (X-shooter)

Bitácora de pasos, decisiones y cifras: [METODOLOGIA.md](METODOLOGIA.md).

## Ubicaciones

| Qué | Windows | WSL2 |
|---|---|---|
| Insumos de la Entrega 1 (6 ZIP, `headers.csv`; solo lectura) | `C:\Bases` | `/mnt/c/Bases` |
| Este proyecto | `C:\Bases\entrega2` | `/mnt/c/Bases/entrega2` |
| venv de Python | — | `~/.venvs/entrega2` (ext4 nativo, no `/mnt/c`) |

Las rutas y URIs están en [src/config.py](src/config.py) y se pueden cambiar con variables de
entorno (`ENTREGA2_DATA_DIR`, `ENTREGA2_MONGO_URI`, `ENTREGA2_WEBHDFS_URL`, ...).

## Preparación (una vez)

```bash
# WSL2 (Ubuntu 24.04); el límite de RAM de la VM está en infra/.wslconfig (copiar a %USERPROFILE%)
sudo apt-get update && sudo apt-get install -y openjdk-17-jdk-headless python3-venv python3-pip
python3 -m venv ~/.venvs/entrega2
source ~/.venvs/entrega2/bin/activate
pip install pyspark==4.0.1 pytest pandas pymongo requests scipy matplotlib threadpoolctl scikit-learn  # sklearn: solo tests
```

## Servicios: MongoDB + HDFS de un nodo

```bash
cd /mnt/c/Bases/entrega2
docker compose -f infra/docker-compose.yml up -d     # e2-mongo, e2-namenode, e2-datanode
docker compose -f infra/docker-compose.yml ps
# UI del namenode: http://localhost:9870   MongoDB: mongodb://localhost:27017
docker compose -f infra/docker-compose.yml down      # conserva los volúmenes (down -v los borra)
```

## Fase 1

```bash
source ~/.venvs/entrega2/bin/activate && cd /mnt/c/Bases/entrega2

# Extracción de headers y verificación celda por celda contra /mnt/c/Bases/headers.csv
python src/extraer_headers.py                         # -> salidas/headers_regenerado.csv
python src/verificar_headers.py salidas/headers_regenerado.csv

# ETL (PySpark): FITS a HDFS (/eso/xshooter/AAAA/MM/DD/...) + documentos en MongoDB (eso.xshooter)
python src/etl.py --zips XSHOO.2026-09-07.zip --limpiar --etiqueta prueba_1zip   # 1 ZIP
N=3 PAUSA=60 ./medir_etl.sh            # 3 corridas completas desde cero (6 ZIP)
python src/resumen_etl.py              # tabla + mediana -> informe/etl_tiempos.csv

# Conteos y verificación cruzada MongoDB <-> HDFS; Prueba E (caja RA/DEC con el índice ra_dec)
python src/conteos.py --esperados 1861
python src/verificar_prueba_e.py

# R1/R6: eso.revision y hdfs:/eso/revision reciben conflictos de ARCFILE y archivos ilegibles
```

## Fase 2 (tokenizador) y Fase 3 (TF-IDF + LSI)

```bash
python src/fase2_tokens.py         # modos de campos texto/todos + artefactos del tokenizador vs prototipo
python src/construir_indice.py     # corpus desde MongoDB -> TF-IDF + LSI -> indice/ (+ manifiesto.json)
                                   #   --modo texto|todos  --idf suavizado|clasico  --criterio sin_primera|energia
python src/prueba_preliminar.py    # top 5 de A-D con TF-IDF y LSI + sensibilidad a k (no es el benchmark)
```

## Fase 4 (K-Means y LSH) y Fase 5 (CLI)

```bash
python src/kmeans_indice.py        # barrido c ∈ {4..128} (consultas cortas = oficial; documentos = secundario) -> elige y persiste
python src/lsh_indice.py           # barrido b × L × radio × centrado, ambos conjuntos -> elige y persiste
python src/buscar.py --texto "filt b"                                        # solo semántica
python src/buscar.py --ra-min 84 --ra-max 85 --dec-min -70 --dec-max -69      # solo numérica (Prueba E)
python src/buscar.py --texto "flat sky" --fecha-desde 2026-09-05 --fecha-hasta 2026-09-05 \
                     --modelo lsi --optim kmeans                             # combinada
python src/prueba_preliminar_optim.py   # 6 configuraciones × A–E + recall + RSS (no es el benchmark)
```

La búsqueda **no usa HDFS** (solo MongoDB e `indice/`): puede correr con
`docker compose -f infra/docker-compose.yml stop namenode datanode`. BLAS corre con 1 hilo
(`ENTREGA2_HILOS_BLAS`; METODOLOGIA.md, Fase 6).

## Fase 6 (benchmark y precisión)

```bash
docker compose -f infra/docker-compose.yml stop namenode datanode   # requisito: HDFS detenido
python src/benchmark.py todo --corrida corta --reps 2000      # corrida corta: estimación y medianas preliminares
python src/benchmark.py todo --corrida completa --reps 100000 # tiempo + RAM + resumen en informe/
python src/benchmark.py resumen --corrida completa            # rehace las tablas desde los datos crudos
python src/benchmark_informe.py                              # boxplot, mediana por ronda, deriva y completa vs. corta
python src/precision.py   # P@5 (informe/p_at_5_revision.csv para revisión manual) y recall relativo A–E
```

### Datos crudos del benchmark

`salidas/benchmark/` (101 MiB, 758 archivos) **no está en git**: se versiona comprimido en
`salidas/benchmark.tar.xz` (8,5 MB). Para restaurarlo, desde la raíz del repositorio:

```bash
tar -xJf entrega2/salidas/benchmark.tar.xz -C entrega2/salidas/
# deja entrega2/salidas/benchmark/{corta,completa}/ con tiempo/, ram/<config>/, plan.json,
# condiciones.jsonl, monitor.csv y resumen/ (la corta), tal como los citan METODOLOGIA.md y
# src/benchmark_informe.py
```

Verificado: tras extraerlo, el árbol es idéntico al original (`diff -r`), y
`python src/benchmark.py resumen --corrida completa` y `python src/benchmark_informe.py`
regeneran las tablas de `informe/benchmark_*` idénticas byte a byte y los PNG idénticos píxel a
píxel, sin necesitar MongoDB.

Datos crudos y condiciones en `salidas/benchmark/<corrida>/`. Si las condiciones dejan de ser
válidas (sin corriente, otro modo de energía, HDFS encendido…), el benchmark se pausa con
código 3; el mismo comando reanuda desde la última ronda completa.

## Tests

```bash
python -m pytest -m "not integracion"   # unitarios (tokenizador, extracción, R1/R6, TF-IDF/LSI/coseno)
python -m pytest -m integracion          # ETL real con Spark + MongoDB + HDFS sobre datos sintéticos (e2_test)
```

Antes de medir tiempos: notebook **enchufado**, modo de energía de Windows en **"Máximo
rendimiento"** y suspensión desactivada. `src/etl.py` registra estas condiciones en las
métricas y avisa si no se cumplen.
