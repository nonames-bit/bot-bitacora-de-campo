"""Pruebas del motor sanitario (periodos de retiro y bloqueos)."""
from datetime import date

from src.engine.health_engine import (
    HealthEngine, bloqueo_carne, bloqueo_ordenio, en_retiro, fecha_fin_retiro,
)


def test_fecha_fin_retiro():
    assert fecha_fin_retiro(date(2026, 8, 20), 14) == date(2026, 9, 3)


def test_en_retiro_activo():
    assert en_retiro(date(2026, 8, 20), 14, date(2026, 8, 25)) is True


def test_en_retiro_fuera():
    assert en_retiro(date(2026, 8, 20), 14, date(2026, 9, 10)) is False


def test_sin_retiro():
    assert en_retiro(date(2026, 8, 20), 0, date(2026, 8, 25)) is False


def test_bloqueo_ordenio():
    assert bloqueo_ordenio(date(2026, 8, 20), 14, date(2026, 8, 25)) is True


def test_bloqueo_carne():
    assert bloqueo_carne(date(2026, 8, 20), 14, date(2026, 8, 25)) is True
    assert bloqueo_carne(date(2026, 8, 20), 14, date(2026, 9, 10)) is False


def test_calcular_fin_retiros():
    res = HealthEngine.calcular_fin_retiros(date(2026, 8, 20), 14, 21)
    assert res["fecha_fin_retiro_leche"] == "2026-09-03"
    assert res["fecha_fin_retiro_carne"] == "2026-09-10"
