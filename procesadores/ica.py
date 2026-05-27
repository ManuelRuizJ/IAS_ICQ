"""
procesadores/ica.py
-------------------
NADF-009-AIRE-2017 — calculo del Indice de Calidad del Aire.

Los nombres de columna generados tienen formato:
    ICA_<contaminante>_<estacion>
(la NADF no requiere unidad en el nombre porque el ICA es adimensional)
"""

import numpy as np
import pandas as pd


# ============================================================================
# Funciones matematicas base
# ============================================================================


def calcular_ica(conc: float, bandas: list) -> float:
    """
    Interpola el ICA dentro de la banda correspondiente (Ecuacion 2, NADF-009).

    Parametros
    ----------
    conc : float
        Concentracion promediada (ya convertida a ppm para gases)
    bandas : list of tuples
        Lista de bandas [(pcinf, pcsup, iinf, isup), ...]
        donde pcinf/pcsup son limites de concentracion,
        iinf/isup son limites del ICA.

    Retorna
    -------
    float
        ICA redondeado a entero, o np.nan si la concentracion esta fuera
        de todas las bandas (eso no deberia ocurrir con bandas cerradas).
    """
    for pcinf, pcsup, iinf, isup in bandas:
        if pcinf <= conc <= pcsup:
            # Calculo lineal: ICA = I_inf + (I_sup - I_inf)/(C_sup - C_inf) * (C - C_inf)
            k = (isup - iinf) / (pcsup - pcinf)
            return round((k * (conc - pcinf)) + iinf)
    return np.nan


def promedio_movil_simple(
    serie: pd.Series, ventana: int, suficiencia: float
) -> pd.Series:
    """
    Promedio movil con minimo de datos requerido.

    Parametros
    ----------
    serie : pd.Series
        Datos horarios (pueden contener NaN)
    ventana : int
        Tamano de la ventana en horas (ej. 8, 24)
    suficiencia : float
        Fraccion minima de datos validos en la ventana (0.0 a 1.0)

    Retorna
    -------
    pd.Series
        Promedio movil con el mismo indice. Las posiciones donde no se
        alcanza el minimo de datos quedan como NaN.
    """
    min_datos = int(np.ceil(ventana * suficiencia))
    return serie.rolling(window=ventana, min_periods=min_datos).mean()


def nowcast(serie: pd.Series, pollutant: str) -> pd.Series:
    """
    NowCast EPA original para PM10/PM2.5 (ventana de 12 h, FA fijo).

    Nota: para el modulo NOM-172 se usa nowcast_12h() definido en nom.py,
    que implementa el algoritmo exacto del Anexo A de la NOM-172-2023.
    Esta funcion se mantiene para compatibilidad con versiones anteriores.

    Parametros
    ----------
    serie : pd.Series
        Datos horarios de concentracion de PM (ug/m3)
    pollutant : str
        'PM10' o 'PM2.5' (define el factor FA)

    Retorna
    -------
    pd.Series
        NowCast calculado para cada hora (con las primeras 11 horas NaN).
    """
    fa = 0.714 if pollutant == "PM10" else 0.694
    valores = serie.values
    n = len(valores)
    resultado = np.full(n, np.nan)

    for i in range(n):

        # Se requieren al menos 12 horas de datos para el primer NowCast
        if i < 11:
            continue

        # Al menos 2 validas en las ultimas 3 horas
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



# ============================================================================
# Procesador de alto nivel
# ============================================================================
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
    Calcula el ICA (NADF-009) para cada par (contaminante, estacion).

    Flujo interno:
        1. Itera sobre cada columna de datos (salta la columna de fecha/hora)
        2. Filtra por contaminante + unidad segun configuracion 'ventanas'
        3. Aplica filtro de calidad: solo filas con 'Status' = 'ok'
        4. Promedio movil segun ventana requerida
        5. Conversiones: O3, NO2, SO2 de ppb a ppm
        6. Interpolacion de ICA usando 'bandas' correspondientes

    Columnas generadas: ICA_<contaminante>_<estacion>

    Parametros
    ----------
    estaciones : np.ndarray
        Nombres de estacion por columna (fila de encabezado)
    contaminantes : np.ndarray
        Nombre del contaminante por columna (segunda fila)
    unidades : np.ndarray
        Unidad de medida por columna (tercera fila)
    data_df : pd.DataFrame
        Datos numericos con indice horario
    num_orig_cols : int
        Numero total de columnas en el Excel original (incluye fecha/hora)
    ventanas : dict
        Mapeo "contaminante_unidad" -> ventana en horas
    bandas : dict
        Mapeo "contaminante_unidad" -> lista de bandas [pcinf, pcsup, iinf, isup]
    suficiencia : float
        Fraccion minima de datos validos para promedios moviles

    Retorna
    -------
    pd.DataFrame
        DataFrame con columnas ICA_* y el mismo indice que data_df.
        Si no se pudo calcular ningun ICA, retorna DataFrame vacio.
    """
    df_hoja = pd.DataFrame(index=data_df.index)

    # i = 0 es la columna de fecha/hora, los datos empiezan en i=1
    for i in range(1, num_orig_cols):
        col_in_data = i - 1             # indice dentro de data_df (sin columna fecha)
        estacion = estaciones[i]
        contaminante = contaminantes[i]
        unidad = unidades[i]

        # Saltar columnas no contaminantes (ej. 'Status')
        if not isinstance(contaminante, str) or contaminante == "Status":
            continue

        clave_orig = f"{contaminante}_{unidad}"
        if clave_orig not in ventanas:
            continue

        ventana_horas = ventanas[clave_orig]
        valores = pd.to_numeric(data_df.iloc[:, col_in_data], errors="coerce")

        # Filtro de calidad: si existe columna de Status a la derecha (i+1)
        # se chequea que sea "ok", caso contrario se pone NaN.
        if i + 1 < num_orig_cols:
            status_str = data_df.iloc[:, i].astype(str).str.strip().str.lower()
            valores = valores.where(status_str == "ok", np.nan)

        # Los valores <= 0 no son fisicos en calidad del aire
        valores = valores.where(valores > 0, np.nan)

        # Promedio movil segun NADF
        valores_prom = promedio_movil_simple(valores, ventana_horas, suficiencia)

        # Conversiones: la NADF trabaja con gases en ppm (entrada en ppb)
        if contaminante in ("O3", "NO2", "SO2"):
            valores_prom = valores_prom / 1000.0
            clave_bandas = f"{contaminante}_ppm"
        else:
            clave_bandas = clave_orig

        if clave_bandas not in bandas:
            continue
        
        # Calcular ICA para cada hora
        ica_lista = [
            calcular_ica(x, bandas[clave_bandas]) if not np.isnan(x) else np.nan
            for x in valores_prom
        ]
        df_hoja[f"ICA_{contaminante}_{estacion}"] = ica_lista

    # Si no se genero ninguna columna, retornar DataFrame vacio
    return df_hoja.dropna(how="all")
