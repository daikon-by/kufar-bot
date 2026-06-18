#!/usr/bin/env bash
# Быстрое обновление на сервере: pull образа + пересоздание контейнера.
#
# Использование:
#   ./scripts/update.sh              # latest из .env (KUFAR_BOT_IMAGE)
#   ./scripts/update.sh v0.1.0       # конкретный тег
#   ./scripts/update.sh abc1234      # конкретный git sha из GHCR
#
# Режим без образа (git на сервере):
#   unset KUFAR_BOT_IMAGE && ./scripts/update.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/lib.sh"

ROOT="$(project_root)"
cd "$ROOT"
load_dotenv "$ROOT"

TAG="${1:-latest}"
COMPOSE_FILE="${COMPOSE_FILE:-$(prod_compose_file "$ROOT")}"

if [[ -n "${KUFAR_BOT_IMAGE:-}" && "$TAG" != "latest" ]]; then
  export KUFAR_BOT_IMAGE="${KUFAR_BOT_IMAGE%:*}:${TAG}"
fi

if [[ -n "$COMPOSE_FILE" && -n "${KUFAR_BOT_IMAGE:-}" ]]; then
  echo "==> Обновление из образа: ${KUFAR_BOT_IMAGE}"
  compose_cmd -f "$COMPOSE_FILE" pull kufar-bot
  compose_cmd -f "$COMPOSE_FILE" up -d --force-recreate --remove-orphans
else
  echo "==> Обновление из git + локальная сборка"
  git_pull_if_repo "$ROOT"
  compose_cmd -f docker-compose.yml up -d --build --force-recreate --remove-orphans
fi

echo ""
compose_cmd -f "${COMPOSE_FILE:-docker-compose.yml}" ps
echo ""
echo "Готово. Логи: compose logs -f kufar-bot"
