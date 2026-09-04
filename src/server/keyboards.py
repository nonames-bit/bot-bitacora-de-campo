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


def crear_teclado_ayuda_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📖 Manual / Comandos", callback_data="cmd:ayuda"),
            InlineKeyboardButton("💬 Cómo Preguntar al Chat", callback_data="guia:chat_hub"),
        ],
        [
            InlineKeyboardButton("📝 Ejemplos de Notas", callback_data="cmd:ejemplos"),
            InlineKeyboardButton("💡 Guía de Campo", callback_data="menu:campo"),
        ],
        [
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
            InlineKeyboardButton("🆘 SOS / Emergencia", callback_data="cmd:sos"),
        ],
        [
            InlineKeyboardButton("❓ Ayuda & Guías", callback_data="cmd:ayuda_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_admin(rol: Optional[str] = None) -> InlineKeyboardMarkup:
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
            InlineKeyboardButton("🤰 Reproducción & Termo", callback_data="cmd:reprod_menu"),
            InlineKeyboardButton("💊 Medicamentos & Retiro", callback_data="cmd:medicamentos"),
        ],
        [
            # Composición Genética (razas del hato) vive dentro de Población &
            # KPIs SG — no se repite aquí como atajo aparte para no tener dos
            # caminos distintos a la misma pantalla.
            InlineKeyboardButton("📊 Población & KPIs SG", callback_data="cmd:poblacion"),
            InlineKeyboardButton("📷 Galería Fotos", callback_data="cmd:fotos"),
        ],
        [
            InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
            InlineKeyboardButton("📊 Gráficos de la Finca", callback_data="cmd:graficos"),
        ],
        [
            InlineKeyboardButton("📦 Sistema & Reportes", callback_data="cmd:sistema_menu"),
            InlineKeyboardButton("❓ Ayuda & Guías", callback_data="cmd:ayuda_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def crear_teclado_sistema_menu(rol: Optional[str] = None) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📋 Reporte Semanal PDF", callback_data="cmd:reporte"),
            InlineKeyboardButton("📦 Descargar Backup ZIP", callback_data="cmd:exportar"),
        ],
        [
            InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
        ],
    ]
    # "Ver Últimos Logs" y "Usuarios / Permisos" solo los procesa el handler
    # para el OWNER (rechaza a ADMIN con un mensaje de error) — se ocultan
    # aquí para no mostrar botones que van a rebotar.
    if rol == "OWNER" or rol is None:
        keyboard.append([
            InlineKeyboardButton("📜 Ver Últimos Logs", callback_data="cmd:logs"),
            InlineKeyboardButton("👥 Usuarios / Permisos", callback_data="cmd:usuarios"),
        ])
    keyboard.append([
        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
    ])
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_sistema_detalle() -> InlineKeyboardMarkup:
    """Teclado compacto para las sub-vistas de Sistema & Reportes (estado del
    servidor, usuarios, logs): solo navegación de vuelta, sin repetir los
    botones de acción que ya viven en el menú padre."""
    keyboard = [
        [
            InlineKeyboardButton("◀ Volver a Sistema & Reportes", callback_data="cmd:sistema_menu"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
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


def crear_teclado_animal_detalle(tag: str) -> InlineKeyboardMarkup:
    """Teclado compacto para sub-vistas de un animal (pesajes, leche, sanidad, genealogía, gráficos).

    Solo muestra botones de navegación simplificada [◀ Volver a Ficha | 🏠 Menú Principal]
    para evitar saturar la pantalla debajo de las consultas de detalle.
    """
    tag_clean = str(tag).strip()
    keyboard = [
        [
            InlineKeyboardButton(f"◀ Volver a Ficha ({tag_clean})", callback_data=f"ficha:{tag_clean}"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_graficos() -> InlineKeyboardMarkup:
    """Menú de gráficos generales de la finca agrupados en 4 categorías zootécnicas:
    Hato, Reproducción & Genética, Pasturas & Rotación y Producción Lechera."""
    keyboard = [
        # --- Categoría 1: HATO ---
        [
            InlineKeyboardButton("─── 🐄 HATO ───", callback_data="noop:hato"),
        ],
        [
            InlineKeyboardButton("📈 Evolución", callback_data="panel_grafico:evolucion"),
            InlineKeyboardButton("🌊 Waterfall", callback_data="panel_grafico:waterfall"),
        ],
        [
            InlineKeyboardButton("🥧 Categorías del Hato", callback_data="panel_grafico:categorias"),
        ],
        # --- Categoría 2: REPRODUCCIÓN ---
        [
            InlineKeyboardButton("─── 🧬 REPRODUCCIÓN ───", callback_data="noop:reprod"),
        ],
        [
            InlineKeyboardButton("⚖️ GMD del Hato", callback_data="panel_grafico:gmd"),
            InlineKeyboardButton("📦 IEP (2 años)", callback_data="panel_grafico:iep"),
        ],
        [
            InlineKeyboardButton("📦 IEP Histórico", callback_data="panel_grafico:iep_completo"),
            InlineKeyboardButton("🐄 Destete por Raza", callback_data="panel_grafico:destete_raza"),
        ],
        [
            InlineKeyboardButton("🐂 Rendimiento Padre", callback_data="panel_grafico:padre"),
            InlineKeyboardButton("🤰 Preñadas vs Vacías", callback_data="panel_grafico:prenadas"),
        ],
        [
            InlineKeyboardButton("📉 Días Abiertos KM", callback_data="panel_grafico:dias_abiertos_km"),
            InlineKeyboardButton("🧬 Estado Reproductivo", callback_data="panel_grafico:reproductivo_hato"),
        ],
        # --- Categoría 3: PASTURAS ---
        [
            InlineKeyboardButton("─── 🌱 PASTURAS ───", callback_data="noop:pasturas"),
        ],
        [
            InlineKeyboardButton("🌱 Aforo Potreros", callback_data="panel_grafico:aforo"),
            InlineKeyboardButton("🔄 Ocupación Voisin", callback_data="panel_grafico:ocupacion"),
        ],
        [
            InlineKeyboardButton("🐄 Carga Animal (UGG/ha)", callback_data="panel_grafico:carga_animal"),
        ],
        [
            InlineKeyboardButton("🗺️ Mapa de Potreros", callback_data="panel_grafico:mapa_potreros"),
        ],
        # --- Categoría 4: LECHE ---
        [
            InlineKeyboardButton("─── 🥛 LECHE ───", callback_data="noop:leche"),
        ],
        [
            InlineKeyboardButton("🥛 Producción Total", callback_data="panel_grafico:leche_total"),
            InlineKeyboardButton("⚡ Eficiencia Lechera", callback_data="panel_grafico:eficiencia_lechera"),
        ],
        [
            InlineKeyboardButton("🏆 Ranking de Vacas", callback_data="panel_grafico:ranking_leche"),
        ],
        # --- Navegación ---
        [
            InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_grafico_detalle() -> InlineKeyboardMarkup:
    """Teclado compacto para la vista de detalle de un gráfico general.

    Solo muestra botones de navegación simplificada para evitar saturar
    la pantalla debajo de la imagen del gráfico.
    """
    keyboard = [
        [
            InlineKeyboardButton("◀ Volver a Gráficos", callback_data="cmd:graficos"),
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


def crear_teclado_alertas_detalle() -> InlineKeyboardMarkup:
    """Teclado compacto para la vista de detalle de alertas."""
    keyboard = [
        [
            InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
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


def crear_teclado_poblacion_detalle() -> InlineKeyboardMarkup:
    """Teclado compacto para la sub-vista de composición genética y población."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Volver a Población", callback_data="cmd:poblacion"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_reproduccion(rol: Optional[str] = None) -> InlineKeyboardMarkup:
    """Menú de gestión reproductiva, termo criogénico y diagnósticos."""
    keyboard = [
        [
            InlineKeyboardButton("🧪 Stock Pajuelas", callback_data="cmd:pajuelas"),
            InlineKeyboardButton("❄️ N₂ / Termo", callback_data="cmd:termo"),
        ],
        [
            InlineKeyboardButton("🩺 Diagnósticos Gestación", callback_data="cmd:diagnosticos"),
            InlineKeyboardButton("📊 Tasa Concepción & S/C", callback_data="cmd:kpi_reprod"),
        ],
        [
            InlineKeyboardButton("🐂 Rendimiento Toros", callback_data="panel_grafico:padre"),
            InlineKeyboardButton("🤰 Preñadas vs Vacías", callback_data="panel_grafico:prenadas"),
        ],
        [
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_reproduccion_detalle() -> InlineKeyboardMarkup:
    """Teclado compacto para sub-vistas del módulo de reproducción."""
    keyboard = [
        [
            InlineKeyboardButton("🤰 Volver a Reproducción", callback_data="cmd:reprod_menu"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_confirmar_factura_pajuelas(toro: str, cantidad: int) -> InlineKeyboardMarkup:
    """Teclado interactivo para confirmar o descartar la carga de stock de pajuelas detectadas por OCR."""
    toro_param = str(toro).replace(":", "_").strip()
    keyboard = [
        [
            InlineKeyboardButton(
                f"✅ Cargar {cantidad} pajuelas {toro}",
                callback_data=f"cmd:confirmar_factura:{toro_param}:{cantidad}",
            ),
            InlineKeyboardButton(
                "❌ Descartar",
                callback_data="cmd:confirmar_factura:descartar",
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_clima() -> InlineKeyboardMarkup:
    """Menú de gestión climática, pluviometría y balance forrajero (Fase 6.2)."""
    keyboard = [
        [
            InlineKeyboardButton("🌾 Balance Forrajero (MS)", callback_data="cmd:balance_forrajero"),
            InlineKeyboardButton("🌧️ Reporte Pluviométrico", callback_data="cmd:clima"),
        ],
        [
            InlineKeyboardButton("🛰️ Satélite NDVI", callback_data="cmd:ndvi"),
            InlineKeyboardButton("🌱 Aforo Potreros", callback_data="panel_grafico:aforo"),
        ],
        [
            InlineKeyboardButton("🔄 Ocupación Voisin", callback_data="panel_grafico:ocupacion"),
            InlineKeyboardButton("🌿 Potreros SG", callback_data="cmd:potreros"),
        ],
        [
            InlineKeyboardButton("🗺️ Mapa de Potreros", callback_data="panel_grafico:mapa_potreros"),
        ],
        [
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_clima_detalle() -> InlineKeyboardMarkup:
    """Teclado compacto para sub-vistas del módulo de clima y balance forrajero."""
    keyboard = [
        [
            InlineKeyboardButton("🌧️ Volver a Clima", callback_data="cmd:clima"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def crear_teclado_ndvi() -> InlineKeyboardMarkup:
    """Teclado interactivo para el panel satelital NDVI Sentinel-2 (Fase 8.2)."""
    keyboard = [
        [
            InlineKeyboardButton("🌾 Balance Forrajero", callback_data="cmd:balance_forrajero"),
            InlineKeyboardButton("🌧️ Reporte Pluviométrico", callback_data="cmd:clima"),
        ],
        [
            InlineKeyboardButton("🌿 Matriz Potreros", callback_data="cmd:potreros"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)




