"""Generador de reportes Excel (.xlsx) para Ganadería JA usando openpyxl.

Crea libros de trabajo con formato corporativo institucional (verde marca,
encabezados destacados, tipos de datos nativos, formatos numéricos y anchos
auto-ajustados) para cada sección del sistema:
- inventario: Hato activo completo, desglose por categorías y razas.
- leche: Producción diaria de leche, promedio por vaca y rendimiento.
- finanzas: Libro de ingresos, egresos, categorías y contrapartes.
- pasturas: Tablero integral de potreros, áreas, ocupación, reposo y aforos.
- sanidad: Historial de tratamientos, medicamentos y retiros de carne/leche.
- reproduccion: Servicios, tactos/palpaciones, partos y banco de pajuelas/termo.
"""
from __future__ import annotations

import io
import re
from datetime import date
from typing import Any, Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..db.database import Database
from ..utils import to_date

# Estilos corporativos Ganadería JA
COLOR_VERDE_HEADER = "1E3A1E"      # Verde institucional oscuro
COLOR_VERDE_HEADER_TXT = "FFFFFF"  # Blanco
COLOR_ZEBRA = "F4FBF4"             # Verde muy pálido para alternar filas
COLOR_SUBTOTAL = "E2F0D9"          # Verde suave para totales
COLOR_BORDE = "D1D5DB"             # Gris claro

FONT_HEADER = Font(name="Calibri", size=11, bold=True, color=COLOR_VERDE_HEADER_TXT)
FONT_BOLD = Font(name="Calibri", size=11, bold=True)
FONT_NORMAL = Font(name="Calibri", size=10)
FONT_TITULO = Font(name="Calibri", size=14, bold=True, color="1E3A1E")
FONT_SUBTITULO = Font(name="Calibri", size=9, italic=True, color="4B5563")

FILL_HEADER = PatternFill(start_color=COLOR_VERDE_HEADER, end_color=COLOR_VERDE_HEADER, fill_type="solid")
FILL_ZEBRA = PatternFill(start_color=COLOR_ZEBRA, end_color=COLOR_ZEBRA, fill_type="solid")
FILL_SUBTOTAL = PatternFill(start_color=COLOR_SUBTOTAL, end_color=COLOR_SUBTOTAL, fill_type="solid")

BORDER_THIN = Border(
    left=Side(style="thin", color=COLOR_BORDE),
    right=Side(style="thin", color=COLOR_BORDE),
    top=Side(style="thin", color=COLOR_BORDE),
    bottom=Side(style="thin", color=COLOR_BORDE),
)

ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")


def _aplicar_cabecera_hoja(ws, titulo_seccion: str, subtitulo: str) -> int:
    """Escribe el banner corporativo en las primeras 2 filas y retorna la fila de inicio de tabla."""
    ws.merge_cells("A1:H1")
    ws["A1"] = f"GANADERÍA JA · {titulo_seccion.upper()}"
    ws["A1"].font = FONT_TITULO
    ws["A1"].alignment = ALIGN_LEFT
    ws.row_dimensions[1].height = 24

    ws.merge_cells("A2:H2")
    ws["A2"] = f"{subtitulo}  |  Fecha de emisión: {date.today().isoformat()}"
    ws["A2"].font = FONT_SUBTITULO
    ws["A2"].alignment = ALIGN_LEFT
    ws.row_dimensions[2].height = 18

    ws.row_dimensions[3].height = 8  # Fila vacía separadora
    return 4


