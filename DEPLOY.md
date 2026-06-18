# Деплой на сервер (Podman / Podman Desktop)

## Что понадобится

- Сервер Linux с Podman (или Podman Desktop с подключением к удалённому серверу)
- Репозиторий на GitHub: `https://github.com/<user>/kufar-bot`
- Токен Telegram-бота (`BOT_TOKEN`)
- Ваш Telegram ID в `ADMIN_IDS`

---

## 1. Залить код на GitHub (один раз, с вашего ПК)

```bash
cd /path/to/kufar-bot
git init
git add .
git commit -m "Initial commit: Kufar Telegram bot"
git branch -M main
git remote add origin https://github.com/<user>/kufar-bot.git
git push -u origin main
```

Создайте пустой репозиторий на GitHub заранее (без README).

После push GitHub Actions соберёт образ и опубликует его в **GitHub Container Registry**:

`ghcr.io/<user>/kufar-bot:latest`

Проверка: вкладка **Actions** → workflow **Docker image** → зелёная галочка.  
Образ: **Packages** на GitHub или `ghcr.io/<user>/kufar-bot`.

Если образ приватный — на сервере нужен Personal Access Token с правом `read:packages`.

---

## 2. Подготовка сервера

```bash
sudo mkdir -p /opt/kufar-bot/data
sudo chown -R $USER:$USER /opt/kufar-bot
cd /opt/kufar-bot
```

Скопируйте конфиг:

```bash
curl -fsSL -o .env.example https://raw.githubusercontent.com/<user>/kufar-bot/main/.env.example
cp .env.example .env
nano .env
```

Обязательно заполните:

```env
BOT_TOKEN=123456:ABC...
ADMIN_IDS=ваш_telegram_id
ADMIN_USERNAME=ваш_username
```

Остальное можно оставить по умолчанию. База и логи лежат в `./data`.

---

## 3. Запуск через Podman Compose

### Вариант A — собрать на сервере из исходников

```bash
git clone https://github.com/<user>/kufar-bot.git /opt/kufar-bot
cd /opt/kufar-bot
cp .env.example .env && nano .env
mkdir -p data

podman compose up -d --build
```

### Вариант B — готовый образ с GitHub (быстрее)

```bash
cd /opt/kufar-bot
# только .env и data, без клонирования всего репо:
curl -fsSL -o docker-compose.prod.yml \
  https://raw.githubusercontent.com/<user>/kufar-bot/main/docker-compose.prod.yml
sed -i 's/YOUR_GITHUB_USER/<user>/' docker-compose.prod.yml

# если образ приватный:
# echo "YOUR_GITHUB_PAT" | podman login ghcr.io -u <user> --password-stdin

podman compose -f docker-compose.prod.yml pull
podman compose -f docker-compose.prod.yml up -d
```

---

## 4. Podman Desktop (с вашего компьютера)

1. Установите [Podman Desktop](https://podman-desktop.io/).
2. Подключите удалённый Podman machine / SSH к серверу (Settings → Resources).
3. Склонируйте репозиторий локально или откройте папку проекта.
4. Создайте `.env` из `.env.example`.
5. В терминале Podman Desktop или встроенном терминале:

```bash
podman compose up -d --build
```

Либо: **Containers** → **Create** → импорт `docker-compose.yml`.

---

## 5. Полезные команды

```bash
# логи
podman compose logs -f kufar-bot

# статус
podman compose ps

# перезапуск после смены .env
podman compose up -d --force-recreate

# обновление (вариант B)
podman compose -f docker-compose.prod.yml pull
podman compose -f docker-compose.prod.yml up -d

# остановка
podman compose down
```

Логи в файле: `./data/kufar_bot.log`  
База SQLite: `./data/kufar_bot.db`

---

## 6. Автозапуск после перезагрузки (systemd)

```bash
podman generate systemd --name kufar-bot --files --new
mkdir -p ~/.config/systemd/user
mv container-kufar-bot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now container-kufar-bot.service
loginctl enable-linger $USER
```

---

## 7. Миграция с локального бота

Если уже есть `data/kufar_bot.db` и настройки:

```bash
scp -r ./data user@server:/opt/kufar-bot/
```

На сервере перезапустите контейнер — группы, расписание и избранное сохранятся.
