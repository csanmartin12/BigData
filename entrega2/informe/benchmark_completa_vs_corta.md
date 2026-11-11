## Deriva: mediana del primer vs. el último cuarto de las rondas (ms)

| Configuración | Primer cuarto | Último cuarto | Cambio | ¿> 10 %? |
|---|---:|---:|---:|---|
| TF-IDF | 2,482 | 2,489 | 0,3 % | no |
| TF-IDF + K-Means | 0,856 | 0,915 | 6,9 % | no |
| TF-IDF + LSH | 5,253 | 5,293 | 0,8 % | no |
| LSI | 0,737 | 0,780 | 5,8 % | no |
| LSI + K-Means | 0,655 | 0,733 | 11,9 % | **sí** |
| LSI + LSH | 0,998 | 1,070 | 7,2 % | no |

Pares (configuración × consulta) con cambio > 10 %: LSI C (11,6 %), LSI E (10,8 %), LSI + K-Means D (10,6 %)

## Medianas: corrida completa (100.000 rep.) vs. corta (2.000 rep.). ms

| Configuración | Corta | Completa | Cambio | Por consulta A / B / C / D / E (completa) |
|---|---:|---:|---:|---|
| TF-IDF | 2,485 | 2,488 | 0,1 % | 4,22 / 2,47 / 2,52 / 2,47 / 1,01 |
| TF-IDF + K-Means | 0,821 | 0,896 | 9,2 % | 2,50 / 0,85 / 0,65 / 0,65 / 1,02 |
| TF-IDF + LSH | 5,231 | 5,322 | 1,8 % | 4,41 / 9,03 / 5,14 / 5,99 / 1,01 |
| LSI | 0,647 | 0,784 | 21,1 % | 2,10 / 0,64 / 0,66 / 0,67 / 1,01 |
| LSI + K-Means | 0,658 | 0,722 | 9,8 % | 2,12 / 0,60 / 0,60 / 0,59 / 1,01 |
| LSI + LSH | 0,960 | 1,046 | 9,0 % | 2,44 / 0,97 / 1,01 / 1,04 / 1,01 |
