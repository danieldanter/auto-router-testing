# ============================================
# Query Router Service - Dockerfile
# FastAPI + Vertex AI (Gemini)
# ============================================

FROM python:3.11-slim

# System-Pakete installieren
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis setzen
WORKDIR /app

# Dependencies zuerst kopieren (für besseres Caching)
COPY requirements.txt .

# Python-Dependencies installieren
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode kopieren
COPY . .

# Port freigeben
EXPOSE 8000

# Health-Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# FastAPI mit uvicorn starten
# --host 0.0.0.0 : Auf allen Interfaces lauschen
# --port 8000    : Port 8000
# --workers 2    : 2 Worker-Prozesse
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
