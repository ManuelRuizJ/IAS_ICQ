import pandas as pd
from pathlib import Path

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
    xl = pd.ExcelFile(p)
    for hoja in xl.sheet_names:
        df = pd.read_excel(p, sheet_name=hoja)
        # Buscar columnas de cantidad (CANTIDAD_...)
        cols_cant = [c for c in df.columns if c.startswith("CANTIDAD_")]
        if not cols_cant:
            continue
        # Contar ceros exactos en esas columnas
        cero_count = 0
        for col in cols_cant:
            # Filtrar valores no nulos y que sean igual a 0
            cero_count += (df[col].notna() & (df[col] == 0)).sum()
        if cero_count > 0:
            print(
                f"{archivo} - hoja '{hoja}': cantidad de ceros en columnas de cantidad = {cero_count}"
            )
        else:
            print(f"{archivo} - hoja '{hoja}': ✅ sin ceros en columnas de cantidad")
