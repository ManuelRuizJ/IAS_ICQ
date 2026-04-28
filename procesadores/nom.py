"""
procesadores/nom.py
-------------------
NOM-172-SEMARNAT-2023 — cálculo horario del Índice AIRE Y SALUD.

Cambios respecto a la versión anterior
---------------------------------------
* PM10 y PM2.5 usan **promedio móvil ponderado de 12 horas (NowCast)** para el
  reporte horario, en lugar del promedio simple de 24h (sección 5.2.3 / Tabla 3).
* SO2 usa promedio **horario** (no de 24h) para el reporte horario (Tabla 3).
* Los nombres de columna incluyen la **unidad** del contaminante:
    AIRE_<unidad>_<contaminante>_<estacion>   → categoría
    CANTIDAD_<unidad>_<contaminante>_<estacion> → concentración
  Ejemplo:  AIRE_ppb_O3_AGUA SANTA  /  CANTIDAD_ppb_O3_AGUA SANTA
* Las bandas (tablas 4-9) corresponden a los valores vigentes a partir de
  enero de 2024 establecidos en la NOM-172-SEMARNAT-2023.
"""

import numpy as np
import pandas as pd

from procesadores.ica import promedio_movil_simple


def descartar_cero_por_redondeo(valor, decimales):
    """
    Retorna np.nan si el valor redondeado es cero en los decimales significativos.
    - decimales = 0 para PM10, PM2.5
    - decimales = 2 para CO
    - decimales = 3 para O3, NO2, SO2
    """
    if pd.isna(valor):
        return np.nan
    # Redondear al número de decimales indicado
    redondeado = round(valor, decimales)
    # Si el redondeo es cero, descartar
    if redondeado == 0:
        return np.nan
    return redondeado


# ── Unidades canónicas por clave ─────────────────────────────────────────────
# Se usa para construir el prefijo de unidad en los nombres de columna.
UNIDAD_DISPLAY = {
<<<<<<< HEAD
    "O3_ppb": "ppb",
    "NO2_ppb": "ppb",
    "SO2_ppb": "ppb",
    "CO_ppm": "ppm",
    "PM10_ug/m3": "ug/m3",
=======
    "O3_ppb":      "ppm",
    "NO2_ppb":     "ppm",
    "SO2_ppb":     "ppm",
    "CO_ppm":      "ppm",
    "PM10_ug/m3":  "ug/m3",
>>>>>>> main
    "PM2.5_ug/m3": "ug/m3",
}


# ── Funciones matemáticas base ───────────────────────────────────────────────


def clasificar_nom(conc: float, bandas: list):
    """
    Devuelve la categoría NOM-172 para una concentración dada.

    Las bandas tienen formato (lim_inf, lim_sup, categoria) donde el
    intervalo es (lim_inf, lim_sup] (abierto en el inferior, cerrado en el
    superior), excepto el primer intervalo que incluye el cero.
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
    Redondea según la Tabla 2 de la NOM-172-SEMARNAT-2023:
      PM10, PM2.5  → 0 decimales (entero)
      O3, NO2, SO2 → 3 decimales
      CO           → 2 decimales
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
    Promedio móvil ponderado de 12 horas (NowCast) para PM10 y PM2.5.

    Implementa exactamente el algoritmo del Anexo A de la NOM-172-2023:
      FA = 0.714  si es PM10
      FA = 0.694  si es PM2.5
      W  = max(1 - (Cmax-Cmin)/Cmax, 0.5)  redondeado a 2 decimales
      C̄  = [Σ Ci·W^(i-1) / Σ W^(i-1)] · FA   (i=1 es la hora más reciente)

    Condición de validez: al menos 2 de las 3 horas más recientes con dato.
    Si la condición no se cumple → NaN para esa hora.
    """
    fa = 0.714 if pollutant == "PM10" else 0.694
    valores = serie.values
    n = len(valores)
    resultado = np.full(n, np.nan)

    for t in range(n):
        # Ventana de 12 horas: índices [t-11 … t], i=1 es el más reciente
        inicio = t - 11
        if inicio < 0:
            continue

        ventana = valores[inicio : t + 1]  # 12 elementos, ventana[11] = hora t

        # Condición: ≥2 de las 3 horas más recientes con dato
        ultimas3 = ventana[9:]  # índices 9,10,11 → horas t-2,t-1,t
        if np.sum(~np.isnan(ultimas3)) < 2:
            continue

        validos = ventana[~np.isnan(ventana)]
        if len(validos) == 0:
            continue

        cmax = np.nanmax(ventana)
        cmin = np.nanmin(ventana)
        w_raw = 1.0 if cmax == 0 else 1.0 - (cmax - cmin) / cmax
        W = round(max(w_raw, 0.5), 2)

        # i=1 es la hora más reciente (índice 11 en ventana),
        # i=12 es la hora más antigua (índice 0 en ventana)
        suma_num = suma_den = 0.0
        for offset in range(12):
            i = offset + 1  # i va de 1 (más reciente) a 12
            idx_ventana = 11 - offset  # índice dentro de 'ventana'
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
    Devuelve la categoría más grave por fila, solo si la fracción de series
    con dato ≥ umbral.
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


