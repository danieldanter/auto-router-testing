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
- Ausgewählt: {selection_type}
- Details: {selection_info}

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

Antwort NUR als JSON:
- "mode": "QA" oder "BASIC"
- "reason": Kurze Aktionsbeschreibung (max 8 Wörter). Nutze "{target_word}" statt "Dokument" wenn passend.

Beispiele (mit Ordner):
- QA + "Wer ist der Autor?" → "Suche nach dem Autor im Ordner"
- BASIC + "Fasse zusammen" → "Erstelle Zusammenfassung des Ordners"

Beispiele (mit Datei):
- QA + "Was steht über KI?" → "Durchsuche Datei nach KI-Informationen"
- BASIC + "Überblick geben" → "Analysiere gesamte Datei"

{{"mode": "QA oder BASIC", "reason": "kontextbezogene Aktionsbeschreibung"}}
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

Antwort NUR als JSON:
- "mode": "SEARCH" oder "BASIC"
- "reason": Eine kurze, kontextbezogene Aktionsbeschreibung (max 8 Wörter) die sich auf die Anfrage bezieht

Beispiele für gute "reason" Antworten:
- SEARCH + "Wie ist das Wetter?" → "Suche aktuelle Wetterdaten"
- SEARCH + "News über Tesla" → "Suche aktuelle Tesla-Nachrichten"
- BASIC + "Erkläre Photosynthese" → "Erkläre den Prozess der Photosynthese"
- BASIC + "Schreibe ein Gedicht" → "Verfasse ein kreatives Gedicht"

{{"mode": "SEARCH oder BASIC", "reason": "kontextbezogene Aktionsbeschreibung"}}
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
        selection_info: str = "",
        selection_type: str = ""
    ) -> dict:
        """
        Analyze a query and determine the appropriate mode.

        Args:
            query: The user's query
            has_files: Whether files/folders are selected
            selection_info: Description of selected files/folders
            selection_type: Type of selection ("Ordner", "Datei", "Dateien")

        Returns:
            dict with 'mode' and 'reason'
        """
        if not self.available or not self.model:
            logger.warning("Gemini service not available, using fallback")
            return self._fallback_analysis(has_files)

        try:
            # Choose prompt based on context
            if has_files:
                # Determine target word for reason
                target_word = "Ordner" if "Datenspeicher" in selection_info or "Ordner" in selection_type else "Datei"
                if selection_type:
                    type_desc = selection_type
                else:
                    type_desc = "Ordner" if "Datenspeicher" in selection_info else "Datei(en)"

                prompt = FILES_PROMPT.format(
                    selection_type=type_desc,
                    selection_info=selection_info or "Auswahl",
                    target_word=target_word,
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
                    max_output_tokens=1024,  # Higher to avoid truncation issues
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

            # Extract mode first (always needed)
            mode_match = re.search(r'"mode":\s*"(QA|BASIC|SEARCH)"', clean_text, re.IGNORECASE)
            if not mode_match:
                logger.warning(f"Could not find mode in response: {result_text}")
                return self._fallback_analysis(has_files, selection_type)

            mode = mode_match.group(1).upper()

            # Extract reason - try complete JSON first, then partial
            reason = None
            json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    reason = result.get("reason")
                except json.JSONDecodeError:
                    pass

            # If no reason from JSON, extract partial reason
            if not reason:
                reason_match = re.search(r'"reason":\s*"([^"]*)', clean_text)
                if reason_match and reason_match.group(1).strip():
                    reason = reason_match.group(1).strip()

            # If still no reason, generate a default based on mode and selection
            if not reason:
                reason = self._generate_default_reason(mode, selection_type)

            # Validate mode
            if mode not in ["QA", "BASIC", "SEARCH"]:
                mode = "QA" if has_files else "BASIC"

            # Enforce rule: no SEARCH with files
            if has_files and mode == "SEARCH":
                mode = "QA"
                reason = self._generate_default_reason("QA", selection_type)

            return {"mode": mode, "reason": reason}

        except Exception as e:
            logger.error(f"Gemini analysis error: {e}")
            return self._fallback_analysis(has_files, selection_type if has_files else "")

    def _generate_default_reason(self, mode: str, selection_type: str) -> str:
        """Generate a default reason when LLM response is incomplete."""
        target = "Ordner" if "Ordner" in selection_type else "Datei"

        if mode == "QA":
            return f"Durchsuche {target}"
        elif mode == "BASIC":
            return f"Analysiere {target}"
        elif mode == "SEARCH":
            return "Suche im Web"
        return "Verarbeite Anfrage"

    def _fallback_analysis(self, has_files: bool, selection_type: str = "") -> dict:
        """Fallback when Gemini is not available."""
        if has_files:
            target = "Ordner" if "Ordner" in selection_type else "Datei"
            return {"mode": "QA", "reason": f"Durchsuche {target}"}
        else:
            return {"mode": "BASIC", "reason": "Verarbeite Anfrage"}

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
