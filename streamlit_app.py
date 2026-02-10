"""
Streamlit Testing App for Autonomous Mode Router.
Allows testing queries with pseudo files/folders and editing prompts.
"""
import json
import logging
import streamlit as st

from src.models.api_schemas import (
    DetectModeRequest,
    DetectModeResponse,
    SelectedFileInfo,
    SelectedDatastoreInfo,
)
from src.services.mode_detector import get_mode_detector
import src.services.gemini_service as gs

# Configure logging to capture Gemini responses
logging.basicConfig(level=logging.INFO)

# Store original prompts (from module source code, never changes)
_ORIGINAL_FILES_PROMPT = gs.FILES_PROMPT
_ORIGINAL_NO_FILES_PROMPT = gs.NO_FILES_PROMPT

# Initialize widget keys for text_area (these are owned by the widget via key=)
if "widget_files_prompt" not in st.session_state:
    st.session_state.widget_files_prompt = _ORIGINAL_FILES_PROMPT
if "widget_no_files_prompt" not in st.session_state:
    st.session_state.widget_no_files_prompt = _ORIGINAL_NO_FILES_PROMPT

# Track which prompts are actually applied to Gemini
if "applied_files_prompt" not in st.session_state:
    st.session_state.applied_files_prompt = _ORIGINAL_FILES_PROMPT
if "applied_no_files_prompt" not in st.session_state:
    st.session_state.applied_no_files_prompt = _ORIGINAL_NO_FILES_PROMPT

# Always apply the confirmed prompts to module (survives reruns)
gs.FILES_PROMPT = st.session_state.applied_files_prompt
gs.NO_FILES_PROMPT = st.session_state.applied_no_files_prompt


def _reset_prompts():
    """Callback for Reset button - runs before next rerun so widget keys can be set."""
    st.session_state.widget_files_prompt = _ORIGINAL_FILES_PROMPT
    st.session_state.widget_no_files_prompt = _ORIGINAL_NO_FILES_PROMPT
    st.session_state.applied_files_prompt = _ORIGINAL_FILES_PROMPT
    st.session_state.applied_no_files_prompt = _ORIGINAL_NO_FILES_PROMPT
    gs.FILES_PROMPT = _ORIGINAL_FILES_PROMPT
    gs.NO_FILES_PROMPT = _ORIGINAL_NO_FILES_PROMPT

# ============================================
# Pseudo Test-Daten
# ============================================
PSEUDO_FOLDERS = [
    {"id": "ds-1", "name": "Bachelorarbeiten", "totalTokenSize": 602_338},
    {"id": "ds-2", "name": "Verträge 2024", "totalTokenSize": 245_000},
    {"id": "ds-3", "name": "Technische Dokumentation", "totalTokenSize": 890_000},
    {"id": "ds-4", "name": "HR Unterlagen", "totalTokenSize": 150_000},
    {"id": "ds-5", "name": "Marketing Material", "totalTokenSize": 78_000},
    {"id": "ds-6", "name": "Forschungspapiere", "totalTokenSize": 1_200_000},
    {"id": "ds-7", "name": "Kundenkorrespondenz", "totalTokenSize": 340_000},
    {"id": "ds-8", "name": "Projektberichte", "totalTokenSize": 520_000},
    {"id": "ds-9", "name": "Schulungsmaterial", "totalTokenSize": 95_000},
    {"id": "ds-10", "name": "Archiv 2023", "totalTokenSize": 1_500_000},
]

PSEUDO_FILES = [
    {"id": "f-1", "name": "Bachelorarbeit_KI.pdf", "tokenSize": 158_924},
    {"id": "f-2", "name": "Vertrag_Kunde_A.docx", "tokenSize": 12_500},
    {"id": "f-3", "name": "Jahresbericht_2024.pdf", "tokenSize": 89_000},
    {"id": "f-4", "name": "API_Dokumentation.md", "tokenSize": 45_200},
    {"id": "f-5", "name": "Meeting_Notes_Q4.txt", "tokenSize": 8_300},
    {"id": "f-6", "name": "Finanzbericht.xlsx", "tokenSize": 234_000},
    {"id": "f-7", "name": "Handbuch_v2.pdf", "tokenSize": 670_000},
    {"id": "f-8", "name": "Praesentation_Pitch.pptx", "tokenSize": 15_800},
    {"id": "f-9", "name": "Datenschutz_Policy.pdf", "tokenSize": 32_100},
    {"id": "f-10", "name": "Forschung_ML_Paper.pdf", "tokenSize": 112_000},
]

