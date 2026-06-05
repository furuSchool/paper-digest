from datetime import datetime
from pydantic import BaseModel, EmailStr


# --- SourceInterest ---


class SourceInterestBase(BaseModel):
    arxiv_categories: str = ""
    keywords: str = ""


class SourceInterestCreate(SourceInterestBase):
    pass


class SourceInterestRead(SourceInterestBase):
    id: int
    source_id: int

    model_config = {"from_attributes": True}


# --- Source ---


class SourceBase(BaseModel):
    name: str
    description: str = ""
    type: str = "arxiv"
    enabled: bool = True
    schedule_frequency: int = 1
    email_to: EmailStr
    max_results: int = 20
    period: int = 1
    google_drive_folder_id: str | None = None
    dedup_enabled: bool = True
    citation_filter_enabled: bool = False
    citation_top_multiplier: int = 5
    llm_prompt: str | None = None


class SourceCreate(SourceBase):
    interests: list[SourceInterestCreate] = []


class SourceUpdate(SourceBase):
    interests: list[SourceInterestCreate] = []


class SourceRead(SourceBase):
    id: int
    created_at: datetime
    last_triggered_at: datetime | None = None
    interests: list[SourceInterestRead] = []

    model_config = {"from_attributes": True}


# --- GoogleToken ---


class GoogleTokenStatus(BaseModel):
    authenticated: bool
    token_expiry: datetime | None = None


# --- Digest ---


class PaperSummary(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    summary_ja: str
    matched_by_keyword: bool = False
    citation_count: int | None = None  # 引用数フィルタ使用時のみ設定


class DigestResult(BaseModel):
    source_id: int
    papers: list[PaperSummary]
    doc_url: str | None = None  # previewでは None
