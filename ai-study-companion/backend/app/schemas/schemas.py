"""Pydantic schemas for request/response validation."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Auth ───────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str
    role: str


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    created_at: datetime
    last_active_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ─── Spaces ─────────────────────────────────────────
class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    color: Optional[str] = "#6366f1"
    icon: Optional[str] = "📚"


class SpaceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class SpaceOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    color: Optional[str]
    icon: Optional[str]
    created_at: datetime
    project_count: int = 0

    model_config = {"from_attributes": True}


# ─── Projects ────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    learning_goal: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    learning_goal: Optional[str] = None


class ConceptSummary(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    mastery_score: Optional[float] = None
    trend: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: UUID
    space_id: UUID
    name: str
    description: Optional[str]
    learning_goal: Optional[str]
    created_at: datetime
    last_activity_at: Optional[datetime]
    material_count: int = 0
    ready_material_count: int = 0
    concept_count: int = 0

    model_config = {"from_attributes": True}


class ProjectDashboard(BaseModel):
    project: ProjectOut
    top_concepts: List[ConceptSummary] = []
    latest_recommendation: Optional[dict] = None
    recent_assessment_score: Optional[float] = None
    mastery_avg: Optional[float] = None
    activity_count_7d: int = 0


# ─── Materials ──────────────────────────────────────
class MaterialOut(BaseModel):
    id: UUID
    original_filename: str
    file_size: Optional[int]
    status: str
    error_message: Optional[str]
    page_count: Optional[int]
    created_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ─── Tutor ───────────────────────────────────────────
class TutorMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[UUID] = None


class CitationOut(BaseModel):
    source: str
    page: int
    excerpt: str


class TutorResponseOut(BaseModel):
    message_id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: List[CitationOut] = []
    confidence: Optional[str] = None
    insufficient_evidence: bool = False


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    citations: Optional[List[dict]] = []
    confidence: Optional[str]
    insufficient_evidence: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: UUID
    title: Optional[str]
    created_at: datetime
    messages: List[MessageOut] = []

    model_config = {"from_attributes": True}


# ─── Quiz ────────────────────────────────────────────
class QuizStartRequest(BaseModel):
    length: Optional[int] = Field(default=10, ge=3, le=20)


class QuestionOut(BaseModel):
    id: UUID
    assessment_id: UUID
    question_type: str
    difficulty: int
    question_text: str
    options: Optional[List[str]] = None  # MCQ only
    question_number: int
    total_questions: int


class AnswerSubmitRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


class AnswerResultOut(BaseModel):
    question_id: UUID
    is_correct: Optional[bool]
    ai_score: Optional[float]
    ai_feedback: Optional[str]
    understood_correctly: Optional[List[str]] = []
    missing_concepts: Optional[List[str]] = []
    correct_answer: Optional[str]
    explanation: Optional[str]
    next_question_available: bool


class AssessmentOut(BaseModel):
    id: UUID
    status: str
    total_questions: int
    correct_count: int
    score_pct: Optional[float]
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ─── Mastery ─────────────────────────────────────────
class MasteryConceptOut(BaseModel):
    concept_id: UUID
    concept_name: str
    score: float
    trend: str
    evidence_count: int
    history: List[dict] = []


class GrowthAnalysisOut(BaseModel):
    project_id: UUID
    improving: List[MasteryConceptOut] = []
    stable: List[MasteryConceptOut] = []
    needs_attention: List[MasteryConceptOut] = []
    insufficient_data: List[MasteryConceptOut] = []
    overall_mastery: float = 0.0


# ─── Recommendations ────────────────────────────────
class RecommendationOut(BaseModel):
    id: UUID
    recommendation_type: str
    content: str
    reason: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Analytics ──────────────────────────────────────
class ProjectAnalyticsOut(BaseModel):
    project_id: UUID
    total_events: int
    tutor_messages: int
    quizzes_completed: int
    avg_quiz_score: Optional[float]
    materials_count: int
    concepts_count: int
    mastery_avg: float
    event_timeline: List[dict] = []
    concept_mastery_list: List[dict] = []


class GlobalAnalyticsOut(BaseModel):
    total_users: int
    total_spaces: int
    total_projects: int
    total_materials: int
    total_tutor_messages: int
    total_quizzes: int
    total_ai_calls: int
    total_ai_cost_usd: float
    active_users_7d: int


# ─── Admin ──────────────────────────────────────────
class AdminUserOut(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    created_at: datetime
    last_active_at: Optional[datetime]
    space_count: int = 0
    project_count: int = 0
    ai_call_count: int = 0


class AdminSystemHealth(BaseModel):
    db_status: str
    redis_status: str
    worker_status: str
    pending_jobs: int
    failed_jobs_24h: int


class AIUsageStats(BaseModel):
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    success_rate: float
    by_feature: List[dict] = []
    by_model: List[dict] = []
