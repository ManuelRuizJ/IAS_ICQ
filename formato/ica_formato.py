"""
formato/ica_formato.py
----------------------
Aplicación de colores y estilos a las hojas del Excel de ICA (NADF-009).
"""

import json
import pandas as pd
from openpyxl.styles import PatternFill, Alignment, Font
from openpyxl.utils import get_column_letter


# Cargar colores desde config al importar el módulo
with open("config.json", "r", encoding="utf-8") as _f:
    _cfg = json.load(_f)

COLORES_NADF: dict = {
    tuple(map(int, k.split("-"))): v for k, v in _cfg["NADF"]["colores"].items()
}


def obtener_color_ica(valor: int) -> str | None:
    """
    Devuelve el código hexadecimal de color NADF-009 para un valor ICA dado.
    Retorna None si el valor no cae en ningún rango.
    """
    for (lo, hi), color in COLORES_NADF.items():
        if lo <= valor <= hi:
            return color
    return None


def aplicar_formato_ica(ws) -> None:
    """
    Aplica formato visual a una hoja de ICA:
      - Alineación centrada con ajuste de texto
      - Encabezado en negrita
      - Fondo de color según rango ICA en celdas de datos
      - Ancho de columna automático
      - Alto de fila fijo
    """
    # Alineación global
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(
                wrap_text=True, horizontal="center", vertical="center"
            )

    # Encabezado en negrita
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Colores según valor ICA
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if (
                cell.column > 1
                and isinstance(cell.value, (int, float))
                and not pd.isna(cell.value)
            ):
                color = obtener_color_ica(int(cell.value))
                if color:
                    cell.fill = PatternFill(
                        start_color=color, end_color=color, fill_type="solid"
                    )

    # Ancho de columnas
    for col in ws.columns:
        max_len = max((len(str(cell.value)) for cell in col if cell.value), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(
            max_len + 4, 50
        )

    # Alto de filas
    for row in ws.iter_rows():
        ws.row_dimensions[row[0].row].height = 25
