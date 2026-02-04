"""Mode detection service - determines BASIC, QA, or SEARCH mode."""
import logging

from src.models.api_schemas import (
    DetectModeRequest,
    DetectModeResponse,
    DetectModeEnum
)
from src.services.gemini_service import get_gemini_service

logger = logging.getLogger(__name__)

# Default threshold: if tokens > this % of context limit, use QA Mode
CONTEXT_THRESHOLD_PERCENT = 0.7


class ModeDetector:
    """Detects the appropriate mode based on query and context."""

    def __init__(self):
        """Initialize the mode detector."""
        self.gemini_service = None
        logger.info("ModeDetector initialized")

    def _get_gemini_service(self):
        """Lazy-load Gemini service."""
        if self.gemini_service is None:
            self.gemini_service = get_gemini_service()
        return self.gemini_service

    def detect(self, request: DetectModeRequest) -> DetectModeResponse:
        """
        Detect the appropriate mode based on the request.

        Logic:
        1. If File/Folder selected → NEVER SEARCH
           - If tokens > threshold → Always QA (Vector Search)
           - If tokens fit → LLM decides QA vs BASIC
        2. If no selection → LLM decides SEARCH vs BASIC

        Args:
            request: The detection request with query, history, and selections

        Returns:
            DetectModeResponse with mode, confidence, and reason
        """
        query = request.query.strip()
        token_limit = request.tokenLimit
        token_threshold = int(token_limit * CONTEXT_THRESHOLD_PERCENT)

        logger.info(f"Detecting mode for query: {query[:50]}...")
        logger.info(f"Token limit: {token_limit}, Threshold (70%): {token_threshold}")

        # ============================================
        # Check if Folder OR Files are selected
        # ============================================
        has_folder = bool(request.selectedFolderId) or bool(request.selectedDatastores)
        has_files = bool(request.selectedFiles) or bool(request.selectedFileIds)
        has_selection = has_folder or has_files

        if has_selection:
            # Calculate total tokens
            total_tokens = self._calculate_total_tokens(request)
            selection_desc = self._get_selection_description(request)

            logger.info(f"Selection: {selection_desc}, Total tokens: {total_tokens}")

            # RULE: If tokens exceed threshold → Always QA
            if total_tokens > token_threshold:
                logger.info(f"Tokens {total_tokens} > {token_threshold} → QA (forced)")
                return DetectModeResponse(
                    mode=DetectModeEnum.QA,
                    confidence=0.95,
                    reason="Dokument zu groß - Verwende Vector Search"
                )

            # Tokens fit in context → LLM decides between QA and BASIC
            logger.info(f"Tokens {total_tokens} ≤ {token_threshold} → LLM decides QA vs BASIC")
            llm_result = self._analyze_with_llm(query, has_files=True, selection_info=selection_desc)

            # Map LLM result to mode (SEARCH is blocked when files selected)
            mode = llm_result.get("mode", "QA")
            if mode == "SEARCH":
                mode = "QA"  # Enforce no SEARCH with files
                llm_result["reason"] = "Web-Suche nicht möglich mit Dateien → RAG"

            return DetectModeResponse(
                mode=DetectModeEnum(mode),
                confidence=0.90,
                reason=llm_result.get('reason', 'LLM-Analyse')
            )

        # ============================================
        # No selection → LLM decides SEARCH vs BASIC
        # ============================================
        logger.info("No files/folders selected → LLM decides SEARCH vs BASIC")
        llm_result = self._analyze_with_llm(query, has_files=False)

        mode = llm_result.get("mode", "BASIC")
        # Without files, only SEARCH or BASIC are valid
        if mode == "QA":
            mode = "BASIC"  # QA doesn't make sense without files

        return DetectModeResponse(
            mode=DetectModeEnum(mode),
            confidence=0.90,
            reason=llm_result.get("reason", "LLM-Analyse")
        )

    def _analyze_with_llm(self, query: str, has_files: bool, selection_info: str = "") -> dict:
        """Analyze query with Gemini LLM."""
        try:
            service = self._get_gemini_service()
            return service.analyze_query(query, has_files, selection_info)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            # Fallback
            if has_files:
                return {"mode": "QA", "reason": "Fallback: Dateien ausgewählt → RAG"}
            return {"mode": "BASIC", "reason": "Fallback: Normaler Chat"}

    def _calculate_total_tokens(self, request: DetectModeRequest) -> int:
        """Calculate total tokens from all selections."""
        total = 0

        # Tokens from selected datastores
        for ds in request.selectedDatastores:
            logger.debug(f"Datastore '{ds.name}': {ds.totalTokenSize} tokens")
            total += ds.totalTokenSize

        # Tokens from selected files
        for f in request.selectedFiles:
            logger.debug(f"File '{f.name}': {f.tokenSize} tokens")
            total += f.tokenSize

        logger.info(f"Token calculation: {len(request.selectedDatastores)} datastores + {len(request.selectedFiles)} files = {total} total tokens")

        # If we have IDs but no token info, return a high number to trigger QA
        if total == 0 and (request.selectedFileIds or request.selectedFolderId):
            logger.warning("Selection without token info - defaulting to high token count")
            return 999999999  # Force QA mode

        return total

    def _get_selection_description(self, request: DetectModeRequest) -> str:
        """Get a human-readable description of the selection."""
        parts = []

        if request.selectedDatastores:
            ds_names = [ds.name for ds in request.selectedDatastores[:2]]
            if len(request.selectedDatastores) > 2:
                ds_names.append(f"+{len(request.selectedDatastores) - 2}")
            parts.append(f"Datenspeicher: {', '.join(ds_names)}")
        elif request.selectedFolderId:
            parts.append(f"Datenspeicher-ID: {request.selectedFolderId[:8]}...")

        if request.selectedFiles:
            file_names = [f.name[:20] for f in request.selectedFiles[:2]]
            if len(request.selectedFiles) > 2:
                file_names.append(f"+{len(request.selectedFiles) - 2}")
            parts.append(f"Dateien: {', '.join(file_names)}")
        elif request.selectedFileIds:
            parts.append(f"{len(request.selectedFileIds)} Datei(en)")

        return " | ".join(parts) if parts else "Auswahl"


# Singleton instance
_detector = None


def get_mode_detector() -> ModeDetector:
    """Get or create the mode detector singleton."""
    global _detector
    if _detector is None:
        _detector = ModeDetector()
    return _detector
