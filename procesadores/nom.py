"""
procesadores/nom.py
-------------------
NOM-172-SEMARNAT-2023 — calculo horario del Indice AIRE Y SALUD.

Cambios respecto a la version anterior
---------------------------------------
* PM10 y PM2.5 usan promedio movil ponderado de 12 horas (NowCast) para el
  reporte horario, en lugar del promedio simple de 24h (seccion 5.2.3 / Tabla 3).
* SO2 usa promedio horario (no de 24h) para el reporte horario (Tabla 3).
* Los nombres de columna incluyen la **unidad** del contaminante:
    AIRE_<unidad>_<contaminante>_<estacion>   → categoria
    CANTIDAD_<unidad>_<contaminante>_<estacion> → concentracion
  Ejemplo:  AIRE_ppb_O3_AGUA SANTA  /  CANTIDAD_ppb_O3_AGUA SANTA
* Las bandas (tablas 4-9) corresponden a los valores vigentes a partir de
  enero de 2024 establecidos en la NOM-172-SEMARNAT-2023.
"""

import numpy as np
import pandas as pd

from procesadores.ica import promedio_movil_simple


# ============================================================================
# Funciones de validacion y descarte de ceros
# ============================================================================
def descartar_cero_por_redondeo(valor, decimales):
    """
    Retorna np.nan si el valor redondeado es cero en los decimales significativos.

    Parametros
    ----------
    valor : float o nan
        Concentracion a evaluar
    decimales : int
        Numero de decimales con que se redondea segun NOM-172:
        - decimales = 0 para PM10, PM2.5
        - decimales = 2 para CO
        - decimales = 3 para O3, NO2, SO2

    Retorna
    -------
    float o nan
        El valor redondeado si es distinto de cero, o nan si es cero.
        Esta regla evita categorias "Buena" cuando todas las mediciones
        estan en cero (posible falla de instrumento).
    """
    if pd.isna(valor):
        return np.nan
    # Redondear al numero de decimales indicado
    redondeado = round(valor, decimales)
    # Si el redondeo es cero, descartar
    if redondeado == 0:
        return np.nan
    return redondeado



# ============================================================================
# Unidades canonicas por clave (para nombres de columna)
# ============================================================================
# Se usa para construir el prefijo de unidad en los nombres de columna.
# La clave es "contaminante_unidad_entrada", el valor es la cadena que
# se mostrara en el Excel (los gases se muestran como ppm aunque el
# archivo de entrada traiga ppb).
UNIDAD_DISPLAY = {
    "O3_ppb": "ppm",
    "NO2_ppb": "ppm",
    "SO2_ppb": "ppm",
    "CO_ppm": "ppm",
    "PM10_ug/m3": "ug/m3",
    "PM2.5_ug/m3": "ug/m3",
}



# ============================================================================
# Funciones matematicas base (clasificacion, redondeo, NowCast)
# ============================================================================
def clasificar_nom(conc: float, bandas: list):
    """
    Devuelve la categoria NOM-172 para una concentracion dada.

    Parametros
    ----------
    conc : float
        Concentracion ya redondeada (o aun sin redondear, pero con los
        limites en las mismas unidades)
    bandas : list of tuples
        Estructura: (lim_inf, lim_sup, categoria)
        El intervalo es (lim_inf, lim_sup] (abierto en el inferior,
        cerrado en el superior), excepto el primer intervalo que incluye el cero.

    Retorna
    -------
    str or None
        Nombre de la categoria ("Buena", "Aceptable", etc.) o None si
        la concentracion es nan.
    """
    if pd.isna(conc):
        return None
    for lim_inf, lim_sup, cat in bandas:
        if lim_inf < conc <= lim_sup:
            return cat
        elif conc == lim_inf == 0:
            return cat
    return None


def redondear_nom(valor: float, contaminante: str, unidad: str) -> float:
    """
    Redondea segun la Tabla 2 de la NOM-172-SEMARNAT-2023:
      PM10, PM2.5  → 0 decimales (entero)
      O3, NO2, SO2 → 3 decimales
      CO           → 2 decimales

    Parametros
    ----------
    valor : float
        Concentracion a redondear
    contaminante : str
        Nombre del contaminante (ej. "PM10", "O3")
    unidad : str (no se usa directamente, pero se conserva por consistencia)

    Retorna
    -------
    float
        Valor redondeado segun la norma, o nan si era nan.
    """
    if pd.isna(valor):
        return np.nan
    if contaminante in ("PM10", "PM2.5"):
        return int(round(valor))
    if contaminante in ("O3", "NO2", "SO2"):
        return round(valor, 3)
    if contaminante == "CO":
        return round(valor, 2)
    return valor


