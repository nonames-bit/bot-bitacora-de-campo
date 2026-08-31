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
    dias_ocupacion INTEGER
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
    notas TEXT
);

CREATE TABLE IF NOT EXISTS partos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vaca_id INTEGER,
    fecha TEXT,
    sexo_cria TEXT,
    estado_cria TEXT,
    peso_nacimiento REAL,
    id_cria INTEGER,
    notas TEXT
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
    creado_en TEXT
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

CREATE INDEX IF NOT EXISTS idx_animales_tag ON animales(tag);
CREATE INDEX IF NOT EXISTS idx_animales_estado ON animales(estado);
CREATE INDEX IF NOT EXISTS idx_animales_potrero ON animales(potrero_id);
CREATE INDEX IF NOT EXISTS idx_partos_vaca_fecha ON partos(vaca_id, fecha);
CREATE INDEX IF NOT EXISTS idx_partos_cria ON partos(id_cria);
CREATE INDEX IF NOT EXISTS idx_servicios_vaca_fecha ON servicios(vaca_id, fecha);
CREATE INDEX IF NOT EXISTS idx_celos_vaca_fecha ON celos(vaca_id, fecha);
CREATE INDEX IF NOT EXISTS idx_tratamientos_animal_fecha ON tratamientos(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_traslados_animal_fecha ON traslados(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_pesajes_animal_fecha ON pesajes(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_movimientos_animal_fecha ON movimientos(animal_id, fecha);
CREATE INDEX IF NOT EXISTS idx_fotos_animal_tag ON fotos(animal_id, tag);
CREATE INDEX IF NOT EXISTS idx_recordatorios_fecha_estado ON recordatorios_programados(fecha_programada, estado);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_vaca_fecha ON diagnosticos_gestacion(vaca_id, fecha);
CREATE INDEX IF NOT EXISTS idx_pajuelas_toro ON pajuelas_inventario(codigo_toro);
CREATE INDEX IF NOT EXISTS idx_termo_recarga ON termo_nitrogeno(fecha_recarga);
"""

# Orden de creación (potreros y animales antes que sus referencias).
TABLAS = [
    "potreros", "animales", "partos", "muertes", "servicios", "celos",
    "tratamientos", "traslados", "pesajes", "movimientos", "condicion_corporal",
    "produccion_leche", "alertas", "fotos", "import_sg_historial", "consultas_animal",
    "recordatorios_programados", "diagnosticos_gestacion", "pajuelas_inventario",
    "termo_nitrogeno",
]


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


