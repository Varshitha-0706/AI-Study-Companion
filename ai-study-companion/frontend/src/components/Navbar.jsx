import React from 'react';
import { 
  BookOpen, Sparkles, Shield, LogOut, User as UserIcon, 
  ChevronRight, Brain, Plus 
} from 'lucide-react';

export default function Navbar({ 
  user, 
  onLogout, 
  activeSpace, 
  activeProject, 
  onNavigateHome,
  onNavigateAdmin,
  isAdminView,
  onOpenAuth
}) {
  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '12px 28px',
      background: 'rgba(15, 23, 42, 0.85)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      borderBottom: '1px solid var(--border-subtle)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Brand & Breadcrumbs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div 
          onClick={onNavigateHome}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '10px', 
            cursor: 'pointer',
            userSelect: 'none'
          }}
        >
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: 'var(--gradient-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(99, 102, 241, 0.4)',
          }}>
            <Brain size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ 
              fontWeight: 800, 
              fontSize: '1.1rem', 
              fontFamily: 'var(--font-display)',
              background: 'linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: '-0.02em'
            }}>
              StudyTutor <span style={{ color: 'var(--primary)', WebkitTextFillColor: 'var(--primary)', fontSize: '0.8rem', fontWeight: 600 }}>AI</span>
            </div>
          </div>
        </div>

        {/* Breadcrumb path */}
        {(activeSpace || activeProject || isAdminView) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            <ChevronRight size={14} />
            {isAdminView ? (
              <span style={{ color: 'var(--accent-purple)', fontWeight: 600 }}>Admin Platform Portal</span>
            ) : (
              <>
                {activeSpace && (
                  <span style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span>{activeSpace.icon || '📚'}</span>
                    <span style={{ fontWeight: 500 }}>{activeSpace.name}</span>
                  </span>
                )}
                {activeProject && (
                  <>
                    <ChevronRight size={14} />
                    <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{activeProject.name}</span>
                  </>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* User Actions & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {user ? (
          <>
            {/* Admin toggle if user is admin */}
            {user.role === 'admin' && (
              <button 
                className={isAdminView ? "btn-primary" : "btn-secondary"}
                onClick={onNavigateAdmin}
                style={{ fontSize: '0.8rem', padding: '6px 12px' }}
                title="Admin Management Portal"
              >
                <Shield size={14} />
                {isAdminView ? "Exit Admin" : "Admin Portal"}
              </button>
            )}

            {/* Role Badge */}
            <span className={user.role === 'admin' ? "glow-pill glow-pill-amber" : "glow-pill glow-pill-indigo"} style={{ fontSize: '0.7rem' }}>
              {user.role}
            </span>

            {/* User Profile */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 10px',
              background: 'rgba(30, 41, 59, 0.6)',
              borderRadius: 'var(--radius-full)',
              border: '1px solid var(--border-subtle)',
            }}>
              <div style={{
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                fontWeight: 700,
                color: '#fff',
              }}>
                {user.display_name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                {user.display_name}
              </span>
            </div>

            {/* Logout button */}
            <button 
              className="btn-ghost"
              onClick={onLogout}
              style={{ padding: '6px', color: 'var(--text-muted)' }}
              title="Log out"
            >
              <LogOut size={16} />
            </button>
          </>
        ) : (
          <button className="btn-primary" onClick={onOpenAuth}>
            <UserIcon size={16} />
            Sign In / Register
          </button>
        )}
      </div>
    </header>
  );
}