def nowcast_12h(serie: pd.Series, pollutant: str) -> pd.Series:
    """
    Promedio movil ponderado de 12 horas (NowCast) para PM10 y PM2.5.

    Implementa exactamente el algoritmo del Anexo A de la NOM-172-2023:

      FA = 0.714  si es PM10
      FA = 0.694  si es PM2.5

      W = max(1 - (Cmax - Cmin) / Cmax, 0.5)  redondeado a 2 decimales

      C̄ = [ Σ Ci·W^(i-1) / Σ W^(i-1) ] · FA
          donde i=1 es la hora mas reciente, i=12 la mas antigua.

    Condicion de validez: al menos 2 de las 3 horas mas recientes con dato.
    Si la condicion no se cumple → NaN para esa hora.

    Parametros
    ----------
    serie : pd.Series
        Datos horarios de concentracion de PM (ug/m3)
    pollutant : str
        'PM10' o 'PM2.5'

    Retorna
    -------
    pd.Series
        NowCast calculado para cada hora (las primeras 11 horas seran NaN).
    """
    fa = 0.714 if pollutant == "PM10" else 0.694
    valores = serie.values
    n = len(valores)
    resultado = np.full(n, np.nan)

    for t in range(n):
        # Ventana de 12 horas: indices [t-11 … t], i=1 es el mas reciente
        inicio = t - 11
        if inicio < 0:
            continue

        ventana = valores[inicio : t + 1]  # 12 elementos, ventana[11] = hora t

        # Condicion: ≥2 de las 3 horas mas recientes con dato
        ultimas3 = ventana[9:]  # indices 9,10,11 → horas t-2,t-1,t
        if np.sum(~np.isnan(ultimas3)) < 2:
            continue

        validos = ventana[~np.isnan(ventana)]
        if len(validos) == 0:
            continue

        cmax = np.nanmax(ventana)
        cmin = np.nanmin(ventana)
        w_raw = 1.0 if cmax == 0 else 1.0 - (cmax - cmin) / cmax
        W = round(max(w_raw, 0.5), 2)

        # i=1 es la hora mas reciente (indice 11 en ventana),
        # i=12 es la hora mas antigua (indice 0 en ventana)
        suma_num = suma_den = 0.0
        for offset in range(12):
            i = offset + 1                  # i va de 1 (mas reciente) a 12
            idx_ventana = 11 - offset       # indice dentro de 'ventana'
            c = ventana[idx_ventana]
            if not np.isnan(c):
                w_i = W ** (i - 1)
                suma_num += c * w_i
                suma_den += w_i

        if suma_den > 0:
            resultado[t] = (suma_num / suma_den) * fa

    return pd.Series(resultado, index=serie.index)


def peor_categoria(series_categorias: list, orden: dict, umbral: float = 0.75):
    """
    Devuelve la categoria mas grave por fila, solo si la fraccion de series
    con dato >= umbral.

    Parametros
    ----------
    series_categorias : list of pd.Series
        Lista de series que contienen categorias (strings)
    orden : dict
        Mapeo categoria -> valor numerico (0 mejor, 4 peor)
    umbral : float
        Fraccion minima de columnas que deben tener dato para calcular
        la categoria global. Si no se alcanza, la fila se deja vacia.

    Retorna
    -------
    pd.Series
        Serie con la categoria global (peor) por fila, o None si no
        se cumple el umbral.
    """
    if not series_categorias:
        return pd.Series(index=pd.Index([]), dtype="object")

    df_cat = pd.concat(series_categorias, axis=1)
    count_valid = df_cat.notna().sum(axis=1)
    min_req = int(np.ceil(len(series_categorias) * umbral))

    df_num = df_cat.apply(lambda col: col.map(orden).fillna(-1))
    max_num = df_num.max(axis=1)
    max_num = max_num.where(count_valid >= min_req, -1)

    inverso = {v: k for k, v in orden.items()}
    return max_num.map(inverso).where(max_num >= 0, None)



