# Базовый образ — Python 3.11
FROM python:3.11-slim

# Устанавливаем curl для healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Рабочая директория внутри контейнера
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Порт который будет открыт
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
