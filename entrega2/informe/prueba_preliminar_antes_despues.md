## Relevantes en el top-5 (antes → después)

| Configuración | A | B | C | D | E |
|---|---|---|---|---|---|
| TFIDF exhaustiva | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| TFIDF K-Means | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| TFIDF LSH | vacío → **5/5** | vacío → **5/5** | vacío → **5/5** | vacío → **5/5** | 5/5 |
| LSI exhaustiva | 5/5 | 0/5 | 5/5 | 1/5 | 5/5 |
| LSI K-Means | 5/5 | 0/5 | 2/2 → **5/5** | 1/5 → **0/5** | 5/5 |
| LSI LSH | 5/5 | 0/5 | 5/5 | 1/5 | 5/5 |

## Recall relativo top-10 con tolerancia / estricto (antes → después)

| Configuración | A | B | C | D | Media A–D (tol.) |
|---|---|---|---|---|---|
| TFIDF K-Means | 1.0 / 1.0 | 1.0 / 1.0 | 0.6 / 0.5 | 0.0 / 0.0 | 0.65 → **0.65** |
| TFIDF LSH | 0.0 / 0.0 → **1.0 / 0.9** | 0.0 / 0.0 → **1.0 / 1.0** | 0.0 / 0.0 → **0.5 / 0.5** | 0.0 / 0.0 | 0.00 → **0.62** |
| LSI K-Means | 1.0 / 1.0 | 1.0 / 1.0 | 0.2 / 0.2 → **0.8 / 0.7** | 0.8 / 0.8 → **1.0 / 0.2** | 0.75 → **0.95** |
| LSI LSH | 1.0 / 1.0 | 1.0 / 1.0 | 0.5 / 0.5 → **1.0 / 1.0** | 0.0 / 0.0 → **1.0 / 1.0** | 0.62 → **1.00** |

## Memoria del proceso de búsqueda (RSS, MiB)

| Momento | Antes | Después |
|---|---|---|
| Con todos los índices cargados | 109.4 | 107.9 |
| Tras las 30 consultas | 111.8 | 116.1 |
| Pico (VmHWM) | 211.8 | 211.7 |
