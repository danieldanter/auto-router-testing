"""FastAPI Backend for Autonomous Mode Router."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.models.api_schemas import DetectModeRequest, DetectModeResponse
from src.services.mode_detector import get_mode_detector

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting Autonomous Mode Router API...")

    # Initialize the mode detector on startup
    detector = get_mode_detector()
    logger.info("Mode detector initialized")

    # Pre-initialize Gemini service (so first request is fast)
    logger.info("Pre-initializing Gemini LLM service...")
    detector._get_gemini_service()
    logger.info("Gemini service ready")

    yield
    logger.info("Shutting down Autonomous Mode Router API...")


# Create FastAPI app
app = FastAPI(
    title="Autonomous Mode Router API",
    description="Intelligent query routing for CompanyGPT - detects BASIC, QA, or WEB mode",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for Chrome Extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Autonomous Mode Router",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check for load balancers."""
    return {"status": "healthy"}


@app.post("/api/qr/detect-mode", response_model=DetectModeResponse)
async def detect_mode(request: DetectModeRequest) -> DetectModeResponse:
    """
    Detect the appropriate mode for a query using Gemini LLM.

    Returns:
    - **BASIC**: Normal chat or full document summary
    - **QA**: RAG/Vector Search for specific questions
    - **SEARCH**: Web search for current information

    Decision Logic:
    1. If File/Folder selected → NEVER SEARCH
       - Tokens > 70% threshold → Always QA (Vector Search)
       - Tokens fit → LLM decides QA vs BASIC
    2. If no selection → LLM decides SEARCH vs BASIC
    """
    try:
        detector = get_mode_detector()
        response = detector.detect(request)

        logger.info(f"Mode detected: {response.mode} (confidence: {response.confidence})")
        return response

    except Exception as e:
        logger.error(f"Error detecting mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
