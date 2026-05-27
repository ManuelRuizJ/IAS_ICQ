"""
verificacion_de_ceros.py
------------------------
Script de verificacion que revisa los archivos Excel de salida en busca de
ceros exactos en las columnas de cantidad (CANTIDAD_*).

Un cero en estas columnas puede indicar datos erroneos (por ejemplo,
concentraciones de ozono que deberian ser no detectables o valores
redondeados a cero). La NOM-172 y NADF-009 recomiendan tratar ceros
como datos faltantes (NaN) cuando son producto de redondeo.

Uso:
    python verificacion_de_ceros.py

Nota: Este script es auxiliar para depuracion; no modifica los archivos.
"""

import pandas as pd
from pathlib import Path

# Lista de archivos de salida generados por main.py
archivos = [
    "datos/datos_calidad_aire_ICA.xlsx",
    "datos/datos_calidad_aire_AIRE_Y_SALUD.xlsx",
    "datos/datos_calidad_aire_DIARIO_IAS.xlsx",
    "datos/datos_calidad_aire_DIARIO_ICA.xlsx",
]

for archivo in archivos:
    p = Path(archivo)
    if not p.exists():
        print(f"{archivo} no existe")
        continue

    # Leer todas las hojas del Excel
    xl = pd.ExcelFile(p)
    for hoja in xl.sheet_names:
        df = pd.read_excel(p, sheet_name=hoja)

        # Identificar columnas que representan concentraciones (CANTIDAD_*)
        cols_cant = [c for c in df.columns if c.startswith("CANTIDAD_")]
        if not cols_cant:
            continue

        # Contar cuantas celdas contienen un cero exacto (no nulo y valor 0)
        cero_count = 0
        for col in cols_cant:
            # Se cuentan solo los ceros, ignorando NaN
            cero_count += (df[col].notna() & (df[col] == 0)).sum()

        if cero_count > 0:
            print(
                f"{archivo} - hoja '{hoja}': cantidad de ceros en columnas de cantidad = {cero_count}"
            )
        else:
            print(f"{archivo} - hoja '{hoja}': ✅ sin ceros en columnas de cantidad")