"""
almacenamiento/combinador.py
----------------------------
Fusiona un DataFrame nuevo con los datos ya guardados en el Excel de salida,
usando la fecha como ID único (en caso de colisión gana el dato nuevo).
"""

import os
import pandas as pd


def combinar_con_existente(
    df_nuevo: pd.DataFrame,
    archivo: str,
    nombre_hoja: str,
    col_fecha: str,
    es_diario: bool = False,
) -> pd.DataFrame:
    """
    Lee la hoja `nombre_hoja` del archivo Excel existente y la combina
    con `df_nuevo`. Si el archivo no existe, devuelve `df_nuevo` tal cual.

    Parámetros
    ----------
    df_nuevo     : DataFrame con los datos nuevos (índice DatetimeIndex)
    archivo      : ruta al Excel de salida
    nombre_hoja  : nombre de la hoja a leer/combinar
    col_fecha    : nombre que tiene la columna de fecha en el Excel guardado
    es_diario    : True cuando la fecha está guardada como columna (no índice)

    Retorna
    -------
    DataFrame combinado, sin duplicados, ordenado cronológicamente.
    En caso de fecha duplicada, prevalece el dato de `df_nuevo`.
    """
    if not os.path.exists(archivo):
        return df_nuevo

    try:
        if es_diario:
            df_existente = pd.read_excel(
                archivo,
                sheet_name=nombre_hoja,
                engine="openpyxl",
                index_col=None,
            )
            fecha_col = (
                col_fecha
                if col_fecha in df_existente.columns
                else df_existente.columns[0]
            )
            df_existente[fecha_col] = pd.to_datetime(df_existente[fecha_col])
            df_existente.set_index(fecha_col, inplace=True)
            df_existente.index.name = col_fecha
        else:
            df_existente = pd.read_excel(
                archivo,
                sheet_name=nombre_hoja,
                engine="openpyxl",
                index_col=0,
            )
            if not isinstance(df_existente.index, pd.DatetimeIndex):
                df_existente.index = pd.to_datetime(df_existente.index)

        df_combinado = pd.concat([df_existente, df_nuevo], axis=0, sort=False)
        df_combinado = df_combinado[~df_combinado.index.duplicated(keep="last")]
        df_combinado.sort_index(inplace=True)
        return df_combinado

    except Exception as e:
        print(
            f"Advertencia: No se pudo leer hoja '{nombre_hoja}' "
            f"de {archivo}. Se creará nueva. Error: {e}"
        )
        return df_nuevo
