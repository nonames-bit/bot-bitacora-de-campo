"""responseSchema de Gemini por dominio zootécnico.

Cada schema fuerza a Gemini a devolver JSON conforme a esta forma exacta
(``generationConfig.responseSchema`` + ``responseMimeType: application/json``),
por lo que no hace falta parsear/extraer JSON de texto libre.

El objeto ``datos`` de cada dominio es un superset PLANO de las propiedades de
todos los tipos de evento de ese dominio (todas nullable) en vez de un
``oneOf`` condicional por tipo, porque el soporte de esquemas condicionales
varía entre backends de Gemini — un superset simple es más robusto y solo
cada agente de dominio sabe qué subconjunto de campos llenar según ``tipo``.
"""
from __future__ import annotations

_EVENTO_BASE = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string"},
        "animal_tag": {"type": "string", "nullable": True},
        "fecha": {"type": "string", "nullable": True},
        "datos": {"type": "object"},
    },
    "required": ["tipo"],
}


def _lista_eventos(tipos_enum: list[str], propiedades_datos: dict) -> dict:
    evento = {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": tipos_enum},
            "animal_tag": {"type": "string", "nullable": True},
            "fecha": {"type": "string", "nullable": True},
            "datos": {"type": "object", "properties": propiedades_datos},
        },
        "required": ["tipo"],
    }
    return {
        "type": "object",
        "properties": {"eventos": {"type": "array", "items": evento}},
        "required": ["eventos"],
    }


SCHEMA_REPRODUCCION = _lista_eventos(
    ["parto", "servicio", "celo"],
    {
        # parto
        "sexo_cria": {"type": "string", "enum": ["Macho", "Hembra"], "nullable": True},
        "estado_cria": {"type": "string", "enum": ["VIVO", "MUERTO"], "nullable": True},
        "peso_nacimiento": {"type": "number", "nullable": True},
        "id_cria": {"type": "string", "nullable": True},
        # servicio
        "tipo_servicio": {"type": "string", "enum": ["IA", "MONTA"], "nullable": True},
        "toro_pajilla": {"type": "string", "nullable": True},
        "raza_toro": {"type": "string", "nullable": True},
        # celo
        "am_pm": {"type": "string", "enum": ["AM", "PM"], "nullable": True},
    },
)

SCHEMA_SANIDAD = _lista_eventos(
    ["tratamiento", "muerte"],
    {
        # tratamiento
        "producto": {"type": "string", "nullable": True},
        "dosis": {"type": "string", "nullable": True},
        "via": {"type": "string", "enum": ["SC", "IM", "IV", "Oral"], "nullable": True},
        "dias_retiro": {"type": "integer", "nullable": True},
        # muerte
        "causa_presunta": {"type": "string", "nullable": True},
    },
)

SCHEMA_MANEJO = _lista_eventos(
    ["pesaje", "traslado", "movimiento"],
    {
        # pesaje
        "peso_kg": {"type": "number", "nullable": True},
        "evento": {"type": "string", "enum": ["Control", "DESTETE", "NACIMIENTO"], "nullable": True},
        # traslado
        "lote": {"type": "string", "nullable": True},
        "potrero_origen": {"type": "string", "nullable": True},
        "potrero_destino": {"type": "string", "nullable": True},
        # movimiento
        "tipo_movimiento": {"type": "string", "enum": ["COMPRA", "VENTA", "SALIDA", "ENTRADA"], "nullable": True},
        "cantidad": {"type": "integer", "nullable": True},
        "procedencia_destino": {"type": "string", "nullable": True},
    },
)

SCHEMA_CLASIFICADOR = {
    "type": "object",
    "properties": {
        "dominios": {
            "type": "array",
            "items": {"type": "string", "enum": ["reproduccion", "sanidad", "manejo"]},
        }
    },
    "required": ["dominios"],
}
