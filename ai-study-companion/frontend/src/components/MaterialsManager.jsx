import React, { useState, useEffect } from 'react';
import { 
  Upload, FileText, CheckCircle2, Clock, AlertCircle, 
  Layers, Eye, RefreshCw, Sparkles, FileUp 
} from 'lucide-react';
import { materialsApi } from '../services/api';

export default function MaterialsManager({ project, onMaterialProcessed }) {
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedMaterial, setSelectedMaterial] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const fetchMaterials = async () => {
    if (!project) return;
    try {
      const data = await materialsApi.list(project.id);
      setMaterials(data);
    } catch (err) {
      console.error('Failed to load materials:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMaterials();
    // Poll every 4 seconds if any material is queued or processing
    const interval = setInterval(() => {
      if (materials.some(m => m.status === 'queued' || m.status === 'processing')) {
        fetchMaterials();
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [project?.id, materials]);

  const handleFileUpload = async (files) => {
    const file = files[0];
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a PDF document.');
      return;
    }

    setUploading(true);
    try {
      await materialsApi.upload(project.id, file);
      await fetchMaterials();
      if (onMaterialProcessed) onMaterialProcessed();
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleViewChunks = async (material) => {
    setSelectedMaterial(material);
    setLoadingChunks(true);
    try {
      const data = await materialsApi.getChunks(material.id);
      setChunks(data);
    } catch (err) {
      alert(`Failed to load chunks: ${err.message}`);
    } finally {
      setLoadingChunks(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Upload Dropzone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          if (e.dataTransfer.files?.length) handleFileUpload(e.dataTransfer.files);
        }}
        style={{
          border: `2px dashed ${dragActive ? 'var(--primary)' : 'var(--border-subtle)'}`,
          background: dragActive ? 'rgba(99, 102, 241, 0.1)' : 'rgba(30, 41, 59, 0.4)',
          borderRadius: 'var(--radius-lg)',
          padding: '36px 20px',
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'all var(--transition-fast)',
        }}
        onClick={() => document.getElementById('file-upload-input').click()}
      >
        <input
          id="file-upload-input"
          type="file"
          accept=".pdf"
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files?.length) handleFileUpload(e.target.files);
          }}
        />
        <div style={{
          width: '54px',
          height: '54px',
          borderRadius: '50%',
          background: 'rgba(99, 102, 241, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 16px',
        }}>
          {uploading ? (
            <RefreshCw size={24} className="spin" color="var(--primary)" />
          ) : (
            <FileUp size={26} color="var(--primary)" />
          )}
        </div>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '6px' }}>
          {uploading ? 'Uploading & Queuing PDF Pipeline...' : 'Upload Learning Material (PDF)'}
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', maxWidth: '440px', margin: '0 auto' }}>
          Drop textbook chapters, research papers, or syllabus notes. Our RAG engine extracts text, generates 3072-dim embeddings, and extracts core concepts.
        </p>
      </div>

      {/* Materials List */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h3 style={{ fontSize: '1.1rem' }}>Project Materials & Extracted Chunks</h3>
          <button className="btn-ghost" onClick={fetchMaterials} style={{ fontSize: '0.8rem' }}>
            <RefreshCw size={14} /> Refresh Status
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
            Loading materials...
          </div>
        ) : materials.length === 0 ? (
          <div className="glass-panel" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No materials uploaded yet. Upload a PDF above to activate the AI Tutor and practice arena!
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {materials.map((mat) => {
              const isReady = mat.status === 'ready';
              const isProcessing = mat.status === 'processing';
              const isQueued = mat.status === 'queued';
              const isFailed = mat.status === 'failed';

              return (
                <div key={mat.id} className="glass-panel glass-panel-hover" style={{ padding: '18px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <FileText size={22} color="var(--primary)" />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#fff', wordBreak: 'break-all' }}>
                          {mat.original_filename}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {mat.page_count ? `${mat.page_count} pages` : 'Analyzing pages...'}
                        </div>
                      </div>
                    </div>

                    {/* Status Pill */}
                    {isReady && <span className="glow-pill glow-pill-emerald">Ready</span>}
                    {isProcessing && <span className="glow-pill glow-pill-indigo">Processing...</span>}
                    {isQueued && <span className="glow-pill glow-pill-amber">Queued</span>}
                    {isFailed && <span className="glow-pill glow-pill-rose">Failed</span>}
                  </div>

                  {/* Error if any */}
                  {mat.error_message && (
                    <div style={{ fontSize: '0.78rem', color: '#fb7185', background: 'rgba(244, 63, 94, 0.1)', padding: '6px 10px', borderRadius: '4px', marginBottom: '12px' }}>
                      {mat.error_message}
                    </div>
                  )}

                  {/* Actions */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {mat.file_size ? `${(mat.file_size / 1024 / 1024).toFixed(2)} MB` : ''}
                    </span>
                    {isReady && (
                      <button 
                        className="btn-secondary" 
                        onClick={() => handleViewChunks(mat)}
                        style={{ fontSize: '0.78rem', padding: '4px 10px' }}
                      >
                        <Layers size={13} /> View Chunks
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal: View Chunks */}
      {selectedMaterial && (
        <div className="modal-overlay" onClick={() => setSelectedMaterial(null)}>
          <div className="modal-content" style={{ maxWidth: '720px', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem' }}>Extracted RAG Chunks</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                  {selectedMaterial.original_filename} (VECTOR(3072) Indexed)
                </p>
              </div>
              <button className="btn-ghost" onClick={() => setSelectedMaterial(null)}>✕</button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px', paddingRight: '4px' }}>
              {loadingChunks ? (
                <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                  Loading chunk data...
                </div>
              ) : chunks.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>
                  No chunks extracted.
                </div>
              ) : (
                chunks.map((chunk, idx) => (
                  <div key={chunk.id || idx} style={{
                    padding: '12px 14px',
                    background: 'rgba(30, 41, 59, 0.4)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '0.82rem',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--primary)', fontWeight: 600, fontSize: '0.75rem', marginBottom: '6px' }}>
                      <span>Chunk #{idx + 1} • Page {chunk.page_number}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{chunk.token_count || '~150'} tokens</span>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                      {chunk.content}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
