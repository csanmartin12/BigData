# Metodología — Entrega 2: Buscador híbrido de metadatos FITS (X-shooter)

Este documento registra cada paso, comando y decisión del manejo de datos. Cada cifra
proviene de una ejecución; se indica el script que la produjo.

---

## Fase 0 — Reconocimiento (2026-11-10)

### Insumos de la Entrega 1 (no se modifican)

Ubicación actual: `C:\Bases` en Windows = `/mnt/c/Bases` en WSL2 (en la Fase 0 estaban en
`D:\Bases` del equipo anterior; ver [Cambio de equipo](#cambio-de-equipo-2026-11-11)).

| Archivo | Contenido |
|---|---|
| `/mnt/c/Bases/XSHOO.2026-09-0{4..9}.zip` | 6 ZIP, 8,7 GB comprimidos / 14,8 GB sin comprimir. 1.861 FITS (máx. 16,9 MB) + 1.861 entradas `__MACOSX/._*` que no son FITS (metadatos de macOS) |
| `/mnt/c/Bases/headers.csv` | 1.861 filas × 685 columnas |
| `/mnt/c/Bases/extraer_headers.py` | Script de extracción **no coincide** con el CSV: no excluye COMMENT/HISTORY/CONTINUE y lee de `./rars`. El CSV fue generado por otra versión |
| `/mnt/c/Bases/main.typ` + `Informe_Big_Data.pdf` | **Informe 1, versión final** (copiados a `C:\Bases` el 2026-11-11 a las 12:34). Es la referencia para el modelo de datos: Figura 3 (documento `search`/`storage`/`header`), Tabla 7 (campos principales), Tabla 9 (índices), Tabla 10 (categorías) y Tabla 11 (reglas R1–R6) |
| `/mnt/c/Bases/informe.typ` | **Borrador** del Informe 1 (2026-09-14), con otro modelo (`coordenadas.geo` + `2dsphere`, nombres en español). Hasta el 2026-11-11 se usó por error como referencia; ver [Corrección: alineación con el Informe 1 final](#corrección-alineación-con-el-informe-1-final) |

Conteo de FITS por ZIP: 09-04: 378 · 09-05: 433 · 09-06: 277 · 09-07: 176 · 09-08: 325 · 09-09: 272.

### Composición de las 685 columnas de `headers.csv`

Se leyeron las tarjetas de 80 caracteres del HDU primario de los 1.861 FITS directamente
desde los ZIP (streaming, sin astropy; `HIERARCH` normalizado como lo hace astropy):

- **681 llaves FITS distintas**; todas están en el CSV y el CSV no tiene ninguna llave FITS adicional.
- Los FITS **no contienen tarjetas COMMENT, HISTORY ni CONTINUE** y ninguna llave se repite
  dentro de un header; la exclusión y la regla "una ocurrencia por llave" se implementan igual
  pero no alteran estos datos.
- **4 columnas técnicas** (posiciones 439–442 en base 0, es decir, 440–443 en base 1;
  van justo después de las 439 llaves del primer archivo):
  - `_n_campos_header`: número de llaves presentes en el header.
  - `_n_campos_sin_info`: número de valores vacíos (`''`) más valores que contienen
    "unknown" o "not set" (sin distinguir mayúsculas). Verificado con 0 discrepancias
    en las 1.861 filas. Casos reales: `UNKNOWN` (2.900 celdas) y
    `TELESCOP='Tel name not set'` (1.592 archivos).
  - `_source_zip`, `_source_file`: origen del archivo.
- Orden de filas: ZIP en orden alfabético y, dentro de cada ZIP, archivos en orden alfabético.
- Nota: el borrador `informe.typ` indica 684 columnas (682 + 2); el CSV actual tiene 685
  (681 + 4), y el Informe 1 final (`main.typ`) habla de 681 campos FITS distintos.

### Respuestas con datos (headers.csv)

| Pregunta | Resultado |
|---|---|
| Llaves con valor `1.6x11` | Solo `ESO INS OPTI3 NAME`, 58 archivos |
| Llaves FILT con valor `B` | Solo `ESO INS FILT1 NAME`, 10 archivos |
| `ESO DET EXP TYPE = Normal` | 1.232 archivos (Led 192, Dark 30, vacío 407) |
| `ESO DPR TYPE = FLAT,SKY` y DATE-OBS 2026-09-05 | 100 archivos (son todos los FLAT,SKY; todos CALIB) |
| RA ∈ [84, 85] y DEC ∈ [−70, −69] | 18 archivos (CALIB, OBJECT `LAMP,AFC`). 1.592 archivos no tienen RA/DEC |
| Categorías (`ESO DPR CATG`) | CALIB 1.841 · SCIENCE 18 · ACQUISITION 2 |

### Entorno de la Fase 0 (equipo anterior, ya no se usa)

- Windows 11 Pro 10.0.26200; Intel i5-11400 (6 núcleos / 12 hilos, 2,6 GHz); 16 GB RAM (2×8 GB, 2133 MHz).
- `D:` era un **disco duro mecánico SATA** (Toshiba MQ01ABD100, 1 TB). Los ZIP estaban ahí.
- Python 3.13.14 (Microsoft Store) sin paquetes; sin Java, sin Docker; virtualización
  deshabilitada en firmware (WSL2 no arrancaba).
- La Fase 0 solo leyó los ZIP y `headers.csv` (conteos y verificaciones). Ninguna de sus
  cifras es un tiempo, así que el cambio de equipo no invalida ninguna.

---

## Cambio de equipo (2026-11-11)

Desde la Fase 1 se trabaja en un notebook nuevo. **Todas las mediciones de la Entrega 2
(tiempos del ETL y benchmark de búsqueda) se hacen en este equipo.**

| Componente | Especificación | Fuente |
|---|---|---|
| Equipo | Notebook Dell Pro 16 PC16250 | `Win32_ComputerSystem` |
| Sistema | Windows 11 Pro 10.0.26200 (build 26200.9711) | `cmd.exe /c ver`, `Win32_OperatingSystem` |
| CPU | Intel Core Ultra 5 235U: **12 núcleos / 14 hilos, híbrido**: 2 núcleos P (con Hyper-Threading) + 8 núcleos E + 2 núcleos E de bajo consumo | `Win32_Processor` (12 núcleos, 14 lógicos); el reparto P/E viene de la ficha técnica de Intel |
| RAM | 32 GB DDR5-5600 (2×16 GB: Crucial CT16G56C46S5 + Samsung M425R2GA3PB0) | `Win32_PhysicalMemory` |
| Disco | SSD NVMe WD PC SN5000S, 512 GB (476,9 GiB), volumen `C:` NTFS | `Get-PhysicalDisk` |
| WSL2 | Ubuntu 24.04.5 LTS, kernel 6.18.58.1-microsoft-standard-WSL2 | `/etc/os-release`, `uname -r` |
| Límite de la VM | `memory=20GB` en `%USERPROFILE%\.wslconfig` → `free -h`: 19 GiB de RAM + 5 GiB de swap | `infra/.wslconfig` |
| Docker | Docker Desktop 29.9.3 (backend WSL2), Docker Compose v5.7.0; la VM expone 14 CPU y 19,5 GiB | `docker info`, `docker compose version` |

Qué muestra WSL2 y en qué difiere del equipo físico:

- `lscpu` dentro de WSL2 muestra una topología virtual (1 socket × 7 núcleos × 2 hilos = 14 CPU)
  y **no distingue los núcleos P de los E**. Linux reparte los hilos de Spark entre las 14 vCPU
  sin saber que unas son más rápidas que otras.
- `lsblk -d` dentro de WSL2 solo ve discos virtuales (`Virtual Disk`, `ROTA=1` aunque el disco
  físico sea un SSD). El modelo real se obtuvo desde Windows con `Get-PhysicalDisk`.

Condiciones de medición (es un notebook):

- Correr **enchufado** a la corriente, con el modo de energía de Windows en **"Máximo
  rendimiento"** y la suspensión y el apagado de pantalla desactivados mientras se mide. Al
  registrar el equipo estaba **con batería (62 %) y en el plan "Equilibrado"**
  (`powercfg /getactivescheme`); hay que cambiar ambas cosas antes de cada medición.
- **Varianza por la arquitectura híbrida P/E**: el planificador de Windows decide en qué
  núcleos corre cada vCPU, así que una misma tarea puede ir en un núcleo P o en uno E. A eso
  se suman el turbo variable y la limitación térmica del notebook. Por eso cada medición se
  repite varias veces y se informan la mediana y la dispersión, no una ejecución aislada.

---

## Decisiones de entorno

- **WSL2 (Ubuntu 24.04) + Docker Desktop** (backend WSL2).
- Dentro de WSL2: Python 3.12 de Ubuntu, Java 17 (OpenJDK) y PySpark en un venv en
  `~/.venvs/entrega2`, en el ext4 nativo de la VM y **no en `/mnt/c`**: así la importación de
  módulos y los archivos temporales no pasan por 9P.
- MongoDB y HDFS de un solo nodo (namenode + datanode) en `docker-compose`.
- Memoria de la VM de WSL2 limitada a **20 GB** con `infra/.wslconfig`, que se copia a
  `%USERPROFILE%\.wslconfig` (de 32 GB físicos quedan ~12 GB para Windows). MongoDB, HDFS
  y Spark comparten ese límite.
- Los datos permanecen en `C:\Bases` y se leen como `/mnt/c/Bases` desde WSL2.
  **Costo de I/O**: `C:` es un SSD NVMe, pero `/mnt/c` cruza la frontera WSL2↔Windows
  mediante el protocolo 9P, que es bastante más lento que el ext4 nativo de la VM (sobre todo
  por operación de archivo). Esto influye en los tiempos del ETL, que lee los ZIP; el
  benchmark de búsqueda no los lee.

## Decisiones de extracción

- Se reescribe la lógica en `entrega2/` sin tocar `extraer_headers.py`: excluir
  COMMENT/HISTORY/CONTINUE, conservar una ocurrencia por llave e ignorar `__MACOSX/` y `._*`.
- Requisito: el CSV generado debe ser idéntico a `/mnt/c/Bases/headers.csv` (1.861 × 685,
  mismos valores, incluidas las 4 columnas técnicas). Un script de verificación compara
  celda por celda.

## Decisiones de preprocesamiento (tokenizador)

Se aplican las 5 reglas del enunciado en su orden, con estas interpretaciones:

1. **Regla 1**: se eliminan las palabras iniciales `ESO`, `DET`, `INS` de la **llave**
   (como palabras completas; `INSTRUME` se conserva). No se aplica a los valores.
   Las consultas pasan por la **misma función** sin llave, por lo que `ins` de la consulta D
   se conserva como token. Los tokens de la consulta que no estén en el vocabulario se
   ignoran y se reportan en la salida de la CLI (casos `ins`, `opti`, `filt`).
2. **Regla 2**: se eliminan las subcadenas `unknown` y `not set`, sin distinguir mayúsculas.
3. **Regla 3**:
   - "x entre números": fragmento completo `\d+(\.\d+)?x\d+(\.\d+)?` → los `.` pasan a `_`
     (`1.6x11` → `1_6x11`).
   - "Identificador de hardware": fragmento (secuencia maximal de `[A-Za-z0-9_.-]`) formado
     por segmentos **alfanuméricos** unidos por guiones, con al menos una letra y un dígito,
     excluyendo explícitamente las fechas ISO (comienzan con `AAAA-MM-DD`) y la notación
     científica (`1.8e-05`, `5e-05`). Sus guiones pasan a `_`. Así se respeta el orden 3→4
     sin que la regla 3 capture fechas. El detalle de las 28 llaves con guiones está en
     `informe/llaves_con_guion_regla3.csv`.
4. **Regla 4**: se elimina el **valor** de las fechas ISO (en cualquier posición del texto,
   incluida la fecha incrustada en ARCFILE, de la que quedan `xshoo` y `fits`) y el valor
   de `CHECKSUM` y `DATASUM` (aunque DATASUM sea numérico). Las llaves se conservan como tokens.
5. **Regla 5**: toda puntuación se reemplaza por un espacio (`FLAT,SKY` → `flat sky`),
   se conserva `_`, se pasa a minúsculas y se separa por espacios.

- La consulta C **no se corrige** en el tokenizador: es la prueba de polisemia. Sus tres tokens
  aparecen en los 1.861 documentos (`normal` proviene también de `INS SWSIM`, `DET READ MODE`,
  `DET FRAM TYPE`, etc.).
- Tests: `tests/test_tokenizer.py` (66 casos: cada regla, la definición de hardware y las
  5 consultas, incluidos los desajustes conocidos para que no se "arreglen").

## Decisiones de representación (adelantadas)

- IDF por defecto **suavizado**: `idf(t) = ln((1+N)/(1+df(t))) + 1`; opción configurable
  clásica `idf(t) = ln(N/df(t))`. Si la consulta queda con norma 0, se devuelve un resultado
  vacío con aviso (no un error).

## Artefactos para el informe

| Archivo | Contenido | Generado con |
|---|---|---|
| `informe/prototipo/df_tokens_consultas.csv` | Por consulta y token: si está en el vocabulario, df global, cuántos relevantes lo contienen, IDF suavizado y clásico | Prototipo del tokenizador con las interpretaciones de arriba sobre `headers.csv` (vocabulario: 14.746 tokens). Regenerado en la Fase 2 (ver abajo) |
| `informe/prototipo/llaves_con_guion_regla3.csv` | Las 28 llaves con valores con guion (excluidas las fechas): fragmento, clasificación según la regla 3 y tokens resultantes | Ídem |
| `informe/etl_tiempos.csv` | Las 3 corridas del ETL completo con el código final (R1/R6; la 1 con caché fría) y la mediana: tiempos, MB/s, insertados/omitidos/revisión, % por etapa, condiciones de energía | `src/resumen_etl.py` sobre `salidas/etl_*_completo_v2_*.json` (Fase 1) |
| `informe/etl_tiempos_v1_previa.csv` | Las 3 corridas de la versión previa (sin R1/R6) | `src/resumen_etl.py --patron 'etl_*_completo_[0-9].json'` |
| `informe/df_tokens_consultas.csv` | **Regenerado con `src/tokenizer.py`** desde MongoDB, modos `texto` y `todos` (columna `modo`) | `src/fase2_tokens.py` (Fase 2) |
| `informe/df_tokens_consultas_control_csv.csv` | Control: el tokenizador real sobre `headers.csv` | Ídem |
| `informe/llaves_con_guion_regla3.csv` | **Regenerado** desde MongoDB: 523 filas, 30 llaves; columnas nuevas `tipo_valor` y `en_modo_texto` | Ídem |
| `informe/modos_campos.csv` | Vocabulario y tokens por documento de cada modo | Ídem |
| `informe/prototipo/*.csv` | Los dos CSV del prototipo, sin cambios, para comparar | Prototipo (Fase 0) |
| `informe/lsi_varianza.csv`, `informe/lsi_varianza_explicada.png` | Curvas de varianza acumulada (`energia` y `sin_primera`) y k elegido | `src/construir_indice.py` (Fase 3) |
| `informe/prueba_preliminar_top5.csv` / `.md` | Top 5 de A–D con TF-IDF y LSI, metadatos de relevancia y marca de relevante | `src/prueba_preliminar.py` (Fase 3) |
| `informe/sensibilidad_k.csv` | P@5, P@10 y R-precisión para k = 2, 5, 14 y 54 (posterior a la elección) | Ídem |
| `informe/validacion_kmeans.csv` / `.png` | Barrido de K-Means (c × n_probe × espacio): recall estricto y con tolerancia, costo, tamaños, silueta, inercia | `src/kmeans_indice.py` (Fase 4) |
| `informe/validacion_lsh.csv` / `.png` | Barrido de LSH (b × L × espacio): recall, costo, multi-probe, buckets, idénticos y casi idénticos | `src/lsh_indice.py` (Fase 4) |
| `informe/prueba_preliminar_optim_top5.csv` / `.md` | 6 configuraciones × A–E: top-5 con metadatos y relevancia | `src/prueba_preliminar_optim.py` (Fase 5) |
| `informe/prueba_preliminar_optim_recall.csv` | Recall relativo top-10 (estricto y con tolerancia) de las 4 configuraciones optimizadas | Ídem |
| `informe/memoria_busqueda.json` | RSS del proceso de búsqueda y tamaño de cada estructura | Ídem |
| `informe/consultas_cortas.csv` | Las 200 consultas cortas de validación (texto, largo, llave y ARCFILE de origen) | `src/conjuntos.py` (Fase 4b) |
| `informe/validacion_v2_kmeans.csv`, `informe/validacion_cortas_kmeans.png` | Barrido de K-Means con c ∈ {4..128} y ambos conjuntos (columna `conjunto`); curva con consultas cortas | `src/kmeans_indice.py` (Fase 4b) |
| `informe/validacion_v2_lsh.csv`, `informe/validacion_cortas_lsh.png` | Barrido de LSH (b × L × radio × centrado) con ambos conjuntos; nube con consultas cortas y fronteras de Pareto | `src/lsh_indice.py` (Fase 4b) |
| `informe/prueba_preliminar_optim_*_antes.*`, `informe/memoria_busqueda_antes.json` | Prueba preliminar con los hiperparámetros de la primera validación | `src/prueba_preliminar_optim.py` (Fase 5) |
| `informe/prueba_preliminar_antes_despues.md` / `.csv` | Comparación antes / después de la revisión del protocolo | `src/comparar_antes_despues.py` (Fase 4b) |
| `informe/p_at_5_revision.csv` | Top-5 de TF-IDF y LSI exhaustivas × A–E con los metadatos de relevancia, `relevante_auto` y `relevante_manual` (para el usuario) | `src/precision.py` (Fase 6) |
| `informe/tabla2_p_at_5.md` / `.csv` | Tabla 2: P@5 por consulta y modelo | Ídem |
| `informe/tabla3_recall.md` / `.csv` | Tabla 3: recall relativo top-10 (tolerancia / estricto) y costo, más las referencias K-Means n_probe = 2 y LSH b = 16 | Ídem |
| `salidas/benchmark/<corrida>/` | Datos crudos del benchmark por ronda (`tiempo/`, `ram/<config>/`), `plan.json`, `condiciones.jsonl`, `monitor.csv` | `src/benchmark.py` (Fase 6) |
| `informe/benchmark_*.csv`, `informe/benchmark_resumen.md` | Tabla 1 (tiempo y RAM), RSS base, anexos por consulta y mediana por ronda (corrida completa) | `src/benchmark.py resumen` (Fase 6) |
| `informe/benchmark_tiempo_boxplot.png` | Boxplot de tiempos por configuración (escala log, bigotes p1–p99) | `src/benchmark_informe.py` (Fase 6) |
| `informe/benchmark_deriva_por_ronda.png` | Mediana por ronda relativa a la global, por configuración (banda ±10 %) | Ídem |
| `informe/benchmark_deriva.csv` | Deriva primer vs. último cuarto de rondas, por configuración y por configuración × consulta | Ídem |
| `informe/benchmark_completa_vs_corta.md` / `.csv` | Medianas de la corrida completa vs. la corta, y la tabla de deriva | Ídem |

---

## Fase 1 — Infraestructura, extracción y ETL (2026-11-11)

### Entorno instalado (equipo de medición)

| Componente | Versión | Notas |
|---|---|---|
| Java | OpenJDK 17.0.21 (`openjdk-17-jdk-headless`) | `/usr/lib/jvm/java-17-openjdk-amd64` |
| Python | 3.12.3 (Ubuntu) | venv en `~/.venvs/entrega2` (ext4, no `/mnt/c`) |
| Paquetes | pyspark 4.0.1 (py4j 0.10.9.9), pytest 9.2.0, pandas 3.1.1, numpy 2.5.4, pymongo 4.19.0, requests 2.34.2 | pandas: CSV de verificación; pymongo/requests: carga en MongoDB y WebHDFS |
| MongoDB | 8.0.34 (`mongo:8.0`, `sha256:b9924c33…`) | `--wiredTigerCacheSizeGB 2` |
| HDFS | Hadoop 3.4.1 (`apache/hadoop:3.4.1`, `sha256:69ffa973…`; Java 1.8.0_212 dentro de la imagen) | namenode + datanode, `-Xmx1g` cada uno |

Los paquetes apt los instaló el usuario (`sudo` pide contraseña):
`sudo apt-get update && sudo apt-get install -y openjdk-17-jdk-headless python3-venv python3-pip`.

**Smoke test de PySpark** (`local[*]`, 14 hilos): `spark.range(1000).count() = 1000` y
`sc.parallelize(range(1, 1001), 8).sum() = 500500`, ejecutado en 8 workers de Python distintos
del driver, todos con el intérprete del venv. Arranque + pruebas: 7,9 s. Spark avisa que el
hostname resuelve a loopback, por lo que los scripts fijan `SPARK_LOCAL_IP=127.0.0.1`.

Espacio libre al empezar: 954 GB en el ext4 de WSL2 y 342 GB en `C:`. Docker estaba vacío.

### Servicios (`infra/docker-compose.yml`, `infra/hadoop.env`)

- Proyecto `entrega2`, contenedores `e2-mongo`, `e2-namenode` y `e2-datanode`, con volúmenes con
  nombre `entrega2_mongo-data`, `entrega2_hdfs-namenode` y `entrega2_hdfs-datanode`
  (sobreviven a `down`; solo `down -v` los borra). Los puertos se publican **solo en
  127.0.0.1**, sin autenticación.
- HDFS: `dfs.replication=1`. El namenode se formatea solo en el primer arranque
  (`ENSURE_NAMENODE_DIR=/data/namenode`).
- **Datanode anunciado como `localhost`** (`dfs.datanode.hostname=localhost`, con los puertos
  9864/9866/9867 publicados). Con Docker Desktop, las IP internas de los contenedores no son
  accesibles desde WSL2. Así, la redirección 307 de WebHDFS
  (`http://localhost:9864/webhdfs/v1/...`) y más adelante el cliente HDFS de Spark (con
  `dfs.client.use.datanode.hostname=true`) llegan al datanode sin tocar `/etc/hosts`.
- Probado: escritura y lectura por WebHDFS desde WSL2, `replication = 1`, bloque de 128 MB.

**Desviación justificada respecto del Informe 1: `:` → `_` en el nombre del archivo en HDFS.**
La Figura 3 del Informe 1 define
`hdfs_path = /eso/xshooter/2026/09/06/XSHOO.2026-09-06T08:04:59.035.fits`, es decir, con `:`.
HDFS no lo admite: crear `/prueba/XSHOO.2026-09-04T01:43:37.983.fits` por WebHDFS devuelve
HTTP 400 `InvalidPathException`, y todos los ARCFILE llevan `:` en la hora. Por eso la ruta
queda `/eso/xshooter/AAAA/MM/DD/<ARCFILE con ':' → '_'>`, por ejemplo
`/eso/xshooter/2026/09/06/XSHOO.2026-09-06T08_04_59.035.fits`.

- El reemplazo es inyectivo (ningún ARCFILE contiene `_`), así que la ruta sigue
  identificando un único archivo.
- `_id`, `header.ARCFILE` y `storage.source.file` conservan el nombre original con `:`.
- La fecha de la ruta sale de DATE-OBS, que en los 1.861 archivos coincide con la del ARCFILE y
  con la del ZIP.
- Aprobado por el usuario el 2026-11-11. (Antes, esta bitácora decía por error que el ejemplo
  de la Entrega 1 ya usaba `_`; eso venía del borrador `informe.typ`.)

### Extracción y verificación contra `headers.csv`

- `src/fits_header.py`: lee solo los bloques de 2.880 bytes hasta `END` (sin astropy, sin
  descomprimir las imágenes) y tipa los valores como astropy. `src/extraer_headers.py` arma el
  CSV con pandas (columnas en orden de primera aparición más las 4 de control).
- Tarjetas en los 1.861 headers: 664.482 `HIERARCH`, 52.632 estándar, 202.492 en blanco (relleno)
  y 0 COMMENT/HISTORY/CONTINUE. Hay llaves HIERARCH sin espacio antes del `=`
  (`HIERARCH ESO DET CHIP FRMXFER=`), que se normalizan a `ESO DET CHIP FRMXFER`. No hay valores
  indefinidos. Tipos: 312.606 str, 288.353 float, 105.112 int y 11.043 bool.
- Extracción de los 6 ZIP: 2,9 s (solo lectura de headers) y 4,1 s con la escritura del CSV.
- `src/verificar_headers.py salidas/headers_regenerado.csv` → **IDÉNTICO**: 1.861 × 685, mismas
  columnas en el mismo orden, control en 439–442 (base 0), filas ordenadas por (ZIP, archivo),
  **1.274.785 celdas comparadas, 0 diferencias**. Además, los archivos son idénticos byte a byte
  (mismo SHA-256 `1d4fd43f…f1ef9c7a`).
- Tests: `tests/test_extraccion.py` (31 casos: tipado de valores, exclusiones, una ocurrencia
  por llave, `__MACOSX`, columna sin info, ruta HDFS, documento, coordenadas sin imputar y
  filtro de la Prueba E).

### Corrección: alineación con el Informe 1 final

La primera versión del documento y de los índices (2026-11-11, mañana) se basó en el borrador
`informe.typ` y no en el Informe 1 final (`main.typ`). Tras la revisión del usuario se
realineó todo con la versión final: nombres de `search`/`storage`, índices de la Tabla 9 y
coordenadas. Se eliminaron los campos que solo existían en el borrador (`brazo`, `naxis`,
`origfile`, `programa.tpl_id`, `condiciones`, `calidad`, `es_objetivo_real`,
`nivel_entrega1`); siguen disponibles en `header`. La prueba con 1 ZIP de más abajo se hizo con
la versión anterior; su tiempo sirve igual como estimación, porque la transformación pesa
< 0,1 % del total.

### Documento de MongoDB (`src/documento.py`)

Colección `eso.xshooter`, un documento por FITS con `_id = ARCFILE` (Informe 1: Figura 3 y
Tabla 7):

```text
_id      ARCFILE (original, con ':')
search   object, ra*, dec*, tiene_coordenadas, date_obs (fecha UTC), mjd_obs, exptime,
         dpr.{catg, type, tech}, program_id, instrument, telescope, indexado
storage  hdfs_path, checksum, datasum                       <- Informe 1
         size_bytes, sha256, source.{zip, file}, loaded_at  <- agregados en la Entrega 2
header   header primario completo (llaves FITS originales, valores tipados)
* solo si el header trae el valor
```

Decisiones:

- **Coordenadas en grados originales, sin completar ni imputar.** `search.ra` y `search.dec`
  se copian tal cual del header y **solo si están presentes**: no se guarda `null` ni se
  inventan valores. `search.tiene_coordenadas = true` si el header trae RA y DEC; R3 pide
  revisarlas como par. Según la ESO, que falten en calibraciones es válido (Informe 1, sección
  5.3: no tienen que estar en un BIAS), así que no se trata como un error (R3, R5).
- **Se indexan todas las categorías**: `search.indexado = true` en los 1.861 documentos,
  ACQUISITION incluida, porque las consultas A–D apuntan a archivos CALIB. Aprobado por el
  usuario. La Tabla 10 (qué categorías aparecen *por defecto* en una búsqueda científica) se
  resuelve al consultar (Fase 3), no al cargar.
- **`header` completo — desviación justificada del Informe 1** (aprobada por el usuario el
  2026-11-11). El Informe 1 dice que `header` guarda "los demás
  metadatos" (los que no están en `search`). Aquí se guarda el header entero, incluidos los
  campos promovidos, por dos razones: (1) el tokenizador de la Fase 2 (`tokenizar_header`)
  trabaja sobre las llaves FITS originales (la regla 1 quita `ESO`/`DET`/`INS` de la llave), y
  la consulta A, por ejemplo, necesita `ESO DPR TYPE = FLAT,SKY`; (2) DATE-OBS como fecha de
  MongoDB guarda solo milisegundos, así que `2026-09-04T01:43:39.3915` no se podría
  reconstruir. Costo: unos pocos cientos de bytes por documento.
- **Índices — Tabla 9 del Informe 1** (`INDICES_ENTREGA1`), además del `_id_` único
  automático:

  | Nombre | Campos | Tipo |
  |---|---|---|
  | `date_obs` | `search.date_obs` | simple |
  | `object` | `search.object` | simple |
  | `ra_dec` | `search.ra`, `search.dec` | compuesto |
  | `dpr_catg_type` | `search.dpr.catg`, `search.dpr.type` | compuesto |

  **Índice de `search.program_id`: no se crea** (decisión del usuario, 2026-11-11). En la
  Tabla 9 figura como "Opcional" ("si las consultas por programa son frecuentes") y ninguna de
  las consultas A–E filtra por programa. Queda definido en `INDICES_OPCIONALES` por si se
  necesita más adelante.

#### Índice geográfico: descartado

En la primera versión había un campo GeoJSON `search.coordenadas.geo = [RA − 180, DEC]` con
índice `2dsphere`, tomados del borrador. **Se eliminaron**, y no quedan ni dentro ni fuera del
buscador, por tres razones:

1. El Informe 1 final (Tabla 9) define un índice compuesto **normal** sobre
   `search.ra`/`search.dec` para filtrar por intervalos, y deja la búsqueda por distancia
   angular para "una etapa posterior".
2. En `2dsphere`, los lados de un polígono son geodésicas (arcos de círculo máximo), no
   paralelos. El lado entre (84°, −70°) y (85°, −70°) se aleja del paralelo −70° hacia el polo
   y en el punto medio pasa por −70,000701° (tan φ = tan 70° / cos 0,5°), es decir, 2,5″ fuera.
   El lado de −69° pasa por −69,000730° (2,6″). Un archivo con DEC entre −70,0007° y −70° quedaría
   dentro del polígono aunque esté fuera de la caja, y uno con DEC entre −69,0007° y −69° quedaría
   fuera aunque esté dentro. La Prueba E exige que RA y DEC queden dentro de la caja según sus
   valores numéricos, y eso solo lo garantiza un filtro `$gte/$lte` sobre los grados originales.
3. El desplazamiento `RA − 180` era una convención del borrador, no del Informe 1.

La Prueba E se resuelve con `consultas.filtro_caja_coordenadas` (`$gte/$lte` sobre
`search.ra` y `search.dec`) y el índice `ra_dec`; ver la verificación más abajo.

### ETL con PySpark (`src/etl.py`): qué corre en el driver y qué en los ejecutores

Modo `local[*]`: el driver y el ejecutor comparten una JVM con 14 hilos de tarea, y cada
tarea ejecuta el código Python en un **worker de Python aparte** (`pyspark.daemon`), no en el
proceso Python del driver.

| Dónde | Qué |
|---|---|
| **Driver** | `planificar`: lee solo el **directorio central** de cada ZIP (nombres y tamaños de los miembros; ningún byte de FITS, 0,01–0,04 s). `repartir`: arma **42 particiones** (3 × 14 hilos) equilibradas por bytes, poniendo primero los archivos más grandes. Lanza el job, recibe con `collect()` **solo un dict de métricas por partición** y crea los índices. `--limpiar` (vaciar MongoDB y HDFS) también corre aquí, antes de empezar a medir |
| **Tareas de Spark** (una por partición, 1 stage) | `mapPartitions(extraer)`: abre cada ZIP una vez por partición y lee cada FITS completo y su header → `mapPartitions(subir_hdfs)`: SHA-256 y `CREATE` por WebHDFS (un cliente por partición, `overwrite=true`) → `mapPartitions(transformar)`: documento → `mapPartitions(cargar)`: `ReplaceOne(upsert=True)` en lotes de 100 (un `MongoClient` por partición) |

Las cuatro etapas son transformaciones estrechas, así que Spark las encadena en la misma tarea
y el mismo worker de Python: los bytes de cada FITS no se serializan entre etapas ni pasan por
el driver.

**Evidencia en cada corrida**: `cargar` obtiene `TaskContext.get()`, que solo existe dentro de
una tarea de Spark, y devuelve el stage, la partición, el intento y el PID del worker. El
driver comprueba que estén las particiones `0…41`, todas del mismo stage, y que ningún PID
coincida con el suyo (`spark.trabajo_en_tareas_spark` en el JSON de métricas). En la prueba
de humo con el código nuevo hubo 42 tareas en el stage 0, ejecutadas por 14 workers de Python
distintos del driver.

Otros detalles:

- `--limpiar` vacía la colección y `hdfs:/eso/xshooter` y **espera a que el datanode borre los
  bloques**: en HDFS el borrado es asíncrono. Se consulta el JMX del namenode
  (`BlocksTotal`/`PendingDeletionBlocks` = 0) y del datanode (`DfsUsed` < 50 MB). Este tiempo
  queda fuera de lo medido.
- Tiempo medido = plan + arranque de Spark + job + índices.
- Métricas en `salidas/etl_<fecha>[_etiqueta].json`: tiempos, suma por etapa en los workers,
  métricas por partición y estado del equipo (`src/entorno.py`: corriente/batería, "Modo de
  energía" de Windows 11 leído del registro (`ActiveOverlayAcPowerScheme`), plan de
  `powercfg` y memoria standby de Windows).
- `src/conteos.py`: conteos en MongoDB y HDFS, cruce `storage.hdfs_path` ↔ archivos de HDFS
  (existencia y tamaño) y SHA-256 de una muestra descargada de HDFS.
- (Versión previa) La carga usaba `ReplaceOne(upsert=True)`: sobrescribía un ARCFILE ya
  registrado aunque tuviera otro contenido, y un FITS ilegible detenía el job. Se reemplazó por
  R1/R6; ver [Reglas R1 y R6 en la carga](#reglas-r1-y-r6-en-la-carga-2026-11-11).

#### Prueba con 1 ZIP (`XSHOO.2026-09-07.zip`)

`python src/etl.py --zips XSHOO.2026-09-07.zip --limpiar --etiqueta prueba_1zip`
→ `salidas/etl_20261111T152718Z_prueba_1zip.json`, con el **código y el documento
anteriores**. **Condiciones: enchufado (72 %), pero en modo "Equilibrado"; solo sirve para
estimar, no para el informe.**

| Medida | Valor |
|---|---|
| FITS / bytes | 176 / 1.728,6 MB sin comprimir (997,9 MB comprimidos) |
| Particiones | 42 (4–6 FITS y 39,9–42,5 MB cada una), 14 workers de Python |
| ETL (pared) | **12,6 s** → 136,8 MB/s, 13,9 FITS/s |
| Script completo | 18,9 s (arranque de Spark 4,7 s, limpieza, índices 0,1 s) |
| Suma por etapa en los workers | extraer 48,7 s (39,6 %), subir a HDFS 72,1 s (58,7 %), SHA-256 1,6 s, transformar < 0,1 s, cargar en MongoDB 0,4 s |

Verificación (`src/conteos.py --esperados 176`): 176 documentos y 176 archivos en
`/eso/xshooter/2026/09/07/`, 0 faltantes, 0 sobrantes, 0 tamaños distintos, replicación 1 y
SHA-256 de 10/10 FITS descargados de HDFS iguales a `storage.sha256`.

**Estimación del ETL completo**: 14.812 MB / 136,8 MB/s ≈ 108 s de ETL más ~7 s fijos
(Spark, plan, índices), es decir **unos 2 minutos**. La relación de compresión del ZIP de
prueba (1,73) es parecida a la del total (1,70). Las etapas que pesan son la subida a HDFS
(reenvío de puertos de Docker Desktop) y la lectura del ZIP por 9P. La caché de archivos de
Windows puede hacer que una segunda ejecución sea más rápida que la primera.

La prueba de humo del código nuevo (`--etiqueta humo_codigo_nuevo`, mismo ZIP, ya en
"Máximo rendimiento") tardó 9,9 s de ETL (175 MB/s), frente a 12,6 s en "Equilibrado". Sirvió
para validar el código antes de las corridas medidas y no se usa como medición.

#### Caché de los ZIP: qué significa "caché fría" en este equipo

Se midió con `src/cache_residencia.py` (`mmap` + `mincore`, sin leer el contenido):

- En el montaje 9P de `/mnt/c` (`cache=0x5`, modo mmap), `read()` **no** pasa por la caché de
  páginas de Linux: después de leer 4 MB con `read()` hay 0 MB en caché. Las páginas leídas por
  `mmap` sí aparecen (4,1 MB) mientras el mapeo está abierto, y se descartan al cerrarlo.
  Control en ext4: 8,0 MB de 8,0 MB recién escritos están en caché.
- Antes de cada una de las 3 corridas: **0,0 de 8.694,1 MB** de ZIP en la caché de WSL2. La VM
  no retiene los ZIP entre corridas; cada una vuelve a leerlos por 9P desde Windows.
- La única caché que podía favorecer a las corridas 2 y 3 es la de archivos de Windows (lista
  standby). No se ve por archivo desde WSL2 ni se puede vaciar sin herramientas de
  administrador o un reinicio. Se registra su tamaño total (`Win32_PerfFormattedData_PerfOS_Memory`):
  la VM de WSL2 retiene ~16 GB, así que a Windows le quedan pocos (2,3 / 0,9 / 3,2 GB de
  standby al iniciar cada corrida, frente a 8,7 GB de ZIP).
- Por eso la corrida 1 se etiqueta "caché fría", con la salvedad de que la caché de Windows no
  se vació. El ZIP 09-07 (11 % de los bytes) se había leído completo ~15 min antes, en la
  prueba de humo.

### Corridas del ETL completo (3 desde cero) — versión previa (sin R1/R6)

> **Versión previa.** Estas corridas usaban la carga con `ReplaceOne(upsert=True)`, sin R1/R6.
> Se conservan como referencia: `informe/etl_tiempos_v1_previa.csv` y
> `salidas/medir_etl_3corridas.log`. Las cifras vigentes son las de
> [Corridas con el código final](#corridas-del-etl-completo-con-el-código-final-r1r6).

`N=3 PAUSA=60 ./medir_etl.sh` (log: `salidas/medir_etl_3corridas.log`). Antes de cada corrida,
`--limpiar` vacía MongoDB y HDFS y espera a que se borren los bloques (10–12 s, no medidos);
entre corridas hay 60 s de pausa para que el notebook se enfríe. Antes de empezar se confirmó
en el registro `ActiveOverlayAcPowerScheme = ded574b5-45a0-4f42-8737-46345c09c238` ("Máximo
rendimiento"); las 3 corridas fueron enchufado (76–77 %) y con `condiciones_validas = true`.
Resumen: `python src/resumen_etl.py` → `informe/etl_tiempos.csv`.

| Corrida | Caché | ETL (job Spark) | Total medido | MB/s | FITS/s | Arranque Spark | extraer / HDFS (% del tiempo de workers) | Standby Windows al inicio |
|---|---|---|---|---|---|---|---|---|
| 1 | **fría** | 77,91 s | 83,31 s | 190,1 | 23,9 | 4,11 s | 47,2 / 50,8 | 2.339 MB |
| 2 | tibia | 84,47 s | 90,82 s | 175,4 | 22,0 | 5,06 s | 49,4 / 48,5 | 894 MB |
| 3 | tibia | 76,87 s | 82,75 s | 192,7 | 24,2 | 4,56 s | 50,7 / 47,2 | 3.152 MB |
| **Mediana** | | **77,91 s** | **83,31 s** | **190,1** | **23,9** | | | |

- Datos de cada corrida: 6 ZIP, 1.861 FITS, 14.812,2 MB sin comprimir (8.692,9 MB
  comprimidos). Plan en el driver: 0,03–0,04 s. Índices: 0,1 s.
- Paralelismo: 42 particiones de 43–46 FITS y 352–353 MB cada una, todas en el stage 0, con
  14 workers de Python cuyos PID son distintos del driver. Cada tarea duró 19–30 s; con 14
  hilos son 3 tandas de tareas, lo que cuadra con ~78 s de job.
- Rango del ETL: 76,87–84,47 s (7,6 s, 9,8 % de la mediana). **La corrida fría no fue la más
  lenta**, lo que concuerda con que no hay caché de los ZIP en la VM. La más lenta (2) empezó
  con solo 895 MB disponibles en Windows; es una posible explicación, no está comprobada. Con
  3 corridas no se puede separar ese efecto de la varianza P/E y térmica.
- Etapas (tiempo sumado en los workers): leer y descomprimir los ZIP por 9P (47–51 %) y subir a
  HDFS por WebHDFS a través del reenvío de puertos de Docker Desktop (47–51 %) dominan. SHA-256
  ~2 %; transformar y cargar en MongoDB, < 0,3 %.
- Frente a la estimación (~2 min, hecha con 1 ZIP en "Equilibrado"), lo medido fue 83 s.

### Estado final de la Fase 1 (tras la corrida 3)

`python src/conteos.py --esperados 1861 --muestra-sha 30` → **OK**

| | MongoDB `eso.xshooter` | HDFS `/eso/xshooter` |
|---|---|---|
| Total | 1.861 documentos | 1.861 archivos, 9 directorios, 14.812.220.160 bytes (14,81 GB), replicación 1 en todos |
| Por ZIP / día | 09-04: 378 · 09-05: 433 · 09-06: 277 · 09-07: 176 · 09-08: 325 · 09-09: 272 | igual en `2026/09/04` … `2026/09/09` |
| Por `ESO DPR CATG` | CALIB 1.841 · SCIENCE 18 · ACQUISITION 2 (igual que en la Fase 0) | — |
| Coordenadas | `tiene_coordenadas`: true 269, false 1.592; `search.ra` y `search.dec` existen en 269 y faltan en 1.592 (sin `null`) | — |
| Tamaño | 22,3 MB de datos (12,0 kB/documento), 5,8 MB en disco, 0,19 MB de índices | — |
| Índices | `_id_`, `date_obs`, `object`, `ra_dec`, `dpr_catg_type` | — |

Cruce: 0 documentos sin archivo, 0 archivos sin documento, 0 tamaños distintos, y SHA-256 de
30/30 FITS descargados de HDFS iguales a `storage.sha256`. `search.indexado = true` en los 1.861.

### Prueba E: caja RA [84, 85] × DEC [−70, −69]

`python src/verificar_prueba_e.py` → **OK**

- Esperados según `headers.csv`, sin pasar por MongoDB: **18** (igual que en la Fase 0).
- Filtro: `{"search.ra": {"$gte": 84, "$lte": 85}, "search.dec": {"$gte": -70, "$lte": -69}}`.
  Plan ganador `IXSCAN (ra_dec) → FETCH`, con límites `ra [84, 85]` y `dec [−70, −69]`:
  nReturned = 18, totalKeysExamined = 19, totalDocsExamined = 18, 0 ms.
- Mismo conjunto de ARCFILE: 0 faltantes y 0 sobrantes. Los 18 están estrictamente dentro de
  la caja, sin tocar los bordes; `search.ra/dec` coincide con `header.RA/DEC` en los 18 y todos
  tienen `tiene_coordenadas = true`.
- Los 18 son `CALIB` / `LAMP,AFC` (OBJECT `LAMP,AFC`) y comparten un solo apuntado:
  RA 84,454308, DEC −69,08562.

---

## Reglas R1 y R6 en la carga (2026-11-11)

El usuario decidió implementar las reglas R1 y R6 de la Tabla 11 del Informe 1
(`src/carga.py`, usado por la etapa `cargar` de `src/etl.py`).

| Caso | Qué hace el ETL | Resultado en las métricas |
|---|---|---|
| ARCFILE nuevo | se inserta en `eso.xshooter` y su FITS se sube a `/eso/xshooter/AAAA/MM/DD/…` | `insertados` |
| ARCFILE ya registrado con el **mismo** SHA-256 | se omite: no se inserta ni se sube (carga idempotente) | `omitidos_identicos` |
| ARCFILE ya registrado con **otro** SHA-256 | **no se sobrescribe**. Va a `eso.revision` con motivo `conflicto_arcfile` (SHA-256 nuevo y existente) y su FITS **no** va a la ruta principal | `revision.conflicto_arcfile` |
| ZIP que no se puede listar (directorio central dañado) | el driver lo registra (`ilegible`, etapa `listar_zip`, miembro nulo) y sigue con los demás ZIP | `zips_ilegibles` |
| Miembro dañado (CRC-32, deflate) | `ilegible`, etapa `leer_zip`; no hay bytes | `revision.ilegible` |
| Header corrupto, sin END o que no es FITS | `ilegible`, etapa `leer_header` | `revision.ilegible` |
| Header sin ARCFILE (R1) / DATE-OBS inválida (R2) | `sin_arcfile` / `header_invalido` | `revision.*` |
| Falla la subida a HDFS | se libera el ARCFILE (`delete_one`) y el caso va a revisión | `revision.error_hdfs` |

- **Sin carreras entre tareas paralelas**: el ARCFILE se *reclama* primero con `insert_one`.
  El índice único de `_id` decide quién lo obtiene, incluso entre tareas de Spark concurrentes,
  y solo quien lo reclamó sube el FITS a la ruta principal. Si en una misma corrida aparecen
  dos contenidos distintos con el mismo ARCFILE, gana el primero en reclamarlo (entre tareas
  paralelas ese orden no está definido). Entre corridas gana siempre el ya registrado.
- **`eso.revision`**: `_id` determinista `motivo|zip|miembro|sha256` con upsert (volver a
  ejecutar el ETL no duplica entradas), `motivo`, `etapa`, `zip`, `miembro`, `error`,
  `arcfile`, `sha256`, `sha256_existente`, `size_bytes`, `revision_hdfs_path` y `detectado_en`.
- **Copia en `/eso/revision/<sha256>.fits`** cuando hay bytes (conflicto, header ilegible, sin
  ARCFILE). R6 dice que estos archivos "se separan para revisión en lugar de eliminarse": la
  copia queda fuera de la ruta principal, y nombrarla por SHA-256 evita colisiones y la hace
  idempotente. Aprobado por el usuario el 2026-11-11.
- Flujo de las tareas ahora: `extraer` (lectura, header y SHA-256; R6) → `transformar`
  (documento; R1/R2) → `cargar` (R1: reclamar en MongoDB → subir a HDFS, o ir a revisión).
  La subida a HDFS pasó a la etapa de carga porque depende del reclamo. Todo sigue dentro de
  las tareas de Spark (`mapPartitions`); el driver solo lista los ZIP y registra los que no se
  pueden leer.
- Métricas nuevas en el JSON (`carga`): `insertados`, `omitidos_identicos`, `revision` por
  motivo, `revision_total`, `zips_ilegibles` y `bytes_subidos`. El ETL comprueba que
  insertados + omitidos + revisión = FITS planificados.
- `--limpiar` vacía también `eso.revision` y `/eso/revision`. Las raíces de HDFS y la
  colección de revisión se pueden cambiar con variables de entorno, lo que usa el test de
  integración.

**Tests** (`tests/sinteticos.py` arma FITS y ZIP sintéticos):

- `tests/test_r1_r6.py`, 9 casos con dobles en memoria de MongoDB y HDFS: archivo nuevo;
  **ARCFILE duplicado idéntico** (se omite y se sube una sola vez); **ARCFILE duplicado con otro
  contenido** (conflicto: el registrado y la ruta principal no cambian, revisión con ambos
  SHA-256 y copia en `/eso/revision`); error de HDFS (libera el reclamo); revisión
  idempotente; **FITS truncado** (sin END → `ilegible/leer_header`, y el resto sigue); miembro
  con CRC dañado; header sin ARCFILE y con DATE-OBS inválida; ZIP ilegible en el plan.
- `tests/test_etl_integracion.py` (marcador `integracion`): el ETL real con Spark, MongoDB y
  HDFS en la base `e2_test` y la raíz `/e2_test`, sin tocar `eso` ni `/eso` (21 s).
  - Corrida 1 (`--limpiar`), con un ZIP que tiene un FITS bueno, uno truncado, uno con CRC
    dañado y uno sin ARCFILE: insertados 1, revisión `ilegible` 2 y `sin_arcfile` 1.
  - Corrida 2 (sin limpiar), agregando un ZIP con el mismo FITS idéntico y otro con el mismo
    ARCFILE pero distinto contenido, más un ZIP ilegible: insertados 0, **omitidos 2**,
    revisión `ilegible` 2, `sin_arcfile` 1 y **`conflicto_arcfile` 1**, y 1 ZIP ilegible.
  - Estado final: 1 documento con el SHA-256 original y la ruta principal con los bytes
    originales; 5 entradas en revisión; la copia del conflicto en `/eso/revision` tiene el
    contenido nuevo. Al terminar, el test borra `e2_test` y `/e2_test` (comprobado).
- **Sobre los datos reales**: después de las corridas de abajo se repitió el ETL **sin
  limpiar** (`--etiqueta idempotencia_sin_limpiar`) y dio **0 insertados, 1.861 omitidos por
  duplicado idéntico y 0 a revisión**. Tardó 43,9 s de ETL (solo lectura y SHA-256, nada se
  sube) y `conteos.py` quedó igual (1.861 / 1.861, revisión vacía).

### Corridas del ETL completo con el código final (R1/R6)

Como cambió la etapa de carga, se repitió `N=3 PAUSA=60 PREFIJO=completo_v2 ./medir_etl.sh`
(log: `salidas/medir_etl_3corridas_v2.log`). Las mismas condiciones que antes se comprobaron
antes de empezar y quedaron registradas en cada JSON: enchufado (81–82 %), "Máximo
rendimiento" (`condiciones_validas = true`) y 0,0 MB de ZIP en la caché de WSL2 antes de cada
corrida. Resumen: `python src/resumen_etl.py` → **`informe/etl_tiempos.csv`** (la versión
previa quedó en `informe/etl_tiempos_v1_previa.csv`).

| Corrida | Caché | ETL (job Spark) | Total medido | MB/s | FITS/s | Arranque Spark | Insertados / omitidos / revisión | extraer / HDFS / MongoDB (% del tiempo de workers) | Standby Windows |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **fría** | 75,69 s | 81,88 s | 195,7 | 24,6 | 4,90 s | 1.861 / 0 / 0 | 51,8 / 45,5 / 0,7 | 3.050 MB |
| 2 | tibia | 76,09 s | 82,34 s | 194,7 | 24,5 | 4,91 s | 1.861 / 0 / 0 | 52,7 / 44,3 / 1,0 | 2.777 MB |
| 3 | tibia | 75,67 s | 81,43 s | 195,8 | 24,6 | 4,48 s | 1.861 / 0 / 0 | 52,2 / 45,0 / 0,7 | 2.634 MB |
| **Mediana** | | **75,69 s** | **81,88 s** | **195,7** | **24,6** | | | | |

- Rango del ETL: 75,67–76,09 s (0,42 s, **0,6 %** de la mediana), mucho menos que en la
  versión previa (9,8 %). De nuevo, la corrida fría no fue la más lenta.
- Frente a la versión previa (mediana 77,91 s), el ETL no se hizo más lento. La etapa de
  MongoDB subió de 1,4–1,9 s a 6,9–9,6 s sumados en los workers, porque ahora se usa un
  `insert_one` por documento (el reclamo de R1) en vez de lotes de 100. Aun así es < 1 % del
  tiempo de los workers.
- Paralelismo, igual que antes: 42 particiones en el stage 0 y 14 workers de Python distintos
  del driver en las 3 corridas.

Estado al terminar (tras la corrida 3 y la repetición sin limpiar):
`python src/conteos.py --esperados 1861` → **OK**.
- MongoDB: 1.861 documentos (CALIB 1.841 · SCIENCE 18 · ACQUISITION 2), igual por ZIP que
  antes; `eso.revision` vacía.
- HDFS: 1.861 archivos (14,81 GB, replicación 1) en `/eso/xshooter`; `/eso/revision` vacía.
- Cruce: 0 faltantes, 0 sobrantes, 0 tamaños distintos; SHA-256 10/10.
- Prueba E: OK (18/18).

---

## Fase 2 — Tokenizador (2026-11-11)

### Implementación (`src/tokenizer.py`)

- `tokenizar(valor, llave=None)` y `tokenizar_header(header)`, con una función por regla
  (`regla1_llave` … `regla5_normalizar`, `es_identificador_hardware`), según el contrato de
  `tests/test_tokenizer.py`. **Los 66 tests pasan.**
- La regla 1 actúa sobre la llave, las reglas 2–4 sobre el valor y la regla 5 sobre ambos.
  Con estos datos da lo mismo que aplicar las reglas 2–4 a "llave + valor" unidos: ninguna de
  las 681 llaves cambiaría con ellas, y hay 0 pares llave-valor con tokens distintos entre
  ambas formas. Las palabras `ESO`/`DET`/`INS` solo aparecen al comienzo de las llaves, así que
  "palabras iniciales" no es ambiguo.
- Los valores tipados pasan a texto con `str()`: `True`, `5.0`, `1.8e-05`, la misma
  representación que usa pandas al escribir el CSV.
- `clasificar_fragmento_guion` devuelve el motivo por el que un fragmento con guion es o no
  identificador de hardware, en el orden de prioridad del prototipo: `fecha`, `cientifica`,
  `segmento no alfanumerico`, `sin letra`, `sin digito` y `HW`.

### Corpus desde MongoDB (`src/corpus.py`)

El corpus se lee de `eso.xshooter`, campo `header` ("con los datos dentro de su sistema"), y
no de `headers.csv`. Los documentos se ordenan por `_id` (ARCFILE): la fila *i* de las
matrices siempre es el mismo archivo. Hay dos modos de campos:

- `texto` (**por defecto**): solo los pares cuyo valor es `str` (enunciado 3.3, "los campos de
  texto del encabezado").
- `todos`: todos los pares, como el prototipo.

`python src/fase2_tokens.py` → `informe/modos_campos.csv` y `informe/df_tokens_consultas.csv`
(con columna `modo`).

| Modo | Vocabulario | Tokens por documento (mín / mediana / máx) | Tokens distintos por documento (mín / mediana / máx) | Tokens totales |
|---|---|---|---|---|
| `texto` | **2.497** | 519 / 581 / 778 | 234 / 254 / 386 | 1.135.986 |
| `todos` | **14.746** | 1.151 / 1.274 / 2.175 | 397 / 439 / 796 | 2.645.142 |

Tokens de las consultas (igual en **ambos** modos; N = 1.861):

| Consulta | Relevantes | Token | En vocabulario | df global | Relevantes con el token | IDF suavizado | IDF clásico |
|---|---|---|---|---|---|---|---|
| A `flat sky` | 100 | flat | sí | 628 | 100 | 2,085275 | 1,086329 |
| | | sky | sí | 100 | 100 | 3,914286 | 2,923699 |
| B `filt b` | 10 | filt | **no** | 0 | 0 | 8,529406 | — |
| | | b | sí | 10 | 10 | 6,131511 | 5,226284 |
| C `exp type normal` | 1.232 | exp | sí | 1.861 | 1.232 | 1,0 | 0,0 |
| | | type | sí | 1.861 | 1.232 | 1,0 | 0,0 |
| | | normal | sí | 1.861 | 1.232 | 1,0 | 0,0 |
| D `ins opti 1.6x11` | 58 | ins | **no** | 0 | 0 | 8,529406 | — |
| | | opti | **no** | 0 | 0 | 8,529406 | — |
| | | 1_6x11 | sí | 58 | 58 | 4,451869 | 3,468426 |
| E (solo numérica) | 18 | — | | | | | |

Qué se pierde en el modo `texto` (todo su vocabulario está contenido en el de `todos`): 12.249
tokens. De ellos, **11.888 (97,1 %) son solo dígitos** (valores de medición, contadores,
identificadores numéricos); 258 vienen de llaves cuyo valor no es texto (p. ej. `airm`, `alt`,
`az`, `binx`) y 103 son restos de notación científica (`01e`, `02e`, …).

**Recomendación: modo `texto`** (queda por defecto; aprobado por el usuario el 2026-11-11), por
cuatro razones:

1. **No rompe ninguna consulta**: los 7 tokens de A–D que están en el vocabulario tienen el
   mismo df y la misma cobertura de relevantes que en `todos`, y los 3 que faltan (`filt`,
   `ins`, `opti`) faltan en ambos modos. E es numérica y la resuelve MongoDB.
2. Vocabulario **6 veces menor** (2.497 frente a 14.746) y la mitad de tokens por documento. Lo
   que se pierde es casi todo números: buscarlos como texto no tiene sentido, porque los
   filtros numéricos los resuelve MongoDB con índices.
3. Coincide con el enunciado 3.3 ("campos de texto").
4. La matriz de LSI pasa de 14.746 × 1.861 a 2.497 × 1.861, con el mismo efecto en el costo
   de la SVD y en el tamaño de U_k.

Costo: una consulta textual que nombre una llave numérica (p. ej. "airm") ya no encuentra
nada. Lo aceptable es buscar esos campos con filtros estructurados.

### Comparación con el prototipo

Los archivos del prototipo quedaron en `informe/prototipo/`.

- **`df_tokens_consultas.csv`: 0 diferencias** en `en_vocabulario`, `df_global`,
  `relevantes_con_token` y `n_relevantes`, tanto en modo `todos` como en `texto`.
- **Vocabulario del modo `todos`: 14.746**, igual al del prototipo. Como control se aplicó el
  tokenizador real a `headers.csv` (la fuente del prototipo): mismo vocabulario de 14.746
  (0 tokens de diferencia con MongoDB) y 0 diferencias en df
  (`informe/df_tokens_consultas_control_csv.csv`).
- Diferencia de fuente que **no** cambia el vocabulario: en 54.865 celdas de 62 llaves enteras
  con valores faltantes, el CSV tiene `16.0` (pandas convierte la columna a float) y MongoDB
  tiene el entero `16`. El prototipo generaba además el token `0`, que existe igual por otros
  valores. Solo puede cambiar la frecuencia de `0` en el modo `todos`; el modo `texto` no
  incluye números.
- **`llaves_con_guion_regla3.csv`: 521 → 523 filas (28 → 30 llaves).** Las 521 filas del
  prototipo están todas, con el mismo `n_archivos`, la misma clasificación y los mismos tokens.
  Las 2 nuevas son `CTYPE1 = 'RA---TAN'` y `CTYPE2 = 'DEC--TAN'`. El prototipo solo listaba
  fragmentos con un guion *entre dos alfanuméricos*, y estos tienen guiones seguidos. Se
  clasifican como `segmento no alfanumerico` (la regla 3 no los cambia; tokens `ctype1 ra tan`).
  El archivo tiene ahora una fila por (llave, valor, fragmento), como el prototipo, y dos
  columnas nuevas: `tipo_valor` y `en_modo_texto` (solo 50 de las 523 filas son texto; 473
  son números en notación científica).

---

## Fase 3 — TF-IDF y LSI (2026-11-11)

### TF-IDF manual (`src/tfidf.py`)

- Vocabulario en orden alfabético; df = número de documentos que contienen el término.
- IDF suavizado `ln((1+N)/(1+df)) + 1` por defecto; el clásico `ln(N/df)` es configurable.
- TF = conteo crudo; peso = tf · idf; cada documento se normaliza con su norma L2.
- Matriz `scipy.sparse.csr_matrix` de documentos × términos, armada a mano (indptr, indices,
  data). scipy solo almacena; ningún cálculo usa sklearn.
- La consulta se tokeniza igual y se vectoriza con el mismo vocabulario e IDF. Los tokens fuera
  del vocabulario se informan y se ignoran; si el vector queda con norma 0, se devuelve un
  resultado vacío con aviso.
- Índice en modo `texto`: N = 1.861, |V| = 2.497, 513.883 entradas no nulas (densidad 11,06 %).
  Lectura de MongoDB y tokenización 1,1 s; TF-IDF 0,4 s.

### LSI (`src/lsi.py`)

- `A` = TF-IDF términos × documentos (2.497 × 1.861), densa. SVD con
  `numpy.linalg.svd(A, full_matrices=False)`: completa, porque para elegir k hacen falta todos
  los valores singulares. Tarda 17,3 s.
- A mano: truncamiento `U_k = U[:, :k]`, `Σ_k = diag(σ_1..σ_k)`, `V_k = Vᵀ[:k]ᵀ`.
- **Misma transformación para documentos y consultas: `x_k = Σ_k⁻¹ U_kᵀ x`.** Para el documento
  *j* da exactamente la fila *j* de `V_k`, porque `U_kᵀ A = Σ_k V_kᵀ`. Se calcula con la
  fórmula y se comprueba: máx |docs_k − V_k| = 5,3e-15.
- Rango numérico de A: 1.777 de 1.861 (hay documentos repetidos). Con k = rango completo,
  máx |A − U Σ Vᵀ| = 1,5e-13.

### Elección de k

Primero se aplicó el criterio pedido, σ² acumulada / σ² total ≥ 90 %. Da **k = 2**; con k = 1
ya se supera el 80 %. Diagnóstico, con datos del espectro y sin usar ninguna consulta:

| Medida | Valor |
|---|---|
| σ₁..σ₅ | 38,64 · 15,97 · 4,34 · 3,89 · 3,36 (σ² total = 1.861 = N, porque cada fila tiene norma 1) |
| σ₁² / Σσ² | **0,802** |
| Energía del vector medio (‖media‖² · N / Σσ²) | **0,788** |
| Coseno medio entre documentos | **0,788** |

La matriz TF-IDF no está centrada. Todos los headers de X-shooter comparten cientos de tokens
y, con IDF suavizado, los que tienen df = N pesan 1. Por eso la primera dirección singular es
la **dirección media del corpus**: σ₁² (80,2 %) coincide con la energía del vector medio
(78,8 %). Con el criterio literal, el 90 % mide sobre todo "parecerse al header promedio", no
la variación entre documentos, y deja a LSI con una sola dimensión que discrimina.

**Criterio adoptado (`sin_primera`, objetivo; confirmado por el usuario el 2026-11-11): el menor k con
Σ_{2≤i≤k} σᵢ² / Σ_{i≥2} σᵢ² ≥ 90 %.** Es la misma regla del 90 %, aplicada a la energía que no
es la componente media. La primera componente se conserva en el modelo (k la cuenta). Resultado:
**k = 14**, que explica el 98,0 % de σ² total y el 90,0 % sin la primera. Esta decisión se tomó
**antes de ejecutar cualquier consulta**, solo con el espectro. **El usuario confirmó k = 14 con
el criterio `sin_primera`**, dejando constancia de que la sensibilidad a k (más abajo) **no se
usó para elegir k**. El criterio literal sigue disponible con `--criterio energia` (k = 2).

| Umbral | 50 % | 70 % | 80 % | 90 % | 95 % | 99 % |
|---|---|---|---|---|---|---|
| k (`energia`, literal) | 1 | 1 | 1 | 2 | 4 | 53 |
| k (`sin_primera`) | 2 | 3 | 5 | **14** | 54 | 1.278 |

Referencias, no usadas para elegir: la varianza centrada real (PCA) llega al 90 % con k = 12.
Con IDF clásico (los tokens con df = N pesan 0), σ₁² es solo el 20,4 % y el 90 % literal
necesita k = 536.

Gráfico: `informe/lsi_varianza_explicada.png`, con ambas curvas, el umbral y los dos k marcados
(eje x logarítmico). Datos: `informe/lsi_varianza.csv` (k, σ, σ², acumuladas).

### Similitud coseno (`src/similitud.py`)

- `cos(u, v) = u·v / (‖u‖‖v‖)`. Si cualquiera de los dos vectores tiene norma 0, la similitud es
  0 y se informa; una consulta de norma 0 devuelve un resultado vacío con aviso.
- Búsqueda **exhaustiva** top-K, que será la línea base del recall relativo. Sirve igual para
  TF-IDF (CSR) y LSI (denso) y admite el conjunto de candidatos de un filtro de MongoDB.
- **Empates**: se ordena por puntaje descendente y, a igual puntaje, por posición en el corpus
  (= `_id` ascendente), así que el resultado es determinista. Los empates son frecuentes,
  porque hay muchos headers idénticos en los tokens que importan. Ejemplos con el índice
  actual: en B con TF-IDF solo hay 3 puntajes distintos entre 1.861 documentos (9 empatados en
  el máximo), y en D con TF-IDF, 16 (10 empatados). Esto importa para el benchmark: un top-K
  puede cortar un grupo empatado.

### Tests (`tests/test_tfidf_lsi.py`, 8 casos)

- Vocabulario, df e IDF (suavizado y clásico) contra un cálculo a mano en el test; matriz
  normalizada contra pesos calculados a mano.
- **Igualdad con `sklearn.feature_extraction.text.TfidfVectorizer`** (solo en el test;
  `analyzer` identidad, `smooth_idf=True`, `sublinear_tf=False`, `norm='l2'`): mismo
  vocabulario, mismo IDF y matriz con diferencia máxima < 1e-12.
- Consulta con tokens fuera del vocabulario y con norma 0 (incluido el IDF clásico con df = N).
- LSI: con k = rango completo, `U Σ Vᵀ` = A (< 1e-12) y docs proyectados = `V_k`; un documento
  proyectado como consulta coincide con su fila de `docs_k`; elección de k con los dos
  criterios.
- Coseno: fórmula, fila de norma 0, consulta de norma 0 (aviso), empates y candidatos.

### Persistencia del índice (`src/indice.py`, `entrega2/indice/`)

`python src/construir_indice.py` escribe `vocabulario.json`, `doc_ids.json`, `df.npy`,
`idf.npy`, `tfidf.npz` (CSR), `lsi_U_k.npy` (2.497 × 14), `lsi_sigma_k.npy`,
`lsi_docs_k.npy` (1.861 × 14), `lsi_sigma.npy` (los 1.861 σ) y **`manifiesto.json`**. El
manifiesto guarda la fecha, la fuente, el modo de campos, N, |V|, el IDF, k, el criterio y su
umbral, la varianza en k, el diagnóstico del espectro, las verificaciones numéricas, el
**hash SHA-256 de los datos de entrada** (`_id` + header en el orden del corpus;
`c1c50b4f98d56273…`), el hash del tokenizador y el SHA-256 y tamaño de cada archivo. En total
son 1,1 MB. `cargar()` verifica cada SHA-256 contra el manifiesto antes de usar el índice.

**Por qué archivos y no MongoDB:**

- El índice vectorial es un artefacto **numérico que se usa entero**: la búsqueda exhaustiva
  multiplica la consulta por toda la matriz. `.npy`/`.npz` se cargan directo como arreglos de
  numpy/scipy, sin convertir documento por documento.
- MongoDB limita cada documento a 16 MB. `U_k` y la matriz TF-IDF son objetos de una pieza: en
  Mongo habría que partirlos o usar GridFS, sin ganar nada. Guardar los vectores dentro de cada
  documento obligaría a leer y convertir 1.861 documentos por consulta. MongoDB 8.0 Community
  tampoco tiene índice vectorial.
- El índice se **reconstruye** desde MongoDB, que sigue siendo la fuente de verdad. Los
  archivos son un derivado versionado: el manifiesto con el hash de entrada permite detectar
  que el índice quedó desactualizado respecto de los datos, y el SHA-256 de cada archivo
  detecta corrupción.
- En la búsqueda híbrida, MongoDB resuelve la parte estructurada (filtros con sus índices) y
  entrega los candidatos; los archivos resuelven la parte vectorial.

### Prueba preliminar (no es el benchmark)

`python src/prueba_preliminar.py` → `informe/prueba_preliminar_top5.csv` / `.md` y
`informe/sensibilidad_k.csv`. Usa el índice persistido (modo `texto`, k = 14) y búsqueda
exhaustiva. La consulta A es **híbrida**: MongoDB filtra DATE-OBS = 2026-09-05 (índice
`date_obs`, 433 candidatos, 100 relevantes entre ellos) y el coseno se calcula solo sobre esos
candidatos.

Relevantes en el top 5 (criterios oficiales de la Fase 0):

| Consulta | Tokens usados (fuera del vocabulario) | TF-IDF | LSI (k = 14) | Qué devuelve LSI cuando falla |
|---|---|---|---|---|
| A `flat sky` + día 05 | flat, sky | **5/5** | **5/5** | — |
| B `filt b` | b (filt) | **5/5** | **0/5** | FLAT,SKY con filtro `i_prime` (los vecinos de los flats B en el espacio latente) |
| C `exp type normal` | exp, type, normal | **5/5** | **5/5** | — |
| D `ins opti 1.6x11` | 1_6x11 (ins, opti) | **5/5** | **1/5** | LAMP,WAVE con otras rendijas (0.8x11, 1.0x11, 0.5x11, 1.3x11) |

Lectura preliminar: TF-IDF acierta los 4 top-5 porque los tokens discriminantes (`sky`, `b`,
`1_6x11`) son exactos. LSI con k = 14 "suaviza" los tokens raros (`b` tiene df = 10) hacia los
documentos parecidos: recupera la clase correcta (flats de cielo, lámparas de calibración) pero
no el valor exacto. En C, los tres tokens tienen df = N (IDF = 1): el top 5 sale de la
frecuencia de los tokens, es decir, de la polisemia esperada.

Sensibilidad a k (calculada **después** de fijar k = 14; no lo modifica):

| Consulta | TF-IDF (P@5 / P@10 / R-prec) | LSI k = 2 | k = 5 | **k = 14** | k = 54 |
|---|---|---|---|---|---|
| A | 1,00 / 1,00 / 1,000 | 0,00 / 0,00 / 0,000 | 1,00 / 1,00 / 1,000 | 1,00 / 1,00 / 1,000 | 1,00 / 1,00 / 1,000 |
| B | 1,00 / 1,00 / 1,000 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| C | 1,00 / 1,00 / 0,820 | 0,00 / 0,00 / 0,820 | 1,00 / 1,00 / 0,572 | 1,00 / 1,00 / 0,674 | 1,00 / 1,00 / 0,757 |
| D | 1,00 / 1,00 / 1,000 | 0 / 0 / 0 | 1,00 / 0,50 / 0,172 | 0,20 / 0,10 / 0,190 | 1,00 / 1,00 / 0,828 |

El criterio literal (k = 2) deja LSI inservible en A, B y D, lo que confirma el diagnóstico
del espectro. Con más dimensiones LSI mejora en D y en la R-precisión de C, pero B no se
recupera con ningún k ≤ 54. **Estas cifras no se usan para cambiar k**: hacerlo sería ajustar
sobre el conjunto de prueba.

---

## Fase 4 — Optimización: protocolo fijado ANTES del barrido (2026-11-11)

Esta sección se escribió **antes de ejecutar ningún barrido**. Los hiperparámetros se eligen
sin las consultas A–E.

- **Consultas de validación**: 200 documentos del corpus elegidos con
  `numpy.random.default_rng(20261111).choice(1861, 200, replace=False)`
  (`src/validacion.py`). Cada uno se usa como consulta con su propio vector: la fila TF-IDF en
  el espacio TF-IDF y su `Σ_k⁻¹ U_kᵀ d` (= fila de `docs_k`) en el espacio LSI. **El
  documento consulta se excluye de los resultados** (dejar uno fuera), tanto en la línea base
  como en la búsqueda optimizada; si no, siempre se encontraría a sí mismo. Sus duplicados
  idénticos sí cuentan, porque son otros documentos.
- **Línea base**: búsqueda exhaustiva por coseno en el **mismo espacio** (TF-IDF contra
  TF-IDF, LSI contra LSI), top-10, desempate por `_id`.
- **Costo** = fracción del corpus examinada = documentos sobre los que se calcula el coseno
  exacto / (N − 1). Aparte se informan las comparaciones extra: centroides en K-Means, y
  hiperplanos y vecinos de multi-probe en LSH.
- **Recall relativo top-10**, de dos formas:
  - *estricto*: |top-10 optimizado ∩ top-10 exhaustivo| / 10, con desempate determinista por
    `_id` en ambos;
  - *con tolerancia a empates*: un resultado optimizado cuenta como acierto si su coseno exacto
    es ≥ el coseno del 10.º resultado de la línea base (mismo modelo; tolerancia 1e-12).
- **Decisión sobre empates, tomada antes de medir**: la tabla oficial usa el **recall con
  tolerancia a empates**; el estricto se informa al lado. Motivo: hay grupos grandes de
  puntajes idénticos (headers repetidos; en B con TF-IDF solo hay 3 puntajes distintos entre
  1.861). Dentro de un grupo empatado, el corte del top-10 depende solo del desempate
  arbitrario por `_id`. Un método aproximado que devuelve *otro* documento del mismo grupo
  entrega un resultado igual de bueno, y el estricto lo castigaría por el orden alfabético del
  ARCFILE, no por la calidad.
- **Criterio de elección** (por método y por espacio; 4 elecciones): **el menor costo medio con
  recall medio con tolerancia ≥ 0,90**. Desempate: mayor recall con tolerancia; luego menos
  memoria (menos clústeres, o menor L · b). Si ninguna configuración llega a 0,90, se elige
  la de mayor recall con tolerancia y se informa.
  - K-Means: n_probe = 1 fijo (lo que pide el enunciado) y barrido de
    c ∈ {4, 8, 16, 32, 64}. Con n_probe = 2 se informa como referencia, sin usarlo para elegir.
    La inercia y la silueta se informan como diagnóstico y no entran en el criterio.
  - LSH: barrido de b ∈ {4, 8, 12, 16} × L ∈ {1, 4, 8, 16}, con multi-probe (Hamming 1 y 2) si
    hay menos de K = 10 candidatos.

## Fase 4 — Resultados de la optimización (2026-11-11)

Validación según el protocolo de arriba (200 documentos como consulta, dejar uno fuera, top-10).
Código: `src/validacion.py`, `src/espacios.py`, `src/kmeans_indice.py` y `src/lsh_indice.py`.
Datos: `informe/validacion_kmeans.csv` y `informe/validacion_lsh.csv`. Curvas:
`informe/validacion_kmeans.png` y `informe/validacion_lsh.png` (costo en escala log vs. recall
con tolerancia, umbral 0,90 y punto elegido marcado).

### K-Means (`src/kmeans_indice.py`)

- Centroides: **solo** `sklearn.cluster.KMeans(n_clusters=c, random_state=20261111,
  n_init=10)` (Lloyd). `n_init = 10` corre 10 inicializaciones k-means++ y se queda con la de
  menor inercia, lo que reduce la dependencia de la semilla.
- Espacio TF-IDF: filas con norma 1. Espacio LSI (k = 14): `docs_k` **normalizados con L2
  antes de agrupar**. Para vectores unitarios ‖a − b‖² = 2 − 2·cos(a, b), así que K-Means
  euclídeo agrupa según el coseno, que es la similitud de la búsqueda. Sin normalizar, las
  filas de `docs_k` (= V_k) tienen normas distintas y K-Means agruparía también por norma, que
  la búsqueda ignora.
- A mano: asignación documento → clúster por coseno máximo, la misma regla que para las
  consultas, así que un documento usado como consulta cae en su clúster. Coincide con
  `labels_` de sklearn en el 98,5–100 % de los documentos. También el mapa inverso
  clúster → documentos (ordenamiento por conteo, `indptr` + `docs`), los `n_probe` centroides
  más cercanos (1 por defecto), el coseno exacto solo dentro de esos clústeres, la inercia y la
  silueta con distancia coseno (verificada contra `sklearn.metrics` solo en el test).

| Espacio | c | Recall con tolerancia | Recall estricto | Costo | Tamaños mín / mediana / máx | Silueta (coseno) | Inercia |
|---|---|---|---|---|---|---|---|
| TF-IDF | 4 | 1,000 | 0,998 | 0,378 | 195 / 324 / 1.019 | 0,541 | 85,7 |
| | 8 | 0,997 | 0,968 | 0,153 | 65 / 246 / 407 | 0,516 | 61,7 |
| | 16 | 0,990 | 0,969 | 0,085 | 35 / 116 / 318 | 0,450 | 42,9 |
| | 32 | 0,981 | 0,951 | 0,046 | 12 / 52 / 196 | 0,413 | 31,1 |
| | **64** | **0,946** | 0,917 | **0,027** | 2 / 20 / 100 | 0,345 | 24,4 |
| LSI | 4 | 1,000 | 1,000 | 0,361 | 100 / 412 / 937 | 0,305 | 1.232,7 |
| | 8 | 0,993 | 0,993 | 0,154 | 100 / 204 / 407 | 0,538 | 768,7 |
| | 16 | 0,998 | 0,997 | 0,067 | 68 / 118 / 208 | 0,723 | 301,6 |
| | 32 | 0,985 | 0,983 | 0,043 | 16 / 56 / 178 | 0,838 | 96,0 |
| | **64** | **0,972** | 0,970 | **0,030** | 2 / 18 / 100 | 0,914 | 11,2 |

(n_probe = 1. Con n_probe = 2, de referencia, el recall sube a 0,984–1,000 y el costo se
duplica aproximadamente.)

- **Elegido: c = 64 en ambos espacios** (las 5 configuraciones cumplen ≥ 0,90; gana el menor
  costo). Como 64 es el borde de la grilla, se comprobó c = 128 y 256 con el mismo criterio:
  c = 128 da 0,893 (TF-IDF) y 0,894 (LSI), bajo el umbral, así que **c = 64 es el límite real**
  y no un efecto de la grilla.
- **Clústeres degenerados**: con c = 64 no hay clústeres vacíos ni de un solo documento (el
  menor tiene 2). Pero 9 (TF-IDF) y 12 (LSI) de las 200 consultas caen en clústeres de menos de
  11 documentos y obtienen menos de 10 resultados: es el costo de n_probe = 1. Con c = 128
  aparecen clústeres de un documento (8 en LSI).
- La silueta baja con c en TF-IDF (0,54 → 0,35) y sube en LSI (0,31 → 0,91). En el espacio de
  14 dimensiones, los grupos de headers casi iguales quedan muy compactos (ver LSH).

### LSH con hiperplanos aleatorios (`src/lsh_indice.py`)

- Hiperplanos: **solo** `numpy.random.default_rng(20261111).normal(0, 1, (L, b, d))`.
- A mano: bit j = 1 si `H·x ≥ 0`; empaquetado `Σ bit_j · 2^j` (sin `packbits`); L tablas
  firma → documentos; unión de candidatos; multi-probe a Hamming 1 y luego 2 si hay menos de
  K = 10 candidatos (el filtro y la exclusión cuentan); re-ranking por coseno exacto.

Recall con tolerancia / costo:

| TF-IDF | L = 1 | L = 4 | L = 8 | L = 16 |
|---|---|---|---|---|
| b = 4 | 0,852 / 0,358 | 1,000 / 0,654 | 1,000 / 0,864 | 1,000 / 0,996 |
| b = 8 | 0,684 / 0,138 | 0,998 / 0,619 | 1,000 / 0,727 | 1,000 / 0,743 |
| b = 12 | 0,585 / 0,092 | 0,991 / 0,396 | 0,999 / 0,531 | 1,000 / 0,635 |
| b = 16 | 0,571 / 0,070 | **0,979 / 0,335** | 0,999 / 0,509 | 1,000 / 0,604 |

| LSI | L = 1 | L = 4 | L = 8 | L = 16 |
|---|---|---|---|---|
| b = 4 | 0,962 / 0,086 | 0,997 / 0,317 | 1,000 / 0,488 | 1,000 / 0,680 |
| b = 8 | 0,945 / 0,038 | 0,990 / 0,085 | 0,995 / 0,109 | 1,000 / 0,157 |
| b = 12 | 0,951 / 0,030 | 0,986 / 0,049 | 0,990 / 0,059 | 0,992 / 0,083 |
| b = 16 | **0,953 / 0,026** | 0,978 / 0,037 | 0,983 / 0,039 | 0,985 / 0,045 |

- **Elegidos: TF-IDF b = 16, L = 4** (cumplen 12 de 16; recall estricto 0,912) y **LSI b = 16,
  L = 1** (cumplen 16 de 16; estricto 0,926; Hamming 1 en el 18 % de las consultas, Hamming 2
  en el 4 %).
- LSI b = 16 está en el borde de la grilla. Fuera de ella, b = 20 y 24 (L = 1) también cumplen,
  con un costo apenas menor (0,025 y 0,023 frente a 0,026), algo menos de recall (0,945–0,946)
  y más consultas con menos de 10 candidatos (9–10). **Se mantiene la grilla del protocolo**:
  la ganancia es marginal y ampliar la grilla después de ver los resultados sería cambiar las
  reglas.
- **Buckets** (todas las tablas juntas):
  - TF-IDF (b = 16, L = 4): 64 buckets por tabla, tamaño 1 / 5 / 599 (mín / mediana / máx).
    **El mayor tiene el 32 % del corpus.** Los vectores TF-IDF son todos no negativos y muy
    parecidos (coseno medio 0,79), así que los hiperplanos por el origen los separan mal; por
    eso el costo es alto.
  - LSI (b = 16, L = 1): 107 buckets, tamaño 1 / 6 / 100 (el mayor tiene el 5,4 % del corpus y
    28 vectores distintos).
- **Documentos idénticos**:
  - En TF-IDF **ningún** par de documentos es idéntico bit a bit. 1.681 headers tienen un token
    único (df = 1) que viene del nombre de archivo en ORIGFILE
    (`XSHOOTER_GEN_FLAT_UVB_251_0001.fits` → `xshooter_gen_flat_uvb_251_0001`); en los otros
    180, ORIGFILE lleva una fecha que la regla 4 elimina.
  - Sin los términos de df = 1 hay **268 grupos de casi idénticos (1.562 documentos, 7.702
    pares)**. En TF-IDF, el token único cambia la firma: los pares casi idénticos comparten
    bucket en una tabla dada solo el 48,8 % de las veces, y en al menos una de las 4 tablas el
    93,4 %.
  - En LSI (k = 14) ese token no pesa: **327 grupos de documentos idénticos bit a bit (1.612
    documentos, el mayor de 32)** colisionan siempre (100 %), y los casi idénticos también.

### Persistencia (D)

En `entrega2/indice/` (23 archivos, 3,9 MB):
- K-Means: `kmeans_{tfidf,lsi}_{centroides,asignacion,inverso_indptr,inverso_docs}.npy`.
- LSH: `lsh_{tfidf,lsi}_{hiperplanos,firmas}.npy` y `lsh_{tfidf,lsi}_buckets.npz` (por tabla:
  firmas ordenadas + `indptr` + documentos).

`manifiesto.json` tiene ahora las secciones `kmeans` y `lsh`: parámetros elegidos, semillas,
`n_init`, criterio, métricas de validación y el **SHA-256 de `tfidf.npz` y `lsi_docs_k.npy`**
de los que derivan, para detectar estructuras viejas si se reconstruye el índice. También tiene
el SHA-256 de todos los archivos, que `cargar()` verifica.

Tests: `tests/test_optimizacion.py`, 14 casos. Cubren la muestra fija, los dos recall con un
ejemplo de empate, el desempate, el evaluador (exhaustivo = recall 1 y costo 1), el criterio,
el mapa inverso (con un clúster vacío), la asignación por coseno, que la consulta caiga en su
clúster, la silueta frente a sklearn, el empaquetado de bits, que los idénticos colisionen, el
multi-probe a Hamming 1 y 2 con filtro y exclusión, y la persistencia de K-Means y LSH.

---

## Fase 5 — CLI de búsqueda (2026-11-11)

`src/buscador.py` (motor) y `src/buscar.py` (CLI). Argumentos: `--texto`,
`--modelo {tfidf,lsi}`, `--optim {ninguna,kmeans,lsh}`, `--top`, `--n-probe` (1 por defecto),
`--fecha-desde/--fecha-hasta` (`AAAA-MM-DD` = día completo, o ISO con hora; UTC),
`--ra-min/--ra-max`, `--dec-min/--dec-max`, `--exptime-min/--exptime-max`, `--categoria` y
`--json`.

Flujo híbrido:
1. Si hay filtros, MongoDB devuelve los `_id` candidatos con sus índices (`date_obs`,
   `ra_dec`, `dpr_catg_type`). `exptime` no tiene índice en la Tabla 9: MongoDB recorre la
   colección.
2. Si hay texto, se tokeniza y vectoriza (mismo vocabulario e IDF; en LSI, `Σ_k⁻¹ U_kᵀ q`) y se
   calcula el coseno exacto solo sobre los candidatos. Con K-Means se usa el clúster sondeado ∩
   el filtro; con LSH, los buckets (multi-probe si hay menos de `top`) ∩ el filtro. **Si la
   intersección queda vacía, se informa y no se rellena.**
3. Salida: `storage.hdfs_path` (leído de MongoDB) con el coseno, los tokens fuera del
   vocabulario y los avisos. Solo numérica (consulta E): todos los que pasan el filtro,
   ordenados por `_id` y sin puntaje.

**No depende de HDFS**: `buscador.py` no importa `hdfs_webhdfs`, `pyspark` ni `requests`, y no
abre conexiones a HDFS. Se verificó de dos formas:
- `tests/test_buscar.py::test_no_depende_de_hdfs` corre la CLI en un subproceso con un
  `sitecustomize` que hace fallar la importación de `hdfs_webhdfs`, `pyspark` y `requests` (el
  test comprueba que el bloqueo funciona), rechaza conexiones a los puertos 9870, 9864, 9866,
  9867 y 8020, y apunta WebHDFS a un puerto cerrado. Los tres modos responden con rutas.
- **En vivo**: `docker compose -f infra/docker-compose.yml stop namenode datanode`, con HDFS
  sin responder; la CLI respondió en los tres modos y `tests/test_buscar.py` pasó completo
  (17/17). Después se volvió a levantar HDFS (`start`), que quedó sano.

Tests de la CLI (`tests/test_buscar.py`, 17 casos, marcador `integracion`):
- solo semántica (`filt b`) en las 5 configuraciones con resultados;
- solo numérica: Prueba E (18 rutas ordenadas por `_id`, sin puntaje y con RA/DEC dentro de la
  caja) y fecha + categoría + exptime contra una consulta directa a MongoDB;
- combinada: consulta A en las 5 configuraciones, todas dentro del día 05;
- intersección vacía informada (K-Means y LSH con `--categoria SCIENCE`);
- consulta sin términos del vocabulario y sin argumentos (código 2);
- independencia de HDFS.

**Limitación conocida (con los hiperparámetros de la primera validación; superada en la Fase 4b,
ver más abajo): LSH en el espacio TF-IDF con consultas cortas.** Para A–D no encuentra
candidatos, ni siquiera con multi-probe a Hamming 2. Una consulta de 1–3 tokens tiene un coseno
máximo de 0,05–0,16 con cualquier documento (los documentos tienen ~250 tokens): en la mejor
tabla, la firma más cercana a la de la consulta está a 3–4 bits. En LSI la proyección acerca la
consulta (coseno máximo 0,66–0,77; Hamming mínimo 1–2) y sí encuentra candidatos. El buscador lo
informa y no rellena (fijado en `test_lsh_tfidf_consulta_corta_limitacion_conocida`). La
validación con documentos como consulta no lo detectó, porque esas consultas tienen vecinos de
coseno cercano a 1.

---

## Prueba preliminar de las 6 configuraciones (no es el benchmark)

`python src/prueba_preliminar_optim.py` usa el mismo `Buscador` que la CLI, con top-10 →
`informe/prueba_preliminar_optim_top5.csv` / `.md` (top-5 con metadatos y marca de relevancia),
`informe/prueba_preliminar_optim_recall.csv` y `informe/memoria_busqueda.json`. La consulta A
lleva el filtro del día 2026-09-05 (433 candidatos) y E es solo numérica.

Relevantes en el top-5 según los criterios oficiales (entre paréntesis, cuántos resultados hubo
cuando fueron menos de 10):

| Configuración | A | B | C | D | E |
|---|---|---|---|---|---|
| TF-IDF exhaustiva | 5/5 | 5/5 | 5/5 | 5/5 | 18 de 18 |
| TF-IDF + K-Means (c = 64) | 5/5 | 5/5 | 5/5 | 5/5 (6) | 18 de 18 |
| TF-IDF + LSH (b = 16, L = 4) | vacío ⚠ | vacío ⚠ | vacío ⚠ | vacío ⚠ | 18 de 18 |
| LSI exhaustiva (k = 14) | 5/5 | 0/5 | 5/5 | 1/5 | 18 de 18 |
| LSI + K-Means (c = 64) | 5/5 | 0/5 | 2/2 (2) | 1/5 (8) | 18 de 18 |
| LSI + LSH (b = 16, L = 1) | 5/5 | 0/5 | 5/5 (5) | 1/5 | 18 de 18 |

⚠ = intersección vacía, informada (ver la limitación de arriba). E es solo numérica: las 6
configuraciones devuelven **las mismas 18 rutas** (resuelve MongoDB).

Recall relativo top-10 frente a la búsqueda exhaustiva del mismo modelo (con tolerancia /
estricto):

| Configuración | A | B | C | D |
|---|---|---|---|---|
| TF-IDF + K-Means | 1,0 / 1,0 | 1,0 / 1,0 | 0,6 / 0,5 | 0,0 / 0,0 |
| TF-IDF + LSH | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| LSI + K-Means | 1,0 / 1,0 | 1,0 / 1,0 | 0,2 / 0,2 | 0,8 / 0,8 |
| LSI + LSH | 1,0 / 1,0 | 1,0 / 1,0 | 0,5 / 0,5 | 0,0 / 0,0 |

Lectura:
- **Recall relativo y relevancia miden cosas distintas.** TF-IDF + K-Means en D tiene recall 0
  pero 5/5 relevantes: el clúster sondeado tiene 6 documentos, todos con `1.6x11`, aunque con
  coseno menor que los 10 primeros de la búsqueda exhaustiva, que están empatados en 0,0500.
- **Con consultas cortas, los clústeres y buckets sondeados son pequeños** (K-Means LSI en C: 2
  documentos; LSH LSI en C: 5 candidatos tras multi-probe), y el recall baja respecto de la
  validación. Las 200 consultas de validación son documentos completos, que tienen muchos
  vecinos casi iguales. **No representan bien a las consultas cortas.** No se corrigió nada
  mirando A–E.
- **Empates**: el 10.º resultado de la línea base está empatado con otros 10 documentos en D
  (TF-IDF) y en A (LSI), lo que confirma por qué la tabla oficial usa el recall con tolerancia.
  En esta prueba ambos recall coinciden salvo en TF-IDF + K-Means C (0,6 frente a 0,5).

**Memoria residente** del proceso de búsqueda (`/proc/self/status`; `informe/memoria_busqueda.json`):

| Momento | RSS | Pico (VmHWM) |
|---|---|---|
| Intérprete con las bibliotecas importadas | 52,5 MiB | 52,5 MiB |
| Con **todos** los índices cargados (TF-IDF, LSI, 2 K-Means, 2 LSH, cliente de MongoDB) | **109,4 MiB** | 211,8 MiB |
| Tras las 30 consultas | **111,8 MiB** | 211,8 MiB |

Carga de los índices: 0,26 s. El pico de la carga viene de las copias densas temporales de
TF-IDF. Estructuras en memoria: espacio TF-IDF denso normalizado 35,5 MiB, CSR 5,9 MiB, LSI
0,7 MiB, K-Means 1,3 MiB y LSH 1,4 MiB. Los headers que el script de prueba carga para marcar
la relevancia se leen **después** de medir.

---

## Fase 4b — Revisión del protocolo de validación (2026-11-11)

Narración en orden de lo ocurrido, de la validación original a la revisada.

### 1. Validación con documentos completos

El primer protocolo (sección "Fase 4 — protocolo fijado ANTES del barrido") usó como
consultas 200 documentos del corpus, cada uno con su vector completo y excluido de sus
resultados. Con ese conjunto, las 4 configuraciones elegidas superaron el umbral con holgura
(recall con tolerancia de 0,946 a 0,979).

### 2. Limitación detectada en la prueba preliminar

En la prueba preliminar con A–E ("Prueba preliminar de las 6 configuraciones"):
- **TF-IDF + LSH (b = 16, L = 4) devolvió 0 candidatos en A, B, C y D**, incluso con
  multi-probe a Hamming 2.
- K-Means y LSH en LSI sondearon clústeres y buckets mínimos para C y D (2 a 16 documentos),
  con recall relativo de 0,0 a 0,8.

### 3. Por qué ese conjunto no representaba el uso real

- Un documento usado como consulta tiene ~250 tokens y casi siempre vecinos casi idénticos
  (coseno cercano a 1), porque hay 268 grupos de headers casi iguales. Cualquier método que
  busque "en la vecindad" los encuentra.
- Una consulta de la CLI tiene 1–4 tokens. Su coseno máximo con cualquier documento es
  0,05–0,16 en TF-IDF: está lejos de todos. En LSH, su firma queda a 3–4 bits de la del
  documento más cercano.
- Los vectores TF-IDF son no negativos y muy parecidos entre sí (coseno medio 0,79). Los
  hiperplanos por el origen los separan mal, y la consulta corta cae en una región de firmas
  donde no hay documentos.
- Conclusión: el conjunto validaba bien la búsqueda de "documentos parecidos a un documento",
  pero no la de "documentos que contienen estos pocos términos", que es lo que hace la CLI.
  Corregirlo mirando A–E sería ajustar sobre el conjunto de prueba; por eso se define un
  conjunto nuevo, sin A–E.

### 4. Nuevo protocolo (fijado ANTES de medir; decisión del usuario, opción 1)

**Conjunto de consultas cortas** (`validacion.consultas_cortas`). Se usa un solo generador
`numpy.random.default_rng(20261112)`, con semilla distinta de la anterior (20261111), y para
cada intento se sortea, en este orden:
1. un documento al azar, `integers(0, N)`;
2. un par llave-valor **de tipo texto** de ese documento, `integers(0, n_pares)`, en el orden
   del header (los mismos campos que el modo `texto` del corpus);
3. una longitud `n = integers(1, 5)` (1 a 4).

La consulta son los primeros `n` tokens de `tokenizar(valor, llave)` (llave y valor ya
tokenizados), con los mismos tokens que vería el índice. Se **descarta y se reemplaza** (nuevo
intento con el mismo generador) si todos sus tokens tienen df = N (sin información) o si queda
vacía. Se informa cuántas se reemplazaron y cuántas consultas distintas hay. Se generan **200**
consultas.
- **No se excluye el documento de origen**: una consulta corta no es el documento.
- Vector de consulta: el mismo de la CLI. TF-IDF de los tokens con el vocabulario e IDF del
  índice, normalizado con L2; en LSI, `Σ_k⁻¹ U_kᵀ q` normalizado.
- **Línea base**: exhaustiva en el mismo espacio, top-10, desempate por `_id`.
- **Métricas**: las mismas dos de antes (recall relativo top-10 con tolerancia a empates, el
  oficial, y estricto) y el mismo costo. Costo = documentos rerankeados con coseno exacto / N,
  incluidos **todos** los candidatos que aporta el multi-probe.
- Si una consulta corta coincide con menos de 10 documentos, el 10.º de la línea base puede
  tener coseno 0. El recall con tolerancia cuenta entonces cualquier resultado con coseno ≥ 0.
  Es la misma regla y no se cambia.

**Selección oficial**: con el conjunto de **consultas cortas**, porque representa el uso real
de la CLI. El conjunto de **documentos completos** (el mismo de antes: semilla 20261111, dejar
uno fuera) se corre sobre la misma grilla y se informa como **validación secundaria**, sin
usarlo para elegir.

**Criterio** (el mismo): el menor costo medio con recall medio con tolerancia ≥ 0,90. Si nada
llega, la configuración de mayor recall con tolerancia, y se informa. Desempates en orden:
mayor recall con tolerancia; menos memoria (menor c en K-Means; menor L · b en LSH); en LSH,
menor radio de multi-probe; y luego sin centrado frente a centrado (lo más simple).

**Grilla** (fijada ahora; **no se amplía después de medir**: si el elegido cae en un borde, se
informa):
- K-Means: c ∈ {4, 8, 16, 32, 64, 128}; n_probe = 1 para elegir (n_probe = 2 solo como
  referencia). Semilla 20261111 y `n_init = 10`, como antes.
- LSH: b ∈ {2, 4, 8, 12, 16} × L ∈ {1, 4, 8, 16} × radio máximo de multi-probe ∈ {2, 3, 4} ×
  centrado ∈ {no, sí}; son 120 configuraciones por espacio. El multi-probe avanza por
  distancia de Hamming 1, 2, … hasta el radio (sin pasar de b) mientras haya menos de K = 10
  candidatos.
  - **Centrado = sí**: se resta el vector medio del corpus (media a mano de los vectores de
    documentos con norma 1 del espacio, `Σ x_i / N`) a documentos y consultas (consulta con
    norma 1) **antes de `H·x`**. Solo cambia las firmas; el reranking usa el coseno exacto del
    espacio original. Si el elegido usa centrado, el vector medio se guarda en el índice.
  - Los hiperplanos siguen saliendo solo de `numpy.random.default_rng(20261111).normal`.
- Las dos grillas se aplican a los dos espacios (TF-IDF y LSI).

**Si en algún espacio LSH no llega a 0,90** con ninguna configuración, se elige la de mayor
recall y se documenta la limitación (opción 3), explicada por los vectores TF-IDF no negativos
y las consultas cortas lejanas de todos los documentos.

**Después de elegir**: se repite la prueba preliminar de las 6 configuraciones × A–E (top-5
relevantes, recall relativo con tolerancia y estricto, memoria) y se compara con la anterior en
una tabla "antes / después".

Salidas previstas:
- curvas `informe/validacion_cortas_kmeans.png` e `informe/validacion_cortas_lsh.png`;
- datos `informe/validacion_v2_kmeans.csv` y `informe/validacion_v2_lsh.csv` (con columna
  `conjunto`: `cortas` / `documentos`);
- consultas generadas en `informe/consultas_cortas.csv`;
- los resultados de la primera validación (`informe/validacion_kmeans.csv` / `validacion_lsh.csv`
  y sus PNG) se conservan sin cambios.

### 5. Resultados con el nuevo protocolo (2026-11-11)

Ejecutados después de escribir el punto 4 (protocolo registrado a las 13:57 −03:00):
`python src/kmeans_indice.py` y `python src/lsh_indice.py` (log: `salidas/barrido_lsh_v2.log`).
Datos: `informe/validacion_v2_kmeans.csv`, `informe/validacion_v2_lsh.csv` e
`informe/consultas_cortas.csv`. Curvas: `informe/validacion_cortas_kmeans.png` e
`informe/validacion_cortas_lsh.png`.

**Consultas cortas generadas**: 200, de las cuales **142 son distintas** (algunas se repiten,
como `mode calib`). Largo medio 2,6 tokens (1: 35 · 2: 37 · 3: 100 · 4: 28). Se reemplazaron
**480** intentos, todos porque sus tokens tenían df = N (casi siempre llaves solas como
`dpr type` o `tel name`) y ninguno por quedar vacío. Ejemplos: `opti2 id pin`, `mode calib`,
`observer`, `read mode normal`, `irace`.

#### K-Means

Recall con tolerancia / estricto / costo, con n_probe = 1:

| c | TF-IDF, consultas cortas (oficial) | TF-IDF, documentos (secundario) | LSI, consultas cortas (oficial) | LSI, documentos (secundario) |
|---|---|---|---|---|
| 4 | 0,807 / 0,803 / 0,312 | 1,000 / 1,000 / 0,378 | 0,670 / 0,667 / 0,287 | 1,000 / 1,000 / 0,361 |
| 8 | 0,698 / 0,691 / 0,138 | 0,997 / 0,995 / 0,153 | 0,591 / 0,589 / 0,144 | 0,993 / 0,993 / 0,154 |
| 16 | 0,704 / 0,701 / 0,079 | 0,990 / 0,987 / 0,085 | 0,794 / 0,779 / 0,071 | 0,998 / 0,997 / 0,067 |
| **32** | **0,883 / 0,880 / 0,042** | 0,981 / 0,977 / 0,046 | **0,880 / 0,865 / 0,041** | 0,985 / 0,984 / 0,043 |
| 64 | 0,870 / 0,866 / 0,023 | 0,946 / 0,942 / 0,027 | 0,876 / 0,869 / 0,023 | 0,972 / 0,970 / 0,030 |
| 128 | 0,696 / 0,688 / 0,012 | 0,893 / 0,875 / 0,013 | 0,712 / 0,710 / 0,012 | 0,894 / 0,892 / 0,019 |

- **Con consultas cortas ningún c llega a 0,90 en ninguno de los dos espacios**: se elige la
  de mayor recall, **c = 32 en ambos** (TF-IDF 0,883; LSI 0,880), y queda documentada la
  limitación. No está en el borde de la grilla. Tamaños de los clústeres: TF-IDF 12 / 51,5 /
  196 y LSI 16 / 55,5 / 178, sin vacíos ni de un solo documento.
- Con documentos completos (secundario), la elección habría sido c = 64, como en la primera
  validación (mismas cifras: 0,946 y 0,972).
- El recall con consultas cortas no es monótono en c (c = 4 supera a c = 8 y c = 16). Una
  consulta corta cae en el centroide más parecido a sus pocos términos, que no siempre es el
  clúster donde están los documentos que la contienen.
- Referencia sin uso para elegir (el enunciado pide un clúster): con **n_probe = 2**, las
  consultas cortas sí llegan a 0,90 (TF-IDF c = 64: 0,940 con costo 0,039; LSI c = 64: 0,969
  con costo 0,039).

#### LSH

- Con consultas cortas, de las 120 configuraciones por espacio **solo 12 llegan a 0,90, todas
  con b = 2** (4 buckets por tabla) y L = 8 o 16. **Ninguna llega con costo < 0,5.**
- **Elegido en ambos espacios: b = 2, L = 8, radio 2, centrado.**
  - TF-IDF: recall 0,952 con tolerancia y 0,921 estricto, **costo 0,829**.
  - LSI: 0,914 / 0,914, **costo 0,871**.
  - En el borde de la grilla: b = 2 es el mínimo. El radio no influye: con buckets tan grandes
    el multi-probe nunca se activa, así que r = 2, 3 y 4 dan lo mismo y el desempate elige 2.
- **Lectura**: formalmente se cumple el criterio, pero **LSH con consultas cortas solo llega a
  0,90 rerankeando el 83–87 % del corpus**; casi no ahorra respecto de la búsqueda exhaustiva.
  Es la limitación de la opción 3 en la práctica, aunque la regla de "nadie llega a 0,90" no se
  activa. Se explica por los vectores TF-IDF no negativos y muy parecidos entre sí (coseno
  medio 0,79) y por consultas cortas lejanas de todos los documentos: para que la firma de la
  consulta coincida con la de sus vecinos verdaderos, las firmas tienen que ser tan gruesas que
  cada bucket agrupa a cientos de documentos.
- Con documentos completos (secundario), la elección habría sido otra: TF-IDF b = 16, L = 16,
  radio 2, centrado (0,948, costo 0,091); LSI b = 16, L = 1, radio 2, centrado (0,940, costo
  0,024). Los elegidos con consultas cortas dan recall 1,000 con documentos, a costo 0,75–0,85.
- Buckets de los elegidos: TF-IDF 63 / 396 / 1.124 y LSI 275 / 445 / 668 (mín / mediana /
  máx). Los casi idénticos comparten bucket en ≥ 1 tabla el 100 % de las veces (por tabla:
  TF-IDF 79,5 %, LSI 100 %).

**¿Ayudó el centrado?** Mejor recall con tolerancia alcanzable con costo ≤ x (sin centrar →
centrado):

| Conjunto | Espacio | ≤ 0,05 | ≤ 0,1 | ≤ 0,2 | ≤ 0,5 | Costo mínimo para llegar a 0,90 |
|---|---|---|---|---|---|---|
| Consultas cortas | TF-IDF | 0,221 → 0,162 | 0,246 → 0,247 | 0,320 → 0,255 | 0,604 → 0,587 | 0,909 → **0,829** |
| Consultas cortas | LSI | 0,417 → 0,589 | 0,585 → 0,728 | 0,723 → 0,728 | 0,828 → 0,768 | 0,919 → **0,871** |
| Documentos | TF-IDF | — | 0,585 → **0,948** | 0,684 → **0,991** | 0,991 → 1,000 | 0,335 → **0,091** |
| Documentos | LSI | 0,986 → 0,994 | 0,992 → 0,997 | 1,000 → 0,999 | 1,000 → 0,999 | 0,026 → 0,024 |

- **Con consultas cortas el centrado ayuda poco.** En el umbral baja el costo 8 puntos en
  TF-IDF y 5 en LSI. Con costo bajo mejora a LSI (≤ 0,1: 0,585 → 0,728) y no a TF-IDF. No
  resuelve el problema de fondo, que las consultas cortas están lejos de todos los documentos.
- **Con documentos completos en TF-IDF ayuda mucho**: el costo para llegar a 0,90 cae de 0,335
  a 0,091. Restar la media separa los vectores no negativos, que sin centrar caen casi todos
  del mismo lado de cada hiperplano. En LSI no cambia nada, porque ese espacio ya está
  centrado de hecho (coordenadas positivas y negativas).

**Persistencia**: `kmeans_{tfidf,lsi}_*` (c = 32) y `lsh_{tfidf,lsi}_*` (b = 2, L = 8), más
**`lsh_{tfidf,lsi}_media.npy`** (vector medio para el centrado). En `manifiesto.json`, las
secciones `kmeans` y `lsh` registran el protocolo, las estadísticas de las consultas cortas,
el radio, el centrado, si el elegido está en el borde de la grilla, las métricas con ambos
conjuntos, la elección que habría salido con documentos y el SHA-256 de las matrices base.
`lsh_indice.cargar` lee el radio y el centrado del manifiesto.

Tests nuevos (`tests/test_optimizacion.py`, 17 en total): el centrado (la media se resta antes
de hashear, se guarda y se recarga, y una elección sin centrado borra la media anterior), el
radio de multi-probe (máscaras de 3 y 4 bits, llegar a Hamming 3, no pasar de b) y las consultas
cortas (reproducibles, 1–4 tokens, ninguna con todos los tokens de df = N, solo pares de texto).
`tests/test_buscar.py`: las 6 configuraciones devuelven resultados para consultas cortas. La
intersección vacía se prueba con K-Means en ambos modelos y, para LSH, inyectando un índice sin
buckets. **Suite completa: 151 tests, todos pasan.**

#### Prueba preliminar: antes / después

`python src/prueba_preliminar_optim.py` y luego `python src/comparar_antes_despues.py` →
`informe/prueba_preliminar_antes_despues.md` / `.csv`. "Antes" = hiperparámetros elegidos con
documentos completos (archivos `*_antes.*`); "después" = elegidos con consultas cortas.

| Configuración | Antes | Después |
|---|---|---|
| TF-IDF + K-Means | c = 64 | c = 32 |
| TF-IDF + LSH | b = 16, L = 4, radio 2, sin centrar | b = 2, L = 8, radio 2, centrado |
| LSI + K-Means | c = 64 | c = 32 |
| LSI + LSH | b = 16, L = 1, radio 2, sin centrar | b = 2, L = 8, radio 2, centrado |

Relevantes en el top-5 (criterios oficiales):

| Configuración | A | B | C | D | E |
|---|---|---|---|---|---|
| TF-IDF exhaustiva | 5/5 | 5/5 | 5/5 | 5/5 | 18 rutas |
| TF-IDF + K-Means | 5/5 | 5/5 | 5/5 | 5/5 (6 res.) → 5/5 (10 res.) | 18 rutas |
| TF-IDF + LSH | vacío → **5/5** | vacío → **5/5** | vacío → **5/5** | vacío → **5/5** | 18 rutas |
| LSI exhaustiva | 5/5 | 0/5 | 5/5 | 1/5 | 18 rutas |
| LSI + K-Means | 5/5 | 0/5 | 2/2 → **5/5** | 1/5 → 0/5 | 18 rutas |
| LSI + LSH | 5/5 | 0/5 | 5/5 (5 res.) → 5/5 (10 res.) | 1/5 | 18 rutas |

Recall relativo top-10, con tolerancia / estricto:

| Configuración | A | B | C | D | Media A–D (tol.) | Examinados en B–D (antes → después) |
|---|---|---|---|---|---|---|
| TF-IDF + K-Means | 1,0 / 1,0 | 1,0 / 1,0 | 0,6 / 0,5 | 0,0 / 0,0 | 0,65 → 0,65 | 100, 12, 6 → 100, 30, 30 |
| TF-IDF + LSH | 0 / 0 → **1,0 / 0,9** | 0 / 0 → **1,0 / 1,0** | 0 / 0 → **0,5 / 0,5** | 0 / 0 → 0 / 0 | 0,00 → **0,62** | 0, 0, 0 → 1.742, 1.308, 1.598 |
| LSI + K-Means | 1,0 / 1,0 | 1,0 / 1,0 | 0,2 / 0,2 → **0,8 / 0,7** | 0,8 / 0,8 → **1,0 / 0,2** | 0,75 → **0,95** | 100, 2, 8 → 100, 32, 73 |
| LSI + LSH | 1,0 / 1,0 | 1,0 / 1,0 | 0,5 / 0,5 → **1,0 / 1,0** | 0,0 / 0,0 → **1,0 / 1,0** | 0,62 → **1,00** | 100, 5, 16 → 1.539, 1.696, 1.735 |

Memoria del proceso de búsqueda (RSS): con los índices cargados, 109,4 → 107,9 MiB; tras las 30
consultas, 111,8 → 116,1 MiB; pico 211,8 → 211,7 MiB.

Lectura:
- **LSH dejó de fallar con consultas cortas**, pero porque ahora reranquea casi todo el corpus
  (1.308–1.742 de 1.861 documentos en B–D). En LSI su recall medio sobre A–D es 1,00 y en
  TF-IDF 0,62. En TF-IDF D sigue en 0: los 10 primeros de la búsqueda exhaustiva (empatados en
  0,0500) caen todos en el 14 % que los buckets no cubren.
- **K-Means en LSI mejoró** (0,75 → 0,95) con c = 32: clústeres más grandes para las consultas
  cortas. En TF-IDF no cambió (0,65).
- **Los empates importan**: en LSI + K-Means D el recall con tolerancia es 1,0 y el estricto
  0,2. Los 10 de la búsqueda exhaustiva están empatados con otros documentos del mismo grupo, y
  K-Means devolvió otros 10 igual de buenos. Esto confirma la decisión de usar el recall con
  tolerancia en la tabla oficial.
- Recall relativo ≠ relevancia: TF-IDF + K-Means D tiene recall 0 pero 5/5 relevantes.

### 6. Decisiones del usuario sobre la Fase 4b (2026-11-11)

1. **LSH: se mantienen los elegidos por el protocolo** (b = 2, L = 8, radio 2, centrado) en
   ambos espacios. No se cambia a una configuración más barata: sería cambiar la regla después
   de ver el resultado. **Cumple 0,90 formalmente, pero con costo 0,83 (TF-IDF) y 0,87 (LSI)**:
   rerankea casi todo el corpus y casi no ahorra frente a la búsqueda exhaustiva. Para el
   informe, las tablas de recall y costo incluyen como **referencia, sin cronometrarla**, la
   configuración que se habría elegido con documentos completos (TF-IDF b = 16, L = 16; LSI
   b = 16, L = 1; ambas radio 2 y centradas), con su recall sobre A–E. Muestra cuánto recall
   cuesta ahorrar.
2. **K-Means: n_probe = 1**, como pide el enunciado ("únicamente al clúster relevante").
   n_probe = 2 se informa solo como referencia (recall y costo de validación, y recall sobre
   A–E), sin cronometrarlo.

---

## Fase 6 — Benchmark: diseño fijado ANTES de medir (2026-11-11, 14:20 −03:00)

Scripts: `src/benchmark.py` (tiempo y RAM), `src/precision.py` (P@5 y recall relativo).
Los formatos de las Tablas 1–3 siguen la descripción de las instrucciones de esta fase: el PDF
del enunciado no está en el espacio de trabajo.

### Sonda previa al diseño: dos problemas de medición corregidos

Una sonda de 300 consultas por par con el `Buscador` de la Fase 5 dio 9–15 ms para TF-IDF
exhaustiva y 0,6 ms para LSI exhaustiva. El perfil (cProfile) mostró que el 80 % del tiempo
se iba en `Espacio.cosenos`:

| Operación sobre la matriz TF-IDF densa (1.861 × 2.497, 37 MB) | 1 hilo BLAS | 4 hilos | 14 hilos (por defecto) |
|---|---|---|---|
| `x @ q` | 1,31 ms | 0,72 ms | 4,4–5,1 ms |
| `x[arange(N)] @ q` (lo que hacía la exhaustiva sin filtro) | 7,5 ms | 8,4–8,9 ms | 16–19 ms |
| `csr @ q` (matriz dispersa, solo referencia) | 0,25–0,37 ms | 0,38 ms | 0,47–0,53 ms |

1. **Hilos de BLAS.** Con los 14 hilos por defecto, OpenBLAS reparte un producto
   matriz-vector chico entre núcleos P y E y es 3–4 veces más lento que con 1 hilo. También
   agrega variabilidad según dónde caigan los hilos. **Decisión: 1 hilo de BLAS** en el
   buscador. `Buscador` lo fija al construirse con `threadpoolctl` (`config.HILOS_BLAS`,
   variable `ENTREGA2_HILOS_BLAS`), así que la CLI y el benchmark quedan igual. Un servicio de
   búsqueda atiende una consulta por proceso o hilo: paralelizar cada producto no corresponde.
2. **Copia innecesaria.** La exhaustiva sin filtro calculaba `x[arange(N)] @ q`: copia los
   37 MB en memoria nueva en cada consulta (con fallos de página) y luego multiplica. **Ahora
   calcula `x @ q` cuando los candidatos son todo el corpus**, con resultado idéntico bit a
   bit (verificado y con test). Con filtro, K-Means o LSH se sigue extrayendo solo a los
   candidatos. Es el costo real de rerankear un subconjunto, y en LSH TF-IDF (≈ 1.500
   candidatos) seguirá pesando.
3. **No se cambia a matriz dispersa** (sería ~4 veces más rápida para TF-IDF). Cambia el
   orden de las sumas: el coseno difiere en ~1e-16 y en C eso reordena documentos empatados
   (otro top-10 estricto). Todo lo validado hasta ahora usa la representación densa.

Ninguno de los tres cambia los resultados ya informados. `src/precision.py` verifica que el
top-5 de las 6 configuraciones sea idéntico al de `informe/prueba_preliminar_optim_top5.csv`.

### Hallazgo en la corrida corta: el reloj de `perf_counter_ns` está acelerado (14:37)

En la primera corrida corta, entre dos checkpoints el reloj de pared avanzó 62 s, pero
`perf_counter` midió 64,6 s solo para la segunda ronda. Se compararon los relojes con el de
Windows en una espera activa de ~40 s:

| Reloj | Duración medida | Diferencia con Windows |
|---|---|---|
| Windows (`DateTimeOffset.UtcNow`) | 38,252 s | — |
| `perf_counter` (CLOCK_MONOTONIC) | 40,226 s | **+5,16 %** |
| `time.time` (CLOCK_REALTIME) | 37,232 s | −2,67 % |
| CLOCK_MONOTONIC_RAW | 38,260 s | +0,02 % |

- **Causa**: `systemd-timesyncd` está activo dentro de WSL y corrige el reloj del sistema, que
  WSL también sincroniza con Windows por su cuenta. `adjtimex` muestra `tick` = 10.833
  (nominal 10.000) y freq = 33,5 ppm.
- **Efecto**: CLOCK_MONOTONIC corre **entre 3,4 % y 7,0 % más rápido** según la ventana de
  5 s, de forma variable. `perf_counter_ns` infla todos los tiempos, y no por un factor fijo.
- **Decisión (pendiente de aprobación del usuario, que había pedido `perf_counter_ns`)**:
  - El cronómetro usa `time.clock_gettime_ns(CLOCK_MONOTONIC_RAW)`: el contador del hardware
    sin ajustes, que coincide con Windows. Cuesta 115 ns por lectura frente a 61 ns, nada al
    lado de una consulta de ≥ 0,5 ms.
  - Por bloque también se guarda la duración según CLOCK_MONOTONIC, para documentar el
    desvío con los propios datos (`bloque_monotonic_ns` frente a `bloque_raw_ns`).
  - `adjtimex` (`tick`, `freq`) se registra en cada checkpoint.
  - Alternativa o complemento: `sudo systemctl stop systemd-timesyncd`; no hace falta en WSL,
    que ya sincroniza la hora con Windows. Detenerlo no devuelve el `tick` a 10.000; para eso
    hay que reiniciar WSL (`wsl --shutdown`).
- La pasada de RAM no usa el cronómetro. Solo se repitió la pasada de tiempo de la corrida
  corta.

### A. Qué se mide

- **6 configuraciones × 5 consultas = 30 pares**: TF-IDF, TF-IDF + K-Means, TF-IDF + LSH, LSI,
  LSI + K-Means y LSI + LSH, con los hiperparámetros de la Fase 4b (K-Means c = 32 y
  n_probe = 1; LSH b = 2, L = 8, radio 2, centrado), sobre A–E.
- **100.000 repeticiones por par.**
- La consulta completa, como la resuelve la CLI: una llamada a `Buscador.buscar(...)` con los
  mismos argumentos que `src/buscar.py`.
  - Argumentos: `consultas.ARGUMENTOS_CLI`, los de la prueba preliminar. A lleva
    `--fecha-desde/--fecha-hasta 2026-09-05`; E lleva solo RA/DEC.
  - La llamada incluye el filtro en MongoDB (A, E), la tokenización y vectorización, la
    búsqueda (exhaustiva, K-Means o LSH), el coseno exacto y la consulta a MongoDB por las
    `storage.hdfs_path`.
  - No incluye imprimir el resultado.
  - MongoDB corre en un contenedor de Docker Desktop. Cada consulta hace 1–2 viajes de ida y
    vuelta WSL → contenedor, que son parte del tiempo de respuesta real.
- **Integridad**: en cada bloque se compara, fuera de la región medida, la lista de
  `hdfs_path` de la última repetición con la del calentamiento. Si difiere, el benchmark se
  detiene.
- **Carga de índices**: una vez antes de medir, fuera del tiempo de consulta, y se informa
  aparte. Incluye la verificación SHA-256 del manifiesto, igual que la CLI.

### B. Pasada de tiempo (`python src/benchmark.py tiempo`)

- **Cronómetro**: inmediatamente antes y después de cada `buscar`. Se diseñó con
  `time.perf_counter_ns()` y se cambió a `CLOCK_MONOTONIC_RAW` por el hallazgo de la corrida
  corta (ver arriba).
- **Calentamiento**: 1.000 consultas por par antes de medir, sin registrar. También al
  reanudar.
- **Recolector de basura**: `gc.collect()` y `gc.disable()` antes de cada bloque, y
  `gc.enable()` después. El recolector cíclico nunca corre dentro de la región medida. La
  liberación por conteo de referencias sigue activa: es la normal de Python.
- **Intercalado contra la deriva térmica**:
  - Las 100.000 repeticiones se dividen en **100 rondas**. En cada ronda se recorren los 30
    pares con un bloque de 1.000 repeticiones seguidas por par.
  - El orden de los 30 pares es una permutación nueva por ronda, con semilla fija
    (`SEMILLA_BENCHMARK = 20261113`), guardada en `plan.json`.
  - Así cada configuración se mide repartida a lo largo de toda la corrida.
- **Hilos**: 1 hilo de BLAS (ver la sonda). Los hilos de fondo de pymongo (monitor del
  servidor, cada 10 s) siguen activos, como en la CLI.

### C. Pasada de RAM (`python src/benchmark.py ram`), separada de la de tiempo

- **Un proceso nuevo por configuración** (6 procesos, en serie), que carga **solo los índices
  de esa configuración**:
  - `Buscador(solo=(modelo, optim))` construye solo el espacio denso del modelo y, si
    corresponde, solo su K-Means o su LSH.
  - Libera lo que esa consulta no usa: la matriz TF-IDF dispersa y `docs_k` (ya copiados como
    espacio normalizado) y la proyección LSI si el modelo es TF-IDF.
- Calentamiento de 1.000 consultas por consulta.
- Luego **100.000 repeticiones por par**, en rondas de bloques de 1.000 con las 5 consultas en
  orden aleatorio por ronda (misma semilla) y el gc deshabilitado dentro de cada bloque, como
  en la pasada de tiempo.

| Medida | Qué representa | Dónde va |
|---|---|---|
| **Pico de tracemalloc por consulta** (`reset_peak()` antes, `peak − actual_antes` después) | Memoria de trabajo de la consulta: lo máximo que se asignó **además** de lo que ya estaba (vectores, máscara del filtro, candidatos, cosenos, objetos de pymongo y del resultado). tracemalloc ve el asignador de Python y los arreglos de numpy. **No ve** los búferes internos de OpenBLAS ni la memoria del servidor MongoDB (otro proceso) | **Tabla 1 (RAM por consulta)** |
| **RSS base** (después de cargar, y después del calentamiento) | Memoria residente del proceso con los índices de esa configuración: intérprete, numpy, pymongo, índices. Es lo que cuesta tener el buscador listo | Tabla aparte, por configuración |
| **RSS después de cada consulta** (`/proc/self/status`, VmRSS) | Memoria residente total tras la consulta, en páginas de 4 KiB. Sirve para ver si las consultas hacen crecer el proceso (fugas, fragmentación), no para medir una consulta: el asignador reutiliza memoria | Anexo |
| **Neto por consulta** (`actual_después − actual_antes`) | Lo que la consulta deja retenido. Debe ser ≈ 0; si crece, hay acumulación | Control, anexo |

- tracemalloc se activa **después** de cargar y calentar: así los índices no cuentan en el pico.
- Su sobrecarga hace más lenta esta pasada, y por eso estos tiempos no se usan.

### D. Estadísticas y datos crudos

- Para tiempo (ms) y RAM (pico en KiB; RSS en MiB): MIN, Q1, MEDIAN, Q3, MAX, IQR, MEAN y STD.
  - Cuartiles con `numpy.percentile` (interpolación lineal).
  - STD muestral (ddof = 1).
- Dos niveles:
  - (i) **por configuración**, agregando las 5 consultas (500.000 valores): formato de la
    Tabla 1;
  - (ii) **por configuración y consulta**: tabla del anexo.
- Además, la mediana por ronda y configuración (`*_por_ronda.csv`), para ver si hay deriva.
- **Datos crudos** en `salidas/benchmark/<corrida>/`:
  - `tiempo/ronda_NNNNN.npy`: 30 × 1.000 enteros int64 en ns, una fila por par, en el orden
    de `plan.json`;
  - `ram/<modelo>_<optim>/ronda_NNNNN.npz`: pico, neto y RSS, 5 × 1.000.
- **Checkpoints**:
  - Cada ronda se escribe completa de forma atómica (archivo temporal + `os.replace`).
  - Al reanudar con el mismo comando se saltan las rondas ya escritas, si `plan.json` coincide
    con los parámetros.

### E. Condiciones de medición

- **Monitor**: un proceso de PowerShell escribe cada 15 s, en `monitor.csv`, la hora, la
  corriente o batería (`Win32_Battery`), el modo de energía (registro
  `ActiveOverlayAcPowerScheme`), la memoria disponible de Windows y la frecuencia efectiva de
  la CPU.
  - Frecuencia efectiva = `ProcessorFrequency × PercentProcessorPerformance / 100`, de
    `Win32_PerfFormattedData_Counters_ProcessorInformation`.
  - Escribe solo él, para que leer las condiciones no lance procesos en medio de la medición.
  - Se apaga solo si el benchmark deja de dar señales de vida (latido) durante 15 min.
- **Temperatura: no se puede leer** sin permisos de administrador
  (`MSAcpi_ThermalZoneTemperature` falla y `ThermalZoneInformation` no tiene zonas en este
  equipo). Se usa la frecuencia efectiva como indicador de estrangulamiento térmico.
- **Cuándo se revisa**: antes de empezar, con el estado completo de `entorno.resumen_equipo()`;
  y en cada checkpoint (fin de cada ronda), con la última línea del monitor más estas pruebas
  desde WSL:
  - HDFS detenido: no hay nada escuchando en 127.0.0.1:9870 / 9864 / 9000 (puertos del
    NameNode y del DataNode);
  - `MemAvailable` de WSL;
  - el monitor está vivo (última línea con menos de 60 s).
  - Todo queda en `condiciones.jsonl`.
- **Condiciones inválidas**: sin corriente, otro modo de energía, HDFS encendido, monitor
  caído o `MemAvailable` < 2 GiB.
  - Si aparece una, **el benchmark se pausa**: guarda lo medido, escribe el motivo y termina
    con código 3. Se reanuda con el mismo comando una vez corregida la condición.

### F. Precisión (`python src/precision.py`, sin repeticiones)

- **P@5** de TF-IDF y LSI exhaustivas × A–E.
  - `informe/p_at_5_revision.csv`: los 5 resultados por consulta con los metadatos que deciden
    la relevancia, `relevante_auto` (criterio oficial de `consultas.py`) y `relevante_manual`
    vacía, para la revisión del usuario.
  - Al volver a correr se conservan los valores manuales ya escritos.
  - P@5 usa `relevante_manual` cuando la columna está completa para esa consulta; si no, usa
    `relevante_auto` y lo marca.
  - E es solo numérica: sus "5 resultados" son los 5 primeros `_id` de la caja.
- **Recall relativo top-10** (con tolerancia, oficial, y estricto) de las 4 optimizadas frente
  a su exhaustiva, en A–E, con promedio y costo (documentos examinados).
  - En E todas las configuraciones resuelven el mismo filtro de MongoDB, así que su recall es 1
    por construcción; se informa el promedio A–E y también A–D.
  - **Filas de referencia** (sin cronometrar): LSH b = 16 elegido con documentos completos y
    K-Means n_probe = 2.
    - El LSH de referencia se reconstruye en memoria con la misma semilla de hiperplanos, sin
      tocar `indice/`.
    - Se comprueba que reproduce el recall y el costo de `validacion_v2_lsh.csv`.
  - Las tablas también traen el recall y el costo de validación (consultas cortas y
    documentos) de cada configuración.
- **Salidas**: `informe/tabla2_p_at_5.{md,csv}` y `informe/tabla3_recall.{md,csv}`.

### G. Corrida corta antes de la completa

- 2.000 repeticiones por par (2 rondas) en ambas pasadas, con `--corrida corta`.
- Sirve para estimar la duración total y mostrar medianas preliminares.
- **La completa no se lanza hasta que el usuario confirme** que dejó el equipo aislado (HDFS
  detenido, caché vaciada, aplicaciones cerradas).

### Corrida corta (2.000 repeticiones por par; 2026-11-11, 14:28–14:47)

- `python src/benchmark.py todo --corrida corta --reps 2000`, y luego la pasada de tiempo otra
  vez con CLOCK_MONOTONIC_RAW (`python src/benchmark.py tiempo --corrida corta --reps 2000` y
  `resumen`).
  - Logs: `salidas/benchmark_corta.log` y `salidas/benchmark_corta_tiempo_raw.log`.
  - Resumen: `salidas/benchmark/corta/resumen/`.
- Condiciones: HDFS detenido por Claude antes de la corrida
  (`docker compose stop namenode datanode`); enchufado; Máximo rendimiento.
  - Frecuencia efectiva en los checkpoints: 2.045–3.756 MHz (mediana 3.519).
  - El equipo **no** estaba aislado (sin vaciar caché, con aplicaciones abiertas).
- Integridad: todas las rondas devolvieron las mismas rutas que el calentamiento.
- En los bloques medidos, CLOCK_MONOTONIC avanzó **+4,98 %** respecto de MONOTONIC_RAW.
  `adjtimex` alternó entre tick 10.000 y 10.833 entre checkpoints.

Medianas preliminares (ms, A–E agregadas, MONOTONIC_RAW):

| Configuración | MEDIAN | Q1 – Q3 | Por consulta A / B / C / D / E |
|---|---:|---|---|
| TF-IDF | 2,485 | 2,332 – 2,931 | 4,06 / 2,48 / 2,54 / 2,44 / 0,90 |
| TF-IDF + K-Means | 0,821 | 0,587 – 1,046 | 2,27 / 0,80 / 0,57 / 0,57 / 0,90 |
| TF-IDF + LSH | 5,230 | 4,111 – 6,464 | 4,22 / 8,95 / 5,15 / 5,98 / 1,02 |
| LSI | 0,647 | 0,555 – 1,072 | 1,97 / 0,55 / 0,59 / 0,56 / 0,96 |
| LSI + K-Means | 0,658 | 0,517 – 0,985 | 1,94 / 0,50 / 0,55 / 0,56 / 0,88 |
| LSI + LSH | 0,960 | 0,886 – 1,213 | 2,30 / 0,91 / 0,93 / 0,99 / 0,87 |

RAM (pico de tracemalloc por consulta, mediana en KiB) y RSS base (MiB, tras cargar → tras
calentar):

| Configuración | Pico mediano (KiB) | Pico máx. (KiB) | RSS base |
|---|---:|---:|---|
| TF-IDF | 106,6 | 8.552,6 (A: extrae las 433 filas del día) | 103,1 → 110,5 |
| TF-IDF + K-Means | 629,1 | 2.054,4 | 103,2 → 105,4 |
| TF-IDF + LSH | 25.577,2 | 34.052,2 (extrae ≈ 1.300–1.750 filas) | 103,3 → 134,0 |
| LSI | 93,9 | 139,1 | 66,6 → 67,1 |
| LSI + K-Means | 40,0 | 139,1 | 66,6 → 67,3 |
| LSI + LSH | 213,5 | 239,4 | 66,8 → 67,5 |

Lectura preliminar:
- **TF-IDF + LSH es la más lenta** (5,2 ms) **y la que más memoria usa por consulta**
  (25 MB): rerankea el 70–94 % del corpus, y además tiene que extraer esas filas de la matriz
  densa, lo que la exhaustiva sin filtro no hace.
- En LSI el espacio tiene 14 dimensiones: el coseno es casi gratis y todo queda en ~0,5–1 ms,
  dominado por los viajes a MongoDB (E, que no usa el índice vectorial, tarda ~0,9 ms).
- A es la más lenta en todas las configuraciones: el filtro por día en MongoDB devuelve 433
  `_id`.
- El RSS después de cada consulta casi no varía (IQR ≤ 0,6 MiB): las consultas no hacen
  crecer el proceso.

**Estimación de la corrida completa (100.000 repeticiones por par)**:
- Pasada de tiempo: ~61 s por ronda × 100 rondas + carga y calentamiento ≈ **1,7 h**.
- Pasada de RAM: ≈ **2,3 h**. TF-IDF + LSH es la más larga: ~30 s por ronda, ≈ 50 min.
- **Total ≈ 4,1 h.**

### Decisiones del usuario antes de la corrida completa (2026-11-11)

1. **Cronómetro CLOCK_MONOTONIC_RAW: aprobado.** Se mantiene, como evidencia, el registro por
   bloque de la duración según CLOCK_MONOTONIC y el de `adjtimex` en cada checkpoint. **No se
   detiene `systemd-timesyncd`**: requeriría `wsl --shutdown` y no hace falta midiendo con RAW.
2. **BLAS a 1 hilo y exhaustiva sin copia: aprobados.**
3. **Matriz TF-IDF densa: se mantiene** (aprobado).

Equipo aislado según el usuario:
- HDFS detenido y caché de Linux vaciada;
- aplicaciones cerradas;
- Windows Update en pausa;
- suspensión y apagado de pantalla desactivados;
- enchufado y en Máximo rendimiento.

Durante la corrida no se ejecuta nada más en el equipo. Si se pausa por condiciones
inválidas, se espera la confirmación del usuario antes de reanudar.

### Corrida completa (100.000 repeticiones por par; 2026-11-11, 14:47–19:06 −03:00)

- Comando: `python src/benchmark.py todo --corrida completa --reps 100000`.
  - Log: `salidas/benchmark_completa.log` (termina en `exit=0`).
  - Datos crudos: `salidas/benchmark/completa/`.
- Antes de lanzar, Claude verificó las condiciones con los chequeos del script:
  - en corriente y en Máximo rendimiento;
  - sin puertos de HDFS abiertos;
  - 17.294 MiB disponibles en WSL y 15.498 MB en Windows;
  - `adjtimex` con tick 10.000;
  - MongoDB con 1.861 documentos.
- Duración real:
  - pasada de tiempo 1 h 49 min (14:47–16:36);
  - pasada de RAM 2 h 30 min (16:36–19:06);
  - **total 4 h 19 min**, contra ~4,1 h estimadas.
- Durante la corrida Claude no ejecutó nada más.

**Condiciones**: los 715 registros de `condiciones.jsonl` (tiempo y las 6 configuraciones de
RAM) son válidos y la corrida no se pausó nunca.
- Siempre en corriente y siempre en Máximo rendimiento.
- Sin puertos de HDFS abiertos.
- Edad del monitor ≤ 16,6 s.
- Memoria disponible: WSL ≥ 16.989 MiB y Windows ≥ 14.046 MB.
- Frecuencia efectiva de la CPU en los checkpoints: 1.775–3.772 MHz (mediana 3.471).
- Uso de CPU de Windows en los checkpoints: 0–46 %, porque el propio benchmark ocupa un núcleo.

**Integridad**: todas las repeticiones devolvieron las mismas rutas que el calentamiento.
- La pasada de tiempo cargó los índices en 0,32 s (RSS 105,6 MiB) y usó BLAS con 1 hilo
  (OpenBLAS 0.3.34).

**Reloj**: en los bloques medidos, CLOCK_MONOTONIC avanzó **+3,45 %** respecto de
MONOTONIC_RAW.
- Por ronda varió entre −0,06 % y +5,28 %.
- `adjtimex` marcó tick 10.833 en 34 de los 101 checkpoints de la pasada de tiempo.
- Ese error habría entrado entero en las medianas si se cronometrara con `perf_counter_ns`.
  Con MONOTONIC_RAW no afecta.

#### Tabla 1 — Tiempo de respuesta por consulta (ms; A–E agregadas, 500.000 tiempos por fila)

| Configuración | MIN | Q1 | MEDIAN | Q3 | MAX | IQR | MEAN | STD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TF-IDF | 0,751 | 2,357 | 2,488 | 3,232 | 15,960 | 0,875 | 2,685 | 1,150 |
| TF-IDF + K-Means | 0,482 | 0,674 | 0,896 | 1,295 | 27,281 | 0,621 | 1,237 | 0,830 |
| TF-IDF + LSH | 0,738 | 4,268 | 5,322 | 6,756 | 76,533 | 2,487 | 5,385 | 2,835 |
| LSI | 0,490 | 0,641 | 0,784 | 1,181 | 30,156 | 0,541 | 1,099 | 0,711 |
| LSI + K-Means | 0,448 | 0,586 | 0,722 | 1,152 | 17,874 | 0,566 | 1,058 | 0,695 |
| LSI + LSH | 0,761 | 0,964 | 1,046 | 1,503 | 27,282 | 0,538 | 1,403 | 0,749 |

#### Tabla 1 — RAM por consulta: pico de tracemalloc (KiB; A–E agregadas)

| Configuración | MIN | Q1 | MEDIAN | Q3 | MAX | IQR | MEAN | STD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TF-IDF | 19,5 | 106,2 | 106,6 | 113,3 | 8.552,6 | 7,1 | 1.776,5 | 3.380,1 |
| TF-IDF + K-Means | 18,5 | 629,1 | 629,1 | 1.995,1 | 2.054,4 | 1.366,0 | 1.062,3 | 810,4 |
| TF-IDF + LSH | 18,9 | 7.423,4 | 25.577,2 | 31.239,1 | 34.053,2 | 23.815,7 | 19.662,0 | 13.502,8 |
| LSI | 18,9 | 93,3 | 93,9 | 93,9 | 139,2 | 0,6 | 84,8 | 34,3 |
| LSI + K-Means | 19,0 | 39,9 | 40,0 | 40,0 | 139,2 | 0,1 | 52,6 | 36,0 |
| LSI + LSH | 18,5 | 132,4 | 213,5 | 233,2 | 239,4 | 100,8 | 167,5 | 82,9 |

El pico por consulta es casi determinista: IQR 0,0 por consulta, en el anexo. Por eso, en
la tabla agregada la dispersión refleja la diferencia entre consultas, no ruido.

#### RSS base (proceso nuevo por configuración, solo con sus índices; MiB)

| Configuración | Carga (s) | Tras cargar | Tras calentar | VmHWM | Tras la última consulta |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 0,24 | 98,7 | 106,2 | 209,6 | 107,1 |
| TF-IDF + K-Means | 0,23 | 98,7 | 101,0 | 209,8 | 101,3 |
| TF-IDF + LSH | 0,24 | 98,7 | 129,5 | 209,2 | 129,8 |
| LSI | 0,20 | 63,1 | 63,7 | 68,0 | 64,1 |
| LSI + K-Means | 0,18 | 63,0 | 63,7 | 67,8 | 64,0 |
| LSI + LSH | 0,16 | 63,3 | 64,0 | 67,9 | 64,4 |

- El VmHWM de ~209 MiB en TF-IDF es el pico durante la carga: la matriz se lee y luego se
  normaliza.
- El RSS después de cada consulta tiene IQR ≤ 0,2 MiB en las 30 combinaciones: las consultas
  no hacen crecer el proceso.

Los anexos por configuración × consulta (tiempo, pico de tracemalloc y RSS tras cada
consulta) están en `informe/benchmark_resumen.md`, y en CSV en `informe/benchmark_tiempo.csv`
y `informe/benchmark_ram.csv`.

Anexo de tiempo, mediana por consulta (ms; el detalle completo está en el resumen):

| Configuración | A | B | C | D | E |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 4,221 | 2,466 | 2,518 | 2,471 | 1,010 |
| TF-IDF + K-Means | 2,500 | 0,848 | 0,650 | 0,647 | 1,018 |
| TF-IDF + LSH | 4,414 | 9,033 | 5,137 | 5,993 | 1,010 |
| LSI | 2,099 | 0,641 | 0,656 | 0,670 | 1,012 |
| LSI + K-Means | 2,120 | 0,595 | 0,603 | 0,594 | 1,006 |
| LSI + LSH | 2,440 | 0,967 | 1,010 | 1,036 | 1,010 |

Lectura:
- **Velocidad**: LSI + K-Means (0,72 ms) ≈ LSI (0,78) < TF-IDF + K-Means (0,90)
  < LSI + LSH (1,05) < TF-IDF (2,49) < TF-IDF + LSH (5,32).
- **E** no usa el índice vectorial y tarda lo mismo en las seis configuraciones (1,01 ms).
  Es el costo del camino que solo pasa por MongoDB.
- **TF-IDF + LSH es la peor en tiempo y en memoria.** Rerankea el 70–94 % del corpus y
  extrae esas filas de la matriz densa, de modo que paga más que la exhaustiva. Su pico es de
  25–34 MB por consulta.
- En LSI (14 dimensiones) el coseno es casi gratis y las tres variantes quedan dentro de
  ~0,3 ms entre sí.

#### Gráficos (`python src/benchmark_informe.py`)

- `informe/benchmark_tiempo_boxplot.png`: boxplot por configuración en escala logarítmica.
  La caja va de Q1 a Q3, la línea es la mediana rotulada y los bigotes son los percentiles
  1 y 99, sin puntos atípicos.
- `informe/benchmark_deriva_por_ronda.png`: mediana de cada ronda relativa a la mediana
  global, con 6 paneles, una banda de ±10 % y los cuartos marcados.
  - El eje se recortó a ±40 % (constante `LIMITE_EJE_DERIVA`) para que la banda se lea.
  - El máximo fuera de escala se rotula en cada panel.

#### Deriva: primer vs. último cuarto de las rondas (criterio fijado: > 10 %)

| Configuración | Q1 de rondas (1–25) | Q2 | Q3 | Q4 (76–100) | Cambio Q1 → Q4 | ¿> 10 %? |
|---|---:|---:|---:|---:|---:|---|
| TF-IDF | 2,482 | 2,485 | 2,498 | 2,489 | +0,3 % | no |
| TF-IDF + K-Means | 0,856 | 0,901 | 0,952 | 0,915 | +6,9 % | no |
| TF-IDF + LSH | 5,253 | 5,350 | 5,422 | 5,293 | +0,8 % | no |
| LSI | 0,737 | 0,791 | 0,832 | 0,780 | +5,8 % | no |
| LSI + K-Means | 0,655 | 0,720 | 0,782 | 0,733 | **+11,9 %** | **sí** |
| LSI + LSH | 0,998 | 1,045 | 1,076 | 1,070 | +7,2 % | no |

- Por configuración × consulta superan el 10 %: LSI C (+11,6 %), LSI E (+10,8 %) y
  LSI + K-Means D (+10,6 %).
- Detalle en `informe/benchmark_deriva.csv`.

Análisis de la deriva (con los mismos datos crudos, sin medir nada nuevo):

1. **No es continua: es un escalón después del primer cuarto.**
   - Sin las rondas 49–52, las medianas de LSI + K-Means por cuarto son 0,655 / 0,711 /
     0,728 / 0,733 ms.
   - Los tres últimos cuartos coinciden dentro del 3 %. Las otras configuraciones muestran el
     mismo patrón.
   - Las primeras ~20 rondas (~20 min) fueron más rápidas que el resto.
2. **No es del cálculo vectorial.**
   - La exhaustiva TF-IDF (B/C/D: producto de 1.861 × 2.497 en BLAS) no cambió (−0,6 % a
     +0,7 %).
   - E, que solo consulta MongoDB, subió +10 % en las seis configuraciones (0,935 → 1,03 ms
     por deciles de rondas). Se estabiliza desde la ronda ~40.
   - El aumento es de ~+0,05–0,1 ms por consulta y común a todas. Pesa más en porcentaje
     donde la consulta dura ~0,6 ms (LSI y K-Means), por eso solo esas cruzan el 10 %.
   - Los datos no identifican la causa: MongoDB y su caché, WSL o Windows. Distinguirlas
     requeriría otro experimento.
3. **Episodio transitorio en las rondas 49–52 (15:40–15:46 −03:00).**
   - Rondas de 75–107 s en vez de ~64, con frecuencia efectiva de 2.615–3.091 MHz.
   - Picos de la mediana por ronda de +90 a +160 % en las configuraciones rápidas.
   - Las condiciones siguieron válidas.
   - Sin esas 4 rondas, las medianas globales cambian < 2 % (p. ej. LSI 0,784 → 0,771;
     TF-IDF + LSH 5,322 → 5,275). Se dejan en los datos, porque el protocolo no prevé
     descartar rondas.

#### Completa vs. corta (medianas en ms)

| Configuración | Corta (2.000) | Completa (100.000) | Cambio | Cambio por consulta A / B / C / D / E |
|---|---:|---:|---:|---|
| TF-IDF | 2,485 | 2,488 | +0,1 % | +4 / −1 / −1 / +1 / +12 % |
| TF-IDF + K-Means | 0,821 | 0,896 | +9,2 % | +10 / +6 / +15 / +15 / +13 % |
| TF-IDF + LSH | 5,230 | 5,322 | +1,8 % | +5 / +1 / 0 / 0 / −1 % |
| LSI | 0,647 | 0,784 | +21,1 % | +7 / +17 / +11 / +19 / +6 % |
| LSI + K-Means | 0,658 | 0,722 | +9,8 % | +9 / +18 / +11 / +6 / +14 % |
| LSI + LSH | 0,960 | 1,046 | +9,0 % | +6 / +7 / +8 / +4 / +16 % |

- Es el mismo efecto que la deriva. Las configuraciones caras (TF-IDF y TF-IDF + LSH) no
  cambian. Las de ~0,6 ms suben ~0,05–0,1 ms por consulta, lo mismo que la corta (19 min)
  comparada con las rondas posteriores al primer cuarto de la completa.
- El +21 % de LSI agregado está amplificado por la forma de la mezcla.
  - B, C y D (~0,65 ms) son el 60 % de los tiempos, así que la mediana agregada cae en el
    percentil ~83 de ese grupo.
  - Por eso es sensible a su cola. Por consulta, el cambio es de +6 a +19 %.
- Los picos de RAM coinciden con la corta al 0,1 KiB, porque son deterministas.
- El RSS base de la completa es ~4,5 MiB menor que el de la corta (98,7 vs. 103,1 MiB tras
  cargar TF-IDF), probablemente por la caché de Linux vaciada antes de la completa.
- **El orden no cambia, salvo un empate.**
  - LSI y LSI + K-Means intercambian el primer lugar: 0,647 vs. 0,658 en la corta y
    0,784 vs. 0,722 en la completa.
  - Por consulta, en la completa LSI + K-Means es más rápida en B/C/D (≈ 0,60 vs. 0,64–0,67)
    e igual en A y E.
  - Las dos están dentro de la deriva observada, así que deben leerse como empatadas.

Se informa como dato oficial la **corrida completa** (Tabla 1 en
`informe/benchmark_resumen.md`). La deriva de LSI + K-Means (+11,9 %) queda reportada como
excedida, con el análisis anterior.

Cambios de código después de la corrida (no afectan los datos):
- `src/benchmark.py`: separador de miles en español (`_miles`) en los títulos del resumen.
  Se regeneró con `python src/benchmark.py resumen --corrida completa`, y
  `tests/test_benchmark.py` sigue en 11/11.
- `src/benchmark_informe.py`: eje del gráfico de deriva recortado a ±40 %.

### Decisión del usuario sobre la deriva (2026-11-11)

- La deriva de LSI + K-Means (+11,9 % entre el primer y el último cuarto de rondas) **se
  informa tal como está**, con el análisis de la sección anterior.
- No se hace una corrida adicional para aislar la causa (MongoDB, WSL o Windows).
- Los datos oficiales son los de la corrida completa, sin descartar rondas: Tabla 1 y anexos
  en `informe/benchmark_resumen.md`.

## Publicación en GitHub (2026-11-11)

- **Repositorio:** https://github.com/csanmartin12/BigData. La raíz del repositorio es
  `/mnt/c/Bases`, y no se movió ni se renombró ningún archivo.
- **Excluidos por `.gitignore`:**
  - los 6 ZIP (~8,5 GB) y cualquier FITS;
  - cachés de Python;
  - venvs;
  - temporales de Office y de editores;
  - `entrega2/salidas/benchmark/`.
- **Datos crudos del benchmark:** `entrega2/salidas/benchmark/` pesa 101 MiB en 758 archivos,
  sobre el límite de 100 MB fijado por el usuario. Por decisión del usuario se versiona
  comprimido en `entrega2/salidas/benchmark.tar.xz`, de 8,5 MB.
  - El archivo se generó con
    `tar --sort=name --owner=0 --group=0 -cf - -C salidas benchmark | xz -9`.
  - SHA-256: `56c5522b2d7fae49b83760f38f36e7c4a3105e03957def3da9191adc43c45857`.
  - Se restaura con `tar -xJf entrega2/salidas/benchmark.tar.xz -C entrega2/salidas/`.
- **Verificación del archivo**, extraído en una copia aparte:
  - `diff -r` contra el original sin diferencias;
  - `python src/benchmark.py resumen --corrida completa` y `python src/benchmark_informe.py`
    regeneran los 9 archivos de tablas de `informe/benchmark_*` idénticos byte a byte;
  - los 2 PNG salen idénticos píxel a píxel;
  - las rutas citadas en esta bitácora existen tras la extracción.
- **Revisión de secretos:** no hay contraseñas, tokens ni archivos de credenciales.
  - MongoDB corre sin autenticación en `localhost`.
  - `infra/hadoop.env` solo tiene configuración de HDFS.
