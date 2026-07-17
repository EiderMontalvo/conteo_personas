"""
app/services/excel_service.py
------------------------------
Servicio responsable de generar y parsear archivos Excel (.xlsx).
Multiples hojas: Eventos, Resumen, Estadisticas por camara, por hora, por dia.
Valida columnas requeridas y evita duplicados en la importacion.
"""
from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

import pytz

# ─── Exportacion ──────────────────────────────────────────────────────────────

def build_excel(
    events: list,
    cam_names: dict,
    tz_name: str,
    date_from: Optional[str],
    date_to: Optional[str],
) -> io.BytesIO:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    tz = pytz.timezone(tz_name)

    wb = openpyxl.Workbook()

    # --- Estilos ---
    header_fill = PatternFill("solid", fgColor="1E3A5F")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    alt_fill    = PatternFill("solid", fgColor="EBF0FA")
    thin        = Side(style="thin")
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center_align = Alignment(horizontal="center", vertical="center")

    def style_header(ws, headers):
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border

    def auto_width(ws):
        for col in ws.columns:
            max_len = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 30)

    # 1. Hoja: Eventos (Registro detallado)
    ws_events = wb.active
    ws_events.title = "Eventos"
    headers_events = ["Fecha", "Hora", "Camara", "Entradas", "Salidas", "Personas Dentro", "Tipo de Registro"]
    style_header(ws_events, headers_events)

    total_in = 0
    total_out = 0

    stats_cam  = defaultdict(lambda: {"in": 0, "out": 0})
    stats_hour = defaultdict(lambda: {"in": 0, "out": 0})
    stats_day  = defaultdict(lambda: {"in": 0, "out": 0})

    for i, e in enumerate(events, start=2):
        ts_local = e.timestamp.replace(tzinfo=timezone.utc).astimezone(tz)
        fecha    = ts_local.strftime("%Y-%m-%d")
        hora     = ts_local.strftime("%H:%M:%S")
        cam      = cam_names.get(e.camera_id, f"Camara {e.camera_id}")
        entradas = e.in_count or 0
        salidas  = e.out_count or 0
        personas = e.people_inside or 0
        tipo     = e.event_type or "change_event"

        total_in  += entradas
        total_out += salidas

        stats_cam[cam]["in"]  += entradas
        stats_cam[cam]["out"] += salidas

        hora_corta = ts_local.strftime("%H:00")
        stats_hour[f"{fecha} {hora_corta}"]["in"]  += entradas
        stats_hour[f"{fecha} {hora_corta}"]["out"] += salidas

        stats_day[fecha]["in"]  += entradas
        stats_day[fecha]["out"] += salidas

        row_data = [fecha, hora, cam, entradas, salidas, personas, tipo]
        ws_events.append(row_data)

        for col_idx in range(1, len(row_data) + 1):
            cell = ws_events.cell(row=i, column=col_idx)
            cell.border = thin_border
            cell.alignment = center_align
            if i % 2 == 0:
                cell.fill = alt_fill

    auto_width(ws_events)

    # 2. Hoja: Resumen
    ws_sum = wb.create_sheet("Resumen")
    style_header(ws_sum, ["Indicador", "Valor"])
    ws_sum.append(["Total Entradas", total_in])
    ws_sum.append(["Total Salidas", total_out])
    ws_sum.append(["Flujo Neto Total", total_in - total_out])
    ws_sum.append(["Periodo", f"{date_from or 'inicio'} - {date_to or 'hoy'}"])
    ws_sum.append(["Zona horaria", tz_name])
    auto_width(ws_sum)

    # 3. Hoja: Estadisticas por camara
    ws_cam = wb.create_sheet("Estadisticas por camara")
    style_header(ws_cam, ["Camara", "Entradas", "Salidas", "Flujo Neto"])
    for cam, data in stats_cam.items():
        ws_cam.append([cam, data["in"], data["out"], data["in"] - data["out"]])
    auto_width(ws_cam)

    # 4. Hoja: Estadisticas por hora
    ws_hour = wb.create_sheet("Estadisticas por hora")
    style_header(ws_hour, ["Fecha y Hora", "Entradas", "Salidas", "Flujo Neto"])
    for fh, data in sorted(stats_hour.items()):
        ws_hour.append([fh, data["in"], data["out"], data["in"] - data["out"]])
    auto_width(ws_hour)

    # 5. Hoja: Estadisticas por dia
    ws_day = wb.create_sheet("Estadisticas por dia")
    style_header(ws_day, ["Fecha", "Entradas", "Salidas", "Flujo Neto"])
    for d, data in sorted(stats_day.items()):
        ws_day.append([d, data["in"], data["out"], data["in"] - data["out"]])
    auto_width(ws_day)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


# ─── Importacion ──────────────────────────────────────────────────────────────

def parse_excel(
    file_bytes: bytes,
    tz_name: str,
    cam_name_to_id: dict,
) -> tuple[list[dict], list[str]]:
    """
    Lee un archivo .xlsx y devuelve una tupla (registros, errores).
    Columnas requeridas: Fecha, Hora, Camara, Entradas, Salidas.
    """
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb["Eventos"] if "Eventos" in wb.sheetnames else wb.active

    raw_headers = [str(c.value or "").strip().lower() for c in next(ws.iter_rows(min_row=1, max_row=1))]

    required_cols = {"fecha", "hora", "camara", "entradas", "salidas"}
    # Normalizar tilde
    if "cámara" in raw_headers and "camara" not in raw_headers:
        raw_headers[raw_headers.index("cámara")] = "camara"

    missing = required_cols - set(raw_headers)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(sorted(missing))}")

    col = {h: i for i, h in enumerate(raw_headers)}
    tz  = pytz.timezone(tz_name)

    records: list[dict] = []
    errors:  list[str]  = []
    seen: set = set()

    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        try:
            fecha_val    = row[col["fecha"]]
            hora_val     = row[col["hora"]]
            entradas_val = row[col["entradas"]]
            salidas_val  = row[col["salidas"]]

            if fecha_val is None and hora_val is None:
                continue

            entradas = max(0, int(entradas_val or 0))
            salidas  = max(0, int(salidas_val  or 0))

            personas_dentro = 0
            if "personas dentro" in col:
                pd_val = row[col["personas dentro"]]
                personas_dentro = int(pd_val) if pd_val else 0

            fecha_str = str(fecha_val).strip()[:10]
            hora_str  = str(hora_val).strip()[:8]
            if len(hora_str) == 5:
                hora_str += ":00"
            hora_str = hora_str.replace(".", ":")

            dt_local = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M:%S")
            dt_local = tz.localize(dt_local)
            dt_utc   = dt_local.astimezone(timezone.utc)

            cam_name = str(row[col["camara"]]).strip() if row[col["camara"]] else None
            cam_id   = cam_name_to_id.get((cam_name or "").lower(), 0)

            unique_key = (dt_utc.timestamp(), cam_id)
            if unique_key in seen:
                continue
            seen.add(unique_key)

            records.append({
                "camera_id":      cam_id,
                "in_count":       entradas,
                "out_count":      salidas,
                "people_inside":  personas_dentro,
                "event_type":     "imported",
                "location_group": None,
                "timestamp":      dt_utc,
            })

        except Exception as exc:
            errors.append(f"Fila {row_num}: {exc}")

    return records, errors
