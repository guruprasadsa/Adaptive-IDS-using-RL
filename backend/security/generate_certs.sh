#!/bin/bash
# Generate mTLS Certificates for Adaptive IDS
# This script creates a CA and service certificates for mutual TLS authentication

set -e

CERTS_DIR="./certs"
VALIDITY_DAYS=365

echo "Generating mTLS certificates for Adaptive IDS..."
echo "Certificates will be stored in: $CERTS_DIR"

# Create certs directory
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

# 1. Generate CA private key and certificate
echo "1. Generating Certificate Authority (CA)..."
openssl genrsa -out ca-key.pem 4096

openssl req -new -x509 -days $VALIDITY_DAYS \
  -key ca-key.pem \
  -sha256 \
  -out ca-cert.pem \
  -subj "/C=US/ST=State/L=City/O=Adaptive IDS/OU=Security/CN=Adaptive IDS CA"

echo "   ✓ CA certificate created: ca-cert.pem"

# 2. Generate backend API server certificate
echo "2. Generating Backend API server certificate..."
openssl genrsa -out backend-server-key.pem 4096

openssl req -new -key backend-server-key.pem \
  -out backend-server.csr \
  -subj "/C=US/ST=State/L=City/O=Adaptive IDS/OU=Backend/CN=backend-api"

openssl x509 -req -days $VALIDITY_DAYS \
  -sha256 \
  -in backend-server.csr \
  -CA ca-cert.pem \
  -CAkey ca-key.pem \
  -CAcreateserial \
  -out backend-server-cert.pem \
  -extfile <(printf "subjectAltName=DNS:backend,DNS:localhost,IP:127.0.0.1")

rm backend-server.csr
echo "   ✓ Backend server certificate created: backend-server-cert.pem"

# 3. Generate model service server certificate
echo "3. Generating Model Service server certificate..."
openssl genrsa -out model-service-server-key.pem 4096

openssl req -new -key model-service-server-key.pem \
  -out model-service-server.csr \
  -subj "/C=US/ST=State/L=City/O=Adaptive IDS/OU=Model Service/CN=model-service"

openssl x509 -req -days $VALIDITY_DAYS \
  -sha256 \
  -in model-service-server.csr \
  -CA ca-cert.pem \
  -CAkey ca-key.pem \
  -CAcreateserial \
  -out model-service-server-cert.pem \
  -extfile <(printf "subjectAltName=DNS:model-service,DNS:localhost,IP:127.0.0.1")

rm model-service-server.csr
echo "   ✓ Model service server certificate created: model-service-server-cert.pem"

# 4. Generate alerting service client certificate
echo "4. Generating Alerting Service client certificate..."
openssl genrsa -out alerting-service-client-key.pem 4096

openssl req -new -key alerting-service-client-key.pem \
  -out alerting-service-client.csr \
  -subj "/C=US/ST=State/L=City/O=Adaptive IDS/OU=Alerting Service/CN=alerting-service"

openssl x509 -req -days $VALIDITY_DAYS \
  -sha256 \
  -in alerting-service-client.csr \
  -CA ca-cert.pem \
  -CAkey ca-key.pem \
  -CAcreateserial \
  -out alerting-service-client-cert.pem

rm alerting-service-client.csr
echo "   ✓ Alerting service client certificate created: alerting-service-client-cert.pem"

# 5. Generate frontend client certificate (optional)
echo "5. Generating Frontend client certificate..."
openssl genrsa -out frontend-client-key.pem 4096

openssl req -new -key frontend-client-key.pem \
  -out frontend-client.csr \
  -subj "/C=US/ST=State/L=City/O=Adaptive IDS/OU=Frontend/CN=frontend"

openssl x509 -req -days $VALIDITY_DAYS \
  -sha256 \
  -in frontend-client.csr \
  -CA ca-cert.pem \
  -CAkey ca-key.pem \
  -CAcreateserial \
  -out frontend-client-cert.pem

rm frontend-client.csr
echo "   ✓ Frontend client certificate created: frontend-client-cert.pem"

# 6. Set secure permissions
echo "6. Setting secure permissions..."
chmod 600 *.pem
chmod 644 ca-cert.pem *-cert.pem

echo ""
echo "✓ Certificate generation complete!"
echo ""
echo "Generated certificates:"
echo "  - CA: ca-cert.pem, ca-key.pem"
echo "  - Backend API: backend-server-cert.pem, backend-server-key.pem"
echo "  - Model Service: model-service-server-cert.pem, model-service-server-key.pem"
echo "  - Alerting Service: alerting-service-client-cert.pem, alerting-service-client-key.pem"
echo "  - Frontend: frontend-client-cert.pem, frontend-client-key.pem"
echo ""
echo "Next steps:"
echo "  1. Update docker-compose.yml to mount certificates"
echo "  2. Configure services to use mTLS"
echo "  3. Update .env with certificate paths"
echo ""
