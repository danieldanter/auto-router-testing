"""
Gemini LLM Service for intelligent query analysis and mode detection.
Uses Google Vertex AI for Gemini models.
"""
import os
import logging
from typing import Optional

from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

from dotenv import load_dotenv
from src.config import config

load_dotenv()
logger = logging.getLogger(__name__)

# Vertex AI Configuration (hardcoded, same as Vector Service)
PROJECT_ID = "silicon-cocoa-428908-k8"
LOCATION = "europe-west4"

# System prompt when files are selected (QA vs BASIC decision only)
FILES_PROMPT = """Du bist ein Query-Analyzer für ein RAG-System. Analysiere die Benutzeranfrage und entscheide welcher Modus verwendet werden soll.

KONTEXT:
- Der Benutzer hat Dokumente/Dateien ausgewählt: JA
- Ausgewählte Dateien/Ordner: {selection_info}

MODI:
1. **QA** (RAG/Vector Search): Für spezifische Fragen die aus Dokumenten beantwortet werden können
   - "Was steht in dem Dokument über X?"
   - "Finde Informationen zu Y"
   - "Welche Daten gibt es zu Z?"
   - "Was sagt das Dokument zu...?"
   - Allgemeine Fragen über Dokument-Inhalte

2. **BASIC** (Chat mit Dokument im Context): NUR für Fragen die das GESAMTE Dokument benötigen
   - "Fasse das Dokument zusammen"
   - "Was sind die Hauptthemen?"
   - "Erkläre den Zusammenhang zwischen allen Kapiteln"
   - "Gib mir einen Überblick über das ganze Dokument"

WICHTIGE REGELN:
- Bevorzuge QA (RAG ist effizienter)
- BASIC nur wenn explizit das GESAMTE Dokument gebraucht wird (Summary, Überblick)
- Im Zweifel → QA

BENUTZERANFRAGE: "{query}"

Antwort NUR als JSON. Wähle für "reason" EXAKT eine dieser Optionen:
- QA: "Durchsuche Dokument mit RAG" oder "Verwende Vector Search für Frage" 
- BASIC: "Lade gesamtes Dokument" oder "Analysiere das gesamte Dokument"

{{"mode": "QA oder BASIC", "reason": "EXAKT eine der obigen Optionen"}}
"""

# Simpler prompt when no files selected
NO_FILES_PROMPT = """Du bist ein Query-Analyzer. Analysiere ob die Anfrage eine Web-Suche benötigt.

MODI:
1. **SEARCH** (Web-Suche): Für aktuelle Informationen aus dem Internet
   - Wetter, Nachrichten, Aktienkurse
   - "Suche im Internet nach..."
   - Aktuelle Events, Preise, Öffnungszeiten
   - Alles was aktuelle/externe Daten braucht

2. **BASIC** (Normaler Chat): Für alles andere
   - Allgemeine Fragen, Erklärungen
   - Kreative Aufgaben (Texte schreiben, Code)
   - Wissen das kein Internet braucht

BENUTZERANFRAGE: "{query}"

Antwort NUR als JSON. Wähle für "reason" EXAKT eine dieser Optionen:
- SEARCH: "Suche im Web" oder "Hole aktuelle Daten"
- BASIC: "Beantworte direkt" oder "Verarbeite Anfrage"

{{"mode": "SEARCH oder BASIC", "reason": "EXAKT eine der obigen Optionen"}}
"""


