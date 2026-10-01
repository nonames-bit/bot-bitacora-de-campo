"""Fase C: la PWA usa los íconos SVG de la app, no emojis. Solo quedan los
emojis semáforo que manda el servidor y que el JS compara para pintar un punto."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "src" / "pwa"
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⬀-⯿⌀-⏿]")
PERMITIDOS = {"🟢", "🟡", "🟠", "🔴", "⚪", "🌱", "✓"}


def test_index_sin_emojis():
    assert EMOJI.findall((RAIZ / "templates" / "index.html").read_text(encoding="utf-8")) == []


def test_app_js_solo_emojis_de_logica():
    for nombre in ("app.js", "ja-core.js"):
        sobrantes = set(EMOJI.findall((RAIZ / "static" / nombre).read_text(encoding="utf-8"))) - PERMITIDOS
        assert not sobrantes, f"{nombre}: {sorted(sobrantes)}"


def test_iconos_usados_existen():
    core = (RAIZ / "static" / "ja-core.js").read_text(encoding="utf-8")
    definidos = set(re.findall(r"^\s+([a-zA-Z]+): ['A-Z]", core, re.M)) | {"cow", "bull"}
    usados = set()
    for f in (RAIZ / "static" / "js").glob("*.js"):
        usados |= set(re.findall(r'icon\("([a-zA-Z]+)"', f.read_text(encoding="utf-8")))
    assert usados - definidos == set()
