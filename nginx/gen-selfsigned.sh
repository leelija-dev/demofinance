#!/usr/bin/env sh
set -e

# Generate a local self-signed cert for nginx HTTP/2 termination.
# Files are written to nginx/certs/{fullchain.pem,privkey.pem}.

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 \
  -subj "/C=US/ST=CA/L=Local/O=LocalDev/OU=IT/CN=localhost" \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem"

echo "Self-signed cert created in $CERT_DIR"