class GeminiService:
    """Service for Gemini LLM-based query analysis."""

    def __init__(self):
        """Initialize the Gemini service."""
        self.model = None
        self.available = False
        self._initialize()

    def _initialize(self):
        """Initialize the Gemini client via Vertex AI."""
        try:
            # Get credentials from Secrets Service
            credentials_dict = config.get_google_vertex_credentials()

            if not credentials_dict:
                logger.warning("No Google Vertex credentials found in Secrets Service")
                self.available = False
                return

            # Load service account credentials from dict
            logger.info("Loading credentials from Secrets Service")
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            # Initialize Vertex AI
            vertexai.init(
                project=PROJECT_ID,
                location=LOCATION,
                credentials=credentials
            )

            # Initialize the model
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            self.model = GenerativeModel(model_name)

            self.available = True
            logger.info(f"Gemini service initialized with model: {model_name} (Vertex AI)")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {e}")
            self.available = False

    def analyze_query(
        self,
        query: str,
        has_files: bool,
        selection_info: str = ""
    ) -> dict:
        """
        Analyze a query and determine the appropriate mode.

        Args:
            query: The user's query
            has_files: Whether files/folders are selected
            selection_info: Description of selected files/folders

        Returns:
            dict with 'mode' and 'reason'
        """
        if not self.available or not self.model:
            logger.warning("Gemini service not available, using fallback")
            return self._fallback_analysis(has_files)

        try:
            # Choose prompt based on context
            if has_files:
                prompt = FILES_PROMPT.format(
                    selection_info=selection_info or "Dateien/Ordner ausgewählt",
                    query=query
                )
            else:
                prompt = NO_FILES_PROMPT.format(query=query)

            # Call Gemini via Vertex AI
            logger.info(f"Calling Gemini API with prompt length: {len(prompt)}")
            response = self.model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent results
                    max_output_tokens=500,
                )
            )
            logger.info("Gemini API call completed")

            # Parse response
            result_text = response.text.strip()
            logger.info(f"Gemini response: {result_text}")

            # Extract JSON from response (handle markdown code blocks)
            import json
            import re

            # Remove markdown code blocks if present
            clean_text = re.sub(r'```json\s*', '', result_text)
            clean_text = re.sub(r'```\s*', '', clean_text)
            clean_text = clean_text.strip()

            # Try to parse complete JSON first
            json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    mode = result.get("mode", "BASIC").upper()
                    reason = result.get("reason", "LLM-Analyse")
                except json.JSONDecodeError:
                    # JSON incomplete - extract mode manually
                    mode_match = re.search(r'"mode":\s*"(QA|BASIC|SEARCH)"', clean_text, re.IGNORECASE)
                    reason_match = re.search(r'"reason":\s*"([^"]*)', clean_text)

                    if mode_match:
                        mode = mode_match.group(1).upper()
                        reason = reason_match.group(1) if reason_match else "LLM-Analyse"
                    else:
                        return self._fallback_analysis(has_files)
            else:
                # No JSON brackets - try to extract mode directly
                mode_match = re.search(r'"mode":\s*"(QA|BASIC|SEARCH)"', clean_text, re.IGNORECASE)
                reason_match = re.search(r'"reason":\s*"([^"]*)', clean_text)

                if mode_match:
                    mode = mode_match.group(1).upper()
                    reason = reason_match.group(1) if reason_match else "LLM-Analyse"
                else:
                    logger.warning(f"Could not parse Gemini response: {result_text}")
                    return self._fallback_analysis(has_files)

            # Validate mode
            if mode not in ["QA", "BASIC", "SEARCH"]:
                mode = "QA" if has_files else "BASIC"

            # Enforce rule: no SEARCH with files
            if has_files and mode == "SEARCH":
                mode = "QA"
                reason = "Web-Suche nicht möglich mit Dateien - verwende RAG"

            return {"mode": mode, "reason": reason}

        except Exception as e:
            logger.error(f"Gemini analysis error: {e}")
            return self._fallback_analysis(has_files)

    def _fallback_analysis(self, has_files: bool) -> dict:
        """Fallback when Gemini is not available."""
        if has_files:
            return {"mode": "QA", "reason": "Fallback: Dateien ausgewählt → RAG"}
        else:
            return {"mode": "BASIC", "reason": "Fallback: Normaler Chat"}

    def is_available(self) -> bool:
        """Check if Gemini service is available."""
        return self.available


# Singleton instance
_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get or create the Gemini service singleton."""
    global _service
    if _service is None:
        _service = GeminiService()
    return _service
