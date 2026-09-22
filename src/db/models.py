"""Modelos de datos y esquema SQLite de la bitácora de campo zootécnico."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Esquema SQL
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS potreros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT,
    nombre TEXT,
    area_has REAL,
    tipo_pasto TEXT,
    aforo_kg_m2 REAL,
    fecha_entrada TEXT,
    fecha_salida TEXT,
    dias_reposo INTEGER,
    dias_ocupacion INTEGER,
    geom_wkt_4326 TEXT,
    centroide_lat REAL,
    centroide_lon REAL
);

CREATE TABLE IF NOT EXISTS animales (
    id_animal INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT UNIQUE NOT NULL,
    nombre TEXT,
    sexo TEXT,
    raza TEXT,
    fecha_nacimiento TEXT,
    madre_id INTEGER,
    padre_id INTEGER,
    potrero_id INTEGER,
    estado TEXT,
    notas TEXT,
    hierro TEXT,
    chip TEXT,
    color TEXT
);

-- tipo_evento: PARTO | GEMELAR | ABORTO | REABSORCION | MOMIFICACION |
-- MACERACION | MUERTE_FETAL (ver src/db/models.py TIPOS_EVENTO_PARTO).
-- grupo_parto_id agrupa las 2+ filas de un mismo parto GEMELAR.
CREATE TABLE IF NOT EXISTS partos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vaca_id INTEGER,
    fecha TEXT,
    sexo_cria TEXT,
    estado_cria TEXT,
    peso_nacimiento REAL,
    id_cria INTEGER,
    notas TEXT,
    tipo_evento TEXT DEFAULT 'PARTO',
    grupo_parto_id INTEGER
);

CREATE TABLE IF NOT EXISTS muertes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    fecha TEXT,
    causa_presunta TEXT,
    notas TEXT
);

CREATE TABLE IF NOT EXISTS servicios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vaca_id INTEGER,
    fecha TEXT,
    tipo_servicio TEXT,
    toro_pajilla TEXT,
    raza_toro TEXT,
    inseminador TEXT,
    fep_calculada TEXT,
    estado TEXT
);

CREATE TABLE IF NOT EXISTS celos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vaca_id INTEGER,
    fecha TEXT,
    am_pm TEXT,
    notas TEXT
);

CREATE TABLE IF NOT EXISTS tratamientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    fecha TEXT,
    producto TEXT,
    principio_activo TEXT,
    dosis TEXT,
    via TEXT,
    dias_retiro_leche INTEGER,
    dias_retiro_carne INTEGER,
    fecha_fin_retiro_leche TEXT,
    fecha_fin_retiro_carne TEXT,
    diagnostico TEXT
);

CREATE TABLE IF NOT EXISTS traslados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    lote TEXT,
    fecha TEXT,
    potrero_origen INTEGER,
    potrero_destino INTEGER,
    motivo TEXT
);

-- Destete de una cría (se separa de la madre, pasa a potrero de levante) y,
-- opcionalmente, el estado de la madre en ese mismo momento (peso, condición
-- corporal, nuevo potrero) -- equivalente a "Secados/Destetos" en SG.
CREATE TABLE IF NOT EXISTS destetes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER NOT NULL,
    madre_id INTEGER,
    fecha TEXT,
    peso_kg REAL,
    potrero_cria INTEGER,
    potrero_madre INTEGER,
    peso_madre_kg REAL,
    cond_corporal_madre REAL,
    notas TEXT,
    creado_en TEXT,
    registrado_por INTEGER
);

-- Secado real de una vaca lechera (deja de ordeñarse), como evento
-- independiente del destete de su cría -- una vaca puede destetar (separar
-- la cría) y seguir en ordeño normalmente; el secado es una decisión
-- posterior y separada. Sin esto, "En ordeño"/"Seca" en la ficha era solo
-- un estimado (días desde el último parto vs umbral), nunca confirmado.
-- No tiene equivalente de importación/exportación con Software Ganadero
-- (SG solo modela "Secados/Destetos" como un único evento sobre la vaca).
CREATE TABLE IF NOT EXISTS secados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER NOT NULL,
    fecha TEXT,
    potrero_destino INTEGER,
    cond_corporal REAL,
    motivo TEXT,
    notas TEXT,
    creado_en TEXT,
    registrado_por INTEGER
);

-- Pausa temporal de ordeño de una vaca que sigue en etapa de lactancia
-- (ej. se suelta el ternero con la vaca por unos días porque nació flaco),
-- SIN secarla -- distinto de `secados` (fin real de la lactancia). Mientras
-- fecha_fin es NULL la pausa está abierta (la vaca no se está ordeñando);
-- se usa para no contarla en el promedio de litros/vaca/día del recibo de
-- quincena (ver Database.resumen_ordeno).
CREATE TABLE IF NOT EXISTS pausas_ordeno (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER NOT NULL,
    fecha_inicio TEXT,
    fecha_fin TEXT,
    motivo TEXT,
    notas TEXT,
    creado_en TEXT,
    registrado_por INTEGER
);

CREATE TABLE IF NOT EXISTS pesajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    fecha TEXT,
    peso_kg REAL,
    gmd_calculada REAL,
    evento TEXT
);

CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    fecha TEXT,
    tipo_movimiento TEXT,
    procedencia_destino TEXT,
    precio REAL,
    notas TEXT
);

CREATE TABLE IF NOT EXISTS condicion_corporal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    fecha TEXT,
    valor REAL,
    notas TEXT
);

CREATE TABLE IF NOT EXISTS produccion_leche (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    fecha TEXT,
    litros REAL,
    notas TEXT
);

CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    tipo_alerta TEXT,
    fecha_programada TEXT,
    fecha_cumplida TEXT,
    estado TEXT,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS fotos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id INTEGER,
    tag TEXT,
    fecha TEXT,
    ruta TEXT NOT NULL,
    caption TEXT,
    user_id INTEGER,
    notas TEXT,
    ocr_text TEXT
);

CREATE TABLE IF NOT EXISTS import_sg_historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_iso TEXT,
    archivo TEXT,
    nuevos INTEGER,
    duplicados INTEGER
);

CREATE TABLE IF NOT EXISTS consultas_animal (
    animal_id INTEGER PRIMARY KEY,
    ultima_fecha TEXT
);

CREATE TABLE IF NOT EXISTS recordatorios_programados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mensaje TEXT NOT NULL,
    fecha_programada TEXT,
    hora TEXT,
    creado_por INTEGER,
    estado TEXT DEFAULT 'PENDIENTE',
    creado_en TEXT,
    asignado_a TEXT,
    asignado_a_id INTEGER,
    tipo_objetivo TEXT,
    animal_tag TEXT,
    potrero_nombre TEXT,
    tipo_tarea TEXT,
    prioridad TEXT DEFAULT 'NORMAL',
    completado_en TEXT,
    completado_por TEXT,
    completado_por_id INTEGER,
    notas_completado TEXT,
    foto_completado TEXT
);

CREATE TABLE IF NOT EXISTS diagnosticos_gestacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vaca_id INTEGER NOT NULL,
    fecha TEXT,
    resultado TEXT NOT NULL,
    dias_gestacion INTEGER,
    responsable TEXT,
    creado_en TEXT,
    registrado_por INTEGER
);

CREATE TABLE IF NOT EXISTS pajuelas_inventario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_toro TEXT NOT NULL,
    raza TEXT,
    procedencia TEXT,
    canastilla TEXT,
    cantidad INTEGER DEFAULT 0,
    costo REAL DEFAULT 0.0,
    fecha_ingreso TEXT,
    creado_en TEXT
);

CREATE TABLE IF NOT EXISTS termo_nitrogeno (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_recarga TEXT NOT NULL,
    proxima_recarga TEXT,
    dias_intervalo INTEGER DEFAULT 21,
    creado_en TEXT
);

CREATE TABLE IF NOT EXISTS pluviometria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    mm_lluvia REAL NOT NULL,
    estacion_o_sector TEXT,
    observaciones TEXT,
    creado_en TEXT,
    registrado_por INTEGER
);

CREATE TABLE IF NOT EXISTS aforos_historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    potrero_id INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    aforo_kg_m2 REAL NOT NULL,
    pct_ms REAL DEFAULT 22.0,
    observaciones TEXT,
    creado_en TEXT,
    registrado_por INTEGER
);

CREATE TABLE IF NOT EXISTS monitoreo_satelital_ndvi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    potrero_id INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    ndvi_promedio REAL NOT NULL,
    ndvi_min REAL,
    ndvi_max REAL,
    biomasa_estimada_kg_ha REAL,
    aforo_estimado_kg_m2 REAL,
    cobertura_nubes_pct REAL DEFAULT 0.0,
    fuente TEXT DEFAULT 'Sentinel-2 L2A',
    creado_en TEXT,
    registrado_por INTEGER
);

CREATE INDEX IF NOT EXISTS idx_animales_tag ON animales(tag);
CREATE INDEX IF NOT EXISTS idx_animales_estado ON animales(estado);
CREATE INDEX IF NOT EXISTS idx_animales_potrero ON animales(potrero_id);
CREATE INDEX IF NOT EXISTS idx_partos_vaca_fecha ON partos(vaca_id, fecha);
CREATE INDEX IF NOT EXISTS idx_partos_cria ON partos(id_cria);
CREATE INDEX IF NOT EXISTS idx_partos_tipo_evento ON partos(tipo_evento);
CREATE INDEX IF NOT EXISTS idx_partos_grupo ON partos(grupo_parto_id);
CREATE INDEX IF NOT EXISTS idx_servicios_vaca_fecha ON servicios(vaca_id, fecha);
CREATE INDEX IF NOT EXISTS idx_celos_vaca_fecha ON celos(vaca_id, fecha);
CREATE INDEX IF NOT EXISTS idx_tratamientos_animal_fecha ON tratamientos(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_traslados_animal_fecha ON traslados(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_destetes_animal_fecha ON destetes(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_secados_animal_fecha ON secados(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_pausas_ordeno_animal ON pausas_ordeno(animal_id, fecha_fin);
CREATE INDEX IF NOT EXISTS idx_pesajes_animal_fecha ON pesajes(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_movimientos_animal_fecha ON movimientos(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_fotos_animal_tag ON fotos(animal_id, tag);
CREATE INDEX IF NOT EXISTS idx_recordatorios_fecha_estado ON recordatorios_programados(fecha_programada, estado);
CREATE INDEX IF NOT EXISTS idx_recordatorios_asignado ON recordatorios_programados(asignado_a, estado);
CREATE INDEX IF NOT EXISTS idx_recordatorios_tag ON recordatorios_programados(animal_tag);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_vaca_fecha ON diagnosticos_gestacion(vaca_id, fecha);
CREATE INDEX IF NOT EXISTS idx_pajuelas_toro ON pajuelas_inventario(codigo_toro);
CREATE INDEX IF NOT EXISTS idx_termo_recarga ON termo_nitrogeno(fecha_recarga);
CREATE INDEX IF NOT EXISTS idx_pluviometria_fecha ON pluviometria(fecha);
CREATE INDEX IF NOT EXISTS idx_aforos_potrero_fecha ON aforos_historico(potrero_id, fecha);
CREATE INDEX IF NOT EXISTS idx_produccion_leche_animal_fecha ON produccion_leche(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_condicion_corporal_animal_fecha ON condicion_corporal(animal_id, fecha);
-- Ronda Voisin de campo (D2): 10-15 puntos de aforo (g/kg MV por m²) por
-- potrero con su evaluación calculada (promedio, MS/ha, días, semáforo).
CREATE TABLE IF NOT EXISTS aforos_ronda (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    potrero_id INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    mediciones_json TEXT NOT NULL,
    num_puntos INTEGER,
    kg_mv_promedio REAL,
    kg_ms_ha REAL,
    dias_disponibles REAL,
    semaforo TEXT,
    creado_en TEXT,
    registrado_por INTEGER
);

CREATE INDEX IF NOT EXISTS idx_aforos_ronda_potrero_fecha ON aforos_ronda(potrero_id, fecha);
CREATE INDEX IF NOT EXISTS idx_ndvi_potrero_fecha ON monitoreo_satelital_ndvi(potrero_id, fecha);

CREATE TABLE IF NOT EXISTS monitoreo_satelital_lluvia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    dias_acumulados INTEGER NOT NULL DEFAULT 30,
    mm_estimado REAL NOT NULL,
    fuente TEXT DEFAULT 'CHIRPS (UCSB-CHG, vía Google Earth Engine)',
    creado_en TEXT,
    registrado_por INTEGER
);

CREATE INDEX IF NOT EXISTS idx_lluvia_satelital_fecha ON monitoreo_satelital_lluvia(fecha);

-- Muestra climatológica histórica CHIRPS (uno por ventana de días), para
-- ajustar la distribución gamma del SPI sin tener que re-descargar 30 años
-- de Earth Engine en cada corrida semanal (ver src.gis.earth_engine_lluvia.
-- climatologia_historica_chirps y src.engine.spi.calcular_spi).
CREATE TABLE IF NOT EXISTS climatologia_lluvia_chirps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dias_ventana INTEGER NOT NULL,
    muestra_json TEXT NOT NULL,
    lat REAL,
    lon REAL,
    calculado_en TEXT
);

CREATE INDEX IF NOT EXISTS idx_climatologia_ventana ON climatologia_lluvia_chirps(dias_ventana);

-- Índice de Precipitación Estandarizada calculado en cada corrida semanal
-- (una fila por ventana de 30/60/90 días), para el panel de Pasturas.
CREATE TABLE IF NOT EXISTS monitoreo_spi_sequia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    dias_ventana INTEGER NOT NULL,
    mm_actual REAL,
    spi_valor REAL,
    clasificacion TEXT,
    creado_en TEXT
);

CREATE INDEX IF NOT EXISTS idx_spi_sequia_fecha ON monitoreo_spi_sequia(fecha, dias_ventana);

CREATE TABLE IF NOT EXISTS rondas_campo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    usuario_nombre TEXT,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    potrero_id INTEGER,
    potrero_nombre TEXT,
    punto_control TEXT,
    notas TEXT,
    creado_en TEXT
);

CREATE INDEX IF NOT EXISTS idx_rondas_fecha ON rondas_campo(fecha);
CREATE INDEX IF NOT EXISTS idx_rondas_potrero ON rondas_campo(potrero_id);

CREATE TABLE IF NOT EXISTS telemetria_gps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    usuario_nombre TEXT,
    rol TEXT,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    precision_m REAL,
    potrero_id INTEGER,
    potrero_nombre TEXT,
    distancia_m REAL,
    dentro_finca INTEGER DEFAULT 1,
    evento_origen TEXT,
    creado_en TEXT
);

CREATE INDEX IF NOT EXISTS idx_telemetria_fecha ON telemetria_gps(fecha);
CREATE INDEX IF NOT EXISTS idx_telemetria_usuario ON telemetria_gps(user_id);
CREATE INDEX IF NOT EXISTS idx_telemetria_potrero ON telemetria_gps(potrero_id);

CREATE TABLE IF NOT EXISTS usuarios_presencia (
    user_id TEXT PRIMARY KEY,
    nombre TEXT,
    rol TEXT,
    canal TEXT,
    ip TEXT,
    ultima_actividad TEXT,
    detalles TEXT
);

CREATE INDEX IF NOT EXISTS idx_presencia_actividad ON usuarios_presencia(ultima_actividad);

-- Libro único de ingresos y egresos (venta de leche, insumos, nómina, etc.).
-- La venta/compra de animales NO se duplica aquí -- ya vive en `movimientos`
-- (con su `precio`) y los reportes de utilidad la suman desde allá.
CREATE TABLE IF NOT EXISTS finanzas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    tipo TEXT NOT NULL,
    categoria TEXT NOT NULL,
    concepto TEXT,
    monto REAL NOT NULL DEFAULT 0.0,
    litros REAL,
    animal_id INTEGER,
    potrero_id INTEGER,
    contraparte TEXT,
    foto_ruta TEXT,
    notas TEXT,
    creado_en TEXT,
    registrado_por INTEGER
);

CREATE INDEX IF NOT EXISTS idx_finanzas_fecha ON finanzas(fecha);
CREATE INDEX IF NOT EXISTS idx_finanzas_tipo ON finanzas(tipo);
CREATE INDEX IF NOT EXISTS idx_finanzas_categoria ON finanzas(categoria);
CREATE INDEX IF NOT EXISTS idx_finanzas_potrero ON finanzas(potrero_id);

-- Suscripciones para notificaciones Web Push de la PWA
CREATE TABLE IF NOT EXISTS push_suscripciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    endpoint TEXT UNIQUE,
    p256dh TEXT,
    auth TEXT,
    creado_en TEXT,
    ultimo_uso TEXT
);

CREATE INDEX IF NOT EXISTS idx_push_user ON push_suscripciones(user_id);

-- Indicadores económicos y precios de subastas ganaderas de la región
CREATE TABLE IF NOT EXISTS precios_mercado (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    plaza TEXT NOT NULL,
    producto TEXT NOT NULL,
    precio_promedio REAL NOT NULL,
    precio_maximo REAL,
    precio_minimo REAL,
    unidad TEXT NOT NULL DEFAULT '$/kg',
    fuente TEXT,
    notas TEXT,
    creado_en TEXT
);

CREATE INDEX IF NOT EXISTS idx_precios_mercado_fecha ON precios_mercado(fecha);
CREATE INDEX IF NOT EXISTS idx_precios_mercado_plaza ON precios_mercado(plaza);
CREATE INDEX IF NOT EXISTS idx_precios_mercado_producto ON precios_mercado(producto);

-- Canal único de avisos del equipo (broadcast, no mensajes directos).
-- Denormaliza nombre/rol del autor en el momento de publicar (mismo patrón
-- que rondas_campo/telemetria_gps) para que el mensaje siga mostrando quién
-- lo escribió aunque luego se edite o borre ese usuario en users.json.
CREATE TABLE IF NOT EXISTS mensajes_equipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    nombre TEXT NOT NULL,
    rol TEXT NOT NULL,
    texto TEXT NOT NULL,
    creado_en TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mensajes_equipo_creado ON mensajes_equipo(creado_en);
"""

