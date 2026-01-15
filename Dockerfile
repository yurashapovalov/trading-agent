# Базовый образ — Python 3.11
FROM python:3.11-slim

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
