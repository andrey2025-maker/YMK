# Многоступенчатая сборка для уменьшения размера
FROM python:3.11-slim as builder

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Финальный образ
FROM python:3.11-slim

# Устанавливаем системные зависимости для runtime
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем виртуальное окружение из builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 -s /bin/bash botuser
USER botuser

# Создаем рабочий каталог
WORKDIR /app

# Копируем исходный код
COPY --chown=botuser:botuser . .

# Создаем необходимые директории
RUN mkdir -p /app/assets/uploads \
    /app/assets/archives \
    /app/assets/exports \
    /app/assets/temp \
    /app/assets/logs \
    /app/storage/migrations/versions

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Запускаем бота
CMD ["python", "main.py"]