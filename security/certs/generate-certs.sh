#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="security/certs"
mkdir -p "${CERT_DIR}"

openssl genrsa -out "${CERT_DIR}/ca.key" 4096
openssl req -x509 -new -nodes -key "${CERT_DIR}/ca.key" \
  -sha256 -days 365 -out "${CERT_DIR}/ca.crt" \
  -subj "/C=DE/O=HS-Anhalt/CN=DSA Lab Root CA"

create_cert() {
  local name="$1"
  local common_name="$2"
  local san="$3"
  local eku="$4"

  openssl genrsa -out "${CERT_DIR}/${name}.key" 2048
  openssl req -new -key "${CERT_DIR}/${name}.key" \
    -out "${CERT_DIR}/${name}.csr" \
    -subj "/C=DE/O=HS-Anhalt/CN=${common_name}"

  cat > "${CERT_DIR}/${name}.ext" <<EOF
subjectAltName = ${san}
extendedKeyUsage = ${eku}
keyUsage = digitalSignature, keyEncipherment
EOF

  openssl x509 -req -in "${CERT_DIR}/${name}.csr" \
    -CA "${CERT_DIR}/ca.crt" -CAkey "${CERT_DIR}/ca.key" \
    -CAcreateserial -out "${CERT_DIR}/${name}.crt" \
    -days 180 -sha256 -extfile "${CERT_DIR}/${name}.ext"
}

create_cert "gateway" "localhost" "DNS:localhost,IP:127.0.0.1" "serverAuth"
create_cert "grpc-service" "grpc-service" "DNS:grpc-service" "serverAuth"
create_cert "rest-client" "rest-service" "DNS:rest-service" "clientAuth"

chmod 600 "${CERT_DIR}"/*.key