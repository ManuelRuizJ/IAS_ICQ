"""
graficas.py
-----------
Genera gráficas de calidad del aire para reportes oficiales REMA-SMADSOT.

Archivos de entrada (carpeta datos/)
--------------------------------------
  datos_calidad_aire_ICA.xlsx          → ICA horario     (NADF-009-AIRE-2017)
  datos_calidad_aire_AIRE_Y_SALUD.xlsx → IAS horario     (NOM-172-SEMARNAT-2023)
  datos_calidad_aire_DIARIO_IAS.xlsx   → IAS diario      (NOM-172-SEMARNAT-2023)
  datos_calidad_aire_DIARIO_ICA.xlsx   → ICA diario      (NADF-009-AIRE-2017)

Uso
---
  python graficas.py

Salida: carpeta  graficas/  con 115+ imágenes PNG a 150 dpi.
"""

import warnings
import os
import re
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.ticker import MaxNLocator

matplotlib.use("Agg")
warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURACIÓN — RUTAS Y CONSTANTES
# ============================================================================

DIR_SALIDA = "graficas"
os.makedirs(DIR_SALIDA, exist_ok=True)

# ── Archivos de entrada ──────────────────────────────────────────────────────
ARCHIVO_ICA_HORARIO = "datos/datos_calidad_aire_ICA.xlsx"
ARCHIVO_IAS_HORARIO = "datos/datos_calidad_aire_AIRE_Y_SALUD.xlsx"
ARCHIVO_IAS_DIARIO = "datos/datos_calidad_aire_DIARIO_IAS.xlsx"
ARCHIVO_ICA_DIARIO = "datos/datos_calidad_aire_DIARIO_ICA.xlsx"

# ── Zonas geográficas ────────────────────────────────────────────────────────
ZMVP = ["AGUA SANTA", "BINE", "NINFAS", "UTP", "VELODROMO"]
MUNICIPIOS = ["ATLIXCO", "TEHUACAN", "TEXMELUCAN"]
TODAS = ZMVP + MUNICIPIOS

ZONAS = {
    "ZMVP": (ZMVP, "Zona Metropolitana del Valle de Puebla"),
    "General": (TODAS, "Todas las estaciones REMA"),
}

# ── Categorías IAS ───────────────────────────────────────────────────────────
CATEGORIAS = ["Buena", "Aceptable", "Mala", "Muy mala", "Extremadamente mala"]
COLORES_CAT = {
    "Buena": "#00E400",
    "Aceptable": "#FFFF00",
    "Mala": "#FF7E00",
    "Muy mala": "#FF0000",
    "Extremadamente mala": "#8F3F97",
    "Sin dato": "#CCCCCC",
}

# ── Bandas ICA ───────────────────────────────────────────────────────────────
BANDAS_ICA = [
    (0, 50, "#9ACA3C", "Buena  (0–50)"),
    (51, 100, "#F7EC0F", "Aceptable  (51–100)"),
    (101, 150, "#F8991D", "Mala  (101–150)"),
    (151, 200, "#ED2124", "Muy mala  (151–200)"),
    (201, 300, "#7D287D", "Peligrosa  (201–300)"),
    (301, 500, "#7E0023", "Muy peligrosa  (301–500)"),
]

# ── Límites máximos permisibles NOM ─────────────────────────────────────────
LIMITES = {
    "PM10": (60, "µg/m³", "NOM-025-SSA1-2021"),
    "PM2.5": (33, "µg/m³", "NOM-025-SSA1-2021"),
    "O3": (0.060, "ppm", "NOM-020-SSA1-2021"),
    "NO2": (0.106, "ppm", "NOM-023-SSA1-2021"),
    "CO": (9.0, "ppm", "NOM-021-SSA1-2021"),
    "SO2": (0.040, "ppm", "NOM-022-SSA1-2019"),
}

UNIDADES = {
    "PM10": "µg/m³",
    "PM2.5": "µg/m³",
    "O3": "ppm",
    "NO2": "ppm",
    "CO": "ppm",
    "SO2": "ppm",
}

TIPO_PROM = {
    "PM10": "Promedio 24 h",
    "PM2.5": "Promedio 24 h",
    "CO": "Máx. promedio móvil 8 h",
    "O3": "Máx. promedio horario",
    "NO2": "Máx. promedio horario",
    "SO2": "Máx. promedio horario",
}

PARTICULAS = {"PM10", "PM2.5"}
GASES = {"O3", "NO2", "CO", "SO2"}

# ── Colores y nombres por estación ───────────────────────────────────────────
COLOR_EST = {
    "AGUA SANTA": "#1f77b4",
    "BINE": "#ff7f0e",
    "NINFAS": "#2ca02c",
    "UTP": "#d62728",
    "VELODROMO": "#9467bd",
    "ATLIXCO": "#8c564b",
    "TEHUACAN": "#e377c2",
    "TEXMELUCAN": "#7f7f7f",
}
NOMBRE_EST = {
    "AGUA SANTA": "Agua Santa",
    "BINE": "BINE",
    "NINFAS": "Ninfas",
    "UTP": "UTP",
    "VELODROMO": "Velódromo",
    "ATLIXCO": "Atlixco",
    "TEHUACAN": "Tehuacán",
    "TEXMELUCAN": "San Martín Texmelucan",
}

PIE = (
    "Fuente: REMA-SMADSOT  |  Red Estatal de Monitoreo Atmosférico del Estado de Puebla"
)

# ============================================================================
# UTILIDADES
# ============================================================================


def estilo():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linestyle": "--",
            "legend.fontsize": 9,
            "figure.dpi": 150,
        }
    )


def guardar(fig, nombre):
    path = os.path.join(DIR_SALIDA, f"{nombre}.png")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✓ {path}")


def pie_fig(fig):
    fig.text(
        0.99,
        0.005,
        PIE,
        ha="right",
        va="bottom",
        fontsize=6.5,
        color="#666666",
        style="italic",
    )


def nombre(est):
    return NOMBRE_EST.get(est, est.title())


def bandas_fondo(ax, ymax=300):
    for lo, hi, color, _ in BANDAS_ICA:
        if lo > ymax:
            break
        ax.axhspan(lo, min(hi, ymax), color=color, alpha=0.13, zorder=0)


def peor_cat(serie_fila):
    orden = {c: i for i, c in enumerate(CATEGORIAS)}
    validos = serie_fila.dropna()
    if validos.empty:
        return None
    return max(validos, key=lambda c: orden.get(c, -1))


def detectar_formato_col(cols, tipo="AIRE"):
    """
    Detecta si las columnas tienen formato con unidad (AIRE_ppb_O3_EST)
    o sin unidad (AIRE_O3_EST).
    Retorna 'con_unidad' o 'sin_unidad'.
    """
    pat_con = re.compile(rf"^{tipo}_[^_]+_[^_]+_.+$")
    # pat_sin = re.compile(rf"^{tipo}_[^_]+_.+$")
    muestras = [c for c in cols if c.startswith(f"{tipo}_")][:5]
    for c in muestras:
        if pat_con.match(c):
            return "con_unidad"
    return "sin_unidad"


