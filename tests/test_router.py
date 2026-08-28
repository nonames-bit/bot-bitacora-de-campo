"""Pruebas del router determinista de dominios (sin LLM)."""
from src.llm.router import dominios_detectados, tipos_coincidentes


def test_tipos_coincidentes_single():
    assert tipos_coincidentes("pario la 47") == {"parto"}


def test_tipos_coincidentes_multiple():
    tipos = tipos_coincidentes("pario la 47 y vacune la 12 con oxitetraciclina 20ml")
    assert "parto" in tipos
    assert "tratamiento" in tipos


def test_dominios_detectados_un_dominio():
    assert dominios_detectados("pario la 47 un ternero macho") == {"reproduccion"}


def test_dominios_detectados_dos_dominios():
    dominios = dominios_detectados("pario la 47 y vacune la 12 con oxitetraciclina")
    assert dominios == {"reproduccion", "sanidad"}


def test_dominios_detectados_tres_dominios():
    texto = "pario la 47, vacune la 12 con oxitetraciclina, y traslade la 8 al potrero 3"
    dominios = dominios_detectados(texto)
    assert dominios == {"reproduccion", "sanidad", "manejo"}


def test_dominios_detectados_ninguno():
    assert dominios_detectados("xkjh qwerty asdf zxcv") == set()
