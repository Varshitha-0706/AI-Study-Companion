"""
Post-quiz learning workflow.
Triggered after a quiz session completes.

Flow: Quiz completed → evaluate answers → update mastery →
      detect weaknesses → update learning context → generate recommendation
"""
import uuid
import json
import re
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.ai.gemini_client import gemini_client
from app.core.config import settings


def get_sync_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def update_mastery_for_concept(db, concept_id, user_id, project_id, evidence_score: float, evidence_type: str):
    """
    Evidence-weighted mastery update.
    Formula: new_score = (1 - alpha) * prev_score + alpha * (evidence_score * 100)
    NOT Bayesian — uses a configurable weighted moving average.
    alpha = settings.MASTERY_ALPHA (default 0.3)
    """
    from app.models.models import MasteryRecord, MasteryHistory, MasteryTrend

    alpha = settings.MASTERY_ALPHA

    mastery = db.query(MasteryRecord).filter(
        MasteryRecord.concept_id == concept_id,
        MasteryRecord.user_id == user_id,
        MasteryRecord.project_id == project_id,
    ).first()

    evidence_score_100 = evidence_score * 100  # Convert 0-1 → 0-100

    if not mastery:
        mastery = MasteryRecord(
            id=uuid.uuid4(),
            concept_id=concept_id,
            user_id=user_id,
            project_id=project_id,
            score=evidence_score_100,
            evidence_count=1,
            trend=MasteryTrend.insufficient_data,
        )
        db.add(mastery)
    else:
        prev_score = mastery.score
        mastery.score = (1 - alpha) * prev_score + alpha * evidence_score_100
        mastery.evidence_count += 1
        mastery.updated_at = datetime.now(timezone.utc)

    db.flush()

    # Log history point
    history = MasteryHistory(
        id=uuid.uuid4(),
        mastery_record_id=mastery.id,
        score=mastery.score,
        evidence_type=evidence_type,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(history)

    # Calculate trend from last 3 history points
    db.flush()
    history_points = db.query(MasteryHistory).filter(
        MasteryHistory.mastery_record_id == mastery.id
    ).order_by(MasteryHistory.recorded_at.desc()).limit(3).all()

    if len(history_points) >= 3:
        scores = [h.score for h in history_points]  # most recent first
        if scores[0] > scores[-1] + 5:
            mastery.trend = MasteryTrend.improving
        elif scores[0] < scores[-1] - 5:
            mastery.trend = MasteryTrend.needs_attention
        else:
            mastery.trend = MasteryTrend.stable
    elif len(history_points) == 2:
        if history_points[0].score > history_points[1].score + 3:
            mastery.trend = MasteryTrend.improving
        elif history_points[0].score < history_points[1].score - 3:
            mastery.trend = MasteryTrend.needs_attention
        else:
            mastery.trend = MasteryTrend.stable

    return mastery


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.learning_workflow.process_quiz_completion",
)
def process_quiz_completion(self, assessment_id: str, user_id: str, project_id: str):
    """
    Post-quiz learning workflow.
    Updates mastery, learning context, and generates recommendations.
    """
    from app.models.models import (
        Assessment, AssessmentStatus, Question, Answer, QuestionType,
        Concept, MasteryRecord, LearningContext, Recommendation,
        RecommendationStatus, Event
    )

    db = get_sync_db()
    try:
        # Verify ownership
        assessment = db.query(Assessment).filter(
            Assessment.id == uuid.UUID(assessment_id),
            Assessment.user_id == uuid.UUID(user_id),
            Assessment.project_id == uuid.UUID(project_id),
        ).first()

        if not assessment:
            return

        questions = assessment.questions
        if not questions:
            return

        # ── Step 1: Update mastery for each answered concept ──
        concept_scores = {}  # concept_id → list of scores

        for question in questions:
            if not question.answer or not question.concept_id:
                continue

            answer = question.answer
            if question.question_type == QuestionType.mcq:
                score = 1.0 if answer.is_correct else 0.0
            else:
                score = answer.ai_score if answer.ai_score is not None else 0.5

            if question.concept_id not in concept_scores:
                concept_scores[question.concept_id] = []
            concept_scores[question.concept_id].append(score)

        # Average scores per concept and update mastery
        updated_masteries = []
        for concept_id, scores in concept_scores.items():
            avg_score = sum(scores) / len(scores)
            mastery = update_mastery_for_concept(
                db, concept_id,
                uuid.UUID(user_id), uuid.UUID(project_id),
                avg_score, "quiz"
            )
            updated_masteries.append(mastery)

        db.commit()

        # ── Step 2: Update learning context ──
        context = db.query(LearningContext).filter(
            LearningContext.project_id == uuid.UUID(project_id),
            LearningContext.user_id == uuid.UUID(user_id),
        ).first()

        if not context:
            context = LearningContext(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                user_id=uuid.UUID(user_id),
                known_strengths=[],
                known_weaknesses=[],
                repeated_mistakes=[],
            )
            db.add(context)

        # Identify weak concepts (score < 50)
        all_mastery = db.query(MasteryRecord).filter(
            MasteryRecord.project_id == uuid.UUID(project_id),
            MasteryRecord.user_id == uuid.UUID(user_id),
        ).all()

        weak_concepts = []
        strong_concepts = []
        for m in all_mastery:
            concept = db.query(Concept).filter(Concept.id == m.concept_id).first()
            if concept:
                if m.score < 50:
                    weak_concepts.append({"name": concept.name, "score": m.score})
                elif m.score > 75:
                    strong_concepts.append({"name": concept.name, "score": m.score})

        context.known_weaknesses = weak_concepts
        context.known_strengths = strong_concepts

        # Track repeated mistakes (wrong on same concept 2+ times)
        repeated = []
        for q in questions:
            if q.answer and q.concept_id and not q.answer.is_correct:
                concept = db.query(Concept).filter(Concept.id == q.concept_id).first()
                if concept:
                    wrong_count = 0
                    for prev_q in db.query(Question).filter(
                        Question.concept_id == q.concept_id
                    ).all():
                        if prev_q.answer and not prev_q.answer.is_correct:
                            wrong_count += 1
                    if wrong_count >= 2:
                        repeated.append({"concept": concept.name, "wrong_count": wrong_count})

        context.repeated_mistakes = repeated
        context.updated_at = datetime.now(timezone.utc)
        db.commit()

        # ── Step 3: Generate recommendation for learner progression ──
        project = assessment.project
        weak_names = [c["name"] for c in weak_concepts[:3]]
        repeat_names = [m["concept"] for m in repeated[:2]]
        strong_names = [s["name"] for s in strong_concepts[:3]]

        prompt = f"""You are an AI learning advisor. Based on this learner's assessment results, generate ONE specific, actionable recommendation.

Project learning goal: {project.learning_goal or 'Not specified'}
Weak concepts (score < 50%): {', '.join(weak_names) if weak_names else 'None (performing well)'}
Strong concepts (score >= 70%): {', '.join(strong_names) if strong_names else 'In progress'}
Repeated mistakes on: {', '.join(repeat_names) if repeat_names else 'None'}
Recent quiz score: {assessment.score_pct:.0f}% ({assessment.correct_count}/{assessment.total_questions} correct)

Generate ONE recommendation as JSON:
{{
  "recommendation_type": "review_concept|practice_quiz|study_material|advance_topic",
  "content": "Clear, specific, actionable advice (2-3 sentences)",
  "reason": "Why this is the most important next step"
}}

Return ONLY the JSON object."""

        try:
            rec_text, _ = gemini_client.generate(prompt, temperature=0.3)
            json_match = re.search(r'\{.*\}', rec_text, re.DOTALL)
            if json_match:
                rec_data = json.loads(json_match.group())
                # Validate structure
                rec_type = str(rec_data.get("recommendation_type", "review_concept"))
                rec_content = str(rec_data.get("content", "")).strip()
                rec_reason = str(rec_data.get("reason", "")).strip()

                if rec_content:
                    # Deactivate old active recommendations
                    db.query(Recommendation).filter(
                        Recommendation.project_id == uuid.UUID(project_id),
                        Recommendation.user_id == uuid.UUID(user_id),
                        Recommendation.status == RecommendationStatus.active,
                    ).update({"status": RecommendationStatus.dismissed})

                    rec = Recommendation(
                        id=uuid.uuid4(),
                        project_id=uuid.UUID(project_id),
                        user_id=uuid.UUID(user_id),
                        recommendation_type=rec_type,
                        content=rec_content,
                        reason=rec_reason,
                        status=RecommendationStatus.active,
                    )
                    db.add(rec)

                    event = Event(
                        id=uuid.uuid4(),
                        user_id=uuid.UUID(user_id),
                        project_id=uuid.UUID(project_id),
                        event_type="recommendation_generated",
                        payload={"assessment_id": assessment_id, "type": rec_type},
                    )
                    db.add(event)
                    db.commit()
        except Exception as e:
            print(f"[learning_workflow] Recommendation generation via Gemini failed ({e}), creating adaptive recommendation")
            rec_type = "review_concept" if weak_concepts else "practice_quiz"
            target_name = weak_names[0] if weak_names else (repeat_names[0] if repeat_names else "core topics")
            rec_content = f"Focus your study session on reviewing {target_name}. Revisiting key definitions and working through examples will solidify your understanding."
            rec_reason = f"Your mastery level for {target_name} indicates areas requiring reinforcement."

            # Deactivate old active recommendations
            db.query(Recommendation).filter(
                Recommendation.project_id == uuid.UUID(project_id),
                Recommendation.user_id == uuid.UUID(user_id),
                Recommendation.status == RecommendationStatus.active,
            ).update({"status": RecommendationStatus.dismissed})

            rec = Recommendation(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                user_id=uuid.UUID(user_id),
                recommendation_type=rec_type,
                content=rec_content,
                reason=rec_reason,
                status=RecommendationStatus.active,
            )
            db.add(rec)

            event = Event(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                project_id=uuid.UUID(project_id),
                event_type="recommendation_generated",
                payload={"assessment_id": assessment_id, "type": rec_type},
            )
            db.add(event)
            db.commit()

        print(f"[learning_workflow] Assessment {assessment_id} processed: "
              f"{len(concept_scores)} concepts updated")

    except Exception as exc:
        db.rollback()
        print(f"[learning_workflow] ERROR: {exc}")
        if hasattr(self, 'retry'):
            raise self.retry(exc=exc)
        else:
            raise exc
    finally:
        db.close()


