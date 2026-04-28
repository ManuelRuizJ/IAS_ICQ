"""
formato/aire_formato.py
-----------------------
Estilos para hojas AIRE Y SALUD y DIARIO (NOM-172-2023).

Reconoce la nueva nomenclatura:
  AIRE_<unidad>_<contaminante>_<estacion>     → columna de categoría
  CANTIDAD_<unidad>_<contaminante>_<estacion> → columna numérica
  Calidad del aire                            → columna de categoría global
"""

import json
import re
from openpyxl.styles import PatternFill, Alignment, Font
from openpyxl.utils import get_column_letter

with open("config.json", "r", encoding="utf-8") as _f:
    _cfg = json.load(_f)

COLORES_NOM: dict = _cfg["NOM"]["colores"]

<<<<<<< HEAD
# Patrón para detectar contaminante dentro del nombre de columna CANTIDAD_
_PAT_CANT = re.compile(r"^CANTIDAD_[^_]+_([^_]+)_")
=======
# en formato/aire_formato.py
_PAT_CANT = re.compile(r'^CANTIDAD_[^_]+_([^_]+)_')  # grupo1: contaminante
>>>>>>> main


def aplicar_formato_aire(ws) -> None:
    """Aplica colores NOM-172 y formato numérico a una hoja AIRE o DIARIO."""

    # Identificar columnas de categoría
    columnas_cat = []
    for col in ws.iter_cols(min_row=1, max_row=1):
        nombre = col[0].value
        if isinstance(nombre, str):
            if (
                nombre.startswith("AIRE_") and "CANTIDAD" not in nombre
            ) or nombre == "Calidad del aire":
                columnas_cat.append(col[0].column)

    # Alineación global
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(
                wrap_text=True, horizontal="center", vertical="center"
            )

    # Encabezado en negrita
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Colores en columnas de categoría
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.column in columnas_cat and cell.value in COLORES_NOM:
                cell.fill = PatternFill(
                    start_color=COLORES_NOM[cell.value],
                    end_color=COLORES_NOM[cell.value],
                    fill_type="solid",
                )
                color_fuente = (
                    "000000" if cell.value in ("Buena", "Aceptable") else "FFFFFF"
                )
                cell.font = Font(bold=True, color=color_fuente)

    # Formato numérico en columnas de cantidad (detecta contaminante por regex)
    for col in ws.columns:
        nombre = col[0].value
        if isinstance(nombre, str) and nombre.startswith("CANTIDAD_"):
            m = _PAT_CANT.match(nombre)
            cont = m.group(1) if m else ""
            if cont in ("O3", "NO2", "SO2"):
                fmt = "0.000"
            elif cont == "CO":
                fmt = "0.00"
            else:
                fmt = "0"
            for cell in col[1:]:
                if cell.value is not None:
                    cell.number_format = fmt

    # Ancho automático
    for col in ws.columns:
        max_len = max((len(str(cell.value)) for cell in col if cell.value), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(
            max_len + 4, 50
        )

    # Alto de filas
    for row in ws.iter_rows():
        ws.row_dimensions[row[0].row].height = 25
