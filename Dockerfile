# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файлы проекта
COPY config.yml .
COPY main.py .
COPY code ./code

# Устанавливаем зависимости, если есть requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Указываем команду для запуска скрипта
CMD ["python", "main.py"]