# Orden de creación (potreros y animales antes que sus referencias).
TABLAS = [
    "potreros", "animales", "partos", "muertes", "servicios", "celos",
    "tratamientos", "traslados", "destetes", "secados", "pausas_ordeno", "pesajes", "movimientos", "condicion_corporal",
    "produccion_leche", "alertas", "fotos", "import_sg_historial", "consultas_animal",
    "recordatorios_programados", "diagnosticos_gestacion", "pajuelas_inventario",
    "termo_nitrogeno", "pluviometria", "aforos_historico", "aforos_ronda", "monitoreo_satelital_ndvi",
    "monitoreo_satelital_lluvia", "rondas_campo", "telemetria_gps", "usuarios_presencia",
    "finanzas", "climatologia_lluvia_chirps", "monitoreo_spi_sequia", "push_suscripciones",
    "precios_mercado", "mensajes_equipo",
]


# Catálogo de tipos de evento reproductivo para `partos.tipo_evento`
# (equivalente al combo "Tipo" de Software Ganadero: Parto/Gemelar/Aborto/
# Reabsorción/Momificación/Maceración/Muerte fetal). Todos salvo PARTO y
# GEMELAR implican id_cria=NULL (no se crea animal nuevo).
TIPOS_EVENTO_PARTO = (
    "PARTO", "GEMELAR", "ABORTO", "REABSORCION", "MOMIFICACION",
    "MACERACION", "MUERTE_FETAL",
)

