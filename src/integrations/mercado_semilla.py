"""Semilla histórica de precios de mercado (datos de referencia jul-sep 2026).

Son datos de referencia de julio-septiembre 2026 (no cotizaciones reales):
tabla extraída VERBATIM de ``src/db/database.py`` (antes ``TABLA_BASE_HISTORICA``
en ``sembrar_precios_mercado_iniciales``). Procedencia: valores de referencia
inspirados en boletines de subastas del Meta/Casanare/Bogotá (Sugameta,
Subagaucho, Suballanos, Subacasanare, FEDEGÁN), acopios/industria láctea,
MinAgricultura USP y TRM del Banco de la República; sirven solo como punto de
partida cuando ``precios_mercado`` está vacía, hasta sincronizar con
``/api/mercado/sincronizar``.

Estructura por fila: (plaza, producto, unidad, fuente, notas, [precios_7_semanas])
en el mismo orden que las semanas ``2026-07-29`` … ``2026-09-09``.
"""
from __future__ import annotations

# Semanas históricas para análisis de tendencia (7 semanas consecutivas)
FECHAS_SEMILLA_MERCADO = [
    "2026-07-29",
    "2026-08-05",
    "2026-08-12",
    "2026-08-19",
    "2026-08-26",
    "2026-09-02",
    "2026-09-09",
]

