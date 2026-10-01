"""Rutas de la PWA divididas por dominio.

Cada módulo define ``registrar(app, ctx, h)`` y declara sus rutas con
``@app.get/post`` sobre la misma app de ``crear_app``: los nombres de
endpoint y las URLs no cambian. ``ctx`` trae el estado del cierre de
``crear_app`` (db_path, users_file, límites...) y ``h`` sus funciones
auxiliares (_rol_actual, _usuario_actual, _limite_api...).
"""
from __future__ import annotations

from . import _comun, auth, paginas, vistas_campo, leche_finanzas, animales, agenda_equipo, sync, manga_ia, insumos_repro, sistema, push_graficos, revision

MODULOS = (auth, paginas, vistas_campo, leche_finanzas, animales, agenda_equipo, sync, manga_ia, insumos_repro, sistema, push_graficos, revision,)


def registrar_todas(app, ctx, h) -> None:
    _comun.construir(ctx, h)  # helpers compartidos (h._guardar_foto_evento)
    for modulo in MODULOS:
        modulo.registrar(app, ctx, h)