# Tipos que nunca generan una cría viva (id_cria debe quedar NULL).
TIPOS_EVENTO_SIN_CRIA = (
    "ABORTO", "REABSORCION", "MOMIFICACION", "MACERACION", "MUERTE_FETAL",
)

# ---------------------------------------------------------------------------
# Modelos (dataclasses) — espejo de las tablas para transferencia de datos
# ---------------------------------------------------------------------------

@dataclass
class Animal:
    tag: str
    nombre: Optional[str] = None
    sexo: Optional[str] = None
    raza: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    madre_id: Optional[int] = None
    padre_id: Optional[int] = None
    potrero_id: Optional[int] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    id_animal: Optional[int] = None


@dataclass
class Parto:
    vaca_id: Optional[int] = None
    fecha: Optional[str] = None
    sexo_cria: Optional[str] = None
    estado_cria: Optional[str] = "VIVO"
    peso_nacimiento: Optional[float] = None
    id_cria: Optional[int] = None
    notas: Optional[str] = None
    tipo_evento: Optional[str] = "PARTO"
    grupo_parto_id: Optional[int] = None


@dataclass
class Muerte:
    animal_id: Optional[int] = None
    fecha: Optional[str] = None
    causa_presunta: Optional[str] = None
    notas: Optional[str] = None


