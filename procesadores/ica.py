"""
procesadores/ica.py
-------------------
NADF-009-AIRE-2017 — cálculo del Índice de Calidad del Aire.

Los nombres de columna generados tienen formato:
    ICA_<contaminante>_<estacion>
(la NADF no requiere unidad en el nombre porque el ICA es adimensional)
"""

import numpy as np
import pandas as pd


# ── Funciones matemáticas base ───────────────────────────────────────────────


def calcular_ica(conc: float, bandas: list) -> float:
    """Interpola el ICA dentro de la banda correspondiente (Ecuación 2, NADF-009)."""
    for pcinf, pcsup, iinf, isup in bandas:
        if pcinf <= conc <= pcsup:
            k = (isup - iinf) / (pcsup - pcinf)
            return round((k * (conc - pcinf)) + iinf)
    return np.nan


def promedio_movil_simple(
    serie: pd.Series, ventana: int, suficiencia: float
) -> pd.Series:
    """Promedio móvil con mínimo de datos requerido."""
    min_datos = int(np.ceil(ventana * suficiencia))
    return serie.rolling(window=ventana, min_periods=min_datos).mean()


def nowcast(serie: pd.Series, pollutant: str) -> pd.Series:
    """
    NowCast EPA original para PM10/PM2.5 (ventana de 12 h, FA fijo).
    Nota: para el módulo NOM-172 se usa nowcast_12h() definido en nom.py,
    que implementa el algoritmo exacto del Anexo A de la NOM-172-2023.
    Esta función se mantiene para compatibilidad con versiones anteriores.
    """
    fa = 0.714 if pollutant == "PM10" else 0.694
    valores = serie.values
    n = len(valores)
    resultado = np.full(n, np.nan)

    for i in range(n):
        if i < 11:
            continue
        ultimas3 = valores[i - 2 : i + 1]
        if np.sum(~np.isnan(ultimas3)) < 2:
            continue

        inicio = i - 11
        ventana = valores[inicio : i + 1]
        validos = ventana[~np.isnan(ventana)]
        if len(validos) == 0:
            continue

        cmax = np.max(validos)
        cmin = np.min(validos)
        w = 1.0 if cmax == 0 else 1 - (cmax - cmin) / cmax
        W = round(max(w, 0.5), 2)

        suma_num = suma_den = 0.0
        for j, idx in enumerate(range(i, inicio - 1, -1)):
            if j >= 12:
                break
            if not np.isnan(valores[idx]):
                peso = W**j
                suma_num += valores[idx] * peso
                suma_den += peso

        if suma_den > 0:
            resultado[i] = (suma_num / suma_den) * fa

    return pd.Series(resultado, index=serie.index)


# ── Procesador de alto nivel ─────────────────────────────────────────────────


def procesar_ica(
    estaciones: np.ndarray,
    contaminantes: np.ndarray,
    unidades: np.ndarray,
    data_df: pd.DataFrame,
    num_orig_cols: int,
    ventanas: dict,
    bandas: dict,
    suficiencia: float,
) -> pd.DataFrame:
    """
    Calcula el ICA (NADF-009) para cada par (contaminante, estación).

    Columnas generadas: ICA_<contaminante>_<estacion>
    """
    df_hoja = pd.DataFrame(index=data_df.index)

    for i in range(1, num_orig_cols):
        col_in_data = i - 1
        estacion = estaciones[i]
        contaminante = contaminantes[i]
        unidad = unidades[i]

        if not isinstance(contaminante, str) or contaminante == "Status":
            continue

        clave_orig = f"{contaminante}_{unidad}"
        if clave_orig not in ventanas:
            continue

        ventana_horas = ventanas[clave_orig]
        valores = pd.to_numeric(data_df.iloc[:, col_in_data], errors="coerce")

        if i + 1 < num_orig_cols:
            status_str = data_df.iloc[:, i].astype(str).str.strip().str.lower()
            valores = valores.where(status_str == "ok", np.nan)

        valores = valores.where(valores > 0, np.nan)

        valores_prom = promedio_movil_simple(valores, ventana_horas, suficiencia)

        if contaminante in ("O3", "NO2", "SO2"):
            valores_prom = valores_prom / 1000.0
            clave_bandas = f"{contaminante}_ppm"
        else:
            clave_bandas = clave_orig

        if clave_bandas not in bandas:
            continue

        ica_lista = [
            calcular_ica(x, bandas[clave_bandas]) if not np.isnan(x) else np.nan
            for x in valores_prom
        ]
        df_hoja[f"ICA_{contaminante}_{estacion}"] = ica_lista

    return df_hoja.dropna(how="all")
