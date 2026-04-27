"""
procesadores/diario.py
----------------------
Reporte **diario** del Índice AIRE Y SALUD según NOM-172-SEMARNAT-2023,
sección 5.1.2.3 (segunda parte) y Tabla 3:

  PM10, PM2.5  → promedio de 24 h (con suficiencia ≥ 75 % de horas)
  CO           → máximo del promedio móvil de 8 h registrado en el día
  O3, NO2, SO2 → máximo del promedio horario registrado en el día

Los nombres de columna incluyen la unidad del contaminante:
    AIRE_<unidad>_<contaminante>_<estacion>
    CANTIDAD_<unidad>_<contaminante>_<estacion>
"""

import numpy as np
import pandas as pd

from procesadores.ica import promedio_movil_simple
from procesadores.nom import (
    clasificar_nom,
    redondear_nom,
    peor_categoria,
    UNIDAD_DISPLAY,
    descartar_cero_por_redondeo
)


def procesar_diario(
    estaciones:    np.ndarray,
    contaminantes: np.ndarray,
    unidades:      np.ndarray,
    data_df:       pd.DataFrame,
    num_orig_cols: int,
    ventanas:      dict,
    bandas:        dict,
    orden_cat:     dict,
    suficiencia:   float,
) -> pd.DataFrame:
    """
    Genera un DataFrame con un registro por día calendario.

    Parámetros
    ----------
    (mismos que procesar_aire)

    Retorna
    -------
    DataFrame con índice DatetimeIndex diario (sin hora), columnas
    AIRE_<unidad>_<cont>_<est>, CANTIDAD_<unidad>_<cont>_<est>
    y "Calidad del aire".
    """
    dias_ordenados = sorted(pd.to_datetime(data_df.index.normalize().unique()))
    df_dia = pd.DataFrame(index=dias_ordenados)

    for i in range(1, num_orig_cols):
        col_in_data  = i - 1
        estacion     = estaciones[i]
        contaminante = contaminantes[i]
        unidad       = unidades[i]

        if isinstance(contaminante, str): contaminante = contaminante.strip()
        if isinstance(unidad, str):       unidad       = unidad.strip()
        if isinstance(estacion, str):     estacion     = estacion.strip()

        if not isinstance(contaminante, str) or contaminante == "Status":
            continue

        clave_orig = f"{contaminante}_{unidad}"
        if clave_orig not in ventanas:
            continue

        etiqueta_unidad = UNIDAD_DISPLAY.get(clave_orig, unidad)

        valores = pd.to_numeric(data_df.iloc[:, col_in_data], errors="coerce")

        # Filtrar por status "Ok"
        if i + 1 < num_orig_cols:
            status_str = data_df.iloc[:, i].astype(str).str.strip().str.lower()
            valores    = valores.where(status_str == "ok", np.nan)

        valores       = valores.where(valores >= 0, np.nan)
        serie_valores = pd.Series(valores.values, index=data_df.index)

        # ── Concentración diaria representativa (NOM-172-2023 Tabla 3) ───────
        if clave_orig in ("PM10_ug/m3", "PM2.5_ug/m3"):
            # Promedio de 24 h con suficiencia mínima
            min_horas    = int(np.ceil(24 * suficiencia))
            valor_diario = serie_valores.resample("D").apply(
                lambda x: x.mean() if x.count() >= min_horas else np.nan
            )
            valor_redondeado = valor_diario.apply(
                lambda v: int(round(v)) if not pd.isna(v) else np.nan
            )
            clave_bandas = clave_orig

        elif clave_orig == "CO_ppm":
            # Máximo del promedio móvil de 8 h
            prom_8h      = promedio_movil_simple(serie_valores, 8, suficiencia)
            valor_diario = prom_8h.resample("D").max()
            valor_redondeado = valor_diario.apply(
                lambda v: round(v, 2) if not pd.isna(v) else np.nan
            )
            clave_bandas = "CO_ppm"

        else:
            # O3, NO2, SO2: máximo del promedio horario (convertido a ppm)
            serie_ppm    = serie_valores / 1000.0
            valor_diario = serie_ppm.resample("D").max()
            valor_redondeado = valor_diario.apply(
                lambda v: round(v, 3) if not pd.isna(v) else np.nan
            )
            clave_bandas = f"{contaminante}_ppm"

                # ... determinas clave_bandas, valor_redondeado, etc. como antes ...
        if clave_bandas not in bandas:
            continue

        # --- AQUÍ SE APLICA EL DESCARTE (dentro del bucle) ---
        # Determinar decimales según el contaminante
        if clave_orig in ("PM10_ug/m3", "PM2.5_ug/m3"):
            decimales = 0
        elif clave_orig == "CO_ppm":
            decimales = 2
        else:
            decimales = 3
        # Aplicar descarte
        valor_redondeado = valor_redondeado.apply(lambda v: descartar_cero_por_redondeo(v, decimales))
        # Recalcular categorías con los valores ya descartados
        categorias = [clasificar_nom(v, bandas[clave_bandas]) for v in valor_redondeado]
        # --- fin del descarte ---

        col_cat = f"AIRE_{etiqueta_unidad}_{contaminante}_{estacion}"
        col_cant = f"CANTIDAD_{etiqueta_unidad}_{contaminante}_{estacion}"
        df_dia[col_cat] = categorias
        df_dia[col_cant] = valor_redondeado.values

    df_dia = df_dia.dropna(how="all")

    # Calidad del aire global diaria
    if not df_dia.empty:
        cols_cat = [c for c in df_dia.columns if c.startswith("AIRE_")]
        if cols_cat:
            df_dia["Calidad del aire"] = peor_categoria(
                [df_dia[c] for c in cols_cat],
                orden_cat,
                umbral=0.0,
            )

    return df_dia