@dataclass
class Servicio:
    vaca_id: Optional[int] = None
    fecha: Optional[str] = None
    tipo_servicio: Optional[str] = None
    toro_pajilla: Optional[str] = None
    raza_toro: Optional[str] = None
    inseminador: Optional[str] = None
    fep_calculada: Optional[str] = None
    estado: Optional[str] = None


@dataclass
class Celo:
    vaca_id: Optional[int] = None
    fecha: Optional[str] = None
    am_pm: Optional[str] = None
    notas: Optional[str] = None


@dataclass
class Tratamiento:
    animal_id: Optional[int] = None
    fecha: Optional[str] = None
    producto: Optional[str] = None
    principio_activo: Optional[str] = None
    dosis: Optional[str] = None
    via: Optional[str] = None
    dias_retiro_leche: Optional[int] = 0
    dias_retiro_carne: Optional[int] = 0
    fecha_fin_retiro_leche: Optional[str] = None
    fecha_fin_retiro_carne: Optional[str] = None
    diagnostico: Optional[str] = None


@dataclass
class Traslado:
    animal_id: Optional[int] = None
    lote: Optional[str] = None
    fecha: Optional[str] = None
    potrero_origen: Optional[int] = None
    potrero_destino: Optional[int] = None
    motivo: Optional[str] = None


