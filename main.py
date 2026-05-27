"""
main.py
-------

Flujo general:
  1. Leer configuracion desde config.json
  2. Pedir al usuario que seleccione el archivo Excel de entrada (dialogo grafico)
  3. Por cada hoja del archivo: leer, limpiar fechas y calcular ICA, IAS horario,
     IAS diario e ICA diario
  4. Combinar los resultados con los archivos de salida existentes (base de datos)
  5. Exportar los cuatro archivos Excel de salida con hojas por estacion y zona

Archivos de salida (carpeta datos/):
  datos_calidad_aire_ICA.xlsx          - ICA horario    (NADF-009-AIRE-2017)
  datos_calidad_aire_AIRE_Y_SALUD.xlsx - IAS horario    (NOM-172-SEMARNAT-2023)
  datos_calidad_aire_DIARIO_IAS.xlsx   - IAS diario     (NOM-172-SEMARNAT-2023)
  datos_calidad_aire_DIARIO_ICA.xlsx   - ICA diario     (NADF-009-AIRE-2017)
"""


import json
import pandas as pd
import tkinter as tk
from tkinter import filedialog

from procesadores.lector import preparar_datos_hoja
from procesadores.ica import procesar_ica
from procesadores.nom import procesar_aire
from procesadores.diario import procesar_diario
from procesadores.diario_ica import procesar_ica_diario

from almacenamiento.combinador import combinar_con_existente
from almacenamiento.zonas import construir_hojas_zonas
from almacenamiento.exportador import (
    ordenar_columnas_ica,
    ordenar_columnas_aire,
    extraer_estaciones_ica,
    extraer_estaciones_aire,
    guardar_diccionario_excel,
)

# ============================================================================
# CONFIGURACION
# Carga todos los parametros desde config.json para no tener valores
# fijos dentro del codigo. Cambiar bandas, ventanas o zonas solo requiere
# editar el archivo JSON, sin tocar el codigo Python.
# ============================================================================
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# Ventanas de tiempo y bandas de calculo para el ICA (NADF-009-AIRE-2017)
VENTANAS_NADF = config["NADF"]["ventanas"]
BANDAS_NADF = {
    k: [tuple(v) for v in val] for k, val in config["NADF"]["bandas"].items()
}

# Ventanas de tiempo y bandas de calculo para el IAS (NOM-172-SEMARNAT-2023)
VENTANAS_NOM = config["NOM"]["ventanas"]
BANDAS_NOM = {k: [tuple(v) for v in val] for k, val in config["NOM"]["bandas"].items()}

# Fraccion minima de datos validos requerida para calcular un valor representativo
SUFICIENCIA = config["suficiencia"]

# Orden numerico de las categorias IAS (Buena=0 ... Extremadamente mala=4)
ORDEN_CAT = config["orden_categorias"]

# Agrupacion de estaciones por zona geografica
# Zona Metropolitana: Agua Santa, BINE, Ninfas, UTP, Velodromo
# Municipios: Atlixco, Tehuacan, Texmelucan
ZONAS = config["zonas"]



# ============================================================================
# SELECCION DEL ARCHIVO DE ENTRADA
# Se usa un dialogo grafico de tkinter para que el usuario seleccione
# el archivo Excel.
# La ventana principal de tkinter se oculta inmediatamente (withdraw)
# para mostrar solo el dialogo de seleccion de archivo.
# ============================================================================
def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    archivo = filedialog.askopenfilename(
        title="Selecciona el archivo de datos de calidad de aire",
        filetypes=[("Archivos de Exccel", "*.xlsx"), ("All files", "*.*")],
    )
    root.destroy()
    return archivo



# ============================================================================
# RUTAS
# ============================================================================
ARCHIVO_ENTRADA = seleccionar_archivo()
if not ARCHIVO_ENTRADA:
    print("No se selecciono ningun archivo.")
    exit()

# Los archivos de salida actuan como base de datos acumulativa:
# cada ejecucion agrega los nuevos datos sin borrar los anteriores.
# La fecha es el identificador unico; en caso de colision gana el dato nuevo.
SALIDA_ICA = "datos/datos_calidad_aire_ICA.xlsx"
SALIDA_AIRE = "datos/datos_calidad_aire_AIRE_Y_SALUD.xlsx"
SALIDA_DIARIO = "datos/datos_calidad_aire_DIARIO_IAS.xlsx"
SALIDA_ICA_DIARIO = "datos/datos_calidad_aire_DIARIO_ICA.xlsx"