def format_tokens(tokens: int) -> str:
    """Format token count for display."""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.0f}K"
    return str(tokens)

# Log capture handler
class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def clear(self):
        self.records.clear()

    def get_logs(self):
        return [self.format(r) for r in self.records]

# Setup log capture
if "log_handler" not in st.session_state:
    handler = LogCaptureHandler()
    handler.setFormatter(logging.Formatter("%(name)s - %(message)s"))
    logging.getLogger("src.services.gemini_service").addHandler(handler)
    logging.getLogger("src.services.mode_detector").addHandler(handler)
    st.session_state.log_handler = handler

# Page config
st.set_page_config(
    page_title="Auto Router - Testing",
    page_icon="🔀",
    layout="wide",
)

# ============================================
# Password Protection
# ============================================
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "506testing")

def check_password():
    """Simple password gate."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("Autonomous Mode Router - Testing")
    st.markdown("---")
    password = st.text_input("Passwort eingeben", type="password", placeholder="Passwort...")
    if st.button("Login", type="primary"):
        if password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Falsches Passwort")
    return False

if not check_password():
    st.stop()

st.title("Autonomous Mode Router - Testing")

# Initialize detector
@st.cache_resource
def init_detector():
    return get_mode_detector()

detector = init_detector()

# ============================================
# TABS
# ============================================
tab1, tab2, tab3 = st.tabs(["Test Chat", "Prompts bearbeiten", "Logik-Übersicht"])

# ============================================
# TAB 1: Test Chat
# ============================================
with tab1:
    col_input, col_result = st.columns([1, 1])

    with col_input:
        st.subheader("Anfrage konfigurieren")

        query = st.text_input(
            "Query",
            value="Wer ist der Autor der Bachelorarbeit?",
            placeholder="Deine Frage eingeben...",
        )

        # --- Ordner Auswahl ---
        st.markdown("#### Ordner")
        folder_options = [f"{f['name']}  ({format_tokens(f['totalTokenSize'])} Tokens)" for f in PSEUDO_FOLDERS]
        selected_folders = st.multiselect(
            "Ordner auswählen",
            options=folder_options,
            default=[],
            placeholder="Ordner auswählen...",
            label_visibility="collapsed",
        )

        # --- Dateien Auswahl ---
        st.markdown("#### Dateien")
        file_options = [f"{f['name']}  ({format_tokens(f['tokenSize'])} Tokens)" for f in PSEUDO_FILES]
        selected_files = st.multiselect(
            "Dateien auswählen",
            options=file_options,
            default=[],
            placeholder="Dateien auswählen...",
            label_visibility="collapsed",
        )

        # Calculate and show total tokens
        total_tokens = 0
        for i, opt in enumerate(folder_options):
            if opt in selected_folders:
                total_tokens += PSEUDO_FOLDERS[i]["totalTokenSize"]
        for i, opt in enumerate(file_options):
            if opt in selected_files:
                total_tokens += PSEUDO_FILES[i]["tokenSize"]

        token_limit = 980_000
        threshold = int(token_limit * 0.7)

        if selected_folders or selected_files:
            over_threshold = total_tokens > threshold
            color = "red" if over_threshold else "green"
            st.markdown(
                f"**Gesamt: :{color}[{format_tokens(total_tokens)} Tokens]** "
                f"(Threshold 70%: {format_tokens(threshold)} | Limit: {format_tokens(token_limit)})"
            )
            if over_threshold:
                st.caption("Token > 70% vom Limit → QA wird erzwungen (kein LLM-Call)")
        else:
            st.caption("Keine Auswahl → LLM entscheidet SEARCH vs BASIC")

        st.markdown("---")
        analyze_btn = st.button("Analysieren", type="primary", use_container_width=True)

    with col_result:
        st.subheader("Ergebnis")

        if analyze_btn and query.strip():
            # Clear logs
            st.session_state.log_handler.clear()

            # Build request
            req_datastores = []
            req_files = []
            req_folder_id = None

            for i, opt in enumerate(folder_options):
                if opt in selected_folders:
                    f = PSEUDO_FOLDERS[i]
                    req_datastores.append(
                        SelectedDatastoreInfo(id=f["id"], name=f["name"], totalTokenSize=f["totalTokenSize"])
                    )
                    if not req_folder_id:
                        req_folder_id = f["id"]

            for i, opt in enumerate(file_options):
                if opt in selected_files:
                    f = PSEUDO_FILES[i]
                    req_files.append(
                        SelectedFileInfo(id=f["id"], name=f["name"], tokenSize=f["tokenSize"])
                    )

            request = DetectModeRequest(
                query=query,
                tokenLimit=token_limit,
                selectedFiles=req_files,
                selectedDatastores=req_datastores,
                selectedFolderId=req_folder_id,
                selectedFileIds=[],
            )

            with st.spinner("Gemini analysiert..."):
                result = detector.detect(request)

            # Display result
            mode_colors = {"QA": "blue", "BASIC": "green", "SEARCH": "orange"}
            mode_str = result.mode.value
            color = mode_colors.get(mode_str, "gray")

            st.markdown(f"### :{color}[{mode_str}]")
            st.progress(result.confidence or 0.0, text=f"Confidence: {result.confidence}")
            st.info(f"**Reason:** {result.reason}")

            # Raw JSON
            with st.expander("Raw JSON Response"):
                st.json({
                    "mode": mode_str,
                    "confidence": result.confidence,
                    "reason": result.reason,
                })

            # Request details
            with st.expander("Request Details"):
                req_display = {
                    "query": query,
                    "tokenLimit": token_limit,
                    "totalTokens": total_tokens,
                    "selectedFolders": [f["name"] for i, f in enumerate(PSEUDO_FOLDERS) if folder_options[i] in selected_folders],
                    "selectedFiles": [f["name"] for i, f in enumerate(PSEUDO_FILES) if file_options[i] in selected_files],
                }
                st.json(req_display)

            # Logs
            with st.expander("Gemini Logs", expanded=True):
                logs = st.session_state.log_handler.get_logs()
                if logs:
                    for log in logs:
                        st.text(log)
                else:
                    st.text("Keine Logs verfügbar")

        elif analyze_btn:
            st.warning("Bitte eine Query eingeben.")

# ============================================
# TAB 2: Prompts bearbeiten
# ============================================
with tab2:
    st.subheader("System Prompts bearbeiten")
    st.caption("Änderungen gelten sofort für den nächsten Analyse-Call.")

    col_p1, col_p2 = st.columns([1, 1])

    with col_p1:
        st.markdown("#### FILES_PROMPT")
        st.caption("Wird verwendet wenn Dateien/Ordner ausgewählt sind")
        files_prompt_edit = st.text_area(
            "FILES_PROMPT",
            key="widget_files_prompt",
            height=400,
            label_visibility="collapsed",
        )

    with col_p2:
        st.markdown("#### NO_FILES_PROMPT")
        st.caption("Wird verwendet wenn keine Dateien ausgewählt sind")
        no_files_prompt_edit = st.text_area(
            "NO_FILES_PROMPT",
            key="widget_no_files_prompt",
            height=400,
            label_visibility="collapsed",
        )

    col_btn1, col_btn2, _ = st.columns([1, 1, 3])

    with col_btn1:
        if st.button("Übernehmen", type="primary", use_container_width=True):
            if not files_prompt_edit.strip() or not no_files_prompt_edit.strip():
                st.error("Prompts dürfen nicht leer sein! Nutze 'Reset' um die Originale wiederherzustellen.")
            else:
                st.session_state.applied_files_prompt = files_prompt_edit
                st.session_state.applied_no_files_prompt = no_files_prompt_edit
                gs.FILES_PROMPT = files_prompt_edit
                gs.NO_FILES_PROMPT = no_files_prompt_edit
                st.success("Prompts aktualisiert!")

    with col_btn2:
        st.button("Reset", use_container_width=True, on_click=_reset_prompts)

# ============================================
# TAB 3: Logik-Übersicht
# ============================================
with tab3:
    st.subheader("Entscheidungslogik")

    st.graphviz_chart("""
    digraph {
        rankdir=TB
        node [shape=box, style="rounded,filled", fontname="Arial", fontsize=12]
        edge [fontname="Arial", fontsize=10]

        request [label="User Request\\n(Query + Kontext)", fillcolor="#e3f2fd"]
        check_selection [label="Datei/Ordner\\nausgewählt?", shape=diamond, fillcolor="#fff9c4"]
        check_tokens [label="Tokens > 70%\\nvom Limit?", shape=diamond, fillcolor="#fff9c4"]
        llm_qa_basic [label="LLM entscheidet\\nQA vs BASIC", fillcolor="#f3e5f5"]
        llm_search_basic [label="LLM entscheidet\\nSEARCH vs BASIC", fillcolor="#f3e5f5"]

        qa_forced [label="QA\\n(Vector Search)\\nconfidence: 0.95", fillcolor="#bbdefb"]
        qa [label="QA\\n(Vector Search)\\nconfidence: 0.90", fillcolor="#bbdefb"]
        basic_file [label="BASIC\\n(Chat + Dokument)\\nconfidence: 0.90", fillcolor="#c8e6c9"]
        search [label="SEARCH\\n(Web-Suche)\\nconfidence: 0.90", fillcolor="#ffe0b2"]
        basic [label="BASIC\\n(Normaler Chat)\\nconfidence: 0.90", fillcolor="#c8e6c9"]

        request -> check_selection
        check_selection -> check_tokens [label="JA"]
        check_selection -> llm_search_basic [label="NEIN"]
        check_tokens -> qa_forced [label="JA\\n(zu groß)"]
        check_tokens -> llm_qa_basic [label="NEIN\\n(passt in Context)"]
        llm_qa_basic -> qa [label="Spezifische Frage"]
        llm_qa_basic -> basic_file [label="Ganzes Dokument"]
        llm_search_basic -> search [label="Aktuelle Daten"]
        llm_search_basic -> basic [label="Allgemeine Frage"]
    }
    """)

    st.markdown("---")
    st.subheader("Regeln")

    st.markdown("""
