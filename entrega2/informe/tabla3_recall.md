## Tabla 3 — Recall relativo top-10 frente a la exhaustiva del mismo modelo (con tolerancia / estricto)

| Consulta | TF-IDF + K-Means (c = 32, n_probe = 1) | TF-IDF + LSH (b = 2, L = 8, centrado) | LSI + K-Means (c = 32, n_probe = 1) | LSI + LSH (b = 2, L = 8, centrado) |
|---|---:|---:|---:|---:|
| A | 1,0 / 1,0 | 1,0 / 0,9 | 1,0 / 1,0 | 1,0 / 1,0 |
| B | 1,0 / 1,0 | 1,0 / 1,0 | 1,0 / 1,0 | 1,0 / 1,0 |
| C | 0,6 / 0,5 | 0,5 / 0,5 | 0,8 / 0,7 | 1,0 / 1,0 |
| D | 0,0 / 0,0 | 0,0 / 0,0 | 1,0 / 0,2 | 1,0 / 1,0 |
| E | 1,0 / 1,0 | 1,0 / 1,0 | 1,0 / 1,0 | 1,0 / 1,0 |
| **Promedio A–E** | **0,72** / 0,70 | **0,70** / 0,68 | **0,96** / 0,78 | **1,00** / 1,00 |
| **Promedio A–D** | **0,65** / 0,62 | **0,62** / 0,60 | **0,95** / 0,72 | **1,00** / 1,00 |

## Tabla 3 (referencia, sin cronometrar) — K-Means n_probe = 2 y LSH elegido con documentos completos

| Consulta | TF-IDF + K-Means (c = 32, n_probe = 2) [ref.] | TF-IDF + LSH (b = 16, L = 16, centrado; elegido con documentos) [ref.] | LSI + K-Means (c = 32, n_probe = 2) [ref.] | LSI + LSH (b = 16, L = 1, centrado; elegido con documentos) [ref.] |
|---|---:|---:|---:|---:|
| A | 1,0 / 1,0 | 0,1 / 0,1 | 1,0 / 1,0 | 0,0 / 0,0 |
| B | 1,0 / 1,0 | 0,0 / 0,0 | 1,0 / 1,0 | 0,0 / 0,0 |
| C | 1,0 / 1,0 | 0,0 / 0,0 | 1,0 / 1,0 | 0,0 / 0,0 |
| D | 0,0 / 0,0 | 0,0 / 0,0 | 1,0 / 1,0 | 0,0 / 0,0 |
| E | 1,0 / 1,0 | 1,0 / 1,0 | 1,0 / 1,0 | 1,0 / 1,0 |
| **Promedio A–E** | **0,80** / 0,80 | **0,22** / 0,22 | **1,00** / 1,00 | **0,20** / 0,20 |
| **Promedio A–D** | **0,75** / 0,75 | **0,03** / 0,03 | **1,00** / 1,00 | **0,00** / 0,00 |

## Costo (documentos con coseno exacto) y recall de validación

| Configuración | Examinados A / B / C / D | Costo medio A–D | Validación cortas: recall / costo | Validación documentos: recall / costo |
|---|---|---:|---|---|
| TF-IDF + K-Means (c = 32, n_probe = 1) | 100 de 433 / 100 de 1861 / 30 de 1861 / 30 de 1861 | 0,079 | 0,883 / 0,042 | 0,981 / 0,046 |
| TF-IDF + LSH (b = 2, L = 8, centrado) | 376 de 433 / 1742 de 1861 / 1308 de 1861 / 1598 de 1861 | 0,841 | 0,952 / 0,829 | 1,000 / 0,752 |
| TF-IDF + K-Means (c = 32, n_probe = 2) [ref.] | 100 de 433 / 135 de 1861 / 65 de 1861 / 108 de 1861 | 0,099 | 0,912 / 0,073 | 0,998 / 0,080 |
| TF-IDF + LSH (b = 16, L = 16, centrado; elegido con documentos) [ref.] | 48 de 433 / 45 de 1861 / 30 de 1861 / 48 de 1861 | 0,044 | 0,141 / 0,046 | 0,948 / 0,091 |
| LSI + K-Means (c = 32, n_probe = 1) | 100 de 433 / 100 de 1861 / 32 de 1861 / 73 de 1861 | 0,085 | 0,880 / 0,041 | 0,985 / 0,043 |
| LSI + LSH (b = 2, L = 8, centrado) | 327 de 433 / 1539 de 1861 / 1696 de 1861 / 1735 de 1861 | 0,856 | 0,914 / 0,871 | 1,000 / 0,852 |
| LSI + K-Means (c = 32, n_probe = 2) [ref.] | 111 de 433 / 116 de 1861 / 65 de 1861 / 167 de 1861 | 0,111 | 0,925 / 0,073 | 1,000 / 0,072 |
| LSI + LSH (b = 16, L = 1, centrado; elegido con documentos) [ref.] | 1 de 433 / 6 de 1861 / 0 de 1861 / 20 de 1861 | 0,004 | 0,232 / 0,012 | 0,940 / 0,024 |

En E todas las configuraciones resuelven el mismo filtro de MongoDB (sin índice vectorial): su recall es 1 por construcción.

