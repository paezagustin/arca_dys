FROM python:3.11-slim

# Dependencias del sistema necesarias para M2Crypto
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    swig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates
CMD ["python", "app.py"]