| Regel | Beschreibung |
|-------|-------------|
| **SEARCH blockiert** | Wenn Dateien/Ordner ausgewählt sind, ist SEARCH nie möglich |
| **Token-Threshold** | Wenn Tokens > 70% vom Model-Limit, wird QA erzwungen (Vector Search) |
| **QA bevorzugt** | Bei Dateien wird QA (RAG) bevorzugt, BASIC nur für ganze Dokument-Analyse |
| **QA blockiert** | Ohne Dateien ist QA nicht möglich (wird zu BASIC) |
| **Fallback** | Bei Gemini-Fehlern: Mit Dateien → QA, Ohne → BASIC |
    """)

    st.markdown("---")
    st.subheader("Reason-Generierung")
    st.caption("Das LLM generiert kontextbezogene Aktionsbeschreibungen:")

    st.markdown("""
| Query | Auswahl | Mode | Reason |
|-------|---------|------|--------|
| "Wer ist der Autor?" | Ordner | QA | "Suche nach dem Autor im Ordner" |
| "Fasse zusammen" | Datei | BASIC | "Erstelle Zusammenfassung der Datei" |
| "Wie ist das Wetter?" | - | SEARCH | "Suche aktuelle Wetterdaten" |
| "Erkläre Photosynthese" | - | BASIC | "Erkläre den Prozess der Photosynthese" |
    """)
