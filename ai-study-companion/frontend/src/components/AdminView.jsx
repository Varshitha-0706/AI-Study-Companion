import React, { useState, useEffect } from 'react';
import { 
  Shield, Users, Server, Cpu, DollarSign, Activity, 
  RefreshCw, CheckCircle2, AlertCircle, Clock, Database 
} from 'lucide-react';
import { adminApi } from '../services/api';

export default function AdminView() {
  const [overview, setOverview] = useState(null);
  const [users, setUsers] = useState([]);
  const [activity, setActivity] = useState([]);
  const [aiStats, setAiStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSubTab, setActiveSubTab] = useState('overview');

  const fetchAdminData = async () => {
    setLoading(true);
    try {
      const [ov, uList, act, ai] = await Promise.all([
        adminApi.getOverview().catch(() => null),
        adminApi.getUsers().catch(() => []),
        adminApi.getActivity().catch(() => []),
        adminApi.getAiStats().catch(() => null),
      ]);
      setOverview(ov);
      setUsers(uList || []);
      setActivity(act || []);
      setAiStats(ai);
    } catch (err) {
      console.error('Failed to load admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', width: '100%', padding: '10px 0 40px' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '24px',
        paddingBottom: '16px',
        borderBottom: '1px solid var(--border-subtle)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #f59e0b, #ef4444)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 15px rgba(245, 158, 11, 0.3)',
          }}>
            <Shield size={22} color="#fff" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.4rem' }}>Platform Administration Portal</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              System metrics, AI token accounting, background jobs, and user registry
            </p>
          </div>
        </div>

        <button className="btn-secondary" onClick={fetchAdminData} style={{ fontSize: '0.8rem' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh Telemetry
        </button>
      </div>

      {/* Sub tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '22px' }}>
        {['overview', 'users', 'ai-telemetry', 'activity'].map((tab) => (
          <button
            key={tab}
            className={activeSubTab === tab ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setActiveSubTab(tab)}
            style={{ textTransform: 'capitalize', fontSize: '0.85rem', padding: '8px 16px' }}
          >
            {tab.replace('-', ' ')}
          </button>
        ))}
      </div>

      {loading && !overview ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          Loading platform telemetry...
        </div>
      ) : (
        <>
          {/* Subtab 1: Overview */}
          {activeSubTab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
              {/* Stat Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                <div className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>Total Users</span>
                    <Users size={16} />
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff' }}>
                    {overview?.total_users || 0}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '4px' }}>
                    {overview?.active_users_24h || 0} active today
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>Study Spaces</span>
                    <Database size={16} />
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--primary)' }}>
                    {overview?.total_spaces || 0}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    {overview?.total_projects || 0} projects
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>AI Calls (24h)</span>
                    <Cpu size={16} />
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--accent-purple)' }}>
                    {overview?.ai_calls_24h || 0}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    gemini-3.6-flash
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>Estimated AI Cost</span>
                    <DollarSign size={16} />
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
                    ${(overview?.ai_cost_usd_24h || 0).toFixed(4)}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Last 24 hours
                  </div>
                </div>
              </div>

              {/* Infrastructure Status */}
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 style={{ fontSize: '1.1rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Server size={18} color="var(--primary)" /> Infrastructure Health
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
                  <div style={{ padding: '14px', background: 'rgba(30, 41, 59, 0.4)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>PostgreSQL & pgvector</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px' }}>
                      <CheckCircle2 size={16} color="var(--accent-emerald)" />
                      <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>VECTOR(3072) Online</span>
                    </div>
                  </div>

                  <div style={{ padding: '14px', background: 'rgba(30, 41, 59, 0.4)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Celery Background Queue</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px' }}>
                      <CheckCircle2 size={16} color="var(--accent-emerald)" />
                      <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Worker Active (Redis)</span>
                    </div>
                  </div>

                  <div style={{ padding: '14px', background: 'rgba(30, 41, 59, 0.4)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Gemini Generation Model</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px' }}>
                      <CheckCircle2 size={16} color="var(--accent-emerald)" />
                      <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>gemini-3.6-flash</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Subtab 2: Users */}
          {activeSubTab === 'users' && (
            <div className="glass-panel" style={{ padding: '20px', overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '10px' }}>User</th>
                    <th style={{ padding: '10px' }}>Email</th>
                    <th style={{ padding: '10px' }}>Role</th>
                    <th style={{ padding: '10px' }}>Created</th>
                    <th style={{ padding: '10px' }}>Last Active</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }}>
                      <td style={{ padding: '12px 10px', fontWeight: 600, color: '#fff' }}>{u.display_name}</td>
                      <td style={{ padding: '12px 10px', color: 'var(--text-secondary)' }}>{u.email}</td>
                      <td style={{ padding: '12px 10px' }}>
                        <span className={u.role === 'admin' ? 'glow-pill glow-pill-amber' : 'glow-pill glow-pill-indigo'}>
                          {u.role}
                        </span>
                      </td>
                      <td style={{ padding: '12px 10px', color: 'var(--text-muted)' }}>
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ padding: '12px 10px', color: 'var(--text-muted)' }}>
                        {u.last_active_at ? new Date(u.last_active_at).toLocaleString() : 'Never'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Subtab 3: AI Telemetry */}
          {activeSubTab === 'ai-telemetry' && (
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '14px' }}>AI Model Usage & Token Telemetry</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
                <div style={{ padding: '16px', background: 'rgba(30, 41, 59, 0.4)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Input Tokens</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px' }}>
                    {aiStats?.total_prompt_tokens?.toLocaleString() || '0'}
                  </div>
                </div>
                <div style={{ padding: '16px', background: 'rgba(30, 41, 59, 0.4)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Output Tokens</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px' }}>
                    {aiStats?.total_completion_tokens?.toLocaleString() || '0'}
                  </div>
                </div>
                <div style={{ padding: '16px', background: 'rgba(30, 41, 59, 0.4)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Average Latency</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px' }}>
                    {aiStats?.avg_latency_ms ? `${Math.round(aiStats.avg_latency_ms)} ms` : '—'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Subtab 4: Activity Feed */}
          {activeSubTab === 'activity' && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '16px' }}>System Event Stream</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {activity.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>No events logged yet.</div>
                ) : (
                  activity.map((ev) => (
                    <div key={ev.id} style={{
                      padding: '10px 14px',
                      background: 'rgba(30, 41, 59, 0.3)',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '0.82rem',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <Activity size={15} color="var(--primary)" />
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{ev.event_type}</span>
                        {ev.payload && (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                            {JSON.stringify(ev.payload)}
                          </span>
                        )}
                      </div>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                        {new Date(ev.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
