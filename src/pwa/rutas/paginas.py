"""Páginas HTML y archivos de la PWA (índice, ficha, manifest, service worker, offline).

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import os
import re
from flask import render_template


def registrar(app, ctx, h):
    pwa_version = ctx.pwa_version

    @app.get("/")
    def index():
        return render_template("index.html", pwa_v=pwa_version)

    @app.get("/ficha/<tag>")
    def ficha(tag):
        return render_template("ficha.html", tag=tag, pwa_v=pwa_version)

    @app.get("/manifest.json")
    def manifest():
        return app.send_static_file("manifest.json")

    @app.get("/sw.js")
    def sw_js():
        # El service worker debe servirse en la raíz de su scope ("/") y sin
        # caché HTTP (los navegadores lo revalidan agresivamente). Público.
        # BLOQUE 3: se sirve con el token __PWA_VERSION__ sustituido por el
        # hash calculado al arrancar (versionado automático, sin bump manual).
        with open(os.path.join(app.static_folder, "sw.js"), encoding="utf-8") as _f:
            cuerpo_sw = _f.read().replace("__PWA_VERSION__", pwa_version)
        resp = app.response_class(cuerpo_sw, content_type="application/javascript; charset=utf-8")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    @app.get("/offline.html")
    def offline_page():
        # Página de respaldo para el SW (navegación offline). Público.
        # BLOQUE 3: versionado automático — cualquier ?v=... del fichero se
        # reescribe al hash calculado al arrancar (cubre también el token
        # __PWA_VERSION__ que trae offline.html en disco).
        with open(os.path.join(app.static_folder, "offline.html"), encoding="utf-8") as _f:
            cuerpo_off = _f.read().replace("__PWA_VERSION__", pwa_version)
            cuerpo_off = re.sub(r"\?v=[A-Za-z0-9._-]+", "?v=" + pwa_version, cuerpo_off)
        resp = app.response_class(cuerpo_off, content_type="text/html; charset=utf-8")
        resp.headers["Cache-Control"] = "no-cache"
        return resp
