#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
CONFIG_SOURCE="${REPO_ROOT}/deploy/Caddyfile"
CONFIG_DEST="${CADDY_CONFIG_DEST:-/etc/caddy/Caddyfile}"
DOMAIN="${CADDY_CHECK_DOMAIN:-tryimagent.com}"

echo "Using config source: ${CONFIG_SOURCE}"
echo "Installing config to: ${CONFIG_DEST}"

if [[ ! -f "${CONFIG_SOURCE}" ]]; then
  echo "Config source not found: ${CONFIG_SOURCE}" >&2
  exit 1
fi

sudo install -m 0644 "${CONFIG_SOURCE}" "${CONFIG_DEST}"
sudo caddy validate --config "${CONFIG_DEST}"
sudo caddy reload --config "${CONFIG_DEST}" --adapter caddyfile

echo
echo "Installed /etc/caddy/Caddyfile"
sudo sed -n '1,220p' "${CONFIG_DEST}" || true

echo
echo "Caddy systemd unit"
sudo systemctl cat caddy || true

echo
echo "Active admin config hostnames"
curl -fsS http://127.0.0.1:2019/config/ | grep -Eo 'tryimagent\.com|www\.tryimagent\.com' | sort -u || true

echo
echo "Backend probe"
curl -I --max-time 10 http://127.0.0.1:3002 || true

echo
echo "HTTP probe"
curl -I --max-time 10 "http://${DOMAIN}" || true

echo
echo "HTTPS probe"
curl -Iv --max-time 15 "https://${DOMAIN}" || true

echo
echo "Recent Caddy log lines"
sudo journalctl -u caddy -n 200 --no-pager | grep -Ei "${DOMAIN}|acme|tls|certificate|challenge|error|warn" || true
