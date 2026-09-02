"""Fixtures compartidas para la suite de pruebas del bot."""
import os
import sys

import pytest

# Garantiza que el paquete ``src`` sea importable desde la raíz.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot.bot_interface import Bot  # noqa: E402
from src.db.database import Database  # noqa: E402

# Prefijos de proveedores LLM que la cascada híbrida (src/llm/__init__.py)
# lee de variables de entorno. Si el .env real del proyecto tiene alguna key
# configurada, os.environ la hereda igual en el proceso de pytest y un test
# que solo mockea el proveedor "final" (Gemini) puede terminar disparando una
# llamada de red real a un proveedor "barato" anterior en la cascada. Cada
# test que necesite una key específica la agrega con monkeypatch.setenv.
_LLM_ENV_PREFIXES = ("OPENROUTER", "CHEAPERINFERENCE", "OPENCODE", "NVIDIA", "GEMINI")


@pytest.fixture(autouse=True)
def _sin_credenciales_llm_reales(monkeypatch):
    """Aísla la suite de las API keys reales del .env para toda la sesión de tests."""
    for prefix in _LLM_ENV_PREFIXES:
        for suf in ("_API_KEY", "_MODEL", "_BASE_URL"):
            monkeypatch.delenv(f"{prefix}{suf}", raising=False)


@pytest.fixture
def db():
    d = Database(":memory:")
    d.create_tables()
    yield d
    d.close()


@pytest.fixture
def bot(db):
    return Bot(db)
