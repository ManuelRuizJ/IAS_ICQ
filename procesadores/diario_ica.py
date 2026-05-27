"""
procesadores/diario_ica.py
--------------------------
Reporte diario del ICA segun NADF-009-AIRE-2017.

Para cada contaminante/estacion, se calcula:
  - PM10, PM2.5, CO, SO2: promedio de 24 horas (con suficiencia >=75%)
  - O3, NO2: promedio de 24 horas (la NADF-009 usa promedios de 24h para todos)
Luego se interpola el ICA con las bandas de la NADF-009.
Se generan columnas: ICA_<contaminante>_<estacion> (sin unidad).
"""

import numpy as np
import pandas as pd

from procesadores.ica import calcular_ica


def procesar_ica_diario(
    estaciones: np.ndarray,
    contaminantes: np.ndarray,
    unidades: np.ndarray,
    data_df: pd.DataFrame,
    num_orig_cols: int,
    ventanas: dict,  # se usa para saber la ventana de 24h para cada contaminante
    bandas: dict,
    suficiencia: float,
) -> pd.DataFrame:
    """
    Genera un DataFrame diario con el ICA (NADF-009).
    El indice son las fechas (sin hora).

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
        Numero total de columnas en el Excel original
    ventanas : dict
        Mapeo "contaminante_unidad" -> ventana (aqui solo se usa para saber
        si el contaminante esta presente; el promedio siempre es 24h para ICA diario)
    bandas : dict
        Mapeo "contaminante_unidad" -> lista de bandas de interpolacion ICA
    suficiencia : float
        Fraccion minima de datos validos para el promedio diario (ej. 0.75 = 18h)

    Retorna
    -------
    pd.DataFrame
        DataFrame con indice diario (sin hora), columnas ICA_<contaminante>_<estacion>.
        Si no hay datos, DataFrame vacio.
    """
    # Asegurar que el indice sea datetime (por si viene como string)
    if not isinstance(data_df.index, pd.DatetimeIndex):
        data_df.index = pd.to_datetime(data_df.index)
    
    # Lista de dias unicos ordenados
    dias_ordenados = sorted(data_df.index.normalize().unique())
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

        # Leer valores numericos y aplicar filtro de status
        valores = pd.to_numeric(data_df.iloc[:, col_in_data], errors="coerce")
        if i + 1 < num_orig_cols:
            status_str = data_df.iloc[:, i].astype(str).str.strip().str.lower()
            valores = valores.where(status_str == "ok", np.nan)

        # NADF descarta valores negativos y cero (solo concentraciones >0 son validas)
        valores = valores.where(
            valores > 0, np.nan
        )  # NADF descarta negativos y cero? (según tu código, >0)

        serie_valores = pd.Series(valores.values, index=data_df.index)

        # Promedio diario de 24 horas con suficiencia minima (default 75% = 18h)
        min_horas = int(np.ceil(24 * suficiencia))
        valor_diario = serie_valores.resample("D").apply(
            lambda x: x.mean() if x.count() >= min_horas else np.nan
        )

        # Convertir gases a ppm (entrada en ppb) para usar las bandas en ppm
        if contaminante in ("O3", "NO2", "SO2"):
            valor_diario = valor_diario / 1000.0
            clave_bandas = f"{contaminante}_ppm"
        else:
            clave_bandas = clave_orig

        if clave_bandas not in bandas:
            continue
        
         # Calcular ICA para cada dia mediante interpolacion en la banda correspondiente
        ica_lista = [
            calcular_ica(x, bandas[clave_bandas]) if not pd.isna(x) else np.nan
            for x in valor_diario
        ]
        # Si el ICA calculado es 0 (por ejemplo concentracion cero), se trata como NaN
        ica_lista = [np.nan if x == 0 else x for x in ica_lista]

        # Nombre de columna: ICA_<contaminante>_<estacion> (sin unidad)
        df_dia[f"ICA_{contaminante}_{estacion}"] = ica_lista

    # Eliminar filas completamente vacias (ningun contaminante ese dia)
    df_dia = df_dia.dropna(how="all")
    return df_dia
