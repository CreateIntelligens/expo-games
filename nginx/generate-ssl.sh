#!/bin/sh

SSL_DIR="/etc/nginx/ssl"
CERT_FILE="$SSL_DIR/cert.pem"
KEY_FILE="$SSL_DIR/key.pem"

echo "🔐 Checking SSL certificates..."

if [ ! -d "$SSL_DIR" ]; then
    echo "📁 Creating SSL directory: $SSL_DIR"
    mkdir -p "$SSL_DIR"
fi

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    if openssl x509 -checkend 2592000 -noout -in "$CERT_FILE" >/dev/null 2>&1; then
        echo "✅ SSL certificate exists and is valid for at least 30 days"
        exit 0
    else
        echo "⚠️  SSL certificate exists but expires soon, regenerating..."
    fi
else
    echo "🔨 SSL certificate not found, generating new one..."
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "📦 Installing openssl..."
    apk add --no-cache openssl
fi

echo "🔧 Generating self-signed SSL certificate..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/C=TW/ST=Taiwan/L=Taipei/O=ExpoGames/OU=Development/CN=localhost/emailAddress=dev@localhost" \
    2>/dev/null

if [ $? -eq 0 ]; then
    chmod 644 "$CERT_FILE"
    chmod 600 "$KEY_FILE"

    echo "✅ SSL certificate generated successfully!"
    echo "📄 Certificate: $CERT_FILE"
    echo "🔑 Private key: $KEY_FILE"

    echo "📋 Certificate details:"
    openssl x509 -in "$CERT_FILE" -text -noout | grep -E "(Subject:|Not After)" | sed 's/^[[:space:]]*/  /'
else
    echo "❌ Failed to generate SSL certificate"
    exit 1
fi
