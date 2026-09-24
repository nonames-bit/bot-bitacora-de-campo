"""Guardas estructurales de los scripts de operación del VPS (auditoría P1.6).

No se puede ejecutar el VPS desde local, así que estas pruebas fijan las
invariantes que la auditoría encontró rotas:
  - `respaldo_drive.sh` (respaldo OFFSITE) debe quedar agendado en cron.
  - `healthcheck_vps.sh` debe instalarse en cron y cubrir bot + PWA + nginx + HTTPS.
  - UFW debe permitir SSH y HTTP/HTTPS antes de habilitarse.
  - Debe existir un drill de restauración con PRAGMA integrity_check.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SETUP = (RAIZ / "scripts" / "setup_vps.sh").read_text(encoding="utf-8")
HEALTH = (RAIZ / "scripts" / "healthcheck_vps.sh").read_text(encoding="utf-8")
DRILL = (RAIZ / "scripts" / "restore_drill.sh").read_text(encoding="utf-8")


def test_respaldo_offsite_agendado_en_cron():
    assert "respaldo_drive.sh" in SETUP
    assert "CRON_DRIVE" in SETUP
    assert "crontab" in SETUP


def test_healthcheck_agendado_y_cubre_pwa_y_nginx():
    assert "healthcheck_vps.sh" in SETUP
    assert "*/15" in SETUP
    assert "bitacora-pwa" in HEALTH
    assert "nginx" in HEALTH
    assert "curl -sf" in HEALTH


def test_ufw_permite_http_https_antes_de_enable():
    assert "ufw allow OpenSSH" in SETUP
    assert "Nginx Full" in SETUP or ("ufw allow 80/tcp" in SETUP and "ufw allow 443/tcp" in SETUP)
    assert "ufw --force enable" in SETUP


def test_restore_drill_existe_y_valida_integridad():
    assert "PRAGMA integrity_check" in DRILL
    assert "restore_drill.sh" in SETUP
    assert "CRON_DRILL" in SETUP