def extraer_cont_est(col, tipo="AIRE", fmt="sin_unidad"):
    """
    Extrae (contaminante, estacion) de un nombre de columna.
    fmt='sin_unidad' → AIRE_CO_AGUA SANTA     → ('CO', 'AGUA SANTA')
    fmt='con_unidad' → AIRE_ppm_CO_AGUA SANTA → ('CO', 'AGUA SANTA')
    """
    partes = col.split("_", maxsplit=1)[1]  # quitar prefijo AIRE_ o CANTIDAD_
    if fmt == "con_unidad":
        partes = partes.split("_", maxsplit=1)[1]  # quitar unidad
    cont, est = partes.split("_", maxsplit=1)
    return cont.strip(), est.strip()


# ============================================================================
# CARGA DE DATOS
# ============================================================================


def cargar_datos():
    print("Cargando datos...")

    # ICA horario
    df_ica = pd.read_excel(ARCHIVO_ICA_HORARIO, sheet_name="General", index_col=0)
    df_ica.index = pd.to_datetime(df_ica.index, errors="coerce")

    # IAS horario
    df_ias_h = pd.read_excel(ARCHIVO_IAS_HORARIO, sheet_name="General", index_col=0)
    df_ias_h.index = pd.to_datetime(df_ias_h.index, errors="coerce")

    # IAS diario
    df_ias_d = pd.read_excel(ARCHIVO_IAS_DIARIO, sheet_name="General")
    fecha_col = df_ias_d.columns[0]  # primera columna = Fecha
    df_ias_d[fecha_col] = pd.to_datetime(df_ias_d[fecha_col], errors="coerce")
    df_ias_d = df_ias_d.set_index(fecha_col)
    df_ias_d.index.name = "Fecha"

    # ICA diario (opcional)
    df_ica_d = None
    if os.path.exists(ARCHIVO_ICA_DIARIO):
        df_ica_d = pd.read_excel(ARCHIVO_ICA_DIARIO, sheet_name="General", index_col=0)
        df_ica_d.index = pd.to_datetime(df_ica_d.index, errors="coerce")

    # Detectar formato de columnas
    fmt_ias_h = detectar_formato_col(df_ias_h.columns, "AIRE")
    fmt_ias_d = detectar_formato_col(df_ias_d.columns, "AIRE")

    # Contaminantes y estaciones disponibles (desde ICA como referencia)
    contaminantes = sorted(
        {col.split("_")[1] for col in df_ica.columns if col.startswith("ICA_")}
    )
    estaciones = sorted(
        {
            "_".join(col.split("_")[2:])
            for col in df_ica.columns
            if col.startswith("ICA_")
        }
    )

    periodo = (
        df_ias_d.index.min().strftime("%d/%m/%Y"),
        df_ias_d.index.max().strftime("%d/%m/%Y"),
    )
    anio = df_ias_d.index.min().year

    print(f"  Contaminantes : {contaminantes}")
    print(f"  Estaciones    : {estaciones}")
    print(f"  Periodo       : {periodo[0]} – {periodo[1]}")
    print(f"  Formato IAS h : {fmt_ias_h}  |  Formato IAS d : {fmt_ias_d}")

    return (
        df_ica,
        df_ias_h,
        df_ias_d,
        df_ica_d,
        contaminantes,
        estaciones,
        periodo,
        anio,
        fmt_ias_h,
        fmt_ias_d,
    )


# ============================================================================
# G1 — ICA HORARIO POR ESTACIÓN (líneas individuales, sin promediar)
# ============================================================================


def g1_ica_horario(df_ica, cont, ests, nombre_zona, periodo, tag):
    cols = [f"ICA_{cont}_{e}" for e in ests if f"ICA_{cont}_{e}" in df_ica.columns]
    if not cols:
        return

    fig, ax = plt.subplots(figsize=(14, 5))
    bandas_fondo(ax)

    for col in cols:
        est = "_".join(col.split("_")[2:])
        s = df_ica[col]  # <-- SIN dropna()
        if s.isnull().all():
            continue
        ax.plot(
            s.index,
            s,
            label=nombre(est),
            color=COLOR_EST.get(est, "#444"),
            lw=0.9,
            alpha=0.85,
        )

    ax.axhline(100, color="#333", lw=1.2, ls="--", label="ICA = 100")
    ax.set_title(
        f"Índice de Calidad del Aire (ICA) — {cont}\n"
        f"{nombre_zona}  |  Periodo: {periodo[0]} – {periodo[1]}",
        pad=8,
    )
    ax.set_ylabel("ICA (adimensional, NADF-009-AIRE-2017)")
    ax.set_ylim(0)

    leg1 = ax.legend(loc="upper right", framealpha=0.88)
    parches = [
        mpatches.Patch(color=c, alpha=0.5, label=lbl) for _, _, c, lbl in BANDAS_ICA
    ]
    ax.legend(
        handles=parches,
        loc="upper left",
        fontsize=7.5,
        title="Categorías ICA",
        framealpha=0.9,
    )
    ax.add_artist(leg1)
    ax.text(
        0.01,
        0.97,
        "⚠ El ICA es adimensional. No se promedian valores entre estaciones.",
        transform=ax.transAxes,
        fontsize=7.5,
        va="top",
        color="#7D287D",
        style="italic",
    )
    fig.autofmt_xdate()
    pie_fig(fig)
    guardar(fig, f"01_ica_horario_{cont}_{tag}")


# ============================================================================
# G2 — MÁXIMO ICA DIARIO (sin promediar entre estaciones)
# ============================================================================


def g2_ica_max_diario(df_ica, cont, ests, nombre_zona, periodo, tag):
    cols = [f"ICA_{cont}_{e}" for e in ests if f"ICA_{cont}_{e}" in df_ica.columns]
    if not cols:
        return

    fig, ax = plt.subplots(figsize=(14, 5))
    bandas_fondo(ax)

    for col in cols:
        est = "_".join(col.split("_")[2:])
        s = df_ica[col].resample("D").max()
        if s.isnull().all():
            continue
        ax.plot(
            s.index,
            s,
            label=nombre(est),
            color=COLOR_EST.get(est, "#444"),
            lw=1.2,
            marker="o",
            ms=2.5,
            alpha=0.85,
        )

    ax.axhline(100, color="#333", lw=1.3, ls="--", label="ICA = 100")
    ax.set_title(
        f"Máximo ICA diario — {cont}\n"
        f"{nombre_zona}  |  Periodo: {periodo[0]} – {periodo[1]}",
        pad=8,
    )
    ax.set_ylabel("Máximo ICA del día (adimensional)")
    ax.set_ylim(0)
    ax.text(
        0.01,
        0.97,
        "Valor = máximo ICA registrado en el día (no promedio entre estaciones).",
        transform=ax.transAxes,
        fontsize=7.5,
        va="top",
        color="#7D287D",
        style="italic",
    )
    ax.legend(loc="upper right", framealpha=0.88)
    fig.autofmt_xdate()
    pie_fig(fig)
    guardar(fig, f"02_ica_max_diario_{cont}_{tag}")