def _estilizar_tabla(ws, fila_inicio: int, columnas: list[str], datos: list[list[Any]],
                     align_map: Optional[dict[int, Alignment]] = None,
                     num_format_map: Optional[dict[int, str]] = None) -> None:
    """Escribe los encabezados y filas de datos con bordes, zebra y formatos."""
    align_map = align_map or {}
    num_format_map = num_format_map or {}

    # Encabezados
    ws.row_dimensions[fila_inicio].height = 22
    for col_idx, col_name in enumerate(columnas, start=1):
        c = ws.cell(row=fila_inicio, column=col_idx, value=col_name)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.alignment = align_map.get(col_idx, ALIGN_CENTER)
        c.border = BORDER_THIN

    # Filas de datos
    fila_actual = fila_inicio + 1
    for r_idx, fila in enumerate(datos):
        ws.row_dimensions[fila_actual].height = 19
        es_zebra = (r_idx % 2 == 1)
        for col_idx, valor in enumerate(fila, start=1):
            c = ws.cell(row=fila_actual, column=col_idx, value=valor)
            c.font = FONT_NORMAL
            c.alignment = align_map.get(col_idx, ALIGN_LEFT)
            c.border = BORDER_THIN
            if es_zebra:
                c.fill = FILL_ZEBRA
            if col_idx in num_format_map:
                c.number_format = num_format_map[col_idx]
        fila_actual += 1

    # Ajuste automático del ancho de columnas
    for col_idx in range(1, len(columnas) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for row in range(fila_inicio, fila_actual):
            val_str = str(ws.cell(row=row, column=col_idx).value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)

    # Activar autofiltro en la tabla
    col_fin_letter = get_column_letter(len(columnas))
    ws.auto_filter.ref = f"A{fila_inicio}:{col_fin_letter}{max(fila_actual - 1, fila_inicio)}"


def _categoria_sg(sexo: Any, fecha_nacimiento: Any, texto_extra: str = "") -> str:
    """Deriva la categoría zootécnica SG por sexo + edad.

    La tabla ``animales`` NO tiene columna ``categoria``: la clasificación SG se
    calcula en Python (igual que ``src/engine/dashboard_data.py``). Se replica
    aquí la misma lógica para que el Excel coincida con Tablero/Inventario.
    """
    hoy = date.today()
    f_nac = to_date(fecha_nacimiento)
    edad_dias: Optional[int] = None
    if f_nac:
        try:
            edad_dias = max(0, (hoy - f_nac).days)
        except Exception:
            edad_dias = None

    s_raw = str(sexo or "").strip().lower()
    es_macho = bool(s_raw.startswith("m") or s_raw in ("macho", "toro", "ternero", "novillo", "buey"))
    es_hembra = bool(s_raw.startswith("h") or s_raw in ("hembra", "vaca", "ternera", "novilla"))

    if es_hembra:
        if edad_dias is None:
            return "Hembra adulta"
        if edad_dias < 365:
            return "Hembras <1 año (Ternera)"
        if edad_dias < 730:
            return "Hembras 1-2 años (Novilla levante)"
        if edad_dias < 1460:
            return "Hembras 2-4 años (Novilla vientre)"
        if edad_dias <= 2921:
            return "Hembras 4-8 años (Vaca adulta)"
        if edad_dias <= 3651:
            return "Hembras 8-10 años"
        return "Hembras >10 años"
    if es_macho:
        txt_info = texto_extra.upper()
        if re.search(r"\b(?:TORO|REPRODUCTOR|PADRON|SEMEN|PAJILLA)\b", txt_info) or (edad_dias is not None and edad_dias >= 913):
            return "Reproductor (Toro)"
        if edad_dias is None:
            return "Macho"
        if edad_dias < 365:
            return "Machos <1 año (Ternero)"
        if edad_dias < 730:
            return "Machos 1-2 años (Novillo)"
        return "Machos >2 años"
    return "Sin clasificar"


def generar_excel_inventario(db: Database) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hato Activo"

    fila_ini = _aplicar_cabecera_hoja(ws, "Informe de Inventario de Ganado", "Hato Activo (estado = 'ACTIVO')")
    columnas = ["Arete / Tag", "Nombre", "Sexo", "Categoría SG", "Raza", "Potrero Actual", "Peso (kg)", "Edad (meses)", "Hierro / Marca", "Color"]

    # Regla de oro de inventario: siempre estado = 'ACTIVO'
    filas_db = db.query("""
        SELECT a.tag, a.nombre, a.sexo, a.raza,
               COALESCE(p.nombre, a.potrero_id, 'Sin potrero') AS potrero,
               (SELECT pes.peso_kg FROM pesajes pes WHERE pes.animal_id = a.id_animal ORDER BY pes.fecha DESC, pes.id DESC LIMIT 1) AS ult_peso,
               ROUND((julianday('now') - julianday(a.fecha_nacimiento)) / 30.4375, 1) AS edad_meses,
               a.hierro, a.color, a.fecha_nacimiento
        FROM animales a
        LEFT JOIN potreros p ON p.id = a.potrero_id OR p.codigo = a.potrero_id
        WHERE a.estado = 'ACTIVO'
        ORDER BY a.tag ASC
    """)

    datos = []
    for r in filas_db:
        categoria = _categoria_sg(r["sexo"], r["fecha_nacimiento"],
                                  f"{r['nombre'] or ''} {r['tag'] or ''}")
        datos.append([
            str(r["tag"] or ""),
            str(r["nombre"] or ""),
            str(r["sexo"] or ""),
            categoria,
            str(r["raza"] or ""),
            str(r["potrero"] or ""),
            float(r["ult_peso"]) if r["ult_peso"] is not None else None,
            float(r["edad_meses"]) if r["edad_meses"] is not None else None,
            str(r["hierro"] or ""),
            str(r["color"] or ""),
        ])

    align_map = {1: ALIGN_CENTER, 3: ALIGN_CENTER, 4: ALIGN_CENTER, 7: ALIGN_RIGHT, 8: ALIGN_RIGHT}
    num_map = {7: "#,##0.0", 8: "#,##0.0"}
    _estilizar_tabla(ws, fila_ini, columnas, datos, align_map, num_map)
    return wb


def generar_excel_leche(db: Database, dias: int = 90) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Producción Leche"

    fila_ini = _aplicar_cabecera_hoja(ws, "Informe de Producción Lechera", f"Control Diario de Tanque (Últimos {dias} días)")
    columnas = ["Fecha", "Litros Totales (L)", "Vacas en Ordeño", "Promedio L/Vaca/Día", "Notas / Observaciones"]

    # ``produccion_leche`` guarda un registro por animal/día (``litros`` es por
    # vaca). Se agrega por fecha: total de litros y nº de vacas ordenadas.
    filas_db = db.query("""
        SELECT fecha,
               SUM(litros) AS litros_total,
               COUNT(DISTINCT animal_id) AS n_vacas,
               MAX(notas) AS notas
        FROM produccion_leche
        WHERE litros IS NOT NULL AND litros > 0
        GROUP BY fecha
        ORDER BY fecha DESC LIMIT ?
    """, (dias,))

    datos = []
    for r in filas_db:
        litros_total = float(r["litros_total"]) if r["litros_total"] is not None else 0.0
        n_vacas = int(r["n_vacas"] or 0)
        l_por_vaca = round(litros_total / n_vacas, 2) if n_vacas > 0 else None
        datos.append([
            str(r["fecha"] or ""),
            litros_total,
            n_vacas or None,
            l_por_vaca,
            str(r["notas"] or ""),
        ])

    align_map = {1: ALIGN_CENTER, 2: ALIGN_RIGHT, 3: ALIGN_RIGHT, 4: ALIGN_RIGHT}
    num_map = {2: "#,##0.0", 3: "#,##0", 4: "#,##0.00"}
    _estilizar_tabla(ws, fila_ini, columnas, datos, align_map, num_map)
    return wb


def generar_excel_finanzas(db: Database, dias: int = 180) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Flujo de Caja"

    fila_ini = _aplicar_cabecera_hoja(ws, "Informe Financiero y Flujo de Caja", f"Movimientos Contables (Últimos {dias} días)")
    columnas = ["Fecha", "Tipo", "Categoría", "Concepto / Detalle", "Monto ($)", "Litros", "Contraparte / Proveedor", "Potrero", "Notas"]

    filas_db = db.query("""
        SELECT f.fecha, f.tipo, f.categoria, f.concepto, f.monto, f.litros, f.contraparte,
               COALESCE(p.nombre, f.potrero_id) AS potrero, f.notas
        FROM finanzas f
        LEFT JOIN potreros p ON p.id = f.potrero_id OR p.codigo = f.potrero_id
        ORDER BY f.fecha DESC LIMIT ?
    """, (dias,))

    datos = []
    for r in filas_db:
        datos.append([
            str(r["fecha"] or ""),
            str(r["tipo"] or ""),
            str(r["categoria"] or ""),
            str(r["concepto"] or ""),
            float(r["monto"]) if r["monto"] is not None else 0.0,
            float(r["litros"]) if r["litros"] is not None else None,
            str(r["contraparte"] or ""),
            str(r["potrero"] or ""),
            str(r["notas"] or ""),
        ])

    align_map = {1: ALIGN_CENTER, 2: ALIGN_CENTER, 3: ALIGN_CENTER, 5: ALIGN_RIGHT, 6: ALIGN_RIGHT}
    num_map = {5: "$#,##0", 6: "#,##0.0"}
    _estilizar_tabla(ws, fila_ini, columnas, datos, align_map, num_map)
    return wb


def generar_excel_pasturas(db: Database) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Potreros y Pasturas"

    fila_ini = _aplicar_cabecera_hoja(ws, "Tablero de Potreros y Pasturas (Voisin)", "Estado de Rotación, Ocupación, Reposo y Aforos")
    columnas = ["Potrero", "Área (ha)", "Estado Rotación", "Días Ocupación", "Días Reposo", "Cabezas Activas", "Aforo Reciente (kg/m²)", "Biomasa MS (kg/ha)", "Tipo Pasto"]

    # Consulta consolidada de potreros reales
    filas_db = db.query("""
        SELECT p.nombre, p.area_has, p.tipo_pasto,
               (SELECT COUNT(*) FROM animales a WHERE a.estado = 'ACTIVO' AND (a.potrero_id = p.id OR a.potrero_id = p.nombre OR a.potrero_id = p.codigo)) AS total_animales,
               (SELECT afo.aforo_kg_m2 FROM aforos_historico afo WHERE afo.potrero_id = p.id OR afo.potrero_id = p.nombre ORDER BY afo.fecha DESC, afo.id DESC LIMIT 1) AS ult_aforo,
               (SELECT m.biomasa_estimada_kg_ha FROM monitoreo_satelital_ndvi m WHERE m.potrero_id = p.id OR m.potrero_id = p.nombre ORDER BY m.fecha DESC LIMIT 1) AS ult_biomasa,
               (SELECT CAST(ROUND(julianday('now') - julianday(t.fecha)) AS INT) FROM traslados t WHERE (t.potrero_destino = p.id OR t.potrero_destino = p.nombre) ORDER BY t.fecha DESC, t.id DESC LIMIT 1) AS dias_evento
        FROM potreros p
        WHERE (p.geom_wkt_4326 IS NOT NULL OR NOT EXISTS (SELECT 1 FROM potreros WHERE geom_wkt_4326 IS NOT NULL))
        ORDER BY p.nombre ASC
    """)

    datos = []
    for r in filas_db:
        n_anim = int(r["total_animales"] or 0)
        dias_ev = r["dias_evento"]
        dias_ocup = dias_ev if n_anim > 0 else None
        dias_rep = dias_ev if n_anim == 0 else None
        estado = "En Ocupación" if n_anim > 0 else "En Reposo"

        datos.append([
            str(r["nombre"] or ""),
            float(r["area_has"]) if r["area_has"] is not None else None,
            estado,
            dias_ocup,
            dias_rep,
            n_anim,
            float(r["ult_aforo"]) if r["ult_aforo"] is not None else None,
            float(r["ult_biomasa"]) if r["ult_biomasa"] is not None else None,
            str(r["tipo_pasto"] or ""),
        ])

    align_map = {2: ALIGN_RIGHT, 3: ALIGN_CENTER, 4: ALIGN_RIGHT, 5: ALIGN_RIGHT, 6: ALIGN_RIGHT, 7: ALIGN_RIGHT, 8: ALIGN_RIGHT}
    num_map = {2: "#,##0.0", 4: "#,##0", 5: "#,##0", 6: "#,##0", 7: "#,##0.00", 8: "#,##0"}
    _estilizar_tabla(ws, fila_ini, columnas, datos, align_map, num_map)
    return wb


def generar_excel_sanidad(db: Database, dias: int = 180) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tratamientos Sanitarios"

    fila_ini = _aplicar_cabecera_hoja(ws, "Informe Sanitario y Tratamientos", f"Registro Clínico y Control de Retiros (Últimos {dias} días)")
    columnas = ["Fecha", "Animal (Tag)", "Producto", "Principio Activo", "Dosis", "Vía", "Retiro Carne (d)", "Retiro Leche (d)", "Diagnóstico / Motivo", "Veterinario / Resp."]

    filas_db = db.query("""
        SELECT t.fecha, a.tag, t.producto, t.principio_activo, t.dosis, t.via,
               t.dias_retiro_carne, t.dias_retiro_leche, t.diagnostico
        FROM tratamientos t
        JOIN animales a ON a.id_animal = t.animal_id
        ORDER BY t.fecha DESC LIMIT ?
    """, (dias,))

    datos = []
    for r in filas_db:
        datos.append([
            str(r["fecha"] or ""),
            str(r["tag"] or ""),
            str(r["producto"] or ""),
            str(r["principio_activo"] or ""),
            str(r["dosis"] or ""),
            str(r["via"] or "IM"),
            int(r["dias_retiro_carne"]) if r["dias_retiro_carne"] is not None else 0,
            int(r["dias_retiro_leche"]) if r["dias_retiro_leche"] is not None else 0,
            str(r["diagnostico"] or ""),
            "",
        ])

    align_map = {1: ALIGN_CENTER, 2: ALIGN_CENTER, 6: ALIGN_CENTER, 7: ALIGN_RIGHT, 8: ALIGN_RIGHT}
    num_map = {7: "#,##0", 8: "#,##0"}
    _estilizar_tabla(ws, fila_ini, columnas, datos, align_map, num_map)
    return wb


def generar_excel_reproduccion(db: Database) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()

    # Hoja 1: Tactos y Palpaciones (Software Ganadero)
    ws1 = wb.active
    ws1.title = "Tactos y Palpaciones"
    fila_ini1 = _aplicar_cabecera_hoja(ws1, "Tactos / Palpaciones Ginecológicas", "Diagnósticos de Gestación (SG)")
    cols1 = ["Fecha", "Vaca / Tag", "Resultado", "Días Gestación", "Método", "Hallazgo", "Detalle / Notas", "Toro / Pajuela", "Veterinario"]
    
    filas_dg = db.query("""
        SELECT dg.fecha, a.tag, dg.resultado, dg.dias_gestacion, dg.metodo, dg.hallazgo, dg.detalle, dg.toro_pajuela, dg.responsable
        FROM diagnosticos_gestacion dg
        JOIN animales a ON a.id_animal = dg.vaca_id
        ORDER BY dg.fecha DESC, dg.id DESC LIMIT 100
    """)
    datos1 = []
    for r in filas_dg:
        datos1.append([
            str(r["fecha"] or ""),
            str(r["tag"] or ""),
            str(r["resultado"] or ""),
            int(r["dias_gestacion"]) if r["dias_gestacion"] is not None else None,
            str(r["metodo"] or "TACTO"),
            str(r["hallazgo"] or ""),
            str(r["detalle"] or ""),
            str(r["toro_pajuela"] or ""),
            str(r["responsable"] or ""),
        ])
    _estilizar_tabla(ws1, fila_ini1, cols1, datos1, {1: ALIGN_CENTER, 2: ALIGN_CENTER, 3: ALIGN_CENTER, 4: ALIGN_RIGHT, 5: ALIGN_CENTER}, {4: "#,##0"})

    # Hoja 2: Banco de Pajuelas
    ws2 = wb.create_sheet(title="Banco Pajuelas")
    fila_ini2 = _aplicar_cabecera_hoja(ws2, "Inventario de Pajuelas de Semen", "Termo Criogénico de Nitrógeno")
    cols2 = ["Código Toro", "Raza", "Canastilla", "Cantidad / Saldo", "Costo Unitario ($)", "Procedencia / Casa", "Fecha Ingreso"]
    
    pajuelas = db.listar_pajuelas()
    datos2 = []
    for p in pajuelas:
        datos2.append([
            str(p["codigo_toro"] or ""),
            str(p["raza"] or ""),
            str(p["canastilla"] or ""),
            int(p["cantidad"] or 0),
            float(p["costo"] or 0.0),
            str(p["procedencia"] or ""),
            str(p["fecha_ingreso"] or ""),
        ])
    _estilizar_tabla(ws2, fila_ini2, cols2, datos2, {1: ALIGN_CENTER, 3: ALIGN_CENTER, 4: ALIGN_RIGHT, 5: ALIGN_RIGHT, 7: ALIGN_CENTER}, {4: "#,##0", 5: "$#,##0"})

    # Hoja 3: Servicios e Inseminación
    ws3 = wb.create_sheet(title="Servicios e IA")
    fila_ini3 = _aplicar_cabecera_hoja(ws3, "Servicios y Montas", "Historial Reproductivo del Hato")
    cols3 = ["Fecha", "Vaca / Tag", "Tipo Servicio", "Toro / Pajuela", "Inseminador", "FEP Calculada", "Estado"]
    
    filas_serv = db.query("""
        SELECT s.fecha, a.tag, s.tipo_servicio, s.toro_pajilla, s.inseminador, s.fep_calculada, s.estado
        FROM servicios s
        JOIN animales a ON a.id_animal = s.vaca_id
        ORDER BY s.fecha DESC LIMIT 100
    """)
    datos3 = []
    for r in filas_serv:
        datos3.append([
            str(r["fecha"] or ""),
            str(r["tag"] or ""),
            str(r["tipo_servicio"] or "IA"),
            str(r["toro_pajilla"] or ""),
            str(r["inseminador"] or ""),
            str(r["fep_calculada"] or ""),
            str(r["estado"] or "SERVIDA"),
        ])
    _estilizar_tabla(ws3, fila_ini3, cols3, datos3, {1: ALIGN_CENTER, 2: ALIGN_CENTER, 3: ALIGN_CENTER, 6: ALIGN_CENTER, 7: ALIGN_CENTER})

    return wb


def exportar_excel_bytes(db: Database, seccion: str, dias: int = 90) -> bytes:
    """Genera el libro Excel para la sección solicitada y devuelve los bytes en memoria."""
    sec = str(seccion or "inventario").strip().lower()
    if sec in ("leche", "produccion"):
        wb = generar_excel_leche(db, dias)
    elif sec in ("finanzas", "caja", "gastos"):
        wb = generar_excel_finanzas(db, dias)
    elif sec in ("pasturas", "potreros", "aforos"):
        wb = generar_excel_pasturas(db)
    elif sec in ("sanidad", "tratamientos", "salud"):
        wb = generar_excel_sanidad(db, dias)
    elif sec in ("repro", "reproduccion", "pajuelas", "palpaciones", "tactos"):
        wb = generar_excel_reproduccion(db)
    else:
        wb = generar_excel_inventario(db)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