# ============================================================================
# LECTURA Y PROCESAMIENTO
# Se itera sobre cada hoja del archivo de entrada.
# El software exportador puede generar una o varias hojas por archivo;
# el sistema las procesa todas y acumula los resultados en DataFrames totales.
# ============================================================================
xls = pd.ExcelFile(ARCHIVO_ENTRADA)

# DataFrames acumuladores: se van llenando con el resultado de cada hoja
df_ica_total = pd.DataFrame()
df_aire_total = pd.DataFrame()
df_diario_total = pd.DataFrame()
df_diario_ica_total = pd.DataFrame()

for hoja in xls.sheet_names:
    print(f"\n── Hoja: {hoja} ──")

    # Leer la hoja sin encabezados para que preparar_datos_hoja detecte
    # la estructura automaticamente (estaciones, contaminantes, unidades)
    df = pd.read_excel(xls, sheet_name=hoja, header=None)
    estaciones, contaminantes, unidades, data_df, num_cols = preparar_datos_hoja(df)

    # Argumentos comunes a todos los procesadores
    args = dict(
        estaciones=estaciones,
        contaminantes=contaminantes,
        unidades=unidades,
        data_df=data_df,
        num_orig_cols=num_cols,
        suficiencia=SUFICIENCIA,
    )

    # ICA horario: promedio movil segun ventana NADF + calculo del indice
    df_ica = procesar_ica(**args, ventanas=VENTANAS_NADF, bandas=BANDAS_NADF)
    if not df_ica.empty:
        df_ica_total = pd.concat([df_ica_total, df_ica])

    # IAS horario: NowCast 12h para PM, promedio movil 8h para CO,
    # promedio horario para gases; clasifica en categoria NOM-172
    df_aire = procesar_aire(
        **args, ventanas=VENTANAS_NOM, bandas=BANDAS_NOM, orden_cat=ORDEN_CAT
    )
    if not df_aire.empty:
        df_aire_total = pd.concat([df_aire_total, df_aire])

    # IAS diario: promedio 24h para PM, maximo 8h para CO,
    # maximo horario para gases; clasifica en categoria NOM-172
    df_dia = procesar_diario(
        **args, ventanas=VENTANAS_NOM, bandas=BANDAS_NOM, orden_cat=ORDEN_CAT
    )
    if not df_dia.empty:
        df_diario_total = pd.concat([df_diario_total, df_dia])

     # ICA diario: maximo ICA del dia por estacion (no se promedian valores ICA)
    df_dia_ica = procesar_ica_diario(**args, ventanas=VENTANAS_NADF, bandas=BANDAS_NADF)
    if not df_dia_ica.empty:
        df_diario_ica_total = pd.concat([df_diario_ica_total, df_dia_ica])



# ============================================================================
# EXPORTACION — ICA HORARIO
# Estructura de hojas en el Excel de salida:
#   General                             - todos los contaminantes y estaciones
#   <ESTACION>                          - columnas de esa estacion solamente (una hoja por estacion)
#   Zona Metropolitana / Municipios     - agrupacion geografica
# ============================================================================
print("\nGuardando ICA...")
df_ica_g = combinar_con_existente(df_ica_total, SALIDA_ICA, "General", "Fecha & Hora")
df_ica_g = df_ica_g[ordenar_columnas_ica(df_ica_g)]
print(
    f"  Rango: {df_ica_g.index.min()} → {df_ica_g.index.max()}  |  filas: {len(df_ica_g)}"
)

diccionario_ica = {"General": df_ica_g}
diccionario_ica.update(extraer_estaciones_ica(df_ica_g))
diccionario_ica.update(construir_hojas_zonas(df_ica_g, ZONAS, tipo="ICA"))

guardar_diccionario_excel(SALIDA_ICA, diccionario_ica, "ICA", "Fecha & Hora")
print("  ✓ datos_calidad_aire_ICA.xlsx")
print("    Hojas:", list(diccionario_ica.keys()))




