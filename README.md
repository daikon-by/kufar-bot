# Kufar Bot

Telegram-бот для мониторинга объявлений [Kufar.by](https://www.kufar.by): группы поиска по разделам/регионам, минус-фразы, избранное с отслеживанием цены, расписание опросов.

## Быстрый старт

```bash
cp .env.example .env   # заполнить BOT_TOKEN, ADMIN_IDS, ADMIN_USERNAME
docker compose up -d --build
# или Podman:
podman compose up -d --build
```

Подробный деплой на сервер: [DEPLOY.md](DEPLOY.md).

## Быстрое обновление на сервере

```bash
# 1. На ПК: пушим код → GitHub Actions собирает образ
git push origin main

# 2. На сервере (или с ПК одной командой):
./scripts/update.sh
# с ПК:
SERVER=user@host ./scripts/remote-update.sh
```

Конкретная версия: `./scripts/update.sh v0.1.0` или `./scripts/update.sh <git-sha>`.

Локально:

```bash
python -m venv .venv
# bash/zsh:
source .venv/bin/activate && pip install -e ".[dev]" && kufar-bot
# fish:
source .venv/bin/activate.fish; pip install -e ".[dev]"; kufar-bot
# без активации venv (любой shell):
.venv/bin/pip install -e ".[dev]"
.venv/bin/kufar-bot
```

## Команды бота

- **Группы** — несколько ссылок Kufar в одной группе (раздел + регион)
- **Минус-слова** — глобальные и по группе; кнопки под каждым объявлением
- **Расписание** — дни недели + времена (Europe/Minsk)
- **Избранное** — проверка цены при каждом опросе
- **Админ:** `/allow <id> [дней]`, `/revoke <id>`, `/users`
