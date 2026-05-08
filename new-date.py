import openpyxl
from datetime import datetime

# Archivos
archivo_original = "datos/datos_calidad_aire_2025.xlsx"
archivo_nuevo = "datos/datos_calidad_aire_2026.xlsx"
nuevo_anio = 2026  # Cambia al año que desees

# Cargar el libro de trabajo
wb = openpyxl.load_workbook(archivo_original)
ws = wb.active

# Las filas 1-3 son los encabezados. Los datos empiezan en la fila 4
for row in range(4, ws.max_row + 1):
    celda = ws.cell(row, 1)  # Primera columna (Fecha & Hora)
    if celda.value and isinstance(celda.value, str):
        try:
            # Convertir de formato "dd/mm/yyyy HH:MM"
            dt = datetime.strptime(celda.value, "%d/%m/%Y %H:%M")
            # Cambiar el año
            dt = dt.replace(year=nuevo_anio)
            # Volver a escribir en el mismo formato
            celda.value = dt.strftime("%d/%m/%Y %H:%M")
        except:
            # Si la celda no es una fecha válida, la dejamos igual
            pass

# Guardar el archivo modificado
wb.save(archivo_nuevo)
print(f"Archivo generado: {archivo_nuevo} con fechas del año {nuevo_anio}")