#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-anp.local.test}"
OUT_DIR="${2:-config/certs}"
PORT="${3:-443}"

echo "[dev-up] Domain: $DOMAIN OutDir: $OUT_DIR Port: $PORT"

PY=python
if [[ -x "venv/bin/python" ]]; then
  PY="venv/bin/python"
fi

if [[ ! -f "$OUT_DIR/server.crt" || ! -f "$OUT_DIR/server.key" ]]; then
  echo "[dev-up] Generating certificates..."
  "$PY" scripts/gen_dev_certs.py --domain "$DOMAIN" --out "$OUT_DIR"
fi

CERT_PATH=$(realpath "$OUT_DIR/server.crt")
KEY_PATH=$(realpath "$OUT_DIR/server.key")
echo "[dev-up] Using cert: $CERT_PATH"
echo "[dev-up] Using key : $KEY_PATH"

echo "[dev-up] Ensure hosts file contains: 127.0.0.1  $DOMAIN"
echo "           Hosts file: /etc/hosts (requires sudo to edit)"

UNAME=$(uname -s || true)
if [[ "$UNAME" == "Darwin" ]]; then
  echo "[dev-up] macOS: Add $CERT_PATH to System keychain (Keychain Access > System > Certificates)."
  echo "           You may run: sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_PATH"
else
  echo "[dev-up] Linux: Trust cert via system CA store (varies by distro)."
  echo "           For Debian/Ubuntu: sudo cp $CERT_PATH /usr/local/share/ca-certificates/$DOMAIN.crt && sudo update-ca-certificates"
fi

export ANP_SSL_CERT="$CERT_PATH"
export ANP_SSL_KEY="$KEY_PATH"
export ANP_HOST="0.0.0.0"
export ANP_PORT="$PORT"
export ANP_SERVER_DOMAIN="did:wba:$DOMAIN:anp-server"
export ANP_CLIENT_DOMAIN="$DOMAIN"
export ANP_DEV_LOCAL_RESOLVER="false"

echo "[dev-up] Starting ANP SDK server on https://$DOMAIN:$PORT (may require sudo for port 443)"
"$PY" -m servers.anp_sdk_server || {
  echo "[dev-up] Failed to bind port $PORT. Try: sudo $0 $DOMAIN $OUT_DIR 443 or use 8443."
  exit 1
}

