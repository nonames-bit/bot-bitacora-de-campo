"""Guardas del lock de dependencias (auditoría P1.7).

El deploy instalaba `requirements.txt` con especificadores abiertos (`>=`), así
que cualquiera de las 18 libs directas podía romper el próximo deploy sin
aviso. Ahora requirements.txt es un lock pinneado generado con uv, y las de
desarrollo viven en requirements-dev.txt.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

REQ = RAIZ / "requirements.txt"
REQ_IN = RAIZ / "requirements.in"
REQ_DEV = RAIZ / "requirements-dev.txt"
REQ_DEV_IN = RAIZ / "requirements-dev.in"
CI = (RAIZ / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")


def _lineas_requirement(ruta: Path) -> list[str]:
    out = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def test_requirements_es_lock_totalmente_pinneado():
    reqs = _lineas_requirement(REQ)
    assert reqs, "requirements.txt no puede estar vacío"
    abiertos = [r for r in reqs if "==" not in r]
    assert abiertos == [], f"requirements.txt debe ser un lock (todo '=='): {abiertos}"


def test_requirements_in_y_dev_existen():
    assert REQ_IN.exists(), "falta requirements.in (fuente del lock de producción)"
    assert REQ_DEV_IN.exists(), "falta requirements-dev.in (fuente del lock de dev)"
    assert REQ_DEV.exists(), "falta requirements-dev.txt (lock de dev)"


def test_requirements_dev_pinnea_pytest_y_ruff():
    dev = _lineas_requirement(REQ_DEV)
    assert any(r.startswith("pytest==") for r in dev), dev
    assert any(r.startswith("ruff==") for r in dev), dev


def test_ci_instala_lock_y_deps_de_dev():
    assert "-r requirements.txt" in CI
    assert "-r requirements-dev.txt" in CI


def test_ci_mide_cobertura_con_piso():
    """P2.10: el CI debe medir cobertura y fallar bajo el piso."""
    assert "--cov=src" in CI
    assert "--cov-fail-under=" in CI
    dev = (RAIZ / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "pytest-cov==" in dev, "pytest-cov debe estar en el lock de dev"
