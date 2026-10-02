"""Bandeja "Por revisar": qué eventos de un trabajador quedan en pausa.

Decisión del propietario (2026-10-01): solo lo delicado queda en pausa
hasta que un OWNER/ADMIN lo revise -- partos, muertes, ventas (y demás
entradas/salidas de animales) y traslados. Pesajes, leche, celos,
tratamientos, etc. entran de una como siempre.

Lo usan /api/sync y el traslado masivo de la PWA (origen 'app') y el bot de
Telegram / voz (origen 'bot'). Las rutas de aprobación están en
src/pwa/rutas/revision.py.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from .finanzas_categorias import ETIQUETAS as ETIQUETAS_FINANZAS

logger = logging.getLogger(__name__)

ROLES_EN_REVISION = frozenset({"TRABAJADOR"})
ROLES_REVISORES = ("OWNER", "ADMIN")

# Tipos de /api/sync (y del bot) que quedan en pausa para un trabajador.
# "movimiento" cubre venta, compra, entrada y descarte: todos cambian el hato.
TIPOS_EN_REVISION = frozenset({"parto", "muerte", "venta", "movimiento", "traslado", "traslado_masivo"})

NOMBRE_TIPO = {
    "parto": "Parto",
    "muerte": "Muerte",
    "venta": "Venta",
    "movimiento": "Movimiento",
    "traslado": "Traslado",
    "traslado_masivo": "Traslado de potrero",
    "gasto": "Factura",
}

# Campos que el revisor puede corregir antes de aprobar, con su etiqueta.
# Solo se muestran los que el registro trae.
ETIQUETAS_CAMPO = {
    "vaca_tag": "Arete de la vaca",
    "animal_tag": "Arete",
    "tag": "Arete",
    "cria_tag": "Arete de la cría",
    "id_cria_tag": "Arete de la cría",
    "id_cria": "Arete de la cría",
    "tipo_evento": "Tipo de parto",
    "sexo_cria": "Sexo de la cría",
    "estado_cria": "Estado de la cría",
    "peso_nacimiento": "Peso al nacer (kg)",
    "padre_tag": "Padre",
    "potrero_cria": "Potrero de la cría",
    "potrero_madre": "Potrero de la madre",
    "causa_presunta": "Causa",
    "comprador": "Comprador",
    "procedencia_destino": "Procedencia o destino",
    "tipo_movimiento": "Tipo de movimiento",
    "precio": "Precio",
    "peso_kg": "Peso (kg)",
    "motivo": "Motivo",
    "lote": "Lote",
    "potrero_origen": "Potrero de origen",
    "potrero_destino": "Potrero de destino",
    "contraparte": "Proveedor",
    "concepto": "Concepto",
    "monto": "Monto",
    "notas": "Notas",
}


def requiere_revision(rol: Optional[str], tipo: Optional[str]) -> bool:
    """True si el evento de ese rol debe esperar revisión."""
    return (str(rol or "").strip().upper() in ROLES_EN_REVISION
            and str(tipo or "").strip().lower() in TIPOS_EN_REVISION)


def _campos_evento(origen: str, datos: dict) -> dict:
    """Los campos del evento en un solo nivel (el bot los guarda en datos.datos)."""
    if origen == "bot":
        base = dict(datos.get("datos") or {})
        if datos.get("animal_tag"):
            base.setdefault("animal_tag", datos.get("animal_tag"))
        return base
    return dict(datos or {})


def tag_principal(origen: str, datos: dict) -> Optional[str]:
    c = _campos_evento(origen, datos)
    for clave in ("vaca_tag", "animal_tag", "tag", "cria_tag"):
        if c.get(clave):
            return str(c[clave]).strip()
    return None


def _precio(valor: Any) -> str:
    try:
        return "$" + f"{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(valor)


def resumen(origen: str, tipo: str, datos: dict) -> str:
    """Una línea en español para la bandeja, ej. 'Parto de la 47 · cría HEMBRA'."""
    c = _campos_evento(origen, datos)
    tag = tag_principal(origen, datos)
    de = f" de la {tag}" if tag else ""
    partes: list[str]
    if tipo == "parto":
        tipo_ev = str(c.get("tipo_evento") or "PARTO").upper()
        titulo = "Parto" if tipo_ev == "PARTO" else tipo_ev.replace("_", " ").capitalize()
        partes = [titulo + de]
        if c.get("sexo_cria"):
            partes.append(f"cría {str(c['sexo_cria']).lower()}")
        cria = c.get("id_cria_tag") or c.get("id_cria")
        if cria:
            partes.append(f"arete cría {cria}")
    elif tipo == "muerte":
        partes = ["Muerte" + de]
        if c.get("causa_presunta"):
            partes.append(str(c["causa_presunta"]))
    elif tipo in ("venta", "movimiento"):
        tipo_mov = str(c.get("tipo_movimiento") or ("VENTA" if tipo == "venta" else "")).upper()
        partes = [(tipo_mov.capitalize() or "Movimiento") + de]
        precio = c.get("precio") or c.get("monto") or c.get("valor")
        if precio not in (None, ""):
            partes.append(_precio(precio))
        destino = c.get("comprador") or c.get("procedencia_destino") or c.get("destino")
        if destino:
            partes.append(str(destino))
    elif tipo == "traslado_masivo":
        partes = [f"Traslado de todo el potrero {c.get('potrero_origen') or '?'} "
                  f"a {c.get('potrero_destino') or '?'}"]
    elif tipo == "gasto":
        # Facturas del correo de la finca (src/integrations/correo_facturas.py).
        partes = ["Factura" + (f" de {c['contraparte']}" if c.get("contraparte") else "")]
        if c.get("monto") not in (None, ""):
            partes.append(_precio(c["monto"]))
        cats = [g.get("categoria") for g in (c.get("desglose") or []) if isinstance(g, dict)] or [c.get("categoria")]
        partes.append(", ".join(ETIQUETAS_FINANZAS.get(k, str(k)) for k in cats if k))
    elif tipo == "traslado":
        partes = ["Traslado" + de]
        if c.get("potrero_destino"):
            partes.append(f"a {c['potrero_destino']}")
    else:
        partes = [NOMBRE_TIPO.get(tipo, tipo.capitalize()) + de]
    return " · ".join(str(p) for p in partes if p)


def campos_editables(origen: str, datos: dict) -> list[dict]:
    """Campos simples que el revisor puede corregir, en el orden de ETIQUETAS_CAMPO."""
    c = _campos_evento(origen, datos)
    salida = []
    for clave, etiqueta in ETIQUETAS_CAMPO.items():
        if clave not in c:
            continue
        if clave == "monto" and c.get("desglose"):
            continue  # repartida por categoría: el monto sale de cada parte
        valor = c[clave]
        if isinstance(valor, (dict, list)):
            continue
        salida.append({"clave": clave, "etiqueta": etiqueta, "valor": "" if valor is None else valor})
    return salida


def aplicar_cambios(origen: str, datos: dict, cambios: Optional[dict]) -> dict:
    """Devuelve una copia de ``datos`` con las correcciones del revisor. Solo
    se aceptan claves que el registro ya traía (las de campos_editables)."""
    nuevos = json.loads(json.dumps(datos or {}, default=str))
    if not isinstance(cambios, dict) or not cambios:
        return nuevos
    permitidas = {c["clave"] for c in campos_editables(origen, datos)}
    for clave, valor in cambios.items():
        if clave not in permitidas:
            continue
        valor = valor.strip() if isinstance(valor, str) else valor
        if valor == "":
            valor = None
        if origen == "bot":
            if clave == "animal_tag":
                nuevos["animal_tag"] = valor
                nuevos.setdefault("datos", {}).pop("animal_tag", None)
            else:
                nuevos.setdefault("datos", {})[clave] = valor
        else:
            nuevos[clave] = valor
    return nuevos


def _ids_revisores(users_file: Optional[str]) -> list:
    """user_id de OWNER/ADMIN en users.json, más None (suscripciones de la
    contraseña maestra, que es del propietario)."""
    ids: list = [None]
    if not users_file:
        return ids
    try:
        with open(users_file, encoding="utf-8") as f:
            for u in json.load(f):
                if isinstance(u, dict) and str(u.get("rol", "")).strip().upper() in ROLES_REVISORES:
                    ids.append(u.get("user_id"))
    except Exception:
        logger.debug("No se pudo leer %s para avisar a los revisores", users_file, exc_info=True)
    return ids


def avisar_equipo(db, texto: str, user_id: Optional[int] = None, nombre: str = "Sistema",
                  rol: str = "SISTEMA") -> None:
    """Deja el aviso en el canal del equipo. Nunca lanza."""
    try:
        db.registrar_mensaje_equipo(user_id=user_id, nombre=nombre, rol=rol, texto=texto[:500])
    except Exception:
        logger.exception("No se pudo publicar el aviso de revisión en el canal del equipo")


def poner_en_revision(db, *, origen: str, tipo: str, datos: dict, fecha: Optional[str],
                      registrado_por: Optional[int], registrado_por_nombre: Optional[str],
                      canal: str, users_file: Optional[str] = None) -> int:
    """Guarda el evento en la bandeja y avisa a OWNER/ADMIN (canal + push)."""
    texto_resumen = resumen(origen, tipo, datos)
    nombre = (registrado_por_nombre or "").strip() or "Un trabajador"
    pid = db.crear_pendiente(
        origen=origen, tipo=tipo, datos=datos, fecha=fecha,
        animal_tag=tag_principal(origen, datos), resumen=texto_resumen,
        registrado_por=registrado_por, registrado_por_nombre=nombre, canal=canal,
    )
    avisar_equipo(db, f"{nombre} registró: {texto_resumen}. Queda por revisar.",
                  user_id=registrado_por, nombre=nombre, rol="TRABAJADOR")
    try:
        from ..server.push_sender import enviar_push
        enviar_push(db, titulo="Registro por revisar", cuerpo=f"{nombre}: {texto_resumen}",
                    url="/?v=revision", tag="por-revisar", user_ids=_ids_revisores(users_file))
    except Exception:
        logger.exception("No se pudo enviar el push de registro por revisar")
    return pid
