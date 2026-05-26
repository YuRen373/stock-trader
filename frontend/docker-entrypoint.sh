#!/bin/sh
# Ensure BACKEND_URL has http:// prefix
case "$BACKEND_URL" in
  http://*|https://*) ;;
  *) BACKEND_URL="http://${BACKEND_URL}" ;;
esac
export BACKEND_URL
envsubst '${PORT} ${BACKEND_URL}' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf
echo "Nginx config: PORT=$PORT BACKEND_URL=$BACKEND_URL"
cat /etc/nginx/conf.d/default.conf
exec "$@"
