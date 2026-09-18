import React from 'react';
import { 
  Play, TrendingUp, Upload, 
  Target, Sparkles, Lightbulb, ArrowRight
} from 'lucide-react';

export default function ProjectDashboard({ 
  dashboardData, 
  project, 
  onNavigateTab 
}) {
  const stats = dashboardData?.project || {};
  const topConcepts = dashboardData?.top_concepts || [];
  const latestRec = dashboardData?.latest_recommendation;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '26px' }}>
      {/* Learning Goal Banner */}
      <div className="glass-panel" style={{
        padding: '24px 28px',
        background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(168, 85, 247, 0.08) 100%)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', marginBottom: '8px' }}>
              <Target size={18} />
              <span style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Primary Learning Goal
              </span>
            </div>
            <h2 style={{ fontSize: '1.4rem', marginBottom: '8px', color: '#fff' }}>
              {project?.learning_goal || 'Define a learning goal to focus your AI companion.'}
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', maxWidth: '600px', lineHeight: 1.5 }}>
              {project?.description || 'Contextual study space for this subject area.'}
            </p>
          </div>

          <button 
            className="btn-primary"
            onClick={() => onNavigateTab('tutor')}
            style={{ padding: '10px 20px', flexShrink: 0 }}
          >
            <Sparkles size={16} /> Open Tutor Chat
          </button>
        </div>
      </div>

      {/* Recommended Next Step Banner (PRD Page 5) */}
      {latestRec && (
        <div className="glass-panel" style={{
          padding: '16px 20px',
          background: 'rgba(245, 158, 11, 0.08)',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.2)', color: 'var(--accent-amber)' }}>
              <Lightbulb size={20} />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--accent-amber)' }}>
                Recommended Next Step ({latestRec.type || 'Study Action'})
              </div>
              <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', marginTop: '2px' }}>
                {latestRec.content}
              </div>
            </div>
          </div>
          <button
            className="btn-secondary"
            onClick={() => onNavigateTab(latestRec.type === 'take_quiz' ? 'quiz' : 'mastery')}
            style={{ fontSize: '0.8rem', padding: '6px 14px', flexShrink: 0 }}
          >
            Take Action <ArrowRight size={14} />
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
            Avg Mastery
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
            {dashboardData?.mastery_avg ? `${Math.round(dashboardData.mastery_avg)}%` : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Evidence weighted
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
            Extracted Concepts
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--primary)' }}>
            {stats.concept_count || topConcepts.length || 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Vector indexed
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
            Study Materials
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>
            {stats.material_count || stats.materials_count || 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            PDF documents
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
            7-Day Activity
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-purple)' }}>
            {dashboardData?.activity_count_7d || 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Interactions logged
          </div>
        </div>
      </div>

      {/* Quick Launch Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        <div 
          className="glass-panel glass-panel-hover" 
          onClick={() => onNavigateTab('quiz')}
          style={{ padding: '22px', cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
            <div style={{ padding: '10px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)' }}>
              <Play size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem' }}>Practice Arena</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Adaptive quizzes targeted at gaps</p>
            </div>
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Generate multiple choice or open-ended conceptual questions evaluated dynamically by Gemini.
          </p>
        </div>

        <div 
          className="glass-panel glass-panel-hover" 
          onClick={() => onNavigateTab('materials')}
          style={{ padding: '22px', cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
            <div style={{ padding: '10px', borderRadius: '10px', background: 'rgba(6, 182, 212, 0.15)', color: 'var(--accent-cyan)' }}>
              <Upload size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem' }}>Upload Materials</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Expand your knowledge base</p>
            </div>
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Upload course syllabus notes, textbook excerpts, and slides to ground the RAG pipeline.
          </p>
        </div>

        <div 
          className="glass-panel glass-panel-hover" 
          onClick={() => onNavigateTab('mastery')}
          style={{ padding: '22px', cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
            <div style={{ padding: '10px', borderRadius: '10px', background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
              <TrendingUp size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem' }}>Mastery & Growth</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Track concept velocity</p>
            </div>
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Inspect concept breakdown bars, trend changes, and actionable study recommendations.
          </p>
        </div>
      </div>
    </div>
  );
}
