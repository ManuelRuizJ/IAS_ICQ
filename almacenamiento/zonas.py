"""
almacenamiento/zonas.py
-----------------------
Genera las hojas de resumen por zona geográfica para cada archivo de salida.

Zonas definidas en config.json → "zonas":
  "Zona Metropolitana": ["AGUA SANTA", "BINE", "NINFAS", "UTP", "VELODROMO"]
  "Municipios":         ["ATLIXCO", "TEHUACAN", "TEXMELUCAN"]

Estructura de cada hoja de zona
--------------------------------
Las hojas están pensadas para graficar barras fácilmente:

  ICA / AIRE Y SALUD horario
  ──────────────────────────
  Índice: Fecha & Hora (DatetimeIndex horario)
  Columnas: todas las de las estaciones que pertenecen a la zona,
            manteniendo el mismo orden que la hoja General.
  + columna "Calidad del aire zona" con la peor categoría NOM-172
    calculada solo sobre las estaciones de esa zona (solo AIRE/DIARIO).

  DIARIO
  ──────
  Igual que arriba pero con índice diario (fecha sin hora).

Uso
---
    from almacenamiento.zonas import construir_hojas_zonas
    diccionario_ica.update(construir_hojas_zonas(df_general, zonas, tipo='ICA'))
"""

import re
import pandas as pd

from procesadores.nom import peor_categoria


# Patrones de columna (mismos que en exportador.py)
_PAT_AIRE = re.compile(r"^AIRE_([^_]+)_([^_]+)_(.+)$")
_PAT_CANT = re.compile(r"^CANTIDAD_([^_]+)_([^_]+)_(.+)$")
_PAT_ICA = re.compile(r"^ICA_([^_]+)_(.+)$")


def _estacion_de_columna(col: str) -> str | None:
    """Extrae el nombre de estación de una columna, sea ICA, AIRE o CANTIDAD."""
    for pat in (_PAT_ICA, _PAT_AIRE, _PAT_CANT):
        m = pat.match(col)
        if m:
            return m.group(m.lastindex)  # último grupo capturado = estación
    return None


def construir_hojas_zonas(
    df_general: pd.DataFrame,
    zonas: dict,
    tipo: str,
    orden_cat: dict | None = None,
    suficiencia: float = 0.75,
) -> dict:
    """
    Genera un sub-DataFrame por zona geográfica.

    Parámetros
    ----------
    df_general  : hoja General completa (índice DatetimeIndex)
    zonas       : dict { nombre_zona: [lista_estaciones] }  del config.json
    tipo        : 'ICA', 'AIRE' o 'DIARIO'
    orden_cat   : dict de orden de categorías NOM (solo necesario para AIRE/DIARIO)
    suficiencia : umbral para peor_categoria (solo AIRE/DIARIO)

    Retorna
    -------
    dict { nombre_zona: DataFrame }  listo para añadir al diccionario de hojas.
    """
    resultado = {}

    for nombre_zona, estaciones in zonas.items():
        # Seleccionar columnas que pertenecen a alguna estación de la zona
        cols_zona = [
            col for col in df_general.columns if _estacion_de_columna(col) in estaciones
        ]

        if not cols_zona:
            print(f"  AVISO: ninguna columna encontrada para zona '{nombre_zona}'")
            continue

        df_zona = df_general[cols_zona].copy()

        # Agregar columna de calidad de zona (solo AIRE/DIARIO, no ICA)
        if tipo in ("AIRE", "DIARIO") and orden_cat:
            cols_cat = [c for c in cols_zona if c.startswith("AIRE_")]
            if cols_cat:
                df_zona["Calidad del aire zona"] = peor_categoria(
                    [df_zona[c] for c in cols_cat],
                    orden_cat,
                    umbral=suficiencia,
                )

        resultado[nombre_zona[:31]] = df_zona  # límite Excel 31 chars

    return resultado