def execute_learning_workflow_sync(assessment_id: str, user_id: str, project_id: str):
    """Direct synchronous runner for post-quiz learning workflow."""
    from app.models.models import (
        Assessment, Question, Concept, LearningContext,
        Recommendation, RecommendationStatus, Event
    )
    db = get_sync_db()
    try:
        assessment = db.query(Assessment).filter(
            Assessment.id == uuid.UUID(assessment_id),
            Assessment.user_id == uuid.UUID(user_id),
            Assessment.project_id == uuid.UUID(project_id),
        ).first()

        if not assessment:
            return

        questions = db.query(Question).filter(
            Question.assessment_id == assessment.id
        ).all()

        concept_scores = {}
        for q in questions:
            if not q.concept_id or not q.answer:
                continue
            c_id = q.concept_id
            if c_id not in concept_scores:
                concept_scores[c_id] = []
            score_val = q.answer.ai_score if q.answer.ai_score is not None else (1.0 if q.answer.is_correct else 0.0)
            concept_scores[c_id].append(score_val)

        for c_id, scores in concept_scores.items():
            avg_evidence = sum(scores) / len(scores)
            update_mastery_for_concept(
                db=db,
                concept_id=c_id,
                user_id=uuid.UUID(user_id),
                project_id=uuid.UUID(project_id),
                evidence_score=avg_evidence,
                evidence_type="quiz",
            )
        db.commit()

        context = db.query(LearningContext).filter(
            LearningContext.project_id == uuid.UUID(project_id),
            LearningContext.user_id == uuid.UUID(user_id),
        ).first()

        if not context:
            context = LearningContext(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                user_id=uuid.UUID(user_id),
                known_strengths=[],
                known_weaknesses=[],
                repeated_mistakes=[],
            )
            db.add(context)
            db.flush()

        from app.models.models import MasteryRecord
        mastery_rows = db.query(MasteryRecord).filter(
            MasteryRecord.project_id == uuid.UUID(project_id),
            MasteryRecord.user_id == uuid.UUID(user_id),
        ).all()

        strong_concepts = []
        weak_concepts = []

        for m in mastery_rows:
            concept = db.query(Concept).filter(Concept.id == m.concept_id).first()
            if not concept:
                continue
            if m.score >= 70.0:
                strong_concepts.append({"name": concept.name, "score": m.score})
            elif m.score < 50.0:
                weak_concepts.append({"name": concept.name, "score": m.score})

        context.known_strengths = strong_concepts
        context.known_weaknesses = weak_concepts

        repeated = []
        for q in questions:
            if q.answer and q.concept_id and not q.answer.is_correct:
                concept = db.query(Concept).filter(Concept.id == q.concept_id).first()
                if concept:
                    wrong_count = 0
                    for prev_q in db.query(Question).filter(Question.concept_id == q.concept_id).all():
                        if prev_q.answer and not prev_q.answer.is_correct:
                            wrong_count += 1
                    if wrong_count >= 2:
                        repeated.append({"concept": concept.name, "wrong_count": wrong_count})

        context.repeated_mistakes = repeated
        context.updated_at = datetime.now(timezone.utc)
        db.commit()

        project = assessment.project
        weak_names = [c["name"] for c in weak_concepts[:3]]
        repeat_names = [m["concept"] for m in repeated[:2]]
        strong_names = [s["name"] for s in strong_concepts[:3]]

        prompt = f"""You are an AI learning advisor. Based on this learner's assessment results, generate ONE specific, actionable recommendation.

Project learning goal: {project.learning_goal or 'Not specified'}
Weak concepts (score < 50%): {', '.join(weak_names) if weak_names else 'None (performing well)'}
Strong concepts (score >= 70%): {', '.join(strong_names) if strong_names else 'In progress'}
Repeated mistakes on: {', '.join(repeat_names) if repeat_names else 'None'}
Recent quiz score: {assessment.score_pct:.0f}% ({assessment.correct_count}/{assessment.total_questions} correct)

Generate ONE recommendation as JSON:
{{
  "recommendation_type": "review_concept|practice_quiz|study_material|advance_topic",
  "content": "Clear, specific, actionable advice (2-3 sentences)",
  "reason": "Why this is the most important next step"
}}

Return ONLY the JSON object."""

        try:
            rec_text, _ = gemini_client.generate(prompt, temperature=0.3)
            json_match = re.search(r'\{.*\}', rec_text, re.DOTALL)
            if json_match:
                rec_data = json.loads(json_match.group())
                rec_type = str(rec_data.get("recommendation_type", "review_concept"))
                rec_content = str(rec_data.get("content", "")).strip()
                rec_reason = str(rec_data.get("reason", "")).strip()

                if rec_content:
                    db.query(Recommendation).filter(
                        Recommendation.project_id == uuid.UUID(project_id),
                        Recommendation.user_id == uuid.UUID(user_id),
                        Recommendation.status == RecommendationStatus.active,
                    ).update({"status": RecommendationStatus.dismissed})

                    rec = Recommendation(
                        id=uuid.uuid4(),
                        project_id=uuid.UUID(project_id),
                        user_id=uuid.UUID(user_id),
                        recommendation_type=rec_type,
                        content=rec_content,
                        reason=rec_reason,
                        status=RecommendationStatus.active,
                    )
                    db.add(rec)
                    event = Event(
                        id=uuid.uuid4(),
                        user_id=uuid.UUID(user_id),
                        project_id=uuid.UUID(project_id),
                        event_type="recommendation_generated",
                        payload={"assessment_id": assessment_id, "type": rec_type},
                    )
                    db.add(event)
                    db.commit()
        except Exception as e:
            print(f"[learning_workflow_sync] Recommendation generation via Gemini failed ({e}), creating adaptive fallback recommendation")
            rec_type = "review_concept" if weak_concepts else "practice_quiz"
            target_name = weak_names[0] if weak_names else (repeat_names[0] if repeat_names else "core topics")
            rec_content = f"Focus your study session on reviewing {target_name}. Revisiting key definitions and working through practical queries will solidify your understanding."
            rec_reason = f"Your mastery level for {target_name} indicates areas requiring reinforcement."

            db.query(Recommendation).filter(
                Recommendation.project_id == uuid.UUID(project_id),
                Recommendation.user_id == uuid.UUID(user_id),
                Recommendation.status == RecommendationStatus.active,
            ).update({"status": RecommendationStatus.dismissed})

            rec = Recommendation(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                user_id=uuid.UUID(user_id),
                recommendation_type=rec_type,
                content=rec_content,
                reason=rec_reason,
                status=RecommendationStatus.active,
            )
            db.add(rec)
            event = Event(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                project_id=uuid.UUID(project_id),
                event_type="recommendation_generated",
                payload={"assessment_id": assessment_id, "type": rec_type},
            )
            db.add(event)
            db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[learning_workflow_sync] Error: {exc}")
    finally:
        db.close()


# Export alias for worker/quiz compatibility
post_quiz_learning_workflow = process_quiz_completion


