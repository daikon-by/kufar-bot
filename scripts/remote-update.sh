#!/usr/bin/env bash
# Обновление на удалённом сервере одной командой с вашего ПК.
#
# Пример:
#   SERVER=andrey@192.168.1.10 REMOTE_DIR=/opt/kufar-bot ./scripts/remote-update.sh
#   SERVER=andrey@192.168.1.10 ./scripts/remote-update.sh v0.1.0
set -euo pipefail

SERVER="${SERVER:?Укажите SERVER=user@host}"
REMOTE_DIR="${REMOTE_DIR:-/opt/kufar-bot}"
TAG="${1:-latest}"

ssh -t "$SERVER" "cd '$REMOTE_DIR' && ./scripts/update.sh '$TAG'"
