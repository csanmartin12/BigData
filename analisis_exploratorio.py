"""
  1. Cantidad de campos por archivo.
  2. Cantidad de campos sin información por archivo.
  3. Varianza de los campos con información numérica.
  4. Cantidad de elementos distintos por campo no numérico.
  5. Cantidad de elementos con baja frecuencia (outliers) por campo no numérico.

"""

import pandas as pd
import numpy as np

IN_CSV = "headers_consolidado.csv"
OUT_XLSX = "resultados.xlsx"

LOW_FREQ_THRESHOLD = 0.01   # un valor se considera "baja frecuencia" si aparece en <1% de los archivos

df = pd.read_csv(IN_CSV, low_memory=False)
n_files = len(df)
print(f"{n_files} archivos cargados, {df.shape[1]} columnas de header")

# separar columnas propias del pipeline (no son campos FITS)
meta_cols = [c for c in df.columns if c.startswith("_source")]
data_cols = [c for c in df.columns if c not in meta_cols]

# --- 1. Campos por archivo ---
# cuenta cuántos de los campos posibles (data_cols) NO están vacíos en cada fila
campos_por_archivo = df[data_cols].notna().sum(axis=1)
campos_por_archivo.name = "n_campos_presentes"

# --- 2. Campos sin información por archivo ---
sin_info_por_archivo = df[data_cols].isna().sum(axis=1)
sin_info_por_archivo.name = "n_campos_vacios"

# --- 3. Varianza de campos numéricos ---
numeric_cols = df[data_cols].select_dtypes(include=[np.number]).columns
varianzas = df[numeric_cols].var().sort_values(ascending=False)
varianzas.name = "varianza"

# --- 4 y 5. Distintos + baja frecuencia por campo no numérico ---
nonnumeric_cols = [c for c in data_cols if c not in numeric_cols]
distintos = {}
outliers = {}
for col in nonnumeric_cols:
    vc = df[col].value_counts(dropna=True)
    distintos[col] = vc.shape[0]
    baja_frecuencia = vc[vc / n_files < LOW_FREQ_THRESHOLD]
    outliers[col] = baja_frecuencia.to_dict()

distintos_s = pd.Series(distintos, name="n_valores_distintos").sort_values(ascending=False)
outliers_df = pd.DataFrame(
    [(col, val, cnt) for col, d in outliers.items() for val, cnt in d.items()],
    columns=["campo", "valor", "n_apariciones"]
).sort_values(["campo", "n_apariciones"])

with pd.ExcelWriter(OUT_XLSX) as writer:
    campos_por_archivo.to_frame().join(sin_info_por_archivo).to_excel(writer, sheet_name="1-2_por_archivo")
    varianzas.to_frame().to_excel(writer, sheet_name="3_varianza_numericos")
    distintos_s.to_frame().to_excel(writer, sheet_name="4_distintos_no_numericos")
    outliers_df.to_excel(writer, sheet_name="5_baja_frecuencia", index=False)

print(f"Resultados guardados en {OUT_XLSX}")
print("\nResumen rápido:")
print(f"  Campos por archivo -> min {campos_por_archivo.min()}, max {campos_por_archivo.max()}, "
      f"media {campos_por_archivo.mean():.1f}")
print(f"  Campos numéricos con varianza > 0: {(varianzas > 0).sum()} / {len(varianzas)}")
print(f"  Campos no numéricos con algún valor de baja frecuencia (<{LOW_FREQ_THRESHOLD:.0%}): "
      f"{outliers_df['campo'].nunique()} / {len(nonnumeric_cols)}")
