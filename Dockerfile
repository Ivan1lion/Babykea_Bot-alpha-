# 1. Используем легкий образ Python 3.11 (как у тебя в кеше)
FROM python:3.11-slim

# 2. Отключаем создание .pyc файлов и буферизацию вывода (чтобы логи шли сразу)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# 4. Устанавливаем системные зависимости (нужны для сборки psycopg2, если вдруг понадобится, и других либ)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Копируем ВЕСЬ код проекта в контейнер
COPY . .

# 7. Команда запуска (она будет переопределена в docker-compose, но оставим как default)
CMD ["python", "-m", "app.main"]