# ============================================================================
# Procesador de alto nivel
# ============================================================================
def procesar_aire(
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
    Calcula la categoria NOM-172 horaria para cada par (contaminante, estacion).

    Nombre de columnas generadas
    ----------------------------
    AIRE_<unidad>_<contaminante>_<estacion>      → categoria de calidad del aire
    CANTIDAD_<unidad>_<contaminante>_<estacion>  → concentracion redondeada
    Calidad del aire                             → peor categoria global

    Concentraciones base (Tabla 3 NOM-172-2023)
    --------------------------------------------
    PM10, PM2.5  → NowCast 12h ponderado (FA 0.714 / 0.694)
    CO           → promedio movil de 8h
    O3, NO2, SO2 → promedio horario (= valores directos en ppm tras conversion)

    Parametros
    ----------
    estaciones : np.ndarray
        Nombres de estacion por columna
    contaminantes : np.ndarray
        Nombre del contaminante por columna
    unidades : np.ndarray
        Unidad de medida por columna
    data_df : pd.DataFrame
        Datos numericos con indice horario
    num_orig_cols : int
        Numero total de columnas en el Excel original
    ventanas : dict
        Mapeo "contaminante_unidad" -> tipo de ventana (1, 8 o 12h)
        En realidad aqui solo se usa para saber si el contaminante es
        PM, CO o gas; el calculo especifico se hace internamente.
    bandas : dict
        Mapeo "contaminante_unidad" -> lista de bandas (lim_inf, lim_sup, cat)
    orden_cat : dict
        Orden numerico de categorias (Buena=0 ... Extremadamente mala=4)
    suficiencia : float
        Fraccion minima de datos validos para promedios moviles (se usa
        para el promedio de CO, aunque el NowCast tiene su propia logica).

    Retorna
    -------
    pd.DataFrame
        DataFrame con columnas AIRE_*, CANTIDAD_* y "Calidad del aire".
        Si no hay datos, DataFrame vacio.
    """
    df_hoja = pd.DataFrame(index=data_df.index)

    # Iterar sobre columnas (salta la columna 0 que es fecha/hora)
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
        if not isinstance(contaminante, str) or contaminante.lower() == "status":
            continue

        clave_orig = f"{contaminante}_{unidad}"
        if clave_orig not in ventanas:
            continue

        # Etiqueta de unidad para el nombre de columna (ej. "ppm" para O3_ppb)
        etiqueta_unidad = UNIDAD_DISPLAY.get(clave_orig, unidad)

        valores = pd.to_numeric(data_df.iloc[:, col_in_data], errors="coerce")

        # Filtrar por status "Ok" (si existe columna de status a la derecha)
        if i + 1 < num_orig_cols:
            status_str = data_df.iloc[:, i].astype(str).str.strip().str.lower()
            valores = valores.where(status_str == "ok", np.nan)

        # Descartar valores negativos (no fisicos)
        valores = valores.where(valores >= 0, np.nan)

        # ====================================================================
        # 1. Calcular la concentracion base segun la Tabla 3 de NOM-172
        # ====================================================================
        if clave_orig in ("PM10_ug/m3", "PM2.5_ug/m3"):
            tipo = "PM10" if "PM10" in clave_orig else "PM2.5"
            conc_base = nowcast_12h(valores, tipo)
            clave_bandas = clave_orig

        elif clave_orig == "CO_ppm":
            conc_base = promedio_movil_simple(valores, 8, suficiencia)
            clave_bandas = "CO_ppm"

        else:
            # O3, NO2, SO2: promedio horario en ppm (entrada en ppb)
            conc_base = valores / 1000.0
            clave_bandas = f"{contaminante}_ppm"

        if clave_bandas not in bandas:
            continue

        # ====================================================================
        # 2. Redondear segun Tabla 2 y descartar ceros por redondeo
        # ====================================================================
        conc_redondeada = [redondear_nom(x, contaminante, unidad) for x in conc_base]

        # Determinar decimales significativos para el descarte de ceros
        if contaminante in ["PM10", "PM2.5"]:
            decimales = 0
        elif contaminante == "CO":
            decimales = 2
        else:  # O3, NO2, SO2
            decimales = 3

        conc_redondeada = [
            descartar_cero_por_redondeo(x, decimales) for x in conc_redondeada
        ]


        # ====================================================================
        # 3. Clasificar en categoria y construir columnas de salida
        # ====================================================================
        categorias = [clasificar_nom(x, bandas[clave_bandas]) for x in conc_redondeada]

        col_cat = f"AIRE_{contaminante}_{estacion}"
        col_cant = f"CANTIDAD_{etiqueta_unidad}_{contaminante}_{estacion}"

        df_hoja[col_cat] = categorias
        df_hoja[col_cant] = conc_redondeada

    df_hoja = df_hoja.dropna(how="all")

    # =======================================================================
    # 4. Columna global "Calidad del aire": peor categoria entre todas
    #    las columnas AIRE_* de esta hoja.
    # =======================================================================
    if not df_hoja.empty:
        cols_cat = [c for c in df_hoja.columns if c.startswith("AIRE_")]
        if cols_cat:
            df_hoja["Calidad del aire"] = peor_categoria(
                [df_hoja[c] for c in cols_cat],
                orden_cat,
                umbral=0.0,          # Se evalua incluso si solo hay una categoria
            )

    return df_hoja
