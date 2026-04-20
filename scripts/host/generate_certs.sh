#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CERT_DIR="$ROOT_DIR/configs/tls/certs"

mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/server.crt" && -f "$CERT_DIR/server.key" ]]; then
  echo "TLS cert already exists at $CERT_DIR"
  exit 0
fi

openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 365 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -subj "/CN=stream-receiver"

echo "Generated: $CERT_DIR/server.crt"
echo "Generated: $CERT_DIR/server.key"
