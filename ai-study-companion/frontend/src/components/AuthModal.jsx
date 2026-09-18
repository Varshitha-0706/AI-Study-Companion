import React, { useState } from 'react';
import { X, Lock, Mail, User, ArrowRight, ShieldCheck } from 'lucide-react';
import { authApi } from '../services/api';

export default function AuthModal({ isOpen, onClose, onAuthSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let data;
      if (isRegister) {
        if (!displayName.trim()) throw new Error('Please enter your display name');
        data = await authApi.register(email, password, displayName);
      } else {
        data = await authApi.login(email, password);
      }
      onAuthSuccess(data);
      onClose();
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '1.4rem', marginBottom: '4px' }}>
              {isRegister ? 'Create Your Learning Account' : 'Welcome Back'}
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              {isRegister 
                ? 'Begin your contextual AI study companion journey' 
                : 'Access your persistent study spaces, mastery graphs, and tutor'}
            </p>
          </div>
          <button className="btn-ghost" onClick={onClose} style={{ padding: '4px' }}>
            <X size={20} />
          </button>
        </div>

        {/* Tab switch */}
        <div style={{
          display: 'flex',
          background: 'rgba(30, 41, 59, 0.5)',
          borderRadius: 'var(--radius-md)',
          padding: '4px',
          marginBottom: '20px',
        }}>
          <button
            type="button"
            onClick={() => { setIsRegister(false); setError(''); }}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: !isRegister ? 'var(--primary)' : 'transparent',
              color: !isRegister ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)'
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setIsRegister(true); setError(''); }}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: isRegister ? 'var(--primary)' : 'transparent',
              color: isRegister ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)'
            }}
          >
            Register
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div style={{
            padding: '10px 14px',
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: 'var(--radius-md)',
            color: '#fb7185',
            fontSize: '0.85rem',
            marginBottom: '16px',
          }}>
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {isRegister && (
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                Display Name
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  required
                  placeholder="e.g. Alex Rivera"
                  className="input-field"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  style={{ paddingLeft: '38px' }}
                />
                <User size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
              </div>
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Email Address
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="email"
                required
                placeholder="student@university.edu"
                className="input-field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ paddingLeft: '38px' }}
              />
              <Mail size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="password"
                required
                placeholder="••••••••"
                className="input-field"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ paddingLeft: '38px' }}
              />
              <Lock size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <button 
            type="submit" 
            className="btn-primary" 
            disabled={loading}
            style={{ width: '100%', marginTop: '8px', padding: '12px' }}
          >
            {loading ? 'Processing...' : (isRegister ? 'Create Account' : 'Sign In')}
            <ArrowRight size={16} />
          </button>
        </form>

        {/* Security badge note */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px', 
          marginTop: '20px', 
          padding: '10px 14px', 
          background: 'rgba(30, 41, 59, 0.4)', 
          borderRadius: 'var(--radius-md)', 
          fontSize: '0.75rem', 
          color: 'var(--text-muted)' 
        }}>
          <ShieldCheck size={16} color="var(--accent-emerald)" style={{ flexShrink: 0 }} />
          <span>Strict user data isolation enforced across spaces and vector embeddings.</span>
        </div>
      </div>
    </div>
  );
}
