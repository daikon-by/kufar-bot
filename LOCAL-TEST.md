# Локальный тест (Linux / dev-ПК)

## Запуск

```bash
cd /mnt/disk_d/kufar-bot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # BOT_TOKEN, ADMIN_IDS
.venv/bin/python -m kufar_bot.main
```

## Остановка

`Ctrl+C` или:

```bash
pkill -f 'kufar_bot.main'
```

**На сервере Windows** бот тоже нужно остановить — один `BOT_TOKEN` = один экземпляр.

## Копирование на Windows-сервер (без .venv)

Копировать:

```
src/
pyproject.toml
run-bot.cmd
install-windows.ps1
register-task.ps1
.env          # свой, не из git
data/         # база kufar_bot.db
```

**Не копировать:** `.venv/` (создать на Windows: `python -m venv .venv` + `pip install -e .`)

## Проверка дедупликации

1. Первый «Опросить» — много объявлений (первый раз за 24 ч).
2. Второй «Опросить» — в отчёте **видели: много**, **отправлено: мало** (только новые).
3. «⏹ Остановить опрос» — рассылка прекращается в течение ~1 с (не ждёт flood-таймер).
