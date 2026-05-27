"""
almacenamiento/combinador.py
----------------------------
Fusiona un DataFrame nuevo con los datos ya guardados en el Excel de salida,
usando la fecha como ID unico (en caso de colision gana el dato nuevo).
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

    Parametros
    ----------
    df_nuevo : pd.DataFrame
        DataFrame con los datos nuevos (indice DatetimeIndex o columna de fecha)
    archivo : str
        Ruta al archivo Excel de salida (ej. "datos/datos_calidad_aire_ICA.xlsx")
    nombre_hoja : str
        Nombre de la hoja dentro del Excel a leer y combinar
    col_fecha : str
        Nombre de la columna que contiene la fecha en el Excel guardado.
        Para archivos horarios suele ser "Fecha & Hora"; para diarios "Fecha".
    es_diario : bool, default=False
        True cuando la fecha esta guardada como columna (y no como indice).
        False cuando el archivo existente tiene la fecha como indice.

    Retorna
    -------
    pd.DataFrame
        DataFrame combinado, sin duplicados, ordenado cronologicamente.
        En caso de fecha duplicada, prevalece el dato de `df_nuevo`
        (keep="last" en la eliminacion de duplicados).
    """
    # Si el archivo no existe, no hay nada que combinar; devolver solo los nuevos
    if not os.path.exists(archivo):
        return df_nuevo

    try:
        # --------------------------------------------------------------------
        # Caso diario: la fecha esta guardada como columna, no como indice.
        # Se lee sin index_col, se convierte la columna de fecha a datetime,
        # y luego se asigna como indice para unificar el formato con df_nuevo.
        # --------------------------------------------------------------------
        if es_diario:
            df_existente = pd.read_excel(
                archivo,
                sheet_name=nombre_hoja,
                engine="openpyxl",
                index_col=None,
            )
            # Identificar la columna de fecha (puede llamarse col_fecha o ser la primera)
            fecha_col = (
                col_fecha
                if col_fecha in df_existente.columns
                else df_existente.columns[0]
            )
            df_existente[fecha_col] = pd.to_datetime(df_existente[fecha_col])
            df_existente.set_index(fecha_col, inplace=True)
            df_existente.index.name = col_fecha

        # --------------------------------------------------------------------
        # Caso horario: la fecha ya esta como indice al leer con index_col=0
        # --------------------------------------------------------------------
        else:
            df_existente = pd.read_excel(
                archivo,
                sheet_name=nombre_hoja,
                engine="openpyxl",
                index_col=0,
            )
            if not isinstance(df_existente.index, pd.DatetimeIndex):
                df_existente.index = pd.to_datetime(df_existente.index)

        # Concatenar (los nuevos al final) y eliminar duplicados por indice.
        # keep="last" conserva la ultima ocurrencia, que corresponde a df_nuevo.
        df_combinado = pd.concat([df_existente, df_nuevo], axis=0, sort=False)
        df_combinado = df_combinado[~df_combinado.index.duplicated(keep="last")]
        df_combinado.sort_index(inplace=True)
        return df_combinado

    except Exception as e:
        # Si falla la lectura (hoja no existe, formato corrupto, etc.),
        # se imprime advertencia y se devuelve solo el DataFrame nuevo.
        # El archivo original se sobrescribira con los nuevos datos.
        print(
            f"Advertencia: No se pudo leer hoja '{nombre_hoja}' "
            f"de {archivo}. Se creará nueva. Error: {e}"
        )
        return df_nuevo
