FROM mcr.microsoft.com/devcontainers/anaconda:1-3

# Set working directory
WORKDIR /app

# Install pip dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project files
COPY . .

# Запускаем сервер
CMD ["python", "servermain/app.py"]