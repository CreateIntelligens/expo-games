#!/bin/sh
set -e

APP_PORT=${APP_PORT:-8896}
EXTERNAL_PORT=${EXTERNAL_PORT:-8896}

/bin/sh /docker-entrypoint.d/01-generate-ssl.sh

echo "🔧 Configuring Nginx with APP_PORT=$APP_PORT and EXTERNAL_PORT=$EXTERNAL_PORT"

envsubst '${APP_PORT} ${EXTERNAL_PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

echo "✅ Nginx configuration generated"

exec nginx -g 'daemon off;'