@dataclass
class Secado:
    animal_id: Optional[int] = None
    fecha: Optional[str] = None
    potrero_destino: Optional[int] = None
    cond_corporal: Optional[float] = None
    motivo: Optional[str] = None
    notas: Optional[str] = None


@dataclass
class PausaOrdeno:
    animal_id: Optional[int] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    motivo: Optional[str] = None
    notas: Optional[str] = None


@dataclass
class Pesaje:
    animal_id: Optional[int] = None
    fecha: Optional[str] = None
    peso_kg: Optional[float] = None
    gmd_calculada: Optional[float] = None
    evento: Optional[str] = None


@dataclass
class Movimiento:
    animal_id: Optional[int] = None
    fecha: Optional[str] = None
    tipo_movimiento: Optional[str] = None
    procedencia_destino: Optional[str] = None
    precio: Optional[float] = None
    notas: Optional[str] = None


@dataclass
class Alerta:
    animal_id: Optional[int] = None
    tipo_alerta: Optional[str] = None
    fecha_programada: Optional[str] = None
    fecha_cumplida: Optional[str] = None
    estado: Optional[str] = "PENDIENTE"
    descripcion: Optional[str] = None


@dataclass
class Potrero:
    nombre: Optional[str] = None
    codigo: Optional[str] = None
    area_has: Optional[float] = None
    tipo_pasto: Optional[str] = None
    aforo_kg_m2: Optional[float] = None
    fecha_entrada: Optional[str] = None
    fecha_salida: Optional[str] = None
    dias_reposo: Optional[int] = None
    dias_ocupacion: Optional[int] = None
    id: Optional[int] = None


