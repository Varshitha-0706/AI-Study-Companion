import React, { useState, useEffect } from 'react';
import { 
  BookOpen, Brain, Play, TrendingUp, Upload, 
  Sparkles, LayoutDashboard, MessageSquare, Award, 
  FolderPlus, Plus, ChevronRight, Layers 
} from 'lucide-react';

import Navbar from './components/Navbar';
import AuthModal from './components/AuthModal';
import SpacesSidebar from './components/SpacesSidebar';
import ProjectDashboard from './components/ProjectDashboard';
import MaterialsManager from './components/MaterialsManager';
import AITutorView from './components/AITutorView';
import AdaptiveQuizView from './components/AdaptiveQuizView';
import MasteryView from './components/MasteryView';
import AdminView from './components/AdminView';

import { 
  getAuthToken, removeAuthToken, getCurrentUserLocal, 
  setCurrentUserLocal, authApi, spacesApi, projectsApi 
} from './services/api';

export default function App() {
  const [user, setUser] = useState(getCurrentUserLocal());
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isAdminView, setIsAdminView] = useState(false);

  const [spaces, setSpaces] = useState([]);
  const [activeSpace, setActiveSpace] = useState(null);
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [dashboardData, setDashboardData] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(true);

  // Validate session on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = getAuthToken();
      if (token) {
        try {
          const userData = await authApi.getMe();
          setUser(userData);
          setCurrentUserLocal(userData);
        } catch (err) {
          removeAuthToken();
          setUser(null);
        }
      } else {
        // Auto open auth modal for convenience if not logged in
        setShowAuthModal(true);
      }
      setLoading(false);
    };

    initAuth();

    const handleUnauthorized = () => {
      setUser(null);
      setShowAuthModal(true);
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  // Fetch spaces when user is logged in
  const loadSpaces = async () => {
    if (!user) return;
    try {
      const data = await spacesApi.list();
      setSpaces(data || []);
      if (data && data.length > 0 && !activeSpace) {
        setActiveSpace(data[0]);
      }
    } catch (err) {
      console.error('Failed to load spaces:', err);
    }
  };

  useEffect(() => {
    if (user) {
      loadSpaces();
    } else {
      setSpaces([]);
      setActiveSpace(null);
      setProjects([]);
      setActiveProject(null);
    }
  }, [user]);

  // Fetch projects when activeSpace changes
  const loadProjects = async (spaceId) => {
    if (!spaceId) return;
    try {
      const data = await projectsApi.list(spaceId);
      setProjects(data || []);
      if (data && data.length > 0) {
        setActiveProject(data[0]);
      } else {
        setActiveProject(null);
      }
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  };

  useEffect(() => {
    if (activeSpace) {
      loadProjects(activeSpace.id);
    }
  }, [activeSpace?.id]);

  // Fetch project dashboard when activeProject changes
  const loadDashboard = async () => {
    if (!activeProject) {
      setDashboardData(null);
      return;
    }
    try {
      const data = await projectsApi.getDashboard(activeProject.id);
      setDashboardData(data);
    } catch (err) {
      console.error('Failed to load project dashboard:', err);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, [activeProject?.id]);

  const handleAuthSuccess = (data) => {
    setUser({ id: data.user_id, display_name: data.display_name, role: data.role });
    setIsAdminView(false);
    loadSpaces();
  };

  const handleLogout = () => {
    removeAuthToken();
    setUser(null);
    setIsAdminView(false);
    setShowAuthModal(true);
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        Loading AI Study Companion...
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navbar */}
      <Navbar
        user={user}
        onLogout={handleLogout}
        activeSpace={activeSpace}
        activeProject={activeProject}
        onNavigateHome={() => { setIsAdminView(false); setActiveTab('dashboard'); }}
        onNavigateAdmin={() => setIsAdminView(!isAdminView)}
        isAdminView={isAdminView}
        onOpenAuth={() => setShowAuthModal(true)}
      />

      {/* Main Container */}
      <div style={{ display: 'flex', flex: 1 }}>
        {/* Left Spaces & Projects Sidebar (hidden in admin view) */}
        {user && !isAdminView && (
          <SpacesSidebar
            spaces={spaces}
            activeSpace={activeSpace}
            onSelectSpace={(s) => { setActiveSpace(s); }}
            projects={projects}
            activeProject={activeProject}
            onSelectProject={(p) => { setActiveProject(p); setActiveTab('dashboard'); }}
            onRefreshSpaces={loadSpaces}
            onRefreshProjects={loadProjects}
          />
        )}

        {/* Content Area */}
        <main style={{ flex: 1, padding: '24px 32px', overflowY: 'auto', maxHeight: 'calc(100vh - 63px)' }}>
          {!user ? (
            /* Guest hero banner */
            <div style={{ maxWidth: '680px', margin: '80px auto', textAlign: 'center' }}>
              <div style={{
                width: '72px',
                height: '72px',
                borderRadius: '20px',
                background: 'var(--gradient-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 24px',
                boxShadow: '0 8px 30px rgba(99, 102, 241, 0.4)',
              }}>
                <Brain size={38} color="#fff" />
              </div>
              <h1 style={{ fontSize: '2.4rem', lineHeight: 1.2, marginBottom: '16px' }}>
                Your Contextual AI Study Companion
              </h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', lineHeight: 1.6, marginBottom: '32px' }}>
                Upload textbooks and lecture notes. Experience AI tutoring grounded strictly in your curriculum with verifiable citations, adaptive practice, and evidence-weighted mastery tracking.
              </p>
              <button className="btn-primary" onClick={() => setShowAuthModal(true)} style={{ fontSize: '1rem', padding: '12px 32px' }}>
                Get Started
              </button>
            </div>
          ) : isAdminView ? (
            /* Admin Portal */
            <AdminView />
          ) : !activeProject ? (
            /* Empty state when no project selected */
            <div className="glass-panel" style={{ maxWidth: '600px', margin: '60px auto', padding: '40px', textAlign: 'center' }}>
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: 'rgba(99, 102, 241, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
              }}>
                <Layers size={28} color="var(--primary)" />
              </div>
              <h2 style={{ fontSize: '1.35rem', marginBottom: '8px' }}>Select or Create a Learning Project</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6 }}>
                Each project organizes your study materials, RAG vector index, AI tutor conversation history, and adaptive quizzes. Use the left sidebar to select or create a project.
              </p>
            </div>
          ) : (
            /* Active Project Workspace */
            <div style={{ maxWidth: '1120px', margin: '0 auto', width: '100%' }}>
              {/* Tab navigation bar */}
              <div style={{
                display: 'flex',
                gap: '8px',
                borderBottom: '1px solid var(--border-subtle)',
                marginBottom: '24px',
                paddingBottom: '2px',
              }}>
                {[
                  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
                  { id: 'tutor', label: 'AI Study Tutor', icon: MessageSquare },
                  { id: 'quiz', label: 'Adaptive Practice', icon: Play },
                  { id: 'mastery', label: 'Mastery & Growth', icon: TrendingUp },
                  { id: 'materials', label: 'Materials & Chunks', icon: Upload },
                ].map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '10px 18px',
                        borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
                        border: 'none',
                        background: isActive ? 'rgba(30, 41, 59, 0.7)' : 'transparent',
                        color: isActive ? '#fff' : 'var(--text-secondary)',
                        fontWeight: isActive ? 600 : 500,
                        fontSize: '0.9rem',
                        cursor: 'pointer',
                        borderBottom: isActive ? '2px solid var(--primary)' : '2px solid transparent',
                        transition: 'all var(--transition-fast)',
                      }}
                    >
                      <Icon size={16} color={isActive ? 'var(--primary)' : 'var(--text-muted)'} />
                      {tab.label}
                    </button>
                  );
                })}
              </div>

              {/* Active Tab View */}
              {activeTab === 'dashboard' && (
                <ProjectDashboard
                  dashboardData={dashboardData}
                  project={activeProject}
                  onNavigateTab={(tab) => setActiveTab(tab)}
                />
              )}

              {activeTab === 'tutor' && (
                <AITutorView project={activeProject} />
              )}

              {activeTab === 'quiz' && (
                <AdaptiveQuizView
                  project={activeProject}
                  onQuizCompleted={() => {
                    loadDashboard();
                  }}
                />
              )}

              {activeTab === 'mastery' && (
                <MasteryView
                  project={activeProject}
                  onSelectConceptToPractice={() => setActiveTab('quiz')}
                />
              )}

              {activeTab === 'materials' && (
                <MaterialsManager
                  project={activeProject}
                  onMaterialProcessed={() => {
                    loadDashboard();
                    loadProjects(activeSpace?.id);
                  }}
                />
              )}
            </div>
          )}
        </main>
      </div>

      {/* Auth Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={handleAuthSuccess}
      />
    </div>
  );
}
