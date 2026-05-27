"""
procesadores/diario.py
----------------------
Reporte **diario** del Indice AIRE Y SALUD segun NOM-172-SEMARNAT-2023,
seccion 5.1.2.3 (segunda parte) y Tabla 3:

  PM10, PM2.5  → promedio de 24 h (con suficiencia >= 75 % de horas)
  CO           → maximo del promedio movil de 8 h registrado en el dia
  O3, NO2, SO2 → maximo del promedio horario registrado en el dia

Los nombres de columna incluyen la unidad del contaminante:
    AIRE_<unidad>_<contaminante>_<estacion>
    CANTIDAD_<unidad>_<contaminante>_<estacion>
"""

import numpy as np
import pandas as pd

from procesadores.ica import promedio_movil_simple
from procesadores.nom import (
    clasificar_nom,
    peor_categoria,
    UNIDAD_DISPLAY,
    descartar_cero_por_redondeo,
)


def procesar_diario(
    estaciones: np.ndarray,
    contaminantes: np.ndarray,
    unidades: np.ndarray,
    data_df: pd.DataFrame,
    num_orig_cols: int,
    ventanas: dict,
    bandas: dict,
    orden_cat: dict,
    suficiencia: float,
) -> pd.DataFrame:
    """
    Genera un DataFrame con un registro por dia calendario.

    Parametros
    ----------
    estaciones : np.ndarray
        Nombres de estacion por columna
    contaminantes : np.ndarray
        Nombre del contaminante por columna
    unidades : np.ndarray
        Unidad de medida por columna
    data_df : pd.DataFrame
        Datos horarios con indice DatetimeIndex
    num_orig_cols : int
        Numero total de columnas en el Excel original (incluye fecha/hora)
    ventanas : dict
        Mapeo "contaminante_unidad" -> ventana (aqui solo se usa para saber
        si el contaminante esta presente en la configuracion)
    bandas : dict
        Mapeo "contaminante_unidad" -> lista de bandas de clasificacion
    orden_cat : dict
        Orden numerico de categorias (Buena=0 ... Extremadamente mala=4)
    suficiencia : float
        Fraccion minima de datos validos para promedios (ej. 0.75 para 24h)

    Retorna
    -------
    pd.DataFrame
        DataFrame con indice diario (sin hora), columnas AIRE_*, CANTIDAD_*
        y "Calidad del aire". Si no hay datos, DataFrame vacio.
    """
    # Obtener lista de dias unicos ordenados (normaliza eliminando la hora)
    dias_ordenados = sorted(pd.to_datetime(data_df.index.normalize().unique()))
    df_dia = pd.DataFrame(index=dias_ordenados)

    # Iterar sobre columnas (i=1 salta la columna de fecha/hora)
    for i in range(1, num_orig_cols):
        col_in_data = i - 1
        estacion = estaciones[i]
        contaminante = contaminantes[i]
        unidad = unidades[i]

        # Limpiar espacios en blanco
        if isinstance(contaminante, str):
            contaminante = contaminante.strip()
        if isinstance(unidad, str):
            unidad = unidad.strip()
        if isinstance(estacion, str):
            estacion = estacion.strip()

        # Saltar columnas no contaminantes (ej. "Status")
        if not isinstance(contaminante, str) or contaminante == "Status":
            continue

        clave_orig = f"{contaminante}_{unidad}"
        if clave_orig not in ventanas:
            continue
        
        # Unidad para mostrar en el nombre de columna (ej. "ppm" para O3_ppb)
        etiqueta_unidad = UNIDAD_DISPLAY.get(clave_orig, unidad)

        # Extraer y limpiar la serie horaria
        valores = pd.to_numeric(data_df.iloc[:, col_in_data], errors="coerce")

        # Filtrar por status "Ok" (si existe columna de status a la derecha)
        if i + 1 < num_orig_cols:
            status_str = data_df.iloc[:, i].astype(str).str.strip().str.lower()
            valores = valores.where(status_str == "ok", np.nan)

        # Descartar valores negativos (no fisicos)
        valores = valores.where(valores >= 0, np.nan)
        serie_valores = pd.Series(valores.values, index=data_df.index)

        # =====================================================================
        # Calcular la concentracion diaria representativa segun Tabla 3 NOM-172
        # =====================================================================
        if clave_orig in ("PM10_ug/m3", "PM2.5_ug/m3"):
            # PM10 y PM2.5: promedio de 24 horas con suficiencia minima
            min_horas = int(np.ceil(24 * suficiencia))
            valor_diario = serie_valores.resample("D").apply(
                lambda x: x.mean() if x.count() >= min_horas else np.nan
            )
            valor_redondeado = valor_diario.apply(
                lambda v: int(round(v)) if not pd.isna(v) else np.nan
            )
            clave_bandas = clave_orig

        elif clave_orig == "CO_ppm":
            # CO: maximo del promedio movil de 8 horas en el dia
            prom_8h = promedio_movil_simple(serie_valores, 8, suficiencia)
            valor_diario = prom_8h.resample("D").max()
            valor_redondeado = valor_diario.apply(
                lambda v: round(v, 2) if not pd.isna(v) else np.nan
            )
            clave_bandas = "CO_ppm"

        else:
            # O3, NO2, SO2: maximo del promedio horario (convertir de ppb a ppm)
            serie_ppm = serie_valores / 1000.0
            valor_diario = serie_ppm.resample("D").max()
            valor_redondeado = valor_diario.apply(
                lambda v: round(v, 3) if not pd.isna(v) else np.nan
            )
            clave_bandas = f"{contaminante}_ppm"

        if clave_bandas not in bandas:
            continue

        # ====================================================================
        # Descartar ceros por redondeo (valores que redondean a cero no son
        # fisicos y se tratan como datos faltantes)
        # ====================================================================
        if clave_orig in ("PM10_ug/m3", "PM2.5_ug/m3"):
            decimales = 0
        elif clave_orig == "CO_ppm":
            decimales = 2
        else:
            decimales = 3

        valor_redondeado = valor_redondeado.apply(
            lambda v: descartar_cero_por_redondeo(v, decimales)
        )

        categorias = [clasificar_nom(v, bandas[clave_bandas]) for v in valor_redondeado]


        # ====================================================================
        # Construir columnas de salida
        # ====================================================================
        col_cat = f"AIRE_{contaminante}_{estacion}"
        col_cant = f"CANTIDAD_{etiqueta_unidad}_{contaminante}_{estacion}"

        df_dia[col_cat] = categorias
        df_dia[col_cant] = valor_redondeado.values

    # Eliminar filas completamente vacias (sin ningun contaminante ese dia)
    df_dia = df_dia.dropna(how="all")

    
    # ========================================================================
    # Columna global "Calidad del aire": peor categoria diaria entre todos
    # los contaminantes y estaciones de ese dia.
    # ========================================================================
    if not df_dia.empty:
        cols_cat = [c for c in df_dia.columns if c.startswith("AIRE_")]
        if cols_cat:
            df_dia["Calidad del aire"] = peor_categoria(
                [df_dia[c] for c in cols_cat],
                orden_cat,
                umbral=0.0,
            )

    return df_dia
