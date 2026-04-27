import json
import pandas as pd
import tkinter as tk
from tkinter import filedialog
import sys

from procesadores.lector    import preparar_datos_hoja
from procesadores.ica       import procesar_ica
from procesadores.nom       import procesar_aire
from procesadores.diario    import procesar_diario
from almacenamiento.combinador  import combinar_con_existente
from almacenamiento.zonas       import construir_hojas_zonas
from almacenamiento.exportador  import (
    ordenar_columnas_ica,
    ordenar_columnas_aire,
    extraer_estaciones_ica,
    extraer_estaciones_aire,
    guardar_diccionario_excel,
)

# ── Configuracion ────────────────────────────────────────────────────────────
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

VENTANAS_NADF = config["NADF"]["ventanas"]
BANDAS_NADF   = {k: [tuple(v) for v in val]
                 for k, val in config["NADF"]["bandas"].items()}
VENTANAS_NOM  = config["NOM"]["ventanas"]
BANDAS_NOM    = {k: [tuple(v) for v in val]
                 for k, val in config["NOM"]["bandas"].items()}
SUFICIENCIA   = config["suficiencia"]
ORDEN_CAT     = config["orden_categorias"]
ZONAS         = config["zonas"]


# ── Seleccion de archivos ────────────────────────────────────────────────────
def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    archivo = filedialog.askopenfilename(
        title="Selecciona el archivo de datos de calidad de aire",
        filetypes=[("Archivos de Exccel", "*.xlsx"), ("All files", "*.*")]
   )
    root.destroy()
    return archivo


# ── Rutas ────────────────────────────────────────────────────────────────────
ARCHIVO_ENTRADA = seleccionar_archivo()
if not ARCHIVO_ENTRADA:
    print("No se selecciono ningun archivo.")
    exit()
    
SALIDA_ICA      = "datos/datos_calidad_aire_ICA.xlsx"
SALIDA_AIRE     = "datos/datos_calidad_aire_AIRE_Y_SALUD.xlsx"
SALIDA_DIARIO   = "datos/datos_calidad_aire_DIARIO.xlsx"

# ── Lectura ──────────────────────────────────────────────────────────────────
xls = pd.ExcelFile(ARCHIVO_ENTRADA)

df_ica_total    = pd.DataFrame()
df_aire_total   = pd.DataFrame()
df_diario_total = pd.DataFrame()

for hoja in xls.sheet_names:
    print(f"\n── Hoja: {hoja} ──")
    df = pd.read_excel(xls, sheet_name=hoja, header=None)
    estaciones, contaminantes, unidades, data_df, num_cols = preparar_datos_hoja(df)

    args = dict(
        estaciones=estaciones, contaminantes=contaminantes,
        unidades=unidades, data_df=data_df,
        num_orig_cols=num_cols, suficiencia=SUFICIENCIA,
    )

    df_ica = procesar_ica(**args, ventanas=VENTANAS_NADF, bandas=BANDAS_NADF)
    if not df_ica.empty:
        df_ica_total = pd.concat([df_ica_total, df_ica])

    df_aire = procesar_aire(**args, ventanas=VENTANAS_NOM,
                            bandas=BANDAS_NOM, orden_cat=ORDEN_CAT)
    if not df_aire.empty:
        df_aire_total = pd.concat([df_aire_total, df_aire])

    df_dia = procesar_diario(**args, ventanas=VENTANAS_NOM,
                             bandas=BANDAS_NOM, orden_cat=ORDEN_CAT)
    if not df_dia.empty:
        df_diario_total = pd.concat([df_diario_total, df_dia])

# ── ICA ───────────────────────────────────────────────────────────────────────
print("\nGuardando ICA...")
df_ica_g = combinar_con_existente(df_ica_total, SALIDA_ICA, "General", "Fecha & Hora")
df_ica_g = df_ica_g[ordenar_columnas_ica(df_ica_g)]
print(f"  Rango: {df_ica_g.index.min()} → {df_ica_g.index.max()}  |  filas: {len(df_ica_g)}")

diccionario_ica = {"General": df_ica_g}
diccionario_ica.update(extraer_estaciones_ica(df_ica_g))
diccionario_ica.update(construir_hojas_zonas(df_ica_g, ZONAS, tipo="ICA"))

guardar_diccionario_excel(SALIDA_ICA, diccionario_ica, "ICA", "Fecha & Hora")
print("  ✓ datos_calidad_aire_ICA.xlsx")
print("    Hojas:", list(diccionario_ica.keys()))

# ── AIRE Y SALUD horario ──────────────────────────────────────────────────────
print("\nGuardando AIRE Y SALUD horario...")
df_aire_g = combinar_con_existente(df_aire_total, SALIDA_AIRE, "General", "Fecha & Hora")
df_aire_g = df_aire_g[ordenar_columnas_aire(df_aire_g)]
print(f"  Rango: {df_aire_g.index.min()} → {df_aire_g.index.max()}  |  filas: {len(df_aire_g)}")

diccionario_aire = {"General": df_aire_g}
diccionario_aire.update(extraer_estaciones_aire(df_aire_g, ORDEN_CAT, SUFICIENCIA))
diccionario_aire.update(construir_hojas_zonas(
    df_aire_g, ZONAS, tipo="AIRE", orden_cat=ORDEN_CAT, suficiencia=SUFICIENCIA
))

guardar_diccionario_excel(SALIDA_AIRE, diccionario_aire, "AIRE", "Fecha & Hora")
print("  ✓ datos_calidad_aire_AIRE_Y_SALUD.xlsx")
print("    Hojas:", list(diccionario_aire.keys()))

# ── DIARIO ────────────────────────────────────────────────────────────────────
print("\nGuardando DIARIO...")
df_dia_g = combinar_con_existente(df_diario_total, SALIDA_DIARIO, "General",
                                  "Fecha", es_diario=True)
df_dia_g = df_dia_g[ordenar_columnas_aire(df_dia_g)]
print(f"  Rango: {df_dia_g.index.min()} → {df_dia_g.index.max()}  |  filas: {len(df_dia_g)}")

diccionario_diario = {"General": df_dia_g}
diccionario_diario.update(extraer_estaciones_aire(df_dia_g, ORDEN_CAT, SUFICIENCIA))
diccionario_diario.update(construir_hojas_zonas(
    df_dia_g, ZONAS, tipo="DIARIO", orden_cat=ORDEN_CAT, suficiencia=SUFICIENCIA
))

guardar_diccionario_excel(SALIDA_DIARIO, diccionario_diario, "DIARIO", "Fecha")
print("  ✓ datos_calidad_aire_DIARIO.xlsx")
print("    Hojas:", list(diccionario_diario.keys()))



"""
main.py
-------
Punto de entrada. Orquesta: config → lee hojas → procesa → combina → exporta.
Genera hojas por estacion Y por zona geografica en cada archivo de salida.
"""