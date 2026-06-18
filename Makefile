.PHONY: test build update remote-update release

test:
	pytest -q

build:
	podman build -t kufar-bot:local .

# На сервере (в каталоге проекта)
update:
	./scripts/update.sh

# С вашего ПК: push уже сделан, накатить на сервер
remote-update:
	./scripts/remote-update.sh

# Локально: тесты + push в GitHub (CI соберёт образ)
release:
	pytest -q
	git push origin main
	@echo "Дождитесь зелёной галочки в GitHub Actions, затем:"
	@echo "  make remote-update SERVER=user@host"
