"""Pruebas de src/server/push_sender.py: envío real de Web Push (VAPID).

pywebpush.webpush hace una petición HTTP real al push service del
navegador (FCM/Mozilla) -- todas las pruebas mockean esa función, nunca
la llaman de verdad. Lo que se verifica es la lógica propia: a quién le
manda, a quién excluye, y cómo limpia suscripciones vencidas.
"""
from types import SimpleNamespace

import pytest

from src.server import push_sender


@pytest.fixture(autouse=True)
def _vapid_configurada(monkeypatch):
    """La mayoría de los tests necesitan VAPID "configurada" para que
    enviar_push no se salte todo de una -- una excepción explícita
    desactiva esto para probar justamente ese camino."""
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "clave-privada-de-prueba")
    monkeypatch.setenv("VAPID_CLAIMS_EMAIL", "owner@ejemplo.com")


def test_enviar_push_sin_vapid_configurada_no_hace_nada(db, monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_CLAIMS_EMAIL", raising=False)
    llamadas = []
    monkeypatch.setattr(push_sender, "webpush", lambda **kw: llamadas.append(kw))

    db.guardar_push_suscripcion("https://fcm.googleapis.com/x", user_id="1", p256dh="p", auth="a")
    resumen = push_sender.enviar_push(db, "Titulo", "Cuerpo")

    assert resumen == {"enviados": 0, "fallidos": 0, "vencidas_limpiadas": 0}
    assert llamadas == []


def test_enviar_push_llama_webpush_por_cada_suscripcion_valida(db, monkeypatch):
    llamadas = []
    monkeypatch.setattr(push_sender, "webpush", lambda **kw: llamadas.append(kw))

    db.guardar_push_suscripcion("https://fcm.googleapis.com/uno", user_id="1", p256dh="p1", auth="a1")
    db.guardar_push_suscripcion("https://fcm.googleapis.com/dos", user_id="2", p256dh="p2", auth="a2")

    resumen = push_sender.enviar_push(db, "Aviso", "Contenido del aviso")

    assert resumen["enviados"] == 2
    assert resumen["fallidos"] == 0
    endpoints_llamados = {c["subscription_info"]["endpoint"] for c in llamadas}
    assert endpoints_llamados == {"https://fcm.googleapis.com/uno", "https://fcm.googleapis.com/dos"}
    # El payload va como JSON con el título y el cuerpo pasados.
    assert "Aviso" in llamadas[0]["data"]
    assert "Contenido del aviso" in llamadas[0]["data"]


def test_enviar_push_ignora_endpoints_de_relleno_pwa_local(db, monkeypatch):
    """Suscripciones de antes de que existiera VAPID (endpoint pwa-local://
    de relleno, o sin p256dh/auth) no tienen a dónde enviarles -- se saltan
    sin contar como fallo."""
    llamadas = []
    monkeypatch.setattr(push_sender, "webpush", lambda **kw: llamadas.append(kw))

    db.guardar_push_suscripcion("pwa-local://dev_abc123", user_id="1", p256dh=None, auth=None)
    resumen = push_sender.enviar_push(db, "Titulo", "Cuerpo")

    assert llamadas == []
    assert resumen == {"enviados": 0, "fallidos": 0, "vencidas_limpiadas": 0}


def test_enviar_push_excluye_al_autor_del_mensaje(db, monkeypatch):
    llamadas = []
    monkeypatch.setattr(push_sender, "webpush", lambda **kw: llamadas.append(kw))

    db.guardar_push_suscripcion("https://fcm.googleapis.com/autor", user_id="1", p256dh="p", auth="a")
    db.guardar_push_suscripcion("https://fcm.googleapis.com/otro", user_id="2", p256dh="p", auth="a")

    resumen = push_sender.enviar_push(db, "Titulo", "Cuerpo", excluir_user_id="1")

    assert resumen["enviados"] == 1
    assert llamadas[0]["subscription_info"]["endpoint"] == "https://fcm.googleapis.com/otro"


def test_enviar_push_limpia_suscripcion_vencida_410(db, monkeypatch):
    def _falla_vencida(**kw):
        raise push_sender.WebPushException("gone", response=SimpleNamespace(status_code=410))

    monkeypatch.setattr(push_sender, "webpush", _falla_vencida)
    db.guardar_push_suscripcion("https://fcm.googleapis.com/vencido", user_id="1", p256dh="p", auth="a")

    resumen = push_sender.enviar_push(db, "Titulo", "Cuerpo")

    assert resumen == {"enviados": 0, "fallidos": 0, "vencidas_limpiadas": 1}
    assert db.listar_push_suscripciones() == []


def test_enviar_push_error_no_410_cuenta_como_fallido_pero_no_borra(db, monkeypatch):
    def _falla_temporal(**kw):
        raise push_sender.WebPushException("boom", response=SimpleNamespace(status_code=500))

    monkeypatch.setattr(push_sender, "webpush", _falla_temporal)
    db.guardar_push_suscripcion("https://fcm.googleapis.com/temporal", user_id="1", p256dh="p", auth="a")

    resumen = push_sender.enviar_push(db, "Titulo", "Cuerpo")

    assert resumen == {"enviados": 0, "fallidos": 1, "vencidas_limpiadas": 0}
    assert len(db.listar_push_suscripciones()) == 1


def test_listar_push_suscripciones_excluir_user_id(db):
    db.guardar_push_suscripcion("https://fcm.googleapis.com/a", user_id="1", p256dh="p", auth="a")
    db.guardar_push_suscripcion("https://fcm.googleapis.com/b", user_id="2", p256dh="p", auth="a")
    db.guardar_push_suscripcion("https://fcm.googleapis.com/c", user_id=None, p256dh="p", auth="a")

    restantes = db.listar_push_suscripciones(excluir_user_id="1")
    endpoints = {f["endpoint"] for f in restantes}
    # El de user_id=None se conserva (no se sabe si es el mismo autor o no).
    assert endpoints == {"https://fcm.googleapis.com/b", "https://fcm.googleapis.com/c"}
