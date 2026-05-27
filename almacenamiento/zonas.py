"""
almacenamiento/zonas.py
-----------------------
Genera las hojas de resumen por zona geografica para cada archivo de salida.

Zonas definidas en config.json -> "zonas":
  "Zona Metropolitana": ["AGUA SANTA", "BINE", "NINFAS", "UTP", "VELODROMO"]
  "Municipios":         ["ATLIXCO", "TEHUACAN", "TEXMELUCAN"]

Estructura de cada hoja de zona
--------------------------------
Las hojas estan pensadas para graficar barras facilmente:

  ICA / AIRE Y SALUD horario
  --------------------------
  Indice: Fecha & Hora (DatetimeIndex horario)
  Columnas: todas las de las estaciones que pertenecen a la zona,
            manteniendo el mismo orden que la hoja General.
  + columna "Calidad del aire zona" con la peor categoria NOM-172
    calculada solo sobre las estaciones de esa zona (solo AIRE/DIARIO).

  DIARIO
  ------
  Igual que arriba pero con indice diario (fecha sin hora).

Uso
---
    from almacenamiento.zonas import construir_hojas_zonas
    diccionario_ica.update(construir_hojas_zonas(df_general, zonas, tipo='ICA'))
"""

import re
import pandas as pd

from procesadores.nom import peor_categoria


# ----------------------------------------------------------------------------
# Patrones de columna (adaptados a la nueva nomenclatura) regex
# ----------------------------------------------------------------------------
_PAT_AIRE = re.compile(r"^AIRE_([^_]+)_(.+)$")
# CANTIDAD_<unidad>_<contaminante>_<estacion>
_PAT_CANT = re.compile(r"^CANTIDAD_([^_]+)_([^_]+)_(.+)$")
# ICA_<contaminante>_<estacion>
_PAT_ICA = re.compile(r"^ICA_([^_]+)_(.+)$")


def _estacion_de_columna(col: str) -> str | None:
    """Extrae el nombre de estación de una columna."""
    for pat in (_PAT_ICA, _PAT_AIRE, _PAT_CANT):
        m = pat.match(col)
        if m:
            # El ultimo grupo capturado es la estacion
            return m.group(m.lastindex)
    return None


def construir_hojas_zonas(
    df_general: pd.DataFrame,
    zonas: dict,
    tipo: str,
    orden_cat: dict | None = None,
    suficiencia: float = 0.75,
) -> dict:
    """
    Genera un sub-DataFrame por zona geografica.

    Parametros
    ----------
    df_general : pd.DataFrame
        Hoja General completa (indice DatetimeIndex, columnas de todas las estaciones)
    zonas : dict
        Mapeo { nombre_zona: [lista_estaciones] } proveniente del config.json
    tipo : str
        'ICA', 'AIRE' o 'DIARIO' (determina si se agrega la columna de calidad de zona)
    orden_cat : dict or None
        Diccionario de orden de categorias NOM (necesario para AIRE/DIARIO),
        mapeo {"Buena":0, ..., "Extremadamente mala":4}
    suficiencia : float, default=0.75
        Fraccion minima de columnas que deben tener dato para calcular
        la categoria global de la zona (solo para AIRE/DIARIO)

    Retorna
    -------
    dict
        Diccionario { nombre_zona: DataFrame } listo para anadir al
        diccionario de hojas del Excel (por ejemplo, actualizar el de ICA
        o el de AIRE). Los nombres de hoja se truncan a 31 caracteres por
        restriccion de Excel.
    """
    resultado = {}

    for nombre_zona, estaciones in zonas.items():
        # Seleccionar columnas que pertenecen a alguna estacion de la zona
        cols_zona = [
            col for col in df_general.columns if _estacion_de_columna(col) in estaciones
        ]

        if not cols_zona:
            print(f"  AVISO: ninguna columna encontrada para zona '{nombre_zona}'")
            continue

        df_zona = df_general[cols_zona].copy()

        # Agregar columna de calidad de zona (solo para AIRE/DIARIO, no para ICA)
        if tipo in ("AIRE", "DIARIO") and orden_cat:
            # Identificar columnas de categoría (empiezan con "AIRE_")
            cols_cat = [c for c in cols_zona if c.startswith("AIRE_")]
            if cols_cat:
                df_zona["Calidad del aire zona"] = peor_categoria(
                    [df_zona[c] for c in cols_cat],
                    orden_cat,
                    umbral=suficiencia,
                )

        # Truncar nombre de hoja a 31 caracteres (maximo de Excel)
        resultado[nombre_zona[:31]] = df_zona

    return resultado
