#!/bin/bash
# Генерируем миграцию
uv run alembic revision --autogenerate -m "migration-$(uuidgen)" || echo "Failed to generate migration"
# Применяем миграцию
uv run alembic upgrade head || echo "Failed to apply migrations"
# Запускаем приложение
uv run -m src.main