# ============================================================================
# G3 — CONCENTRACIÓN DIARIA CON LÍMITE NOM
# ============================================================================


def g3_concentracion_diaria(df_ias_d, cont, ests, nombre_zona, periodo, tag, fmt):
    prefix = "CANTIDAD"
    cols = []
    for e in ests:
        c1 = f"{prefix}_{cont}_{e}"
        if c1 in df_ias_d.columns:
            cols.append((c1, e))
        else:
            for col in df_ias_d.columns:
                if col.startswith(f"{prefix}_") and col.endswith(f"_{e}"):
                    cont_col = extractar_cont(col, prefix)
                    if cont_col == cont:
                        cols.append((col, e))
                        break

    if not cols:
        return

    lim, unidad, nom_ref = LIMITES.get(cont, (None, "", ""))
    tipo = TIPO_PROM.get(cont, "Concentración diaria")

    fig, ax = plt.subplots(figsize=(14, 5))
    for col, est in cols:
        s = df_ias_d[col]  # <-- SIN dropna()
        if s.isnull().all():
            continue
        ax.plot(
            s.index,
            s,
            label=nombre(est),
            color=COLOR_EST.get(est, "#444"),
            lw=1.2,
            marker="o",
            ms=2.5,
            alpha=0.85,
        )

    if lim:
        ax.axhline(
            lim,
            color="#D62728",
            lw=1.6,
            ls="--",
            label=f"Límite máx.: {lim} {unidad}  ({nom_ref})",
        )

    ax.set_title(
        f"Concentración diaria de {cont}  [{tipo}]  ({unidad})\n"
        f"{nombre_zona}  |  Periodo: {periodo[0]} – {periodo[1]}",
        pad=8,
    )
    ax.set_ylabel(f"Concentración ({unidad})")
    ax.set_ylim(0)
    ax.legend(loc="upper right", framealpha=0.88)
    fig.autofmt_xdate()
    pie_fig(fig)
    guardar(fig, f"03_concentracion_diaria_{cont}_{tag}")


def extractar_cont(col, prefix):
    """Extrae contaminante de columna CANTIDAD_[unidad_]CONT_EST."""
    partes = col[len(prefix) + 1 :].split("_")
    # Puede ser [cont, est...] o [unidad, cont, est...]
    conts_conocidos = {"CO", "NO2", "O3", "PM10", "PM2.5", "SO2"}
    for i, p in enumerate(partes):
        if p in conts_conocidos:
            return p
    return partes[0]


# ============================================================================
# G4 — DÍAS POR CATEGORÍA IAS POR ESTACIÓN (barras horizontales apiladas)
# ============================================================================


def g4_dias_categoria_estacion(df_ias_d, cont, ests, nombre_zona, periodo, tag):
    cols = _buscar_cols_aire(df_ias_d, cont, ests)
    if not cols:
        return

    total_dias = len(df_ias_d)
    registros = {}
    for col, est in cols:
        cnt = df_ias_d[col].value_counts()
        fila = {c: int(cnt.get(c, 0)) for c in CATEGORIAS}
        fila["Sin dato"] = total_dias - sum(fila.values())
        registros[nombre(est)] = fila

    df_p = pd.DataFrame(registros).T
    cats = [
        c for c in CATEGORIAS + ["Sin dato"] if c in df_p.columns and df_p[c].sum() > 0
    ]
    df_p = df_p[cats].fillna(0)

    fig, ax = plt.subplots(figsize=(10, max(3, len(df_p) * 0.75 + 2)))
    left = np.zeros(len(df_p))
    for cat in cats:
        vals = df_p[cat].values
        bars = ax.barh(
            df_p.index, vals, left=left, color=COLORES_CAT[cat], label=cat, height=0.55
        )
        for r, v in zip(bars, vals):
            if v >= 3:
                ax.text(
                    r.get_x() + r.get_width() / 2,
                    r.get_y() + r.get_height() / 2,
                    str(int(v)),
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="bold",
                    color="black"
                    if cat in ("Buena", "Aceptable", "Sin dato")
                    else "white",
                )
        left += vals

    ax.set_title(
        f"Días por categoría IAS — {cont}\n"
        f"{nombre_zona}  |  Periodo: {periodo[0]} – {periodo[1]}",
        pad=8,
    )
    ax.set_xlabel("Número de días")
    ax.legend(loc="lower right", framealpha=0.88)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    pie_fig(fig)
    plt.tight_layout()
    guardar(fig, f"04_dias_cat_estacion_{cont}_{tag}")


# ============================================================================
# G5 — RESUMEN DÍAS POR CONTAMINANTE Y ZONA (barras verticales apiladas)
# ============================================================================


def g5_resumen_zona(df_ias_d, conts, ests, nombre_zona, periodo, tag, grupo):
    data = {}
    for cont in conts:
        cols = _buscar_cols_aire(df_ias_d, cont, ests)
        if not cols:
            continue
        serie_peor = pd.DataFrame({c: df_ias_d[c] for c, _ in cols}).apply(
            peor_cat, axis=1
        )
        cnt = serie_peor.value_counts()
        total = len(serie_peor)
        fila = {c: int(cnt.get(c, 0)) for c in CATEGORIAS}
        fila["Sin dato"] = total - sum(fila.values())
        data[cont] = fila

    if not data:
        return
    df_p = pd.DataFrame(data).T.fillna(0)
    cats = [
        c for c in CATEGORIAS + ["Sin dato"] if c in df_p.columns and df_p[c].sum() > 0
    ]
    df_p = df_p[cats]

    fig, ax = plt.subplots(figsize=(max(8, len(df_p) * 1.4 + 2), 5))
    x = np.arange(len(df_p))
    bot = np.zeros(len(df_p))
    w = 0.6
    for cat in cats:
        vals = df_p[cat].values
        bars = ax.bar(x, vals, bottom=bot, color=COLORES_CAT[cat], label=cat, width=w)
        for r, v in zip(bars, vals):
            if v >= 2:
                ax.text(
                    r.get_x() + r.get_width() / 2,
                    r.get_y() + r.get_height() / 2,
                    str(int(v)),
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="bold",
                    color="black"
                    if cat in ("Buena", "Aceptable", "Sin dato")
                    else "white",
                )
        bot += vals

    ax.set_title(
        f"Calidad del aire por contaminante — {nombre_zona} ({grupo})\n"
        f"Periodo: {periodo[0]} – {periodo[1]}",
        pad=8,
    )
    ax.set_ylabel("Número de días")
    ax.set_xticks(x)
    ax.set_xticklabels(df_p.index, fontsize=10)
    ax.legend(loc="upper right", framealpha=0.88)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    pie_fig(fig)
    plt.tight_layout()
    guardar(fig, f"05_resumen_zona_{tag}_{grupo.lower()}")


