#!/bin/sh
# Garante que o volume de dados pertence ao usuário sem privilégios e então abandona o root.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$(dirname "$DATABASE_PATH")"
  chown -R prumo "$(dirname "$DATABASE_PATH")"
  exec setpriv --reuid=prumo --regid=prumo --init-groups "$@"
fi
exec "$@"
