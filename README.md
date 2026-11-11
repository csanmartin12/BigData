# Big Data (UDP) — Gestión de datos astronómicos: metadatos FITS de X-shooter

Proyecto semestral del curso Big Data (UDP, sección 2). Trabaja con los headers FITS de las
observaciones del espectrógrafo X-shooter (ESO) entre el 2026-09-04 y el 2026-09-09:
1.861 archivos FITS repartidos en 6 ZIP.

- **Entrega 1:** extracción de los headers de los FITS a una tabla (`headers.csv`), análisis
  exploratorio y diseño del modelo de datos. Está en el informe [main.typ](main.typ), compilado
  en [Informe_Big_Data.pdf](Informe_Big_Data.pdf).
- **Entrega 2:** buscador híbrido sobre esos metadatos. Tiene cuatro partes:
  - ETL con PySpark: FITS a HDFS y documentos a MongoDB.
  - Filtros estructurados en MongoDB (fecha, caja RA/DEC…).
  - Búsqueda semántica con TF-IDF y LSI, implementados a mano, y coseno.
  - Optimización con K-Means y LSH, medida con un benchmark de 100.000 repeticiones por
    consulta.
  
  Está en [entrega2/](entrega2/).

## Estructura

```
.
├── README.md                  este archivo
├── .gitignore
├── Informe_Big_Data.pdf       Informe 1 (Entrega 1), compilado
├── main.typ                   fuente final del Informe 1 (Typst)
├── informe.typ                borrador anterior del Informe 1
├── extraer_headers.py         Entrega 1: ZIP -> headers.csv (+ headers_log.jsonl)
├── analisis_exploratorio.py   Entrega 1: análisis exploratorio -> resultados_final.xlsx
├── headers.csv                headers de los 1.861 FITS (insumo y referencia de la Entrega 2)
├── headers_log.jsonl          log de la extracción de la Entrega 1
├── resultados_final.xlsx      resultados del análisis exploratorio
├── XSHOO.2026-09-0{4..9}.zip  DATOS, NO VERSIONADOS (ver abajo)
└── entrega2/
    ├── README.md              cómo instalar, levantar servicios y reproducir cada fase
    ├── METODOLOGIA.md         bitácora: cada paso, decisión y cifra, con el script que la produjo
    ├── infra/                 docker-compose (MongoDB + HDFS de un nodo), hadoop.env, .wslconfig
    ├── src/                   código (ETL, tokenizador, TF-IDF/LSI, K-Means, LSH, CLI, benchmark)
    ├── tests/                 pytest (unitarios + integración)
    ├── indice/                índices persistidos (TF-IDF, LSI, K-Means, LSH) + manifiesto.json
    ├── informe/               tablas (CSV/MD) y gráficos (PNG) para el informe
    └── salidas/               logs y métricas del ETL y del benchmark
        └── benchmark.tar.xz   datos crudos del benchmark, comprimidos (ver abajo)
```

## Datos: los 6 ZIP (no están en el repositorio)

El profesor entregó los 6 archivos `XSHOO.2026-09-04.zip` … `XSHOO.2026-09-09.zip`, que
suman ~8,5 GB. **No se versionan por tamaño**: `.gitignore` excluye `*.zip` y `*.fits`.

Para reproducir el proyecto, copie los 6 ZIP, sin descomprimir y con esos nombres exactos,
en la **raíz del repositorio**, junto a `headers.csv`.

La Entrega 2 los busca ahí por defecto: es `DATA_DIR` en
[entrega2/src/config.py](entrega2/src/config.py), con el valor `/mnt/c/Bases`. Si el
repositorio está en otra ruta, indíquela con una variable de entorno:

```bash
export ENTREGA2_DATA_DIR=/ruta/al/repositorio
```

## Cómo reproducir

Todo se reproduce siguiendo [entrega2/README.md](entrega2/README.md), en orden:
1. preparación del entorno (WSL2 + venv);
2. servicios (Docker);
3. Fases 1 a 6;
4. tests.

La bitácora [entrega2/METODOLOGIA.md](entrega2/METODOLOGIA.md) explica cada decisión y qué
script produce cada cifra.

### Datos crudos del benchmark

`entrega2/salidas/benchmark/` pesa 101 MiB en 758 archivos, así que se versiona comprimido.
Para restaurarlo, desde la raíz del repositorio:

```bash
tar -xJf entrega2/salidas/benchmark.tar.xz -C entrega2/salidas/
```

Esto deja `entrega2/salidas/benchmark/{corta,completa}/` exactamente con la estructura que
esperan `entrega2/src/benchmark_informe.py`, `entrega2/src/benchmark.py resumen` y las rutas
citadas en la bitácora. Se verificó que regenera las tablas y los gráficos idénticos.

## Dónde están los resultados

Todos están en [entrega2/informe/](entrega2/informe/):

| Resultado | Archivo |
|---|---|
| Tabla 1: tiempo y RAM por configuración, anexos por consulta y RSS base | `benchmark_resumen.md` (+ `benchmark_tiempo.csv`, `benchmark_ram.csv`, `benchmark_rss_base.csv`) |
| Tabla 2: P@5 por consulta y modelo | `tabla2_p_at_5.md` / `.csv` (revisión manual en `p_at_5_revision.csv`) |
| Tabla 3: recall relativo top-10 y costo | `tabla3_recall.md` / `.csv` |
| Boxplot de tiempos (escala log) | `benchmark_tiempo_boxplot.png` |
| Deriva: mediana por ronda | `benchmark_deriva_por_ronda.png`, `benchmark_deriva.csv` |
| Corrida completa vs. corta | `benchmark_completa_vs_corta.md` / `.csv` |
| Elección de k en LSI | `lsi_varianza_explicada.png`, `lsi_varianza.csv` |
| Validación de K-Means y LSH | `validacion_cortas_kmeans.png`, `validacion_cortas_lsh.png`, `validacion_v2_*.csv` |
| Tiempos del ETL | `etl_tiempos.csv` |

La tabla de artefactos de [METODOLOGIA.md](entrega2/METODOLOGIA.md#artefactos-para-el-informe)
indica qué script genera cada archivo.

## Nota sobre el Informe 1

`main.typ` importa la plantilla `template.typ` (plantilla UDP), que no está en el
repositorio. Para recompilarlo hay que agregarla en la raíz. La versión compilada es
`Informe_Big_Data.pdf`.
