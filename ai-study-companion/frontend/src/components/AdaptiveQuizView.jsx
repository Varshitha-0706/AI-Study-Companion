import React, { useState } from 'react';
import { 
  Award, CheckCircle2, XCircle, ArrowRight, Play, 
  RotateCcw, Sparkles, Brain, Target, AlertCircle,
  HelpCircle, Check, AlertTriangle, Info
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { quizApi } from '../services/api';

export default function AdaptiveQuizView({ project, onQuizCompleted }) {
  const [quiz, setQuiz] = useState(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [openAnswer, setOpenAnswer] = useState('');
  const [evaluating, setEvaluating] = useState(false);
  const [startingQuiz, setStartingQuiz] = useState(false);
  const [currentResult, setCurrentResult] = useState(null);
  const [completedSummary, setCompletedSummary] = useState(null);
  const [questionCount, setQuestionCount] = useState(5);
  const [error, setError] = useState(null);

  const handleStartQuiz = async () => {
    if (!project) return;
    setStartingQuiz(true);
    setError(null);
    setCurrentResult(null);
    setCompletedSummary(null);
    setSelectedOption(null);
    setOpenAnswer('');
    setCurrentIdx(0);

    try {
      const data = await quizApi.startAdaptiveQuiz(project.id, questionCount);
      if (!data || !data.questions || data.questions.length === 0) {
        throw new Error("No quiz questions were generated. Please make sure project materials have been uploaded and processed.");
      }
      setQuiz(data);
    } catch (err) {
      setError(err.message || 'Could not start quiz. Please try again.');
    } finally {
      setStartingQuiz(false);
    }
  };

  const currentQuestion = quiz?.questions?.[currentIdx];

  const handleSubmitAnswer = async () => {
    if (!currentQuestion || evaluating) return;
    setError(null);

    if (currentQuestion.question_type === 'mcq' && selectedOption === null) {
      setError('Please select an option before submitting.');
      return;
    }
    if (currentQuestion.question_type === 'open_ended' && !openAnswer.trim()) {
      setError('Please type your response before submitting.');
      return;
    }

    setEvaluating(true);
    try {
      const res = await quizApi.submitAnswer(
        quiz.id,
        currentQuestion.id,
        selectedOption,
        openAnswer
      );
      setCurrentResult(res);
    } catch (err) {
      setError(`Evaluation error: ${err.message}`);
    } finally {
      setEvaluating(false);
    }
  };

  const handleNextQuestion = async () => {
    setError(null);
    setCurrentResult(null);
    setSelectedOption(null);
    setOpenAnswer('');

    if (currentIdx + 1 < (quiz?.questions?.length || 0)) {
      setCurrentIdx((prev) => prev + 1);
    } else {
      // Complete quiz
      try {
        const summary = await quizApi.completeQuiz(quiz.id);
        setCompletedSummary(summary);
        // Confetti celebration
        try {
          confetti({
            particleCount: 100,
            spread: 70,
            origin: { y: 0.6 }
          });
        } catch (e) {}
        if (onQuizCompleted) onQuizCompleted();
      } catch (err) {
        setError(`Completion failed: ${err.message}`);
      }
    }
  };

  // Initial State: Start screen or Completed Summary
  if (!quiz || completedSummary) {
    return (
      <div style={{ maxWidth: '680px', margin: '30px auto', width: '100%' }}>
        {error && (
          <div style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            color: 'var(--accent-rose)',
            fontSize: '0.88rem',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
          }}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {completedSummary ? (
          /* Completion Card */
          <div className="glass-panel" style={{ padding: '36px 30px', textAlign: 'center' }}>
            <div style={{
              width: '68px',
              height: '68px',
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.15)',
              border: '2px solid rgba(16, 185, 129, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
            }}>
              <Award size={36} color="var(--accent-emerald)" />
            </div>

            <h2 style={{ fontSize: '1.6rem', marginBottom: '8px' }}>Practice Session Complete!</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '24px' }}>
              Your evidence-weighted mastery levels, learning context, and adaptive recommendations have been updated.
            </p>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '14px',
              marginBottom: '28px',
            }}>
              <div style={{ padding: '16px', background: 'rgba(30, 41, 59, 0.6)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Final Score</div>
                <div style={{ fontSize: '1.9rem', fontWeight: 800, color: (completedSummary.score_pct || 0) >= 60 ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
                  {Math.round(completedSummary.score_pct || 0)}%
                </div>
              </div>

              <div style={{ padding: '16px', background: 'rgba(30, 41, 59, 0.6)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Questions Evaluated</div>
                <div style={{ fontSize: '1.9rem', fontWeight: 800, color: 'var(--primary)' }}>
                  {completedSummary.total_questions || quiz?.questions?.length || 0}
                </div>
              </div>
            </div>

            <button className="btn-primary" onClick={handleStartQuiz} style={{ padding: '12px 28px', margin: '0 auto' }}>
              <RotateCcw size={16} /> Start Another Adaptive Quiz
            </button>
          </div>
        ) : (
          /* Start Screen */
          <div className="glass-panel" style={{ padding: '40px 32px', textAlign: 'center' }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'rgba(99, 102, 241, 0.15)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
            }}>
              <Brain size={32} color="var(--primary)" />
            </div>

            <h2 style={{ fontSize: '1.5rem', marginBottom: '8px' }}>Adaptive Practice Arena</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6, marginBottom: '24px' }}>
              Questions are adaptively selected based on your mastery gaps and past mistakes. 
              Open-ended answers receive instant qualitative Gemini AI evaluation with rubric feedback.
            </p>

            {/* Question count selector */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', marginBottom: '28px' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Question Count:</span>
              {[3, 5, 10].map((count) => (
                <button
                  key={count}
                  type="button"
                  onClick={() => setQuestionCount(count)}
                  style={{
                    padding: '6px 16px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid',
                    borderColor: questionCount === count ? 'var(--primary)' : 'var(--border-subtle)',
                    background: questionCount === count ? 'var(--primary)' : 'rgba(30, 41, 59, 0.6)',
                    color: questionCount === count ? '#fff' : 'var(--text-secondary)',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    transition: 'all var(--transition-fast)'
                  }}
                >
                  {count}
                </button>
              ))}
            </div>

            <button
              className="btn-primary"
              onClick={handleStartQuiz}
              disabled={startingQuiz}
              style={{ padding: '12px 32px', fontSize: '1rem', margin: '0 auto' }}
            >
              <Play size={18} />
              {startingQuiz ? 'Generating Adaptive Questions...' : 'Start Practice Quiz'}
            </button>
          </div>
        )}
      </div>
    );
  }

  // Active Question Card
  const questionTitle = currentQuestion?.question_text || currentQuestion?.content || "Practice Question";
  const scorePercent = currentResult 
    ? Math.round((currentResult.score ?? currentResult.ai_score ?? (currentResult.is_correct ? 1 : 0)) * 100) 
    : 0;

  return (
    <div style={{ maxWidth: '740px', margin: '20px auto', width: '100%' }}>
      {/* Progress header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontWeight: 600, fontSize: '0.92rem' }}>
            Question {currentIdx + 1} of {quiz.questions.length}
          </span>
          {currentQuestion.concept_name && (
            <span className="glow-pill glow-pill-indigo" style={{ fontSize: '0.75rem' }}>
              {currentQuestion.concept_name}
            </span>
          )}
        </div>

        <span style={{
          fontSize: '0.75rem',
          padding: '4px 10px',
          borderRadius: '4px',
          background: 'rgba(30, 41, 59, 0.6)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-muted)',
          fontWeight: 500
        }}>
          {currentQuestion.question_type === 'mcq' ? 'Multiple Choice' : 'Open Response'}
        </span>
      </div>

      {error && (
        <div style={{
          padding: '10px 14px',
          borderRadius: 'var(--radius-md)',
          background: 'rgba(244, 63, 94, 0.15)',
          border: '1px solid rgba(244, 63, 94, 0.3)',
          color: 'var(--accent-rose)',
          fontSize: '0.85rem',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Question Card */}
      <div className="glass-panel" style={{ padding: '28px', marginBottom: '20px' }}>
        <h3 style={{ fontSize: '1.15rem', lineHeight: 1.55, marginBottom: '22px', fontWeight: 600 }}>
          {questionTitle}
        </h3>

        {/* Multiple Choice Options */}
        {currentQuestion.question_type === 'mcq' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {currentQuestion.options?.map((opt, idx) => {
              const isSelected = selectedOption === idx;
              return (
                <div
                  key={idx}
                  onClick={() => !currentResult && !evaluating && setSelectedOption(idx)}
                  style={{
                    padding: '13px 16px',
                    borderRadius: 'var(--radius-md)',
                    background: isSelected ? 'rgba(99, 102, 241, 0.2)' : 'rgba(30, 41, 59, 0.5)',
                    border: `1px solid ${isSelected ? 'var(--primary)' : 'var(--border-subtle)'}`,
                    cursor: (currentResult || evaluating) ? 'default' : 'pointer',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  <div style={{
                    width: '26px',
                    height: '26px',
                    borderRadius: '50%',
                    background: isSelected ? 'var(--primary)' : 'rgba(148, 163, 184, 0.15)',
                    color: isSelected ? '#fff' : 'var(--text-secondary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: '0.8rem',
                    flexShrink: 0,
                    marginTop: '1px'
                  }}>
                    {String.fromCharCode(65 + idx)}
                  </div>
                  <span style={{ fontSize: '0.9rem', color: isSelected ? '#fff' : 'var(--text-primary)', lineHeight: 1.5 }}>
                    {opt}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Open Ended Textarea */}
        {currentQuestion.question_type === 'open_ended' && (
          <div>
            <textarea
              rows={4}
              placeholder="Type your comprehensive explanation or answer in your own words..."
              className="input-field"
              value={openAnswer}
              onChange={(e) => setOpenAnswer(e.target.value)}
              disabled={!!currentResult || evaluating}
              style={{ resize: 'vertical', lineHeight: 1.5, width: '100%' }}
            />
          </div>
        )}

        {/* Evaluation Feedback Card */}
        {currentResult && (
          <div style={{
            marginTop: '22px',
            padding: '18px',
            borderRadius: 'var(--radius-md)',
            background: currentResult.is_correct ? 'rgba(16, 185, 129, 0.10)' : 'rgba(244, 63, 94, 0.10)',
            border: `1px solid ${currentResult.is_correct ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              {currentResult.is_correct ? (
                <>
                  <CheckCircle2 size={18} color="var(--accent-emerald)" />
                  <span style={{ fontWeight: 700, color: 'var(--accent-emerald)', fontSize: '0.92rem' }}>
                    Correct! (Score: {scorePercent}%)
                  </span>
                </>
              ) : (
                <>
                  <XCircle size={18} color="var(--accent-rose)" />
                  <span style={{ fontWeight: 700, color: 'var(--accent-rose)', fontSize: '0.92rem' }}>
                    Needs Improvement (Score: {scorePercent}%)
                  </span>
                </>
              )}
            </div>

            {/* Main Qualitative Feedback / Explanation */}
            <p style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: '12px' }}>
              {currentResult.feedback || currentResult.ai_feedback || currentResult.explanation || 'Answer evaluated by AI tutor.'}
            </p>

            {/* Correct Answer Display for MCQ if incorrect */}
            {currentQuestion.question_type === 'mcq' && !currentResult.is_correct && currentResult.correct_answer && (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                <strong style={{ color: 'var(--accent-emerald)' }}>Correct Option:</strong> {currentResult.correct_answer}
              </div>
            )}

            {/* Qualitative Points Breakdown */}
            {currentResult.understood_correctly?.length > 0 && (
              <div style={{ marginTop: '10px', fontSize: '0.83rem' }}>
                <div style={{ fontWeight: 600, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '4px' }}>
                  <Check size={14} /> Concepts Understood:
                </div>
                <ul style={{ margin: '0 0 8px 18px', padding: 0, color: 'var(--text-secondary)' }}>
                  {currentResult.understood_correctly.map((pt, i) => (
                    <li key={i} style={{ marginBottom: '2px' }}>{pt}</li>
                  ))}
                </ul>
              </div>
            )}

            {currentResult.missing_concepts?.length > 0 && (
              <div style={{ marginTop: '8px', fontSize: '0.83rem' }}>
                <div style={{ fontWeight: 600, color: 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '4px' }}>
                  <AlertTriangle size={14} /> Concepts to Reinforce:
                </div>
                <ul style={{ margin: '0 0 8px 18px', padding: 0, color: 'var(--text-secondary)' }}>
                  {currentResult.missing_concepts.map((pt, i) => (
                    <li key={i} style={{ marginBottom: '2px' }}>{pt}</li>
                  ))}
                </ul>
              </div>
            )}

            {currentResult.misconceptions?.length > 0 && (
              <div style={{ marginTop: '8px', fontSize: '0.83rem' }}>
                <div style={{ fontWeight: 600, color: 'var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '4px' }}>
                  <Info size={14} /> Identified Misconceptions:
                </div>
                <ul style={{ margin: '0 0 8px 18px', padding: 0, color: 'var(--text-secondary)' }}>
                  {currentResult.misconceptions.map((pt, i) => (
                    <li key={i} style={{ marginBottom: '2px' }}>{pt}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Action Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
          {!currentResult ? (
            <button
              className="btn-primary"
              onClick={handleSubmitAnswer}
              disabled={evaluating}
              style={{ padding: '10px 24px' }}
            >
              {evaluating ? 'Evaluating Answer...' : 'Submit Answer'}
            </button>
          ) : (
            <button
              className="btn-primary"
              onClick={handleNextQuestion}
              style={{ padding: '10px 24px' }}
            >
              {currentIdx + 1 < quiz.questions.length ? 'Next Question' : 'Complete Quiz & View Results'}
              <ArrowRight size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
