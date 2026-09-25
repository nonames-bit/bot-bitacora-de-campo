"""Guarda estructural (P2.14): ningún test debe usar las rutas REALES por defecto.

`crear_app(db_path=DB_PATH_DEFAULT, users_file=USERS_FILE_DEFAULT, ...)` ata esos
defaults en la definición de la función (import-time), así que un fixture con
`monkeypatch.setenv`/`setattr` NO los cambia. La única defensa fiable es que cada
llamada pase rutas explícitas (tmp_path). Esta prueba lo verifica de forma
estática con AST: si un test llama `crear_app()` sin primer argumento posicional
ni `db_path=`, falla en CI.

Contexto: la suite ya tuvo un incidente real de contaminación (PNG de gráficos de
prueba cacheados en `data/reportes/`, ver el fixture `_reportes_dir_aislado`).
"""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = sorted((RAIZ / "tests").glob("test_*.py"))
PROPIO = Path(__file__).name


def _llamadas_sin_db_path(texto: str):
    """Llamadas reales (no en comentarios/docstrings) a crear_app sin db_path."""
    hallazgos = []
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return hallazgos
    for node in ast.walk(arbol):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "crear_app"):
            continue
        tiene_db = bool(node.args) or any(kw.arg == "db_path" for kw in node.keywords)
        if not tiene_db:
            hallazgos.append(node.lineno)
    return hallazgos


def test_ninguna_llamada_a_crear_app_sin_ruta_explicita():
    problemas = []
    for ruta in ARCHIVOS:
        if ruta.name == PROPIO:
            continue
        for linea in _llamadas_sin_db_path(ruta.read_text(encoding="utf-8")):
            problemas.append(f"{ruta.name}:{linea}")
    assert problemas == [], f"crear_app() sin db_path explícito en: {problemas}"
