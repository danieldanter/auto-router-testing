# Autonomous Mode Router - API Backend

FastAPI Backend für intelligentes Query-Routing in CompanyGPT.
Nutzt Google Vertex AI (Gemini) für LLM-basierte Entscheidungen.

## Modi

| Mode | Name (DE) | Beschreibung |
|------|-----------|--------------|
| `BASIC` | Chat Modus | Normaler Chat ODER Chat mit Datei im Context |
| `QA` | Abfragemodus | Vector Search (Datei zu groß für Context) |
| `SEARCH` | Websuche | Aktuelle Infos aus dem Internet |

## Projekt-Struktur

```
autonomous-mode/
├── main.py                    # FastAPI Application
├── requirements.txt           # Python Dependencies
├── .env                       # Environment Variables
├── docker/
│   ├── Dockerfile            # Docker Image Definition
│   ├── docker-compose.yml    # Docker Compose Config
│   └── run-docker.sh         # Quick-Start Script
└── src/
    ├── config/
    │   └── config.py         # Secrets Service Integration
    ├── models/
    │   └── api_schemas.py    # Pydantic Models
    └── services/
        ├── gemini_service.py # Vertex AI / Gemini LLM
        └── mode_detector.py  # Mode Detection Logic
```

## Setup

### Lokale Entwicklung

```bash
# Virtual Environment erstellen und aktivieren
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Dependencies installieren
pip install -r requirements.txt

# Server starten
python main.py
```

### Docker

```bash
# Mit Docker Compose (empfohlen)
cd docker
docker-compose up --build

# Oder manuell
docker build -t 506/query-router:dev -f docker/Dockerfile .
docker run -p 8000:8000 --env-file .env 506/query-router:dev
```

## Konfiguration

### Environment Variables (.env)

```env
# Gemini Model
GEMINI_MODEL=gemini-2.5-flash

# Secrets Service (Production)
SECRETS_SERVICE_PATH=https://your-secrets-service.example.com
CUSTOMER=your_customer_name
SECRETS_SERVICE_API_KEY=your_api_key_here
```

### Secrets Service

Die Google Vertex AI Credentials werden vom Secrets Service geladen:

```json
{
  "vectorService": {
    "googleVertexFileKey": {
      "private_key": "-----BEGIN PRIVATE KEY-----\n..."
    }
  }
}
```

### Test-Modus

Für lokale Entwicklung ohne Secrets Service:

```python
# In src/config/config.py
USE_TEST_CONFIG = True   # Nutzt hardcoded Test-Credentials
USE_TEST_CONFIG = False  # Lädt vom Secrets Service (Production)
```

## API Endpoints

### Health Check

```bash
GET /health
```

### Mode Detection

```bash
POST /api/qr/detect-mode
```

**Request:**
```json
{
  "query": "Fasse das Buch zusammen",
  "tokenLimit": 980000,
  "selectedFiles": [
    { "id": "file-1", "name": "Buch.pdf", "tokenSize": 50000 }
  ]
}
```

**Response:**
```json
{
  "mode": "BASIC",
  "confidence": 0.90,
  "reason": "Lade gesamtes Dokument"
}
```

## Entscheidungslogik (Flowchart)

```
┌─────────────────────────────────────┐
│           USER REQUEST              │
└─────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│   Files/Folders ausgewählt?         │
└─────────────────────────────────────┘
        │ JA                    │ NEIN
        ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│ Tokens > 70%    │    │   LLM Decision   │
│ vom Limit?      │    │  SEARCH vs BASIC │
└─────────────────┘    └──────────────────┘
  │ JA      │ NEIN           │        │
  ▼         ▼             SEARCH    BASIC
┌─────┐  ┌───────────┐
│ QA  │  │ LLM       │
│     │  │ QA vs     │
│     │  │ BASIC     │
└─────┘  └───────────┘
              │    │
             QA  BASIC
```

## API Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

## Testing

```bash
# Health Check
curl http://localhost:8000/health

# Mit Datei (QA oder BASIC)
curl -X POST http://localhost:8000/api/qr/detect-mode \
  -H "Content-Type: application/json" \
  -d '{"query": "Fasse das Buch zusammen", "selectedFiles": [{"id": "1", "name": "Buch.pdf", "tokenSize": 50000}]}'

# Ohne Datei (SEARCH oder BASIC)
curl -X POST http://localhost:8000/api/qr/detect-mode \
  -H "Content-Type: application/json" \
  -d '{"query": "Wie ist das Wetter heute?"}'
```

## Technologie

- **Framework:** FastAPI + Uvicorn
- **LLM:** Google Vertex AI (Gemini 2.5 Flash)
- **Auth:** Service Account via Secrets Service
- **Container:** Docker + Docker Compose
