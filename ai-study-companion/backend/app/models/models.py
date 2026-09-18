"""SQLAlchemy ORM models for the AI Study Companion."""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String, Text, Float, Integer, Boolean, DateTime,
    ForeignKey, Enum as SAEnum, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from pgvector.sqlalchemy import Vector
import enum

from app.db.session import Base
from app.core.config import settings


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class MaterialStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class QuestionType(str, enum.Enum):
    mcq = "mcq"
    open_ended = "open_ended"


class AssessmentStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


class MasteryTrend(str, enum.Enum):
    improving = "improving"
    stable = "stable"
    needs_attention = "needs_attention"
    insufficient_data = "insufficient_data"


class RecommendationStatus(str, enum.Enum):
    active = "active"
    dismissed = "dismissed"
    completed = "completed"


class EventType(str, enum.Enum):
    user_registered = "user_registered"
    space_created = "space_created"
    project_created = "project_created"
    material_uploaded = "material_uploaded"
    material_processed = "material_processed"
    material_failed = "material_failed"
    tutor_message = "tutor_message"
    quiz_started = "quiz_started"
    question_answered = "question_answered"
    quiz_completed = "quiz_completed"
    mastery_updated = "mastery_updated"
    recommendation_generated = "recommendation_generated"


# ──────────────────────────────────────────────
# User
# ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.user, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    spaces: Mapped[List["Space"]] = relationship("Space", back_populates="user", cascade="all, delete-orphan")
    events: Mapped[List["Event"]] = relationship("Event", back_populates="user")
    ai_logs: Mapped[List["AILog"]] = relationship("AILog", back_populates="user")


# ──────────────────────────────────────────────
# Space
# ──────────────────────────────────────────────
class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="#6366f1")
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="📚")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="spaces")
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="space", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    learning_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    space: Mapped["Space"] = relationship("Space", back_populates="projects")
    materials: Mapped[List["Material"]] = relationship("Material", back_populates="project", cascade="all, delete-orphan")
    chunks: Mapped[List["Chunk"]] = relationship("Chunk", back_populates="project", cascade="all, delete-orphan")
    concepts: Mapped[List["Concept"]] = relationship("Concept", back_populates="project", cascade="all, delete-orphan")
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")
    assessments: Mapped[List["Assessment"]] = relationship("Assessment", back_populates="project", cascade="all, delete-orphan")
    mastery_records: Mapped[List["MasteryRecord"]] = relationship("MasteryRecord", back_populates="project", cascade="all, delete-orphan")
    recommendations: Mapped[List["Recommendation"]] = relationship("Recommendation", back_populates="project", cascade="all, delete-orphan")
    learning_context: Mapped[Optional["LearningContext"]] = relationship("LearningContext", back_populates="project", uselist=False, cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Material (uploaded PDF)
# ──────────────────────────────────────────────
class Material(Base):
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)         # storage key/path
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False) # user-facing name
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[MaterialStatus] = mapped_column(SAEnum(MaterialStatus), default=MaterialStatus.queued, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="materials")
    chunks: Mapped[List["Chunk"]] = relationship("Chunk", back_populates="material", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Chunk (text segment with embedding)
# VECTOR(3072) — verified dimension for gemini-embedding-2
# ──────────────────────────────────────────────
class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # VECTOR(3072): gemini-embedding-2, verified 2026-09-16
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(3072), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    material: Mapped["Material"] = relationship("Material", back_populates="chunks")
    project: Mapped["Project"] = relationship("Project", back_populates="chunks")


# ──────────────────────────────────────────────
# Concept (extracted from document)
# ──────────────────────────────────────────────
class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    extracted_from_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("materials.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="concepts")
    mastery_record: Mapped[Optional["MasteryRecord"]] = relationship("MasteryRecord", back_populates="concept", uselist=False)
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="concept")


# ──────────────────────────────────────────────
# Conversation + Messages (AI Tutor)
# ──────────────────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation",
                                                      order_by="Message.created_at", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    retrieved_chunk_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


# ──────────────────────────────────────────────
# Assessment (quiz session)
# ──────────────────────────────────────────────
class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[AssessmentStatus] = mapped_column(SAEnum(AssessmentStatus), default=AssessmentStatus.in_progress)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    score_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="assessments")
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="assessment",
                                                        order_by="Question.created_at", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    question_type: Mapped[QuestionType] = mapped_column(SAEnum(QuestionType), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)      # MCQ choices
    correct_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="questions")
    concept: Mapped[Optional["Concept"]] = relationship("Concept", back_populates="questions")
    answer: Mapped[Optional["Answer"]] = relationship("Answer", back_populates="question", uselist=False, cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    ai_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)      # 0.0-1.0
    ai_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    understood_correctly: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    missing_concepts: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    misconceptions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    question: Mapped["Question"] = relationship("Question", back_populates="answer")


# ──────────────────────────────────────────────
# Mastery
# ──────────────────────────────────────────────
class MasteryRecord(Base):
    __tablename__ = "mastery_records"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=50.0)   # 0-100
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    trend: Mapped[MasteryTrend] = mapped_column(SAEnum(MasteryTrend), default=MasteryTrend.insufficient_data)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    concept: Mapped["Concept"] = relationship("Concept", back_populates="mastery_record")
    project: Mapped["Project"] = relationship("Project", back_populates="mastery_records")
    history: Mapped[List["MasteryHistory"]] = relationship("MasteryHistory", back_populates="mastery_record",
                                                            order_by="MasteryHistory.recorded_at", cascade="all, delete-orphan")


class MasteryHistory(Base):
    __tablename__ = "mastery_history"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mastery_record_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("mastery_records.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "quiz" | "assessment" | "tutor"
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    mastery_record: Mapped["MasteryRecord"] = relationship("MasteryRecord", back_populates="history")


# ──────────────────────────────────────────────
# Recommendations
# ──────────────────────────────────────────────
class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "review_concept", "take_quiz"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_concept_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[RecommendationStatus] = mapped_column(SAEnum(RecommendationStatus), default=RecommendationStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="recommendations")


# ──────────────────────────────────────────────
# Learning Context (persistent, per project)
# ──────────────────────────────────────────────
class LearningContext(Base):
    __tablename__ = "learning_contexts"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    known_strengths: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    known_weaknesses: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    important_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repeated_mistakes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="learning_context")


# ──────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────
class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    space_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user: Mapped["User"] = relationship("User", back_populates="events")


# ──────────────────────────────────────────────
# AI Observability Log
# ──────────────────────────────────────────────
class AILog(Base):
    __tablename__ = "ai_logs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    feature: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # tutor/quiz/embedding/evaluation/recommendation
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="ai_logs")


# ──────────────────────────────────────────────
# Background Job tracking
# ──────────────────────────────────────────────
class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending/running/success/failed
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