# ============================================================================
# G6 — CALIDAD GLOBAL DIARIA MENSUAL (columna "Calidad del aire")
# ============================================================================


def g6_calidad_global_mensual(df_ias_d, periodo, anio):
    if "Calidad del aire" not in df_ias_d.columns:
        print("  [Omitida G6] columna 'Calidad del aire' no encontrada.")
        return

    df = df_ias_d[["Calidad del aire"]].copy()
    df["Mes"] = df.index.to_period("M")
    df["cat"] = df["Calidad del aire"].where(
        df["Calidad del aire"].isin(CATEGORIAS), "Sin dato"
    )
    grouped = df.groupby(["Mes", "cat"]).size().unstack(fill_value=0)
    cats = [
        c
        for c in CATEGORIAS + ["Sin dato"]
        if c in grouped.columns and grouped[c].sum() > 0
    ]
    grouped = grouped[cats]

    fig, ax = plt.subplots(figsize=(max(10, len(grouped) * 0.9 + 2), 5))
    x = np.arange(len(grouped))
    bot = np.zeros(len(grouped))
    w = 0.65
    for cat in cats:
        vals = grouped[cat].values
        bars = ax.bar(x, vals, bottom=bot, color=COLORES_CAT[cat], label=cat, width=w)
        for r, v in zip(bars, vals):
            if v >= 1:
                ax.text(
                    r.get_x() + r.get_width() / 2,
                    r.get_y() + r.get_height() / 2,
                    str(int(v)),
                    ha="center",
                    va="center",
                    fontsize=8.5,
                    fontweight="bold",
                    color="black"
                    if cat in ("Buena", "Aceptable", "Sin dato")
                    else "white",
                )
        bot += vals

    totales = {c: int(grouped[c].sum()) for c in cats}
    total_str = "  ".join(f"{k}: {v}" for k, v in totales.items())

    ax.set_title(
        f"Calidad del aire diaria — Todas las estaciones REMA\n"
        f"Periodo: {periodo[0]} – {periodo[1]}",
        pad=8,
    )
    ax.set_ylabel("Número de días")
    ax.set_xticks(x)
    ax.set_xticklabels([str(m) for m in grouped.index], rotation=30, ha="right")
    ax.legend(loc="upper right", framealpha=0.88)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.text(
        0.5,
        -0.28,
        f"Total del periodo — {total_str}",
        transform=ax.transAxes,
        ha="center",
        fontsize=9,
    )
    pie_fig(fig)
    plt.tight_layout()
    guardar(fig, "06_calidad_global_mensual")


# ============================================================================
# G7 — MOSAICO DÍAS FUERA DE NORMA (como Gráfica 2 del Reporte Anual)
# Esta es la gráfica estrella para el reporte oficial.
# Filas = semanas del año, columnas = días de la semana,
# color = peor categoría IAS del día. Una figura por contaminante.
# ============================================================================


def g7_mosaico_fuera_norma(df_ias_d, cont, ests, nombre_zona, periodo, anio, tag):
    """
    Mosaico de calor estilo calendario (semanas × días semana).
    Cada celda representa un día del año.
    Color = categoría IAS (peor entre estaciones de la zona).
    Réplica de la Gráfica 2 del Reporte Anual 2025 REMA-SMADSOT.
    """
    cols = _buscar_cols_aire(df_ias_d, cont, ests)
    if not cols:
        return

    # Calcular peor categoría del día entre estaciones de la zona
    df_cats = pd.DataFrame({e: df_ias_d[c] for c, e in cols})
    serie_peor = df_cats.apply(peor_cat, axis=1).rename("categoria")

    # Construir grilla semanal: índice = semana del año, columna = día semana
    DIAS_SEMANA = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]
    CAT_A_NUM = {c: i for i, c in enumerate(CATEGORIAS + ["Sin dato"])}
    NUM_A_COLOR = [COLORES_CAT[c] for c in CATEGORIAS + ["Sin dato"]]

    inicio = serie_peor.index.min()
    fin = serie_peor.index.max()
    # Extender al lunes de la primera semana y al domingo de la última
    inicio_grid = inicio - pd.Timedelta(days=inicio.weekday())
    fin_grid = fin + pd.Timedelta(days=6 - fin.weekday())
    rango_grid = pd.date_range(inicio_grid, fin_grid, freq="D")
    n_semanas = len(rango_grid) // 7

    # Matriz semanas × 7
    grilla_num = np.full((n_semanas, 7), CAT_A_NUM["Sin dato"])
    grilla_label = np.full((n_semanas, 7), "", dtype=object)

    for i, fecha in enumerate(rango_grid):
        sem = i // 7
        dia = i % 7
        if fecha in serie_peor.index and serie_peor[fecha] in CAT_A_NUM:
            cat = serie_peor[fecha]
        else:
            cat = "Sin dato"
        grilla_num[sem, dia] = CAT_A_NUM[cat]
        grilla_label[sem, dia] = str(fecha.day)

    # Crear figura
    fig_h = max(4, n_semanas * 0.35 + 2.5)
    fig, ax = plt.subplots(figsize=(9, fig_h))

    cmap = ListedColormap(NUM_A_COLOR)
    norm = BoundaryNorm(range(len(NUM_A_COLOR) + 1), cmap.N)

    ax.imshow(
        grilla_num,
        cmap=cmap,
        norm=norm,
        aspect="auto",
        interpolation="nearest",
        origin="upper",
    )

    # Etiquetas de día del mes dentro de cada celda
    for sem in range(n_semanas):
        for dia in range(7):
            lbl = grilla_label[sem, dia]
            if lbl:
                cat_n = grilla_num[sem, dia]
                cat_s = (CATEGORIAS + ["Sin dato"])[cat_n]
                fc = "black" if cat_s in ("Buena", "Aceptable", "Sin dato") else "white"
                ax.text(dia, sem, lbl, ha="center", va="center", fontsize=6.5, color=fc)

    # Eje X: días de la semana
    ax.set_xticks(range(7))
    ax.set_xticklabels(DIAS_SEMANA, fontsize=8)

    # Eje Y: etiquetas de mes en la primera semana de cada mes
    mes_labels = {}
    for i, fecha in enumerate(rango_grid):
        sem = i // 7
        if fecha.day <= 7 and sem not in mes_labels:
            mes_labels[sem] = (
                fecha.strftime("%b\n%Y") if fecha.month == 1 else fecha.strftime("%b")
            )
    ax.set_yticks(list(mes_labels.keys()))
    ax.set_yticklabels(list(mes_labels.values()), fontsize=8)

    # Leyenda
    parches = [
        mpatches.Patch(color=COLORES_CAT[c], label=c) for c in CATEGORIAS + ["Sin dato"]
    ]
    ax.legend(
        handles=parches,
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        fontsize=8,
        title="Categoría IAS\n(NOM-172-2023)",
        framealpha=0.95,
        title_fontsize=8,
    )

    ax.set_title(
        f"Mosaico de días por categoría de calidad del aire — {cont}\n"
        f"{nombre_zona}  |  Periodo: {periodo[0]} – {periodo[1]}",
        pad=8,
    )

    # Conteo de días fuera de norma (Mala + peores)
    fuera = sum(
        int(serie_peor.isin([c]).sum())
        for c in ["Mala", "Muy mala", "Extremadamente mala"]
    )
    ax.text(
        0.0,
        -0.08 if fig_h < 8 else -0.05,
        f"Días fuera de norma (categoría Mala o peor): {fuera}",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#D62728",
        fontweight="bold",
    )

    pie_fig(fig)
    plt.tight_layout()
    guardar(fig, f"07_mosaico_fuera_norma_{cont}_{tag}")