# Matriz histórica de cotizaciones semanales ($/kg en pie / insumos)
# (plaza, producto, unidad, fuente, notas, [precios_7_semanas])
PRECIOS_SEMILLA_HISTORICO = [
    # 1. Granada (Meta) - SubaGranada / Sugameta (Ariari - plaza local 68 km)
    ("GRANADA", "MACHO_GORDO", "$/kg", "Sugameta Granada", "Subasta semanal del Ariari (martes/jueves)", [8250.0, 8300.0, 8280.0, 8350.0, 8380.0, 8400.0, 8450.0]),
    ("GRANADA", "MACHO_LEVANTE", "$/kg", "Sugameta Granada", "Novillos 200-300 kg", [8750.0, 8800.0, 8850.0, 8850.0, 8900.0, 8900.0, 8950.0]),
    ("GRANADA", "TERNERO_DESTETO", "$/kg", "Sugameta Granada", "Destetos macho 7-9 meses", [9550.0, 9520.0, 9480.0, 9450.0, 9420.0, 9450.0, 9400.0]),
    ("GRANADA", "HEMBRA_LEVANTE", "$/kg", "Sugameta Granada", "Novillas de levante", [7450.0, 7480.0, 7500.0, 7520.0, 7550.0, 7580.0, 7600.0]),
    ("GRANADA", "VACA_GORDA", "$/kg", "Sugameta Granada", "Vacas gordas y descarte", [6380.0, 6360.0, 6350.0, 6320.0, 6350.0, 6350.0, 6350.0]),

    # 2. Guamal (Meta) - Sugameta Guamal (115 km)
    ("GUAMAL", "MACHO_GORDO", "$/kg", "Sugameta Guamal", "Subasta tradicional del Piedemonte", [8180.0, 8220.0, 8250.0, 8300.0, 8320.0, 8350.0, 8380.0]),
    ("GUAMAL", "MACHO_LEVANTE", "$/kg", "Sugameta Guamal", "Toretes de levante", [8680.0, 8720.0, 8750.0, 8780.0, 8800.0, 8820.0, 8850.0]),
    ("GUAMAL", "TERNERO_DESTETO", "$/kg", "Sugameta Guamal", "Terneros destetos", [9450.0, 9420.0, 9380.0, 9350.0, 9320.0, 9350.0, 9300.0]),
    ("GUAMAL", "HEMBRA_LEVANTE", "$/kg", "Sugameta Guamal", "Hembras levante", [7350.0, 7380.0, 7400.0, 7420.0, 7450.0, 7480.0, 7500.0]),
    ("GUAMAL", "VACA_GORDA", "$/kg", "Sugameta Guamal", "Descarte", [6280.0, 6260.0, 6280.0, 6300.0, 6300.0, 6300.0, 6300.0]),

    # 3. San Martín (Meta) - Sugameta San Martín (95 km)
    ("SAN_MARTIN", "MACHO_GORDO", "$/kg", "Sugameta San Martín", "Plaza ganadera histórica", [8200.0, 8240.0, 8260.0, 8320.0, 8350.0, 8380.0, 8400.0]),
    ("SAN_MARTIN", "MACHO_LEVANTE", "$/kg", "Sugameta San Martín", "Levante comercial", [8700.0, 8750.0, 8800.0, 8820.0, 8850.0, 8880.0, 8900.0]),
    ("SAN_MARTIN", "TERNERO_DESTETO", "$/kg", "Sugameta San Martín", "Destetos", [9500.0, 9480.0, 9420.0, 9400.0, 9380.0, 9400.0, 9350.0]),
    ("SAN_MARTIN", "HEMBRA_LEVANTE", "$/kg", "Sugameta San Martín", "Hembras cría", [7400.0, 7420.0, 7450.0, 7480.0, 7500.0, 7520.0, 7550.0]),
    ("SAN_MARTIN", "VACA_GORDA", "$/kg", "Sugameta San Martín", "Vaca descarte", [6300.0, 6280.0, 6300.0, 6300.0, 6320.0, 6320.0, 6320.0]),

    # 4. Puerto López (Meta) - Suballanos (215 km)
    ("PUERTO_LOPEZ", "MACHO_GORDO", "$/kg", "Suballanos", "Ganadería de altillanura", [8120.0, 8160.0, 8180.0, 8220.0, 8250.0, 8280.0, 8300.0]),
    ("PUERTO_LOPEZ", "MACHO_LEVANTE", "$/kg", "Suballanos", "Llanos sabana", [8620.0, 8660.0, 8700.0, 8720.0, 8750.0, 8780.0, 8800.0]),
    ("PUERTO_LOPEZ", "TERNERO_DESTETO", "$/kg", "Suballanos", "Destetos sabana", [9400.0, 9360.0, 9320.0, 9300.0, 9280.0, 9300.0, 9250.0]),
    ("PUERTO_LOPEZ", "HEMBRA_LEVANTE", "$/kg", "Suballanos", "Hembras", [7320.0, 7350.0, 7380.0, 7400.0, 7420.0, 7430.0, 7450.0]),
    ("PUERTO_LOPEZ", "VACA_GORDA", "$/kg", "Suballanos", "Vaca gorda", [6220.0, 6200.0, 6220.0, 6220.0, 6250.0, 6250.0, 6250.0]),

    # 5. Villavicencio (Meta) - Catama / Subagaucho (145 km)
    ("CATAMA", "MACHO_GORDO", "$/kg", "Subagaucho Catama", "Concentrador regional de los Llanos", [8350.0, 8400.0, 8420.0, 8460.0, 8500.0, 8520.0, 8550.0]),
    ("CATAMA", "MACHO_LEVANTE", "$/kg", "Subagaucho Catama", "Mayor liquidez", [8900.0, 8950.0, 9000.0, 9020.0, 9050.0, 9080.0, 9100.0]),
    ("CATAMA", "TERNERO_DESTETO", "$/kg", "Subagaucho Catama", "Terneros calidad", [9650.0, 9600.0, 9580.0, 9550.0, 9520.0, 9580.0, 9550.0]),
    ("CATAMA", "HEMBRA_LEVANTE", "$/kg", "Subagaucho Catama", "Novillas seleccionadas", [7550.0, 7580.0, 7600.0, 7620.0, 7650.0, 7680.0, 7700.0]),
    ("CATAMA", "VACA_GORDA", "$/kg", "Subagaucho Catama", "Vacas gordas", [6420.0, 6400.0, 6420.0, 6420.0, 6450.0, 6450.0, 6450.0]),

    # 6. Yopal (Casanare) - Subacasanare (395 km)
    ("YOPAL", "MACHO_GORDO", "$/kg", "Subacasanare", "Norte de los Llanos", [8080.0, 8120.0, 8150.0, 8180.0, 8200.0, 8220.0, 8250.0]),
    ("YOPAL", "MACHO_LEVANTE", "$/kg", "Subacasanare", "Gran oferta de levante", [8580.0, 8620.0, 8660.0, 8680.0, 8700.0, 8720.0, 8750.0]),
    ("YOPAL", "TERNERO_DESTETO", "$/kg", "Subacasanare", "Desteto sabanero", [9350.0, 9300.0, 9280.0, 9250.0, 9220.0, 9250.0, 9200.0]),
    ("YOPAL", "HEMBRA_LEVANTE", "$/kg", "Subacasanare", "Hembras cría", [7280.0, 7300.0, 7320.0, 7350.0, 7380.0, 7380.0, 7400.0]),
    ("YOPAL", "VACA_GORDA", "$/kg", "Subacasanare", "Descarte sabanero", [6120.0, 6100.0, 6120.0, 6120.0, 6150.0, 6150.0, 6150.0]),

    # 7. Bogotá (Cundinamarca) - Guadalupe / Frigoríficos (240 km)
    ("BOGOTA", "MACHO_GORDO", "$/kg", "Frigorífico Guadalupe / DANE", "Mercado terminal consumo capital", [8950.0, 9000.0, 9020.0, 9080.0, 9100.0, 9120.0, 9150.0]),
    ("BOGOTA", "MACHO_LEVANTE", "$/kg", "Ferias Sabana Bogotá", "Ingreso para engorde", [9100.0, 9150.0, 9200.0, 9220.0, 9250.0, 9280.0, 9300.0]),
    ("BOGOTA", "VACA_GORDA", "$/kg", "Frigoríficos Bogotá", "Vaca desposte consumo", [6750.0, 6780.0, 6800.0, 6820.0, 6850.0, 6850.0, 6850.0]),

    # 8. Promedio Nacional (FEDEGÁN)
    ("PROMEDIO_NACIONAL", "MACHO_GORDO", "$/kg", "FEDEGÁN Boletín Semanal", "Consolidado nacional subastas", [8300.0, 8340.0, 8350.0, 8400.0, 8420.0, 8450.0, 8480.0]),
    ("PROMEDIO_NACIONAL", "MACHO_LEVANTE", "$/kg", "FEDEGÁN Boletín Semanal", "Promedio país", [8750.0, 8800.0, 8830.0, 8860.0, 8880.0, 8900.0, 8920.0]),

    # 9. Leche ($/Litro)
    ("META_REGIONAL", "LECHE_QUESERA", "$/L", "Acopio Local Ariari", "Queseras de Mesetas / Granada", [1880.0, 1890.0, 1900.0, 1900.0, 1910.0, 1910.0, 1920.0]),
    ("META_REGIONAL", "LECHE_INDUSTRIA", "$/L", "Industria Formal con Frío", "Bonificación sólidos y frío", [2100.0, 2110.0, 2120.0, 2120.0, 2140.0, 2140.0, 2150.0]),
    ("COLOMBIA", "LECHE_RESOLUCION_USP", "$/L", "MinAgricultura USP Región 2", "Precio base normativo oficial", [2115.0, 2115.0, 2115.0, 2115.0, 2115.0, 2115.0, 2115.0]),

    # 10. Insumos Críticos del Ariari / Meta y TRM
    ("ARIARI_LOCAL", "SAL_MINERAL_8", "$/bulto 40kg", "Almacenes Granada", "Sal mineralizada 8% fósforo", [116000.0, 116000.0, 117000.0, 117000.0, 118000.0, 118000.0, 118000.0]),
    ("ARIARI_LOCAL", "SAL_MINERAL_10", "$/bulto 40kg", "Almacenes Granada", "Sal mineralizada 10% fósforo", [134000.0, 134000.0, 135000.0, 135000.0, 136000.0, 136000.0, 136000.0]),
    ("ARIARI_LOCAL", "UREA_50KG", "$/bulto 50kg", "Distribuidoras Granada / Villavicencio", "Fertilizante nitrogenado pastos", [142000.0, 143000.0, 144000.0, 144000.0, 145000.0, 145000.0, 145000.0]),
    ("ARIARI_LOCAL", "ALAMBRE_PUAS_400M", "$/rollo 400m", "Ferreterías Granada", "Alambre galvanizado ganadero", [182000.0, 183000.0, 184000.0, 184000.0, 185000.0, 185000.0, 185000.0]),
    ("COLOMBIA", "DOLAR_TRM", "COP/USD", "Banco de la República", "Tasa representativa oficial", [4040.0, 4065.0, 4050.0, 4075.0, 4090.0, 4080.0, 4085.0]),
]
