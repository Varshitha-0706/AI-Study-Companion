import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, ArrowUpRight, ArrowRight, AlertTriangle, 
  Sparkles, CheckCircle2, BookOpen, Lightbulb, Compass,
  Brain, Play, ShieldAlert, Award, HelpCircle, Flame, BarChart2
} from 'lucide-react';
import { masteryApi } from '../services/api';

export default function MasteryView({ project, onSelectConceptToPractice }) {
  const [concepts, setConcepts] = useState([]);
  const [growthData, setGrowthData] = useState(null);
  const [contextData, setContextData] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('all'); // 'all' | 'improving' | 'needs_attention' | 'insights'

  const fetchMasteryData = async () => {
    if (!project) return;
    setLoading(true);
    try {
      const [overviewData, recsData, growthRes, ctxRes] = await Promise.all([
        masteryApi.getOverview(project.id).catch(() => []),
        masteryApi.getRecommendations(project.id).catch(() => []),
        masteryApi.getGrowth(project.id).catch(() => null),
        masteryApi.getContext(project.id).catch(() => null),
      ]);
      setConcepts(overviewData || []);
      setRecommendations(recsData || []);
      setGrowthData(growthRes);
      setContextData(ctxRes);
    } catch (err) {
      console.error('Failed to load mastery data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMasteryData();
  }, [project?.id]);

  const getTrendBadge = (trend) => {
    switch (trend) {
      case 'improving':
        return (
          <span className="glow-pill glow-pill-emerald" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <ArrowUpRight size={12} /> Improving
          </span>
        );
      case 'needs_attention':
        return (
          <span className="glow-pill glow-pill-rose" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <AlertTriangle size={12} /> Needs Focus
          </span>
        );
      case 'stable':
        return (
          <span className="glow-pill glow-pill-amber" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <ArrowRight size={12} /> Stable
          </span>
        );
      default:
        return (
          <span className="glow-pill" style={{ background: 'rgba(148, 163, 184, 0.1)', color: 'var(--text-muted)' }}>
            Insufficient Data
          </span>
        );
    }
  };

  const filteredConcepts = concepts.filter((c) => {
    if (activeFilter === 'improving') return c.trend === 'improving';
    if (activeFilter === 'needs_attention') return c.trend === 'needs_attention' || (c.score !== null && c.score < 50);
    return true;
  });

  const overallMastery = growthData?.overall_mastery ?? (
    concepts.filter(c => c.score !== null).length > 0
      ? Math.round(concepts.filter(c => c.score !== null).reduce((acc, c) => acc + c.score, 0) / concepts.filter(c => c.score !== null).length)
      : 0
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Top Header Summary & Growth Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '16px'
      }}>
        {/* Overall Mastery Card */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--primary)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Overall Mastery
            </span>
            <Award size={18} color="var(--primary)" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: overallMastery >= 65 ? 'var(--accent-emerald)' : 'var(--primary)', marginBottom: '6px' }}>
            {Math.round(overallMastery)}%
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Weighted moving average ($\alpha=0.3$) across concepts
          </div>
        </div>

        {/* Improving Concepts Card */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-emerald)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Improving Concepts
            </span>
            <TrendingUp size={18} color="var(--accent-emerald)" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--accent-emerald)', marginBottom: '6px' }}>
            {growthData?.improving?.length ?? concepts.filter(c => c.trend === 'improving').length}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Consistent positive momentum on assessments
          </div>
        </div>

        {/* Needs Attention Card */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-rose)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Needs Focus
            </span>
            <AlertTriangle size={18} color="var(--accent-rose)" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--accent-rose)', marginBottom: '6px' }}>
            {growthData?.needs_attention?.length ?? concepts.filter(c => c.trend === 'needs_attention' || (c.score !== null && c.score < 50)).length}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Mastery &lt; 50% or negative trend line
          </div>
        </div>

        {/* Total Concepts Discovered */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-cyan)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Concepts Discovered
            </span>
            <BookOpen size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--accent-cyan)', marginBottom: '6px' }}>
            {concepts.length}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Extracted from uploaded project materials
          </div>
        </div>
      </div>

      {/* AI Learning Recommendations */}
      {recommendations.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Lightbulb size={18} color="var(--accent-amber)" />
            <h3 style={{ fontSize: '1.15rem' }}>AI Adaptive Recommendations</h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '14px' }}>
            {recommendations.map((rec) => (
              <div 
                key={rec.id} 
                className="glass-panel" 
                style={{ 
                  padding: '18px 20px', 
                  borderLeft: '4px solid var(--accent-amber)',
                  background: 'rgba(30, 41, 59, 0.5)' 
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 700, color: 'var(--accent-amber)' }}>
                    {rec.recommendation_type || 'Study Action'}
                  </span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {new Date(rec.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: '8px' }}>
                  {rec.content}
                </p>
                {rec.reason && (
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                    Reason: {rec.reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Persistent Learning Context (Strengths, Weaknesses, Repeated Mistakes) */}
      {contextData && (contextData.known_strengths?.length > 0 || contextData.known_weaknesses?.length > 0 || contextData.repeated_mistakes?.length > 0) && (
        <div className="glass-panel" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Brain size={18} color="var(--primary)" />
            <h3 style={{ fontSize: '1.1rem' }}>Learner Context & Diagnostic Signals</h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
            {/* Strengths */}
            <div style={{ padding: '14px', borderRadius: 'var(--radius-md)', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--accent-emerald)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle2 size={15} /> Identified Strengths ({contextData.known_strengths?.length || 0})
              </div>
              {contextData.known_strengths?.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                  {contextData.known_strengths.map((s, idx) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>
                      {typeof s === 'object' ? `${s.name} (${Math.round(s.score)}%)` : s}
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Complete more quizzes to identify strengths</div>
              )}
            </div>

            {/* Weaknesses */}
            <div style={{ padding: '14px', borderRadius: 'var(--radius-md)', background: 'rgba(244, 63, 94, 0.08)', border: '1px solid rgba(244, 63, 94, 0.2)' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--accent-rose)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <AlertTriangle size={15} /> Areas for Reinforcement ({contextData.known_weaknesses?.length || 0})
              </div>
              {contextData.known_weaknesses?.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                  {contextData.known_weaknesses.map((w, idx) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>
                      {typeof w === 'object' ? `${w.name} (${Math.round(w.score)}%)` : w}
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>No critical knowledge gaps recorded</div>
              )}
            </div>

            {/* Repeated Mistakes */}
            <div style={{ padding: '14px', borderRadius: 'var(--radius-md)', background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--accent-amber)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <ShieldAlert size={15} /> Repeated Mistakes ({contextData.repeated_mistakes?.length || 0})
              </div>
              {contextData.repeated_mistakes?.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                  {contextData.repeated_mistakes.map((m, idx) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>
                      {typeof m === 'object' ? `${m.concept} (${m.wrong_count}x missed)` : m}
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>No repeated mistake patterns detected</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Concept Mastery Cards Section */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h3 style={{ fontSize: '1.15rem' }}>Evidence-Weighted Concept Mastery</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Real-time mastery tracking with adaptive moving average updates across practice sessions
            </p>
          </div>

          {/* Filter Pills */}
          <div style={{ display: 'flex', gap: '8px' }}>
            {[
              { id: 'all', label: `All (${concepts.length})` },
              { id: 'improving', label: `Improving (${concepts.filter(c => c.trend === 'improving').length})` },
              { id: 'needs_attention', label: `Needs Focus (${concepts.filter(c => c.trend === 'needs_attention' || (c.score !== null && c.score < 50)).length})` },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveFilter(tab.id)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid',
                  borderColor: activeFilter === tab.id ? 'var(--primary)' : 'var(--border-subtle)',
                  background: activeFilter === tab.id ? 'var(--primary)' : 'rgba(30, 41, 59, 0.5)',
                  color: activeFilter === tab.id ? '#fff' : 'var(--text-secondary)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)'
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            Calculating mastery weights & growth trends...
          </div>
        ) : concepts.length === 0 ? (
          <div className="glass-panel" style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No concepts extracted yet. Upload study materials to automatically discover core concepts and track your knowledge progression.
          </div>
        ) : filteredConcepts.length === 0 ? (
          <div className="glass-panel" style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No concepts match the selected filter.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {filteredConcepts.map((concept) => {
              const conceptName = concept.concept_name || concept.name || 'Unnamed Concept';
              const conceptId = concept.concept_id || concept.id;
              const hasScore = concept.score !== null && concept.score !== undefined;
              const score = hasScore ? Math.round(concept.score) : null;
              const scoreColor = score >= 75 ? 'var(--accent-emerald)' : (score >= 45 ? 'var(--accent-amber)' : 'var(--accent-rose)');

              return (
                <div key={conceptId} className="glass-panel glass-panel-hover" style={{ padding: '20px', display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#fff', flex: 1, paddingRight: '8px' }}>
                      {conceptName}
                    </div>
                    {getTrendBadge(concept.trend)}
                  </div>

                  {concept.description && (
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '16px', flex: 1 }}>
                      {concept.description}
                    </p>
                  )}

                  {/* Progress bar */}
                  <div style={{ marginBottom: '8px', marginTop: 'auto' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Mastery Level</span>
                      <span style={{ fontWeight: 700, color: hasScore ? scoreColor : 'var(--text-muted)' }}>
                        {hasScore ? `${score}%` : 'Not Evaluated'}
                      </span>
                    </div>
                    <div style={{
                      height: '7px',
                      borderRadius: 'var(--radius-full)',
                      background: 'rgba(30, 41, 59, 0.8)',
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%',
                        width: hasScore ? `${Math.min(100, Math.max(0, score))}%` : '0%',
                        background: hasScore ? scoreColor : 'transparent',
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 600ms cubic-bezier(0.4, 0, 0.2, 1)',
                      }} />
                    </div>
                  </div>

                  {/* Footer stats & Practice CTA */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
                    <span>Evidence: {concept.evidence_count || 0} answer{concept.evidence_count === 1 ? '' : 's'}</span>
                    {onSelectConceptToPractice && (
                      <button
                        type="button"
                        onClick={() => onSelectConceptToPractice(concept)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--primary)',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: 0,
                          fontSize: '0.75rem'
                        }}
                      >
                        <Play size={12} /> Practice
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