# ============================================================================
# G8 — PROMEDIO DEL PERIODO POR ESTACIÓN (barras horizontales)
# ============================================================================


def g8_promedios_periodo(df_ias_d, cont, ests, nombre_zona, periodo, tag):
    cols = [(c, e) for c, e in _buscar_cols_cantidad(df_ias_d, cont, ests)]
    if not cols:
        return

    lim, unidad, nom_ref = LIMITES.get(cont, (None, "", ""))
    promedios = {}
    for col, est in cols:
        s = df_ias_d[col].dropna()
        if not s.empty:
            promedios[nombre(est)] = s.mean()

    if not promedios:
        return
    nombres = list(promedios.keys())
    valores = list(promedios.values())
    colores = [
        COLORES_CAT["Mala"] if (lim and v > lim) else COLORES_CAT["Buena"]
        for v in valores
    ]

    fig, ax = plt.subplots(figsize=(9, max(3, len(nombres) * 0.75 + 2)))
    bars = ax.barh(nombres, valores, color=colores, height=0.55)
    for bar, v in zip(bars, valores):
        fmt_v = f"{v:.3f}" if unidad == "ppm" else f"{v:.1f}"
        ax.text(
            bar.get_width() + max(valores) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            fmt_v,
            va="center",
            fontsize=9,
        )
    if lim:
        ax.axvline(
            lim,
            color="#D62728",
            ls="--",
            lw=1.5,
            label=f"Límite: {lim} {unidad}  ({nom_ref})",
        )
    ax.set_title(
        f"Concentración promedio del periodo — {cont}  ({unidad})\n"
        f"{nombre_zona}  |  Periodo: {periodo[0]} – {periodo[1]}",
        pad=8,
    )
    ax.set_xlabel(f"Promedio ({unidad})")
    ax.set_xlim(0, max(valores) * 1.2)
    if lim:
        ax.legend(fontsize=9)
    pie_fig(fig)
    plt.tight_layout()
    guardar(fig, f"08_promedios_periodo_{cont}_{tag}")


# g9 — Dispersión PM10 vs PM2.5 (diario) - CORREGIDA
def g9_pm10_vs_pm25(df_ias_d, ests, nombre_zona, periodo, tag):
    # Buscar columnas de cantidad para PM10 y PM2.5 usando la función auxiliar
    cols_pm10 = _buscar_cols_cantidad(df_ias_d, "PM10", ests)
    cols_pm25 = _buscar_cols_cantidad(df_ias_d, "PM2.5", ests)
    if not cols_pm10 or not cols_pm25:
        return
    # Tomar la primera columna de cada contaminante (promediar entre estaciones)
    col_pm10 = cols_pm10[0][0]
    col_pm25 = cols_pm25[0][0]
    df_pair = df_ias_d[[col_pm10, col_pm25]].dropna()
    if df_pair.empty:
        return
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(df_pair[col_pm10], df_pair[col_pm25], alpha=0.5, s=20, c="steelblue")
    ax.set_xlabel("PM10 (µg/m³)")
    ax.set_ylabel("PM2.5 (µg/m³)")
    max_val = max(df_pair[col_pm10].max(), df_pair[col_pm25].max()) * 1.1
    ax.set_xlim(0, max_val)
    ax.set_ylim(0, max_val)
    x_line = np.linspace(0, max_val, 100)
    ax.plot(x_line, 0.5 * x_line, "r--", label="PM2.5 = 0.5 × PM10", alpha=0.7)
    ax.set_title(
        f"Relación PM10 vs PM2.5 – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.legend()
    pie_fig(fig)
    guardar(fig, f"09_pm10_vs_pm25_{tag}")


# g10 — Comparativa de promedios por estación (separado: partículas / gases)
def g10_comparativa_contaminantes(
    df_ias_d, cont_list, ests, nombre_zona, periodo, tag, grupo
):
    """
    grupo = "particulas" o "gases"
    """
    data = {est: {} for est in ests}
    for est in ests:
        for cont in cont_list:
            cols = _buscar_cols_cantidad(df_ias_d, cont, [est])
            if cols:
                data[est][cont] = df_ias_d[cols[0][0]].mean()
    df_plot = pd.DataFrame(data).T.dropna(how="all")
    if df_plot.empty:
        return
    conts_present = [c for c in cont_list if c in df_plot.columns]
    if not conts_present:
        return
    fig, ax = plt.subplots(figsize=(12, max(4, len(df_plot) * 0.6 + 2)))
    x = np.arange(len(df_plot))
    width = 0.8 / len(conts_present)
    for i, cont in enumerate(conts_present):
        vals = df_plot[cont].fillna(0)
        bars = ax.bar(x + i * width, vals, width, label=cont, alpha=0.8)
        for bar, v in zip(bars, vals):
            if v > 0:
                fmt = f"{v:.1f}" if grupo == "particulas" else f"{v:.3f}"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.5,
                    fmt,
                    ha="center",
                    fontsize=7,
                )
    ax.set_xticks(x + width * (len(conts_present) - 1) / 2)
    ax.set_xticklabels([nombre(e) for e in df_plot.index], rotation=45, ha="right")
    unidad = "µg/m³" if grupo == "particulas" else "ppm"
    ax.set_ylabel(f"Concentración promedio ({unidad})", fontsize=9)
    ax.set_title(
        f"Comparativa de contaminantes ({grupo}) – {nombre_zona}\nPeriodo completo"
    )
    ax.legend()
    pie_fig(fig)
    guardar(fig, f"10_comparativa_{grupo}_{tag}")


