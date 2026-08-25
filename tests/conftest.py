"""Fixtures compartidas para la suite de pruebas del bot."""
import os
import sys

import pytest

# Garantiza que el paquete ``src`` sea importable desde la raíz.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot.bot_interface import Bot  # noqa: E402
from src.db.database import Database  # noqa: E402


@pytest.fixture
def db():
    d = Database(":memory:")
    d.create_tables()
    yield d
    d.close()


@pytest.fixture
def bot(db):
    return Bot(db)
