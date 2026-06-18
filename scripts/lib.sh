#!/usr/bin/env bash
# Общие функции для install.sh и update.sh
set -euo pipefail

script_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

project_root() {
  cd "$(script_dir)/.." && pwd
}

compose_cmd() {
  if command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    podman compose "$@"
  elif command -v docker >/dev/null 2>&1; then
    docker compose "$@"
  else
    echo "Не найден podman compose или docker compose" >&2
    exit 1
  fi
}

load_dotenv() {
  local root="$1"
  if [[ -f "$root/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$root/.env"
    set +a
  fi
}

prod_compose_file() {
  local root="$1"
  if [[ -f "$root/docker-compose.prod.yml" ]]; then
    echo "$root/docker-compose.prod.yml"
  else
    echo ""
  fi
}

git_pull_if_repo() {
  local root="$1"
  if [[ -d "$root/.git" ]]; then
    git -C "$root" pull --ff-only
  fi
}
