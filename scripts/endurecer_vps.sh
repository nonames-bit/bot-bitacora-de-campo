#!/usr/bin/env bash
# Endurece un VPS Ubuntu para la Bitácora en Docker (ejecutar como root, una vez).
#   - Firewall: solo SSH (22), HTTP (80) y HTTPS (443).
#   - SSH solo con llave (sin contraseña) y sin login de root por contraseña.
#   - fail2ban contra intentos repetidos de SSH.
#   - Actualizaciones de seguridad automáticas.
#   - Docker Engine + plugin compose.
# ANTES de correrlo, confirme que entra por SSH con su llave: si no, se queda afuera.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Ejecute como root: sudo bash scripts/endurecer_vps.sh" >&2
    exit 1
fi
if [ ! -s /root/.ssh/authorized_keys ] && [ -z "${SUDO_USER:-}" ]; then
    echo "No hay llaves en /root/.ssh/authorized_keys: agregue la suya antes de desactivar contraseñas." >&2
    exit 1
fi

echo "== Paquetes =="
apt-get update -y
apt-get install -y ufw fail2ban unattended-upgrades ca-certificates curl

echo "== Docker =="
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "== Firewall =="
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "== SSH solo con llave =="
cat > /etc/ssh/sshd_config.d/90-bitacora.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
CONF
sshd -t && systemctl reload ssh || systemctl reload sshd

echo "== fail2ban =="
cat > /etc/fail2ban/jail.d/sshd.local <<'CONF'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
CONF
systemctl enable --now fail2ban
systemctl restart fail2ban

echo "== Actualizaciones de seguridad automáticas =="
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "✅ Servidor endurecido. Siguiente paso: docs/DESPLIEGUE_DOCKER.md"
