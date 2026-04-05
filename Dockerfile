FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpoppler-cpp-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e installa
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice
COPY . .

# Crea directory per i file temporanei
RUN mkdir -p /tmp/uploads

# Esponi la porta
EXPOSE 5000

# Comando di avvio
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