# g11 — Series diarias comparativas (separado: partículas / gases)
def g11_series_comparativas(
    df_ias_d, cont_list, ests, nombre_zona, periodo, tag, grupo
):
    df_zone = pd.DataFrame()
    for cont in cont_list:
        cols = _buscar_cols_cantidad(df_ias_d, cont, ests)
        if cols:
            df_zone[cont] = df_ias_d[[c for c, _ in cols]].mean(axis=1, skipna=True)
    if df_zone.empty:
        return
    fig, ax = plt.subplots(figsize=(14, 5))
    for cont in df_zone.columns:
        s = df_zone[cont]  # <-- SIN dropna()
        if s.isnull().all():
            continue
        ax.plot(s.index, s, label=cont, lw=1.2, marker=".", ms=2)
    ax.legend()
    unidad = "µg/m³" if grupo == "particulas" else "ppm"
    ax.set_ylabel(f"Concentración ({unidad})")
    ax.set_title(
        f"Evolución diaria de contaminantes ({grupo}) – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    pie_fig(fig)
    guardar(fig, f"11_series_{grupo}_{tag}")


# g12 — Mapa de calor de correlaciones (separado)
def g12_correlacion_contaminantes(
    df_ias_d, cont_list, ests, nombre_zona, periodo, tag, grupo
):
    df_corr = pd.DataFrame()
    for cont in cont_list:
        cols = _buscar_cols_cantidad(df_ias_d, cont, ests)
        if cols:
            df_corr[cont] = df_ias_d[[c for c, _ in cols]].mean(axis=1, skipna=True)
    if df_corr.shape[1] < 2:
        return
    corr = df_corr.corr()
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.columns)))
    ax.set_yticklabels(corr.columns)
    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            ax.text(
                j,
                i,
                f"{corr.iloc[i, j]:.2f}",
                ha="center",
                va="center",
                color="white" if abs(corr.iloc[i, j]) > 0.6 else "black",
                fontsize=8,
            )
    plt.colorbar(im, ax=ax, label="Coeficiente de correlación")
    ax.set_title(
        f"Correlación entre contaminantes ({grupo}) – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    pie_fig(fig)
    guardar(fig, f"12_correlacion_{grupo}_{tag}")


# g13 — Perfil horario (separado)
def g13_perfil_horario(df_ias_h, cont_list, ests, nombre_zona, periodo, tag, grupo):
    df_hour = pd.DataFrame()
    for cont in cont_list:
        cols = _buscar_cols_cantidad(df_ias_h, cont, ests)
        if cols:
            df_hour[cont] = df_ias_h[[c for c, _ in cols]].mean(axis=1, skipna=True)
    if df_hour.empty:
        return
    df_hour["hora"] = df_hour.index.hour
    perfil = df_hour.groupby("hora").mean()
    fig, ax = plt.subplots(figsize=(12, 5))
    for cont in perfil.columns:
        ax.plot(perfil.index, perfil[cont], label=cont, marker="o", lw=1.5)
    ax.set_xlabel("Hora del día")
    unidad = "µg/m³" if grupo == "particulas" else "ppm"
    ax.set_ylabel(f"Concentración promedio ({unidad})")
    ax.set_title(
        f"Perfil horario de contaminantes ({grupo}) – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.legend()
    ax.grid(True, alpha=0.3)
    pie_fig(fig)
    guardar(fig, f"13_perfil_horario_{grupo}_{tag}")


# ============================================================================
# GRÁFICAS ADICIONALES (G14 - G25)
# ============================================================================


# G14 — Evolución del ICA (línea temporal) - por zona y contaminante
def g14_evolucion_ica_linea(df_ica, cont, ests, nombre_zona, periodo, tag):
    cols = [f"ICA_{cont}_{e}" for e in ests if f"ICA_{cont}_{e}" in df_ica.columns]
    if not cols:
        return
    fig, ax = plt.subplots(figsize=(14, 5))
    for col in cols:
        est = "_".join(col.split("_")[2:])
        s = df_ica[col]  # <-- SIN dropna()
        if s.isnull().all():
            continue
        ax.plot(s.index, s, label=nombre(est), lw=0.9, alpha=0.85)
    ax.axhline(100, color="red", ls="--", lw=1.2, label="ICA = 100")
    ax.set_title(
        f"Evolución del ICA – {cont}\n{nombre_zona}  |  Periodo: {periodo[0]} – {periodo[1]}"
    )
    ax.set_ylabel("ICA (adimensional, NADF-009)")
    ax.legend(loc="upper right", framealpha=0.88)
    fig.autofmt_xdate()
    pie_fig(fig)
    guardar(fig, f"14_evolucion_ica_{cont}_{tag}")


# G15 — Boxplot de concentraciones por estación
def g15_boxplot_contaminante(df_ias_d, cont, ests, nombre_zona, periodo, tag):
    datos = []
    etiquetas = []
    for est in ests:
        cols = _buscar_cols_cantidad(df_ias_d, cont, [est])
        if not cols:
            continue
        serie = df_ias_d[cols[0][0]].dropna()
        if not serie.empty:
            datos.append(serie.values)
            etiquetas.append(nombre(est))
    if len(datos) < 2:
        return
    fig, ax = plt.subplots(figsize=(10, max(5, len(etiquetas) * 0.6)))
    ax.boxplot(datos, labels=etiquetas, showfliers=False)
    ax.set_title(
        f"Distribución de {cont} – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.set_ylabel("Concentración")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    pie_fig(fig)
    guardar(fig, f"15_boxplot_{cont}_{tag}")


# G16 — Comparativa de promedios entre zonas (barras) - por contaminante
def g16_comparativa_promedios_zona(
    df_ias_d, cont, zonas_dict, nombre_zona, periodo, tag
):
    promedios = {}
    for zona, ests in zonas_dict.items():
        valores = []
        for est in ests:
            cols = _buscar_cols_cantidad(df_ias_d, cont, [est])
            if cols:
                valores.append(df_ias_d[cols[0][0]].mean())
        if valores:
            promedios[zona] = np.nanmean(valores)
    if len(promedios) < 2:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(promedios.keys(), promedios.values(), color=["#1f77b4", "#ff7f0e"])
    ax.set_title(
        f"Concentración promedio de {cont} – Comparación de zonas\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.set_ylabel("Concentración promedio")
    pie_fig(fig)
    guardar(fig, f"16_comparativa_promedios_zona_{cont}_{tag}")


# G17 — Evolución mensual (barras) - por contaminante y zona
def g17_evolucion_mensual(df_ias_d, cont, ests, nombre_zona, periodo, tag):
    cols = _buscar_cols_cantidad(df_ias_d, cont, ests)
    if not cols:
        return
    serie_prom = df_ias_d[[c for c, _ in cols]].mean(axis=1, skipna=True)
    mensual = serie_prom.resample("ME").mean()
    meses = mensual.index.strftime("%b")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(meses, mensual.values, color="teal")
    ax.set_title(
        f"Evolución mensual de {cont} – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.set_ylabel("Concentración promedio")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    pie_fig(fig)
    guardar(fig, f"17_evolucion_mensual_{cont}_{tag}")


# G18 — Días fuera de norma (barras verticales) - por zona
def g18_dias_fuera_norma(df_ias_d, conts, ests, nombre_zona, periodo, tag):
    resultado = {}
    for cont in conts:
        cols = _buscar_cols_cantidad(df_ias_d, cont, ests)
        if not cols:
            continue
        serie_prom = df_ias_d[[c for c, _ in cols]].mean(axis=1, skipna=True)
        lim, _, _ = LIMITES.get(cont, (None, "", ""))
        if lim is None:
            continue
        excedencias = (serie_prom > lim).sum()
        resultado[cont] = excedencias
    if not resultado:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(resultado.keys(), resultado.values(), color="coral")
    ax.set_title(
        f"Días fuera de norma – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.set_ylabel("Número de días")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    pie_fig(fig)
    guardar(fig, f"18_dias_fuera_norma_{tag}")


# G19 — Días fuera de norma por estación (barras horizontales) - por contaminante
def g19_dias_fuera_norma_estacion(df_ias_d, cont, ests, nombre_zona, periodo, tag):
    lim, _, _ = LIMITES.get(cont, (None, "", ""))
    if lim is None:
        return
    excedencias = {}
    for est in ests:
        cols = _buscar_cols_cantidad(df_ias_d, cont, [est])
        if not cols:
            continue
        serie = df_ias_d[cols[0][0]]
        excedencias[nombre(est)] = (serie > lim).sum()
    if not excedencias:
        return
    fig, ax = plt.subplots(figsize=(10, max(4, len(excedencias) * 0.5)))
    ests_ord = sorted(excedencias.items(), key=lambda x: x[1], reverse=True)
    nombres = [e[0] for e in ests_ord]
    valores = [e[1] for e in ests_ord]
    ax.barh(nombres, valores, color="darkred")
    ax.set_title(
        f"Días fuera de norma ({cont}) – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.set_xlabel("Número de días (> límite NOM)")
    pie_fig(fig)
    guardar(fig, f"19_excedencias_estacion_{cont}_{tag}")


# G21 — Porcentaje de días por categoría IAS (torta) - por zona
def g21_porcentaje_categorias(df_ias_d, nombre_zona, periodo, tag):
    if "Calidad del aire" not in df_ias_d.columns:
        return
    conteo = df_ias_d["Calidad del aire"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        conteo,
        labels=conteo.index,
        autopct="%1.1f%%",
        colors=[COLORES_CAT.get(c, "#cccccc") for c in conteo.index],
    )
    ax.set_title(
        f"Distribución de la calidad del aire – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    pie_fig(fig)
    guardar(fig, f"21_porcentaje_categorias_{tag}")


# G22 — Comparación de estaciones (barras) - por contaminante
def g22_comparacion_estaciones(df_ias_d, cont, ests, nombre_zona, periodo, tag):
    promedios = {}
    for est in ests:
        cols = _buscar_cols_cantidad(df_ias_d, cont, [est])
        if cols:
            promedios[nombre(est)] = df_ias_d[cols[0][0]].mean()
    if not promedios:
        return
    fig, ax = plt.subplots(figsize=(12, max(5, len(promedios) * 0.5)))
    nombres = list(promedios.keys())
    valores = list(promedios.values())
    lim, _, _ = LIMITES.get(cont, (None, "", ""))
    colores = ["#2ecc71" if (lim is None or v <= lim) else "#e74c3c" for v in valores]
    ax.bar(nombres, valores, color=colores)
    ax.set_title(
        f"Concentración promedio de {cont} por estación – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.set_ylabel("Concentración promedio")
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    pie_fig(fig)
    guardar(fig, f"22_comparacion_estaciones_{cont}_{tag}")


# G23 — Calidad del aire por día de semana (barras apiladas) - por zona
def g23_calidad_dia_semana(df_ias_d, nombre_zona, periodo, tag):
    if "Calidad del aire" not in df_ias_d.columns:
        return
    df_dia = df_ias_d.copy()
    df_dia["Día semana"] = df_dia.index.dayofweek
    mapa_dias = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}
    df_dia["Día"] = df_dia["Día semana"].map(mapa_dias)
    calidad_por_dia = (
        df_dia.groupby("Día")["Calidad del aire"].value_counts().unstack(fill_value=0)
    )
    # Reordenar columnas según CATEGORIAS
    calidad_por_dia = calidad_por_dia.reindex(columns=CATEGORIAS, fill_value=0)
    fig, ax = plt.subplots(figsize=(12, 6))
    calidad_por_dia.plot(
        kind="bar",
        ax=ax,
        color=[COLORES_CAT.get(c, "#ccc") for c in CATEGORIAS],
        width=0.8,
    )
    ax.set_title(
        f"Calidad del aire por día de la semana – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.set_ylabel("Número de días")
    ax.legend(title="Categoría", bbox_to_anchor=(1.05, 1))
    ax.set_xlabel("")
    pie_fig(fig)
    guardar(fig, f"23_calidad_dia_semana_{tag}")


# G24 — Diagrama de dispersión O3 vs NO2 - por zona (promedio de la zona)
def g24_dispersion_o3_no2(df_ias_d, ests, nombre_zona, periodo, tag):
    cols_o3 = _buscar_cols_cantidad(df_ias_d, "O3", ests)
    cols_no2 = _buscar_cols_cantidad(df_ias_d, "NO2", ests)
    if not cols_o3 or not cols_no2:
        return
    df_comb = pd.DataFrame(
        {
            "O3": df_ias_d[[c for c, _ in cols_o3]].mean(axis=1, skipna=True),
            "NO2": df_ias_d[[c for c, _ in cols_no2]].mean(axis=1, skipna=True),
        }
    ).dropna()
    if df_comb.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(df_comb["NO2"], df_comb["O3"], alpha=0.4, color="teal", s=15)
    ax.set_xlabel("NO₂ (ppm)")
    ax.set_ylabel("O₃ (ppm)")
    ax.set_title(
        f"Relación O₃ vs NO₂ – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}"
    )
    ax.grid(alpha=0.3)
    pie_fig(fig)
    guardar(fig, f"24_dispersion_o3_no2_{tag}")


# G25 — Calendario de excedencias (mosaico) - por contaminante y zona
def g25_calendario_excedencias(df_ias_d, cont, ests, nombre_zona, periodo, anio, tag):
    if cont not in LIMITES:
        return
    cols = _buscar_cols_cantidad(df_ias_d, cont, ests)
    if not cols:
        return
    serie_prom = df_ias_d[[c for c, _ in cols]].mean(axis=1, skipna=True)
    lim, _, _ = LIMITES[cont]
    excede = (serie_prom > lim).astype(int)
    fecha_min = excede.index.min()
    fecha_max = excede.index.max()
    fecha_min = fecha_min - pd.Timedelta(days=fecha_min.weekday())
    fecha_max = fecha_max + pd.Timedelta(days=6 - fecha_max.weekday())
    rango = pd.date_range(fecha_min, fecha_max, freq="D")
    semanas = len(rango) // 7
    matriz = np.full((semanas, 7), np.nan)
    for i, fecha in enumerate(rango):
        semana = i // 7
        dia = i % 7
        if fecha in excede.index:
            matriz[semana, dia] = excede.loc[fecha]
    fig, ax = plt.subplots(figsize=(12, max(4, semanas * 0.3)))
    cmap = ListedColormap(["#d4e6f1", "#e74c3c"])
    ax.imshow(matriz, cmap=cmap, aspect="auto", vmin=0, vmax=1)
    # Etiquetas de día
    for semana in range(semanas):
        for dia in range(7):
            idx = semana * 7 + dia
            if idx < len(rango):
                fecha = rango[idx]
                ax.text(dia, semana, fecha.day, ha="center", va="center", fontsize=7)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(
        f"Excedencias ({cont}) – {nombre_zona}\nPeriodo: {periodo[0]} – {periodo[1]}\n(Valor > {lim} {UNIDADES[cont]} – en rojo)",
        fontsize=10,
    )
    pie_fig(fig)
    guardar(fig, f"25_calendario_excedencias_{cont}_{tag}")


# ============================================================================
# HELPERS — buscar columnas independiente del formato
# ============================================================================


def _buscar_cols_aire(df, cont, ests):
    """Retorna lista de (columna, estacion) para columnas AIRE_<cont>_<est>."""
    resultado = []
    for e in ests:
        # Formato sin unidad
        c = f"AIRE_{cont}_{e}"
        if c in df.columns:
            resultado.append((c, e))
            continue
        # Formato con unidad embebida
        for col in df.columns:
            if col.startswith("AIRE_") and col.endswith(f"_{e}"):
                c_cont = extractar_cont(col, "AIRE")
                if c_cont == cont:
                    resultado.append((col, e))
                    break
    return resultado


def _buscar_cols_cantidad(df, cont, ests):
    """Retorna lista de (columna, estacion) para columnas CANTIDAD_<cont>_<est>."""
    resultado = []
    for e in ests:
        c = f"CANTIDAD_{cont}_{e}"
        if c in df.columns:
            resultado.append((c, e))
            continue
        for col in df.columns:
            if col.startswith("CANTIDAD_") and col.endswith(f"_{e}"):
                c_cont = extractar_cont(col, "CANTIDAD")
                if c_cont == cont:
                    resultado.append((col, e))
                    break
    return resultado


# ============================================================================
# ORQUESTADOR PRINCIPAL
# ============================================================================


def generar_todas():
    estilo()
    (
        df_ica,
        df_ias_h,
        df_ias_d,
        df_ica_d,
        contaminantes,
        estaciones,
        periodo,
        anio,
        fmt_h,
        fmt_d,
    ) = cargar_datos()

    total = 0

    # ── Gráficas globales (una sola vez) ─────────────────────────────────────
    print("\n[GLOBAL]")
    g6_calidad_global_mensual(df_ias_d, periodo, anio)
    total += 1

    # ── Por zona ────────────────────────────────────────────────────────────
    for tag, (ests_zona, nombre_zona) in ZONAS.items():
        ests_ok = [e for e in ests_zona if e in estaciones]
        if not ests_ok:
            continue

        print(f"\n{'─' * 60}")
        print(f"Zona: {nombre_zona}")
        print(f"{'─' * 60}")

        # 1) Resúmenes de calidad del aire por grupo (partículas y gases)
        for grupo, conts_grupo in [
            ("particulas", [c for c in contaminantes if c in PARTICULAS]),
            ("gases", [c for c in contaminantes if c in GASES]),
        ]:
            if conts_grupo:
                g5_resumen_zona(
                    df_ias_d, conts_grupo, ests_ok, nombre_zona, periodo, tag, grupo
                )
                total += 1

        # 2) Gráficas por contaminante
        for cont in contaminantes:
            if cont not in LIMITES:
                continue
            print(f"\n  [{cont}]")

            # ICA horario y diario
            g1_ica_horario(df_ica, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}")
            total += 1
            g2_ica_max_diario(
                df_ica, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}"
            )
            total += 1

            # Concentraciones diarias
            g3_concentracion_diaria(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}", fmt_d
            )
            total += 1

            # Días por categoría por estación
            g4_dias_categoria_estacion(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}"
            )
            total += 1

            # Mosaico días fuera de norma (categoría)
            g7_mosaico_fuera_norma(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, anio, f"{tag}_{cont}"
            )
            total += 1

            # Promedio del periodo por estación
            g8_promedios_periodo(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}"
            )
            total += 1

            # Gráficas adicionales por contaminante (G14, G15, G16?, G17, G19, G22, G25)
            g14_evolucion_ica_linea(
                df_ica, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}"
            )
            total += 1
            g15_boxplot_contaminante(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}"
            )
            total += 1
            g17_evolucion_mensual(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}"
            )
            total += 1
            g19_dias_fuera_norma_estacion(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}"
            )
            total += 1
            g22_comparacion_estaciones(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, f"{tag}_{cont}"
            )
            total += 1
            g25_calendario_excedencias(
                df_ias_d, cont, ests_ok, nombre_zona, periodo, anio, f"{tag}_{cont}"
            )
            total += 1

        # 3) Gráficas multi‑contaminante (separadas por partículas y gases)
        particulas = [c for c in contaminantes if c in PARTICULAS]
        gases = [c for c in contaminantes if c in GASES]

        if len(particulas) >= 2:
            g9_pm10_vs_pm25(df_ias_d, ests_ok, nombre_zona, periodo, tag)
            total += 1
            g10_comparativa_contaminantes(
                df_ias_d, particulas, ests_ok, nombre_zona, periodo, tag, "particulas"
            )
            total += 1
            g11_series_comparativas(
                df_ias_d, particulas, ests_ok, nombre_zona, periodo, tag, "particulas"
            )
            total += 1
            g12_correlacion_contaminantes(
                df_ias_d, particulas, ests_ok, nombre_zona, periodo, tag, "particulas"
            )
            total += 1
            g13_perfil_horario(
                df_ias_h, particulas, ests_ok, nombre_zona, periodo, tag, "particulas"
            )
            total += 1

        if len(gases) >= 2:
            g10_comparativa_contaminantes(
                df_ias_d, gases, ests_ok, nombre_zona, periodo, tag, "gases"
            )
            total += 1
            g11_series_comparativas(
                df_ias_d, gases, ests_ok, nombre_zona, periodo, tag, "gases"
            )
            total += 1
            g12_correlacion_contaminantes(
                df_ias_d, gases, ests_ok, nombre_zona, periodo, tag, "gases"
            )
            total += 1
            g13_perfil_horario(
                df_ias_h, gases, ests_ok, nombre_zona, periodo, tag, "gases"
            )
            total += 1

        # 4) Gráficas globales de la zona (independientes del contaminante)
        g16_comparativa_promedios_zona(df_ias_d, cont, ZONAS, nombre_zona, periodo, tag)
        total += 1
        g18_dias_fuera_norma(
            df_ias_d, contaminantes, ests_ok, nombre_zona, periodo, tag
        )
        total += 1
        g21_porcentaje_categorias(df_ias_d, nombre_zona, periodo, tag)
        total += 1
        g23_calidad_dia_semana(df_ias_d, nombre_zona, periodo, tag)
        total += 1
        g24_dispersion_o3_no2(df_ias_d, ests_ok, nombre_zona, periodo, tag)
        total += 1

    print(f"\n{'=' * 60}")
    print(f"✓  {total} gráficas guardadas en '{DIR_SALIDA}/'")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    generar_todas()

    # TODO: Hacer un nuevo script para camibar a otro año
