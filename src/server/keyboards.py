"""Constructores de teclados táctiles (InlineKeyboardMarkup) del bot de Telegram.

Lógica de UI pura: reciben los datos que necesitan como parámetros explícitos
(la única excepción histórica era ``crear_teclado_buscar_animal``, que ahora
recibe ``db`` en vez de capturarlo por clausura) y no dependen del resto de
``construir_application`` — se pueden importar y probar de forma aislada.
"""
from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..db.database import Database


def crear_teclado_guia_chat() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🐮 1. Preguntas sobre un Animal", callback_data="guia:preguntas_animal"),
        ],
        [
            InlineKeyboardButton("🌿 2. Preguntas de Potreros & Voisin", callback_data="guia:preguntas_potreros"),
        ],
        [
            InlineKeyboardButton("🥛 3. Preguntas de Leche & Reproducción", callback_data="guia:preguntas_reprod"),
        ],
        [
            InlineKeyboardButton("💉 4. Preguntas de Medicamentos & Retiro", callback_data="guia:preguntas_sanidad"),
        ],
        [
            InlineKeyboardButton("🎙️ 5. Cómo Dictar por Voz y Fotos", callback_data="guia:voz_fotos"),
        ],
        [
            InlineKeyboardButton("📝 Ejemplos de Notas", callback_data="cmd:ejemplos"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_despacho_matutino() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🥛 Registrar Leche Hoy", callback_data="cmd:registrar_leche"),
            InlineKeyboardButton("⏰ Programar Recordatorio", callback_data="cmd:programar_recordatorio"),
        ],
        [
            InlineKeyboardButton("🚨 Alertas del Día", callback_data="cmd:alertas"),
            InlineKeyboardButton("💊 Medicamentos & Retiro", callback_data="cmd:medicamentos"),
        ],
        [
            InlineKeyboardButton("🌿 Potreros & Pasturas", callback_data="cmd:potreros"),
            InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
        ],
        [
            InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_trabajador() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🌅 Despacho Matutino", callback_data="cmd:despacho"),
            InlineKeyboardButton("🚨 Alertas del Día", callback_data="cmd:alertas"),
        ],
        [
            InlineKeyboardButton("🔍 Buscar Animal / Ficha", callback_data="cmd:buscar_animal"),
            InlineKeyboardButton("🌿 Potreros & Pasturas", callback_data="cmd:potreros"),
        ],
        [
            InlineKeyboardButton("💊 Medicamentos & Retiro", callback_data="cmd:medicamentos"),
            InlineKeyboardButton("📷 Galería de Fotos", callback_data="cmd:fotos"),
        ],
        [
            InlineKeyboardButton("💬 Guía: Cómo Preguntar al Chat", callback_data="guia:chat_hub"),
        ],
        [
            InlineKeyboardButton("📝 Cómo Anotar Reportes", callback_data="cmd:ejemplos"),
            InlineKeyboardButton("📖 Todos los Comandos", callback_data="cmd:ayuda"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_admin(rol: Optional[str]) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🌅 Despacho Matutino", callback_data="cmd:despacho"),
            InlineKeyboardButton("🚨 Alertas del Día", callback_data="cmd:alertas"),
        ],
        [
            InlineKeyboardButton("🔍 Buscar Animal / Ficha", callback_data="cmd:buscar_animal"),
            InlineKeyboardButton("🌿 Potreros & Pasturas", callback_data="cmd:potreros"),
        ],
        [
            InlineKeyboardButton("💊 Medicamentos & Retiro", callback_data="cmd:medicamentos"),
            InlineKeyboardButton("📊 Población & KPIs SG", callback_data="cmd:poblacion"),
        ],
        [
            InlineKeyboardButton("🧬 Composición Genética", callback_data="cmd:genetica"),
            InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
        ],
        [
            InlineKeyboardButton("📊 Gráficos de la Finca", callback_data="cmd:graficos"),
            InlineKeyboardButton("📷 Galería Fotos", callback_data="cmd:fotos"),
        ],
        [
            InlineKeyboardButton("💬 Guía: Cómo Preguntar al Chat", callback_data="guia:chat_hub"),
            InlineKeyboardButton("📋 Reporte Semanal PDF", callback_data="cmd:reporte"),
        ],
        [
            InlineKeyboardButton("📦 Descargar Backup ZIP", callback_data="cmd:exportar"),
            InlineKeyboardButton("⚙️ Servidor & Logs", callback_data="cmd:sistema"),
        ],
    ]
    if rol == "OWNER":
        keyboard.append([
            InlineKeyboardButton("👥 Usuarios / Permisos", callback_data="cmd:usuarios"),
            InlineKeyboardButton("💡 Modo Guía de Campo", callback_data="menu:campo"),
        ])
        keyboard.append([
            InlineKeyboardButton("📖 Manual / Comandos", callback_data="cmd:ayuda"),
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("💡 Modo Guía de Campo", callback_data="menu:campo"),
            InlineKeyboardButton("📖 Manual / Comandos", callback_data="cmd:ayuda"),
        ])
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_medicamentos() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🚨 Animales en Retiro Activo", callback_data="cmd:retiros_activos"),
        ],
        [
            InlineKeyboardButton("💉 Últimos Tratamientos", callback_data="cmd:ultimos_tratamientos"),
            InlineKeyboardButton("📷 Fotos Medicamentos", callback_data="guia:fotos"),
        ],
        [
            InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_buscar_animal(db: Database) -> InlineKeyboardMarkup:
    try:
        ultimos_recientes = db.ultimas_consultas_animal(limite=4)
    except Exception:
        ultimos_recientes = []
    keyboard = [
        [
            InlineKeyboardButton("🥛 Vacas Paridas", callback_data="filtro:paridas"),
            InlineKeyboardButton("🤰 Inseminadas / Gestantes", callback_data="filtro:inseminadas"),
        ],
        [
            InlineKeyboardButton("🐂 Toros / Reproductores", callback_data="filtro:toros"),
            InlineKeyboardButton("🍼 Crías Recientes", callback_data="filtro:crias"),
        ],
        [
            InlineKeyboardButton("💊 En Retiro Médico", callback_data="cmd:retiros_activos"),
            InlineKeyboardButton("⚖️ Últimos Pesajes", callback_data="filtro:pesajes"),
        ],
    ]
    if ultimos_recientes:
        botones_recientes = [
            InlineKeyboardButton(f"🐮 {r['tag']}", callback_data=f"ficha:{r['tag']}")
            for r in ultimos_recientes
        ]
        keyboard.append(botones_recientes)

    keyboard.append([
        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
    ])
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_preguntas_rapidas() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🥛 ¿Quién está en retiro de leche?", callback_data="faq:retiro_leche"),
        ],
        [
            InlineKeyboardButton("🌿 ¿Qué potreros tienen >30d reposo?", callback_data="faq:potreros_listos"),
        ],
        [
            InlineKeyboardButton("⚠️ ¿Qué vacas tienen >90d abiertas?", callback_data="faq:dias_abiertos"),
        ],
        [
            InlineKeyboardButton("🍼 ¿Qué partos hubo en los últimos 30 días?", callback_data="faq:partos_mes"),
        ],
        [
            InlineKeyboardButton("⚖️ ¿Últimos pesajes y ganancias?", callback_data="faq:pesajes"),
        ],
        [
            InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_principal(rol: Optional[str]) -> InlineKeyboardMarkup:
    if rol in ("OWNER", "ADMIN"):
        return crear_teclado_admin(rol)
    return crear_teclado_trabajador()

def crear_teclado_ejemplos() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🍼 Parto", callback_data="ejemplo:parto"),
            InlineKeyboardButton("🔥 Celo AM/PM", callback_data="ejemplo:celo"),
        ],
        [
            InlineKeyboardButton("🐂 Inseminación", callback_data="ejemplo:servicio"),
            InlineKeyboardButton("💉 Tratamiento", callback_data="ejemplo:tratamiento"),
        ],
        [
            InlineKeyboardButton("⚖️ Pesaje", callback_data="ejemplo:pesaje"),
            InlineKeyboardButton("🚚 Traslado", callback_data="ejemplo:traslado"),
        ],
        [
            InlineKeyboardButton("💀 Muerte / Baja", callback_data="ejemplo:muerte"),
            InlineKeyboardButton("📥 Entrada / Salida", callback_data="ejemplo:movimiento"),
        ],
        [
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_animal(tag: str) -> InlineKeyboardMarkup:
    tag_clean = str(tag).strip()
    keyboard = [
        [
            InlineKeyboardButton("⚖️ Pesajes & GMD", callback_data=f"animal:pesos:{tag_clean}"),
            InlineKeyboardButton("🍼 Partos & Crías", callback_data=f"animal:reprod:{tag_clean}"),
        ],
        [
            InlineKeyboardButton("🥛 Control Leche", callback_data=f"animal:leche:{tag_clean}"),
            InlineKeyboardButton("💉 Sanidad & Retiro", callback_data=f"animal:sanidad:{tag_clean}"),
        ],
        [
            InlineKeyboardButton("🌳 Genealogía (3G)", callback_data=f"animal:geneal:{tag_clean}"),
            InlineKeyboardButton("📷 Ver Foto", callback_data=f"foto:{tag_clean}"),
        ],
        [
            InlineKeyboardButton("📈 Gráfico de Peso", callback_data=f"animal:grafico:{tag_clean}"),
            InlineKeyboardButton("📉 Curva de Lactancia", callback_data=f"animal:grafico_leche:{tag_clean}"),
        ],
        [
            InlineKeyboardButton("📋 Ficha Resumen", callback_data=f"animal:resumen:{tag_clean}"),
            InlineKeyboardButton("🔍 Buscar Otro", callback_data="cmd:buscar_animal"),
        ],
        [
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_graficos() -> InlineKeyboardMarkup:
    """Menú de gráficos generales de la finca (distinto de los gráficos por
    animal, que viven en crear_teclado_animal)."""
    keyboard = [
        [
            InlineKeyboardButton("📈 Evolución del Rebaño", callback_data="panel_grafico:evolucion"),
            InlineKeyboardButton("🌊 Waterfall de Inventario", callback_data="panel_grafico:waterfall"),
        ],
        [
            InlineKeyboardButton("🥧 Categorías del Hato", callback_data="panel_grafico:categorias"),
        ],
        [
            InlineKeyboardButton("⚖️ GMD del Hato", callback_data="panel_grafico:gmd"),
            InlineKeyboardButton("📦 Intervalo Entre Partos", callback_data="panel_grafico:iep"),
        ],
        [
            InlineKeyboardButton("📦 IEP Histórico Completo", callback_data="panel_grafico:iep_completo"),
        ],
        [
            InlineKeyboardButton("🐄 Destete por Raza", callback_data="panel_grafico:destete_raza"),
            InlineKeyboardButton("🐂 Rendimiento por Padre", callback_data="panel_grafico:padre"),
        ],
        [
            InlineKeyboardButton("🌱 Aforo por Potrero", callback_data="panel_grafico:aforo"),
            InlineKeyboardButton("🔄 Ocupación de Potreros", callback_data="panel_grafico:ocupacion"),
        ],
        [
            InlineKeyboardButton("🤰 Preñadas vs Vacías por Potrero", callback_data="panel_grafico:prenadas"),
        ],
        [
            InlineKeyboardButton("📉 Días Abiertos (Kaplan-Meier)", callback_data="panel_grafico:dias_abiertos_km"),
        ],
        [
            InlineKeyboardButton("🧬 Estado Reproductivo del Hato", callback_data="panel_grafico:reproductivo_hato"),
        ],
        [
            InlineKeyboardButton("🥛 Producción Total de Leche", callback_data="panel_grafico:leche_total"),
            InlineKeyboardButton("⚡ Eficiencia Lechera", callback_data="panel_grafico:eficiencia_lechera"),
        ],
        [
            InlineKeyboardButton("🏆 Ranking de Vacas por Leche", callback_data="panel_grafico:ranking_leche"),
        ],
        [
            InlineKeyboardButton("🐄 Carga Animal por Potrero (UGG/ha)", callback_data="panel_grafico:carga_animal"),
        ],
        [
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_alertas() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🔴 Partos Próximos (≤30d)", callback_data="alerta:partos"),
            InlineKeyboardButton("🟡 Vacas para Secado", callback_data="alerta:secados"),
        ],
        [
            InlineKeyboardButton("🟢 Crías para Destete", callback_data="alerta:destetes"),
            InlineKeyboardButton("⚠️ Pérdidas de Peso (GMD)", callback_data="alerta:pesos"),
        ],
        [
            InlineKeyboardButton("⛔ Retiros Sanitarios", callback_data="cmd:retiros_activos"),
            InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
        ],
        [
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_poblacion() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🧬 Composición Genética", callback_data="cmd:genetica"),
            InlineKeyboardButton("🌿 Potreros & Pasturas", callback_data="cmd:potreros"),
        ],
        [
            InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