# ── Procesador de alto nivel ─────────────────────────────────────────────────


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
    Calcula la categoría NOM-172 horaria para cada par (contaminante, estación).

    Nombre de columnas generadas
    ----------------------------
    AIRE_<unidad>_<contaminante>_<estacion>      → categoría de calidad del aire
    CANTIDAD_<unidad>_<contaminante>_<estacion>  → concentración redondeada
    Calidad del aire                             → peor categoría global

    Concentraciones base (Tabla 3 NOM-172-2023)
    --------------------------------------------
    PM10, PM2.5  → NowCast 12h ponderado (FA 0.714 / 0.694)
    CO           → promedio móvil de 8h
    O3, NO2, SO2 → promedio horario (= valores directos en ppm tras conversión)
    """
    df_hoja = pd.DataFrame(index=data_df.index)

    for i in range(1, num_orig_cols):
        col_in_data = i - 1
        estacion = estaciones[i]
        contaminante = contaminantes[i]
        unidad = unidades[i]

        if isinstance(contaminante, str):
            contaminante = contaminante.strip()
        if isinstance(unidad, str):
            unidad = unidad.strip()
        if isinstance(estacion, str):
            estacion = estacion.strip()

        if not isinstance(contaminante, str) or contaminante.lower() == "status":
            continue

        clave_orig = f"{contaminante}_{unidad}"
        if clave_orig not in ventanas:
            continue

        # Etiqueta de unidad para el nombre de columna
        etiqueta_unidad = UNIDAD_DISPLAY.get(clave_orig, unidad)

        valores = pd.to_numeric(data_df.iloc[:, col_in_data], errors="coerce")

        # Filtrar por status "Ok"
        if i + 1 < num_orig_cols:
            status_str = data_df.iloc[:, i].astype(str).str.strip().str.lower()
            valores = valores.where(status_str == "ok", np.nan)

        valores = valores.where(valores >= 0, np.nan)

        # ── Concentración base según NOM-172-2023 Tabla 3 ────────────────────
        if clave_orig in ("PM10_ug/m3", "PM2.5_ug/m3"):
            tipo = "PM10" if "PM10" in clave_orig else "PM2.5"
            conc_base = nowcast_12h(valores, tipo)
            clave_bandas = clave_orig

        elif clave_orig == "CO_ppm":
            conc_base = promedio_movil_simple(valores, 8, suficiencia)
            clave_bandas = "CO_ppm"

        else:
            # O3, NO2, SO2: promedio horario en ppm (convertir de ppb)
            conc_base = valores / 1000.0
            clave_bandas = f"{contaminante}_ppm"

        if clave_bandas not in bandas:
            continue

        conc_redondeada = [redondear_nom(x, contaminante, unidad) for x in conc_base]

        if contaminante in ["PM10", "PM2.5"]:
            decimales = 0
        elif contaminante == "CO":
            decimales = 2
        else:  # O3, NO2, SO2
            decimales = 3

        conc_redondeada = [
            descartar_cero_por_redondeo(x, decimales) for x in conc_redondeada
        ]

        categorias = [clasificar_nom(x, bandas[clave_bandas]) for x in conc_redondeada]

        col_cat = f"AIRE_{contaminante}_{estacion}"
        col_cant = f"CANTIDAD_{etiqueta_unidad}_{contaminante}_{estacion}"

        df_hoja[col_cat] = categorias
        df_hoja[col_cant] = conc_redondeada

    df_hoja = df_hoja.dropna(how="all")

    # Calidad del aire global (peor de todos los contaminantes y estaciones)
    if not df_hoja.empty:
        cols_cat = [c for c in df_hoja.columns if c.startswith("AIRE_")]
        if cols_cat:
            df_hoja["Calidad del aire"] = peor_categoria(
                [df_hoja[c] for c in cols_cat],
                orden_cat,
                umbral=0.0,
            )

    return df_hoja
