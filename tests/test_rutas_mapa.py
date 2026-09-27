"""Mapa de rutas de la PWA: el mismo antes y después de dividir app.py en
src/pwa/rutas/*.py. Si agrega o cambia una ruta a propósito, regenere
tests/fixtures/rutas_pwa.json (ver el docstring de _mapa)."""
import json
from pathlib import Path

from src.db.database import Database
from src.pwa.app import crear_app

FIXTURE = Path(__file__).parent / "fixtures" / "rutas_pwa.json"


def _mapa(tmp_path):
    """[regla, endpoint, métodos] ordenado. Para regenerar el fixture:
    json.dump(_mapa(tmp), open(FIXTURE, "w"), ensure_ascii=False, indent=0)."""
    ruta = str(tmp_path / "r.db")
    Database(ruta).create_tables().close()
    app = crear_app(ruta, password="x")
    return sorted([r.rule, r.endpoint, sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS"))]
                  for r in app.url_map.iter_rules())


def test_mapa_de_rutas_no_cambia(tmp_path):
    esperado = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = _mapa(tmp_path)
    faltan = [r for r in esperado if r not in actual]
    sobran = [r for r in actual if r not in esperado]
    assert not faltan and not sobran, f"faltan={faltan} sobran={sobran}"