# ============================================================================
# EXPORTACION — IAS HORARIO (AIRE Y SALUD)
# Cada par de columnas representa un contaminante en una estacion:
#   AIRE_<cont>_<estacion>     - categoria NOM-172 (texto)
#   CANTIDAD_<cont>_<estacion> - concentracion numerica redondeada
# Al final de cada hoja aparece la columna "Calidad del aire" con
# la peor categoria entre todos los contaminantes de esa estacion.
# ============================================================================
print("\nGuardando AIRE Y SALUD horario...")
df_aire_g = combinar_con_existente(
    df_aire_total, SALIDA_AIRE, "General", "Fecha & Hora"
)
df_aire_g = df_aire_g[ordenar_columnas_aire(df_aire_g)]
print(
    f"  Rango: {df_aire_g.index.min()} → {df_aire_g.index.max()}  |  filas: {len(df_aire_g)}"
)

diccionario_aire = {"General": df_aire_g}
diccionario_aire.update(extraer_estaciones_aire(df_aire_g, ORDEN_CAT, SUFICIENCIA))
diccionario_aire.update(
    construir_hojas_zonas(
        df_aire_g, ZONAS, tipo="AIRE", orden_cat=ORDEN_CAT, suficiencia=SUFICIENCIA
    )
)

guardar_diccionario_excel(SALIDA_AIRE, diccionario_aire, "AIRE", "Fecha & Hora")
print("  ✓ datos_calidad_aire_AIRE_Y_SALUD.xlsx")
print("    Hojas:", list(diccionario_aire.keys()))




# ============================================================================
# EXPORTACION — IAS DIARIO
# Un registro por dia calendario. La concentracion representativa
# sigue NOM-172-2023 Tabla 3 (promedio 24h, maximo 8h o maximo horario
# segun el contaminante). Se usa es_diario=True porque la fecha se
# almacena como columna en lugar de indice en el archivo existente.
# ============================================================================
print("\nGuardando DIARIO...")
df_dia_g = combinar_con_existente(
    df_diario_total, SALIDA_DIARIO, "General", "Fecha", es_diario=True
)
df_dia_g = df_dia_g[ordenar_columnas_aire(df_dia_g)]
print(
    f"  Rango: {df_dia_g.index.min()} → {df_dia_g.index.max()}  |  filas: {len(df_dia_g)}"
)

diccionario_diario = {"General": df_dia_g}
diccionario_diario.update(extraer_estaciones_aire(df_dia_g, ORDEN_CAT, SUFICIENCIA))
diccionario_diario.update(
    construir_hojas_zonas(
        df_dia_g, ZONAS, tipo="DIARIO", orden_cat=ORDEN_CAT, suficiencia=SUFICIENCIA
    )
)

guardar_diccionario_excel(SALIDA_DIARIO, diccionario_diario, "DIARIO", "Fecha")
print("  ✓ datos_calidad_aire_DIARIO.xlsx")
print("    Hojas:", list(diccionario_diario.keys()))



# ============================================================================
# EXPORTACION — ICA DIARIO (NADF-009)
# Un registro por dia. Cada columna contiene el maximo ICA registrado
# en ese dia para un par (contaminante, estacion).
# Se usa es_diario=False porque el DataFrame ya tiene un DatetimeIndex
# con fechas sin hora (no es necesario convertir columna a indice).
# ============================================================================
print("\nGuardando DIARIO ICA...")
df_ica_d_general = combinar_con_existente(
    df_diario_ica_total, SALIDA_ICA_DIARIO, "General", "Fecha", es_diario=False
)
df_ica_d_general = df_ica_d_general[ordenar_columnas_ica(df_ica_d_general)]
print(
    f"  Rango: {df_ica_d_general.index.min()} → {df_ica_d_general.index.max()}  |  filas: {len(df_ica_d_general)}"
)

diccionario_ica_d = {"General": df_ica_d_general}
diccionario_ica_d.update(extraer_estaciones_ica(df_ica_d_general))
diccionario_ica_d.update(construir_hojas_zonas(df_ica_d_general, ZONAS, tipo="ICA"))

guardar_diccionario_excel(SALIDA_ICA_DIARIO, diccionario_ica_d, "ICA", "Fecha")
print("  ✓ datos_calidad_aire_DIARIO_ICA.xlsx")
print("    Hojas:", list(diccionario_ica_d.keys()))