@dataclass
class Foto:
    ruta: str
    animal_id: Optional[int] = None
    tag: Optional[str] = None
    fecha: Optional[str] = None
    caption: Optional[str] = None
    user_id: Optional[int] = None
    notas: Optional[str] = None
    ocr_text: Optional[str] = None
    id: Optional[int] = None


@dataclass
class RecordatorioProgramado:
    mensaje: str
    fecha_programada: Optional[str] = None
    hora: Optional[str] = None
    creado_por: Optional[int] = None
    estado: Optional[str] = "PENDIENTE"
    creado_en: Optional[str] = None
    id: Optional[int] = None


@dataclass
class DiagnosticoGestacion:
    vaca_id: Optional[int] = None
    fecha: Optional[str] = None
    resultado: Optional[str] = "PREÑADA"
    dias_gestacion: Optional[int] = None
    responsable: Optional[str] = None
    creado_en: Optional[str] = None
    registrado_por: Optional[int] = None
    id: Optional[int] = None


@dataclass
class PajuelaInventario:
    codigo_toro: str = ""
    raza: Optional[str] = None
    procedencia: Optional[str] = None
    canastilla: Optional[str] = None
    cantidad: int = 0
    costo: float = 0.0
    fecha_ingreso: Optional[str] = None
    creado_en: Optional[str] = None
    id: Optional[int] = None


