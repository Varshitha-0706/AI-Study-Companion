import React, { useState } from 'react';
import { 
  FolderPlus, Plus, ChevronRight, Folder, 
  Sparkles, Trash2, Edit3, Target, BookMarked
} from 'lucide-react';
import { spacesApi, projectsApi } from '../services/api';

const PRESET_COLORS = ['#6366f1', '#06b6d4', '#a855f7', '#ec4899', '#10b981', '#f59e0b'];
const PRESET_ICONS = ['📚', '🤖', '🧬', '💻', '📐', '🧠', '🔬', '📊'];

export default function SpacesSidebar({
  spaces,
  activeSpace,
  onSelectSpace,
  projects,
  activeProject,
  onSelectProject,
  onRefreshSpaces,
  onRefreshProjects,
}) {
  const [showNewSpaceModal, setShowNewSpaceModal] = useState(false);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);

  // New Space Form
  const [spaceName, setSpaceName] = useState('');
  const [spaceDesc, setSpaceDesc] = useState('');
  const [spaceColor, setSpaceColor] = useState(PRESET_COLORS[0]);
  const [spaceIcon, setSpaceIcon] = useState(PRESET_ICONS[0]);
  const [spaceLoading, setSpaceLoading] = useState(false);

  // New Project Form
  const [projectName, setProjectName] = useState('');
  const [projectDesc, setProjectDesc] = useState('');
  const [learningGoal, setLearningGoal] = useState('');
  const [projectLoading, setProjectLoading] = useState(false);

  const handleCreateSpace = async (e) => {
    e.preventDefault();
    if (!spaceName.trim()) return;
    setSpaceLoading(true);
    try {
      await spacesApi.create({
        name: spaceName.trim(),
        description: spaceDesc.trim(),
        color: spaceColor,
        icon: spaceIcon,
      });
      setSpaceName('');
      setSpaceDesc('');
      setShowNewSpaceModal(false);
      onRefreshSpaces();
    } catch (err) {
      alert(err.message);
    } finally {
      setSpaceLoading(false);
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!projectName.trim() || !activeSpace) return;
    setProjectLoading(true);
    try {
      await projectsApi.create(activeSpace.id, {
        name: projectName.trim(),
        description: projectDesc.trim(),
        learning_goal: learningGoal.trim(),
      });
      setProjectName('');
      setProjectDesc('');
      setLearningGoal('');
      setShowNewProjectModal(false);
      onRefreshProjects(activeSpace.id);
    } catch (err) {
      alert(err.message);
    } finally {
      setProjectLoading(false);
    }
  };

  return (
    <aside style={{
      width: '280px',
      minWidth: '280px',
      background: 'rgba(15, 23, 42, 0.7)',
      backdropFilter: 'blur(16px)',
      borderRight: '1px solid var(--border-subtle)',
      display: 'flex',
      flexDirection: 'column',
      height: 'calc(100vh - 63px)',
      overflowY: 'auto',
    }}>
      {/* Spaces Header */}
      <div style={{
        padding: '16px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--border-subtle)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Study Spaces
          </span>
          <span style={{
            fontSize: '0.7rem',
            background: 'rgba(99, 102, 241, 0.15)',
            color: 'var(--primary)',
            padding: '1px 6px',
            borderRadius: 'var(--radius-full)',
            fontWeight: 600,
          }}>
            {spaces.length}
          </span>
        </div>
        <button 
          className="btn-ghost" 
          onClick={() => setShowNewSpaceModal(true)}
          style={{ padding: '4px 8px', fontSize: '0.75rem' }}
          title="Create New Study Space"
        >
          <Plus size={14} /> New Space
        </button>
      </div>

      {/* Spaces List */}
      <div style={{ padding: '12px 14px', flex: 1, overflowY: 'auto' }}>
        {spaces.length === 0 ? (
          <div style={{
            padding: '24px 16px',
            textAlign: 'center',
            color: 'var(--text-muted)',
            fontSize: '0.85rem',
            background: 'rgba(30, 41, 59, 0.3)',
            borderRadius: 'var(--radius-md)',
            border: '1px dashed var(--border-subtle)',
          }}>
            <BookMarked size={28} style={{ margin: '0 auto 8px', opacity: 0.4 }} />
            <p>No study spaces yet.</p>
            <button 
              className="btn-primary" 
              onClick={() => setShowNewSpaceModal(true)}
              style={{ marginTop: '12px', fontSize: '0.8rem', padding: '6px 14px' }}
            >
              <Plus size={14} /> Create Space
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {spaces.map((space) => {
              const isActive = activeSpace?.id === space.id;
              return (
                <div key={space.id}>
                  {/* Space Card Item */}
                  <div
                    onClick={() => onSelectSpace(space)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                      border: isActive ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid transparent',
                      cursor: 'pointer',
                      transition: 'all var(--transition-fast)',
                    }}
                    className="glass-panel-hover"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '1.2rem' }}>{space.icon || '📚'}</span>
                      <div>
                        <div style={{
                          fontWeight: isActive ? 600 : 500,
                          fontSize: '0.875rem',
                          color: isActive ? '#ffffff' : 'var(--text-primary)',
                        }}>
                          {space.name}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {space.project_count || 0} project{space.project_count === 1 ? '' : 's'}
                        </div>
                      </div>
                    </div>
                    <ChevronRight size={14} color={isActive ? 'var(--primary)' : 'var(--text-muted)'} />
                  </div>

                  {/* Nested Projects if space is active */}
                  {isActive && (
                    <div style={{
                      marginLeft: '20px',
                      paddingLeft: '12px',
                      borderLeft: '1px solid rgba(99, 102, 241, 0.25)',
                      marginTop: '6px',
                      marginBottom: '10px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}>
                      {projects.map((proj) => {
                        const isProjActive = activeProject?.id === proj.id;
                        return (
                          <div
                            key={proj.id}
                            onClick={(e) => { e.stopPropagation(); onSelectProject(proj); }}
                            style={{
                              padding: '8px 10px',
                              borderRadius: 'var(--radius-sm)',
                              background: isProjActive ? 'var(--primary)' : 'rgba(30, 41, 59, 0.4)',
                              color: isProjActive ? '#fff' : 'var(--text-secondary)',
                              fontSize: '0.82rem',
                              fontWeight: isProjActive ? 600 : 400,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              transition: 'all var(--transition-fast)',
                            }}
                          >
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {proj.name}
                            </span>
                            {proj.concept_count > 0 && (
                              <span style={{
                                fontSize: '0.68rem',
                                opacity: 0.8,
                                background: isProjActive ? 'rgba(0,0,0,0.2)' : 'rgba(255,255,255,0.1)',
                                padding: '1px 5px',
                                borderRadius: '4px',
                              }}>
                                {proj.concept_count}c
                              </span>
                            )}
                          </div>
                        );
                      })}

                      {/* Add Project Button */}
                      <button
                        onClick={(e) => { e.stopPropagation(); setShowNewProjectModal(true); }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 10px',
                          fontSize: '0.78rem',
                          color: 'var(--primary)',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          marginTop: '4px',
                          textAlign: 'left',
                        }}
                      >
                        <Plus size={12} /> Add Learning Project
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal: New Space */}
      {showNewSpaceModal && (
        <div className="modal-overlay" onClick={() => setShowNewSpaceModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: '1.25rem', marginBottom: '16px' }}>Create New Study Space</h3>
            <form onSubmit={handleCreateSpace} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Space Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Distributed Systems & AI"
                  className="input-field"
                  value={spaceName}
                  onChange={(e) => setSpaceName(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Description
                </label>
                <input
                  type="text"
                  placeholder="Optional context about this subject area"
                  className="input-field"
                  value={spaceDesc}
                  onChange={(e) => setSpaceDesc(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  Icon & Theme
                </label>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
                  {PRESET_ICONS.map((icon) => (
                    <button
                      key={icon}
                      type="button"
                      onClick={() => setSpaceIcon(icon)}
                      style={{
                        fontSize: '1.2rem',
                        padding: '6px 10px',
                        borderRadius: 'var(--radius-sm)',
                        background: spaceIcon === icon ? 'rgba(99, 102, 241, 0.3)' : 'rgba(30, 41, 59, 0.6)',
                        border: spaceIcon === icon ? '1px solid var(--primary)' : '1px solid transparent',
                        cursor: 'pointer',
                      }}
                    >
                      {icon}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" className="btn-secondary" onClick={() => setShowNewSpaceModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={spaceLoading}>
                  {spaceLoading ? 'Creating...' : 'Create Space'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Project */}
      {showNewProjectModal && (
        <div className="modal-overlay" onClick={() => setShowNewProjectModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: '1.25rem', marginBottom: '16px' }}>
              Add Project to {activeSpace?.name}
            </h3>
            <form onSubmit={handleCreateProject} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Project Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Chapter 4: Self-Attention & Transformers"
                  className="input-field"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Description
                </label>
                <input
                  type="text"
                  placeholder="e.g. Reading papers and lecture slides"
                  className="input-field"
                  value={projectDesc}
                  onChange={(e) => setProjectDesc(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Learning Goal
                </label>
                <textarea
                  placeholder="e.g. Understand scaled dot-product attention and multi-head projection layers thoroughly."
                  className="input-field"
                  rows={3}
                  value={learningGoal}
                  onChange={(e) => setLearningGoal(e.target.value)}
                  style={{ resize: 'vertical' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" className="btn-secondary" onClick={() => setShowNewProjectModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={projectLoading}>
                  {projectLoading ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </aside>
  );
}
