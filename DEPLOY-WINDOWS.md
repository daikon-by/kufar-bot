# Запуск на Windows Server без Docker/Podman

Бот работает из папки, автозапуск — через **Планировщик заданий**.

## Быстрый старт (один скрипт)

Нужны только **Git** и **Python** уже в PATH.

```cmd
setup-windows.cmd
```

Скрипт: `git clone` → `.venv` → `pip install -e .` → запуск бота.

Другая папка: `setup-windows.cmd D:\bots\kufar-bot`

## Логи (для отладки)

| Файл | Что внутри |
|------|------------|
| `data\setup.log` | установка, git, pip |
| `data\console.log` | вывод консоли, traceback |
| `data\kufar_bot.log` | события бота |

Собрать всё в один файл:

```cmd
collect-logs.cmd
```

→ `data\support-bundle.txt` — его и скидывай.

## Шаг 1 — скачать проект

```powershell
cd C:\
git clone https://github.com/daikon-by/kufar-bot.git
cd kufar-bot
```

Или скопируйте папку проекта вручную, например `C:\kufar-bot`.

## Шаг 2 — установить Python

1. https://www.python.org/downloads/ — Python **3.11** или **3.12**
2. При установке: **Add python.exe to PATH**
3. Проверка:

```powershell
python --version
```

## Шаг 3 — установить бота

PowerShell в папке проекта:

```powershell
cd C:\kufar-bot
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install-windows.ps1
```

## Шаг 4 — настроить .env

```powershell
notepad .env
```

Заполнить:

```env
BOT_TOKEN=токен_от_BotFather
ADMIN_IDS=ваш_telegram_id
ADMIN_USERNAME=ваш_username
```

`KUFAR_BOT_IMAGE` для Windows **не нужен** — это только для Docker.

## Шаг 5 — проверить вручную

```powershell
.\run-bot.cmd
```

Если ошибка `No module named 'PIL'` — venv старый, обновите зависимости:

```powershell
.\.venv\Scripts\pip.exe install -e .
```

В Telegram бот должен ответить. Остановка: `Ctrl+C`.

Логи: `data\kufar_bot.log`

## Шаг 6 — автозапуск через Планировщик

PowerShell **от администратора**:

```powershell
cd C:\kufar-bot
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\register-task.ps1
```

Запустить сразу:

```powershell
Start-ScheduledTask -TaskName KufarBot
```

## Управление

| Действие | Команда |
|----------|---------|
| Запустить | `Start-ScheduledTask -TaskName KufarBot` |
| Остановить | `Stop-ScheduledTask -TaskName KufarBot` |
| Статус | `Get-ScheduledTask -TaskName KufarBot` |
| Логи | `notepad data\kufar_bot.log` |

Или: `taskschd.msc` → задача **KufarBot**.

## Обновление

```powershell
cd C:\kufar-bot
.\update-windows.ps1
```

Останавливает бота, `git pull`, обновляет пакет, снова запускает.

## Важно

- Один `BOT_TOKEN` — один запущенный экземпляр. Не держите бота одновременно на ПК и сервере.
- Папка `data\` — база и настройки, делайте бэкап.
- Если задача не стартует: Планировщик → KufarBot → вкладка **Журнал** / **History**.

## Ручная настройка Планировщика (без скрипта)

1. `Win+R` → `taskschd.msc`
2. **Создать задачу...**
3. Имя: `KufarBot`
4. Триггер: **При запуске компьютера**
5. Действие: **Запуск программы**
   - Программа: `C:\kufar-bot\run-bot.cmd`
   - Рабочая папка: `C:\kufar-bot`
6. Параметры: перезапуск при сбое, без лимита времени
7. OK
