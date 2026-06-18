#!/usr/bin/env bash
# Первичная установка на сервере.
# Пример: ./scripts/install.sh dankovvv
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$(dirname "$0")/lib.sh"

GITHUB_USER="${1:-}"
INSTALL_DIR="${INSTALL_DIR:-$ROOT}"
REPO="${GITHUB_REPO:-${GITHUB_USER:+${GITHUB_USER}/}kufar-bot}"

usage() {
  cat <<'EOF'
Установка kufar-bot на сервер.

Использование:
  ./scripts/install.sh <github_user>          # из уже склонированного репо
  GITHUB_USER=dankovvv ./scripts/install.sh   # то же через переменную

После установки отредактируйте .env и запустите:
  ./scripts/update.sh
EOF
}

if [[ -z "$GITHUB_USER" && -z "${GITHUB_REPO:-}" ]]; then
  usage
  exit 1
fi

cd "$INSTALL_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  if [[ -n "$GITHUB_USER" ]]; then
    sed -i "s|ghcr.io/YOUR_GITHUB_USER/kufar-bot:latest|ghcr.io/${GITHUB_USER}/kufar-bot:latest|" .env
  fi
  echo "Создан .env — заполните BOT_TOKEN и ADMIN_IDS"
fi

mkdir -p data

echo "Готово. Проверьте .env и выполните: ./scripts/update.sh"
