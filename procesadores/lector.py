"""
procesadores/lector.py
----------------------
Lee una hoja del Excel de entrada, extrae los metadatos (estaciones,
contaminantes, unidades) y devuelve un DataFrame limpio con índice horario.

Corrección de fechas 24:00
--------------------------
El software exportador escribe las filas de medianoche como "DD/MM/YYYY 24:00"
pero con el año incorrecto (p. ej. 2026 cuando los datos son de 2024).
Esta función corrige el año tomándolo de la fila anterior y luego suma 1 día
para obtener la medianoche correcta del día siguiente.
"""

import pandas as pd


def preparar_datos_hoja(df: pd.DataFrame):
    """
    Parámetros
    ----------
    df : DataFrame leído con header=None desde pd.read_excel()

    Retorna
    -------
    estaciones    : np.ndarray  — nombres de estación por columna
    contaminantes : np.ndarray  — nombre del contaminante por columna
    unidades      : np.ndarray  — unidad de medida por columna
    data_df       : DataFrame   — datos con índice DatetimeIndex horario completo
    num_cols      : int         — número de columnas originales del Excel
    """
    # ── Localizar la fila "Fecha & Hora" ────────────────────────────────────
    start_row = None
    for idx, row in df.iterrows():
        if isinstance(row[0], str) and "Fecha & Hora" in row[0]:
            start_row = idx
            break

    if start_row is None:
        start_row = 0
        print("ADVERTENCIA: No se encontró 'Fecha & Hora'. Usando fila 0.")

    # ── Extraer metadatos ────────────────────────────────────────────────────
    # Estructura del Excel:
    #   start_row+0  →  Fecha & Hora | ESTACION_A | Status | ESTACION_B | ...
    #   start_row+1  →  nan          | O3         | nan    | NO2        | ...
    #   start_row+2  →  nan          | ppb        | nan    | ppb        | ...
    #   start_row+3  →  primer dato
    estaciones = df.iloc[start_row].values
    contaminantes = df.iloc[start_row + 1].values
    unidades = df.iloc[start_row + 2].values
    datos_raw = df.iloc[start_row + 3 :].reset_index(drop=True)

    # ── Parseo robusto de fechas ─────────────────────────────────────────────
    dates_raw = datos_raw.iloc[:, 0].astype(str)
    parts = dates_raw.str.split(" ", expand=True)

    if parts.shape[1] >= 2:
        fecha_str = parts[0].copy()
        hora_str = parts[1].copy()

        # Filas con hora "24:00" tienen el año incorrecto en el origen
        mask_24 = hora_str == "24:00"

        # Tomar el año de la fila anterior (que sí es correcto)
        for idx in fecha_str[mask_24].index:
            if idx > 0:
                anio_correcto = fecha_str.iloc[idx - 1].split("/")[-1]
                partes_fecha = fecha_str.iloc[idx].split("/")
                partes_fecha[-1] = anio_correcto
                fecha_str.iloc[idx] = "/".join(partes_fecha)

        hora_str_corr = hora_str.copy()
        hora_str_corr[mask_24] = "00:00"

        dates = pd.to_datetime(
            fecha_str + " " + hora_str_corr,
            errors="coerce",
            dayfirst=True,
        )
        # Medianoche del día siguiente
        dates[mask_24] = dates[mask_24] + pd.Timedelta(days=1)
    else:
        dates = pd.to_datetime(dates_raw, errors="coerce", dayfirst=True)

    # ── Descartar filas no parseables (Minimum, MaxDate, STD…) ──────────────
    invalid_mask = dates.isna()
    if invalid_mask.any():
        print(
            f"ADVERTENCIA: {invalid_mask.sum()} filas con fecha no válida serán descartadas."
        )
        ejemplos = dates_raw[invalid_mask].unique()[:10].tolist()
        print("  Fechas inválidas:", ejemplos)
        datos_raw = datos_raw.loc[~invalid_mask]
        dates = dates[~invalid_mask]

    datos_raw.index = dates
    datos_raw.index.name = "Fecha"
    datos_raw = datos_raw.drop(columns=0)

    # ── Eliminar duplicados ──────────────────────────────────────────────────
    if datos_raw.index.duplicated().any():
        n = datos_raw.index.duplicated().sum()
        print(
            f"ADVERTENCIA: {n} índices duplicados; se conserva la primera ocurrencia."
        )
        datos_raw = datos_raw[~datos_raw.index.duplicated(keep="first")]

    # ── Reindexar a frecuencia horaria completa (rellenar huecos con NaN) ───
    full_range = pd.date_range(
        start=datos_raw.index.min(),
        end=datos_raw.index.max(),
        freq="h",
    )
    data_df = datos_raw.reindex(full_range)

    gaps = full_range.difference(data_df.index)
    if len(gaps) > 0:
        print(f"INFO: Se agregaron {len(gaps)} horas faltantes (NaN).")

    print(f"Fechas en la hoja: {data_df.index.min()} a {data_df.index.max()}")
    print(f"Número de filas:   {len(data_df)}")

    return estaciones, contaminantes, unidades, data_df, len(df.columns)