@dataclass
class TermoNitrogeno:
    fecha_recarga: str = ""
    proxima_recarga: Optional[str] = None
    dias_intervalo: int = 21
    creado_en: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Pluviometria:
    fecha: str = ""
    mm_lluvia: float = 0.0
    estacion_o_sector: Optional[str] = None
    observaciones: Optional[str] = None
    creado_en: Optional[str] = None
    registrado_por: Optional[int] = None
    id: Optional[int] = None


@dataclass
class AforoHistorico:
    potrero_id: int = 0
    fecha: str = ""
    aforo_kg_m2: float = 0.0
    pct_ms: float = 22.0
    observaciones: Optional[str] = None
    creado_en: Optional[str] = None
    registrado_por: Optional[int] = None
    id: Optional[int] = None


@dataclass
class MonitoreoSatelitalNDVI:
    potrero_id: int = 0
    fecha: str = ""
    ndvi_promedio: float = 0.0
    ndvi_min: Optional[float] = None
    ndvi_max: Optional[float] = None
    biomasa_estimada_kg_ha: Optional[float] = None
    aforo_estimado_kg_m2: Optional[float] = None
    cobertura_nubes_pct: float = 0.0
    fuente: str = "Sentinel-2 L2A"
    creado_en: Optional[str] = None
    registrado_por: Optional[int] = None
    id: Optional[int] = None


@dataclass
class Finanza:
    fecha: str = ""
    tipo: str = ""  # "INGRESO" | "EGRESO"
    categoria: str = ""  # VENTA_LECHE, NOMINA, INSUMO, VETERINARIO, INFRAESTRUCTURA, COMBUSTIBLE, OTRO_INGRESO, OTRO_EGRESO
    concepto: Optional[str] = None
    monto: float = 0.0
    litros: Optional[float] = None
    animal_id: Optional[int] = None
    potrero_id: Optional[int] = None
    contraparte: Optional[str] = None
    foto_ruta: Optional[str] = None
    notas: Optional[str] = None
    creado_en: Optional[str] = None
    registrado_por: Optional[int] = None
    id: Optional[int] = None


