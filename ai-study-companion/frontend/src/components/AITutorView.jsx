import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Bot, User, Sparkles, BookOpen, AlertTriangle, 
  Trash2, RefreshCw, FileText, CheckCircle2 
} from 'lucide-react';
import { tutorApi } from '../services/api';

export default function AITutorView({ project }) {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingHistory, setFetchingHistory] = useState(true);
  const [activeCitation, setActiveCitation] = useState(null);
  const messagesEndRef = useRef(null);

  const loadHistory = async () => {
    if (!project) return;
    setFetchingHistory(true);
    try {
      const data = await tutorApi.getHistory(project.id);
      setMessages(data || []);
    } catch (err) {
      console.error('Failed to load tutor history:', err);
    } finally {
      setFetchingHistory(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [project?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    const text = inputMessage.trim();
    if (!text || loading) return;

    // Optimistically append user message
    const userMsg = {
      id: 'temp-' + Date.now(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputMessage('');
    setLoading(true);

    try {
      const response = await tutorApi.sendMessage(project.id, text);
      setMessages((prev) => [...prev, response]);
    } catch (err) {
      alert(`Tutor error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Clear all conversation history with the AI Tutor for this project?')) return;
    try {
      await tutorApi.clearHistory(project.id);
      setMessages([]);
    } catch (err) {
      alert(`Clear failed: ${err.message}`);
    }
  };

  // Helper to render message content with clickable citation tags [1], [2]
  const renderFormattedMessage = (content, citations = []) => {
    if (!content) return null;

    // Split on citation tags e.g. [1], [2]
    const parts = content.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const citeIndex = parseInt(match[1], 10) - 1;
        const citation = citations && citations[citeIndex];
        return (
          <button
            key={i}
            className="citation-badge"
            onClick={() => setActiveCitation(citation || { number: match[1], content: 'Source chunk reference unavailable' })}
            title="Click to view source evidence chunk"
          >
            [{match[1]}]
          </button>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: 'calc(100vh - 160px)',
      background: 'rgba(15, 23, 42, 0.65)',
      backdropFilter: 'blur(16px)',
      borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--border-subtle)',
      overflow: 'hidden',
    }}>
      {/* Tutor Header */}
      <div style={{
        padding: '14px 20px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(30, 41, 59, 0.4)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '34px',
            height: '34px',
            borderRadius: '50%',
            background: 'var(--gradient-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <Bot size={18} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>Contextual AI Tutor</span>
              <span className="glow-pill glow-pill-indigo" style={{ fontSize: '0.65rem' }}>gemini-3.6-flash</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Strictly grounded in your uploaded project documents with citation links
            </div>
          </div>
        </div>

        <button 
          className="btn-ghost"
          onClick={handleClear}
          style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}
          title="Clear Conversation"
        >
          <Trash2 size={14} /> Clear
        </button>
      </div>

      {/* Message Thread */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        {fetchingHistory ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            Loading contextual conversation history...
          </div>
        ) : messages.length === 0 ? (
          <div style={{
            margin: 'auto',
            textAlign: 'center',
            maxWidth: '460px',
            padding: '30px 20px',
          }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: 'rgba(99, 102, 241, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
            }}>
              <Sparkles size={26} color="var(--primary)" />
            </div>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Ask Your Course Materials Anything</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.6 }}>
              The tutor retrieves the most relevant paragraphs from your uploaded notes, gives precise answers, and provides verifiable citations.
            </p>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isTutor = msg.role === 'tutor' || msg.role === 'assistant';
            const citations = msg.citations || [];
            const isGrounded = msg.is_grounded !== false;

            return (
              <div
                key={msg.id || index}
                style={{
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start',
                  maxWidth: isTutor ? '85%' : '75%',
                  alignSelf: isTutor ? 'flex-start' : 'flex-end',
                }}
              >
                {/* Avatar */}
                {isTutor && (
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: 'var(--gradient-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: '2px',
                  }}>
                    <Bot size={16} color="#fff" />
                  </div>
                )}

                {/* Bubble */}
                <div style={{
                  background: isTutor ? 'rgba(30, 41, 59, 0.7)' : 'var(--primary)',
                  border: isTutor ? '1px solid var(--border-subtle)' : 'none',
                  borderRadius: isTutor ? '4px 18px 18px 18px' : '18px 4px 18px 18px',
                  padding: '12px 16px',
                  color: '#fff',
                  fontSize: '0.9rem',
                  lineHeight: 1.6,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
                }}>
                  {/* Unsupported question disclaimer banner if not grounded */}
                  {isTutor && !isGrounded && (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 12px',
                      background: 'rgba(245, 158, 11, 0.15)',
                      border: '1px solid rgba(245, 158, 11, 0.3)',
                      borderRadius: 'var(--radius-sm)',
                      color: '#fbbf24',
                      fontSize: '0.8rem',
                      marginBottom: '10px',
                      fontWeight: 500,
                    }}>
                      <AlertTriangle size={15} style={{ flexShrink: 0 }} />
                      <span>Note: This question is not directly covered in your uploaded materials.</span>
                    </div>
                  )}

                  {/* Message body */}
                  <div style={{ whiteSpace: 'pre-wrap' }}>
                    {isTutor ? renderFormattedMessage(msg.content, citations) : msg.content}
                  </div>

                  {/* Citations footer list */}
                  {isTutor && citations && citations.length > 0 && (
                    <div style={{
                      marginTop: '12px',
                      paddingTop: '10px',
                      borderTop: '1px solid rgba(148, 163, 184, 0.15)',
                      fontSize: '0.78rem',
                      color: 'var(--text-muted)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px',
                    }}>
                      <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Sources:</span>
                      {citations.map((c, idx) => (
                        <span 
                          key={idx} 
                          onClick={() => setActiveCitation(c)}
                          style={{
                            cursor: 'pointer',
                            color: 'var(--primary)',
                            background: 'rgba(99, 102, 241, 0.1)',
                            padding: '1px 6px',
                            borderRadius: '4px',
                          }}
                        >
                          [{idx + 1}] {c.material_name || 'Doc'} (p.{c.page_number})
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Loading Indicator */}
        {loading && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', alignSelf: 'flex-start' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: 'var(--gradient-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Bot size={16} color="#fff" />
            </div>
            <div style={{
              background: 'rgba(30, 41, 59, 0.7)',
              borderRadius: '4px 18px 18px 18px',
              padding: '10px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              color: 'var(--text-secondary)',
              fontSize: '0.85rem',
            }}>
              <RefreshCw size={14} className="spin" color="var(--primary)" />
              Searching project vectors & composing answer...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <form onSubmit={handleSendMessage} style={{
        padding: '14px 20px',
        background: 'rgba(15, 23, 42, 0.9)',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        gap: '12px',
      }}>
        <input
          type="text"
          placeholder="Ask a question about your study material..."
          className="input-field"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          disabled={loading}
          style={{ flex: 1 }}
        />
        <button 
          type="submit" 
          className="btn-primary" 
          disabled={!inputMessage.trim() || loading}
          style={{ padding: '0 20px' }}
        >
          <Send size={16} />
        </button>
      </form>

      {/* Citation Detail Modal */}
      {activeCitation && (
        <div className="modal-overlay" onClick={() => setActiveCitation(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={18} color="var(--primary)" />
                <h3 style={{ fontSize: '1.1rem' }}>Source Citation Evidence</h3>
              </div>
              <button className="btn-ghost" onClick={() => setActiveCitation(null)}>✕</button>
            </div>

            <div style={{
              padding: '10px 14px',
              background: 'rgba(99, 102, 241, 0.1)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(99, 102, 241, 0.25)',
              marginBottom: '14px',
              fontSize: '0.82rem',
              color: 'var(--text-secondary)',
            }}>
              <div><strong>Document:</strong> {activeCitation.material_name || 'Study Document'}</div>
              <div><strong>Page Number:</strong> {activeCitation.page_number || 'N/A'}</div>
              {activeCitation.similarity_score && (
                <div><strong>Vector Cosine Relevance:</strong> {(activeCitation.similarity_score * 100).toFixed(1)}%</div>
              )}
            </div>

            <div style={{
              maxHeight: '260px',
              overflowY: 'auto',
              padding: '12px',
              background: 'rgba(15, 23, 42, 0.8)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
              lineHeight: 1.6,
              color: 'var(--text-primary)',
              whiteSpace: 'pre-wrap',
            }}>
              {activeCitation.content || activeCitation.chunk_text || 'Exact chunk excerpt text not stored in citation reference.'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
