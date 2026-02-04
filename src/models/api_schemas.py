"""API Request/Response schemas for the detect-mode endpoint."""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DetectModeEnum(str, Enum):
    """Output modes matching the Chrome Panel interface."""
    BASIC = "BASIC"    # Chat Modus (normal chat OR chat with file in context)
    QA = "QA"          # Abfragemodus (Vector Search - file too large for context)
    SEARCH = "SEARCH"  # Websuche (current info from internet)


class HistoryMessage(BaseModel):
    """A message in the chat history."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class SelectedFileInfo(BaseModel):
    """Information about a selected file with token size."""
    id: str
    name: str
    tokenSize: int = Field(..., alias="tokenSize")

    class Config:
        populate_by_name = True


class SelectedDatastoreInfo(BaseModel):
    """Information about a selected datastore with total token size."""
    id: str
    name: str
    totalTokenSize: int = Field(..., alias="totalTokenSize")

    class Config:
        populate_by_name = True


class DetectModeRequest(BaseModel):
    """Request body for /api/qr/detect-mode endpoint."""
    # Die aktuelle Benutzer-Nachricht
    query: str

    # Chat-Verlauf (letzte Nachrichten)
    history: list[HistoryMessage] = Field(default_factory=list)

    # Token-Limit des ausgewählten Models (z.B. 980000 für Gemini 2.5 Flash)
    tokenLimit: int = Field(default=980000, alias="tokenLimit")

    # ID des ausgewählten Datenspeichers (oder null)
    selectedFolderId: Optional[str] = Field(default=None, alias="selectedFolderId")

    # IDs der ausgewählten Dateien (kann leer sein)
    selectedFileIds: list[str] = Field(default_factory=list, alias="selectedFileIds")

    # Ausgewählte Dateien mit Token-Größen
    selectedFiles: list[SelectedFileInfo] = Field(default_factory=list, alias="selectedFiles")

    # Ausgewählte Datenspeicher mit Token-Größen
    selectedDatastores: list[SelectedDatastoreInfo] = Field(default_factory=list, alias="selectedDatastores")

    class Config:
        populate_by_name = True


class DetectModeResponse(BaseModel):
    """Response body for /api/qr/detect-mode endpoint."""
    # Der erkannte Modus: "BASIC" | "QA" | "SEARCH"
    mode: DetectModeEnum

    # Konfidenz-Score (0.0 - 1.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Begründung für die Entscheidung (für Debugging)
    reason: Optional[str] = None
