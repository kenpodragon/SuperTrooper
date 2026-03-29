import { useState, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface FileResult {
  filename: string;
  status: 'pending' | 'uploading' | 'success' | 'failed';
  career_entries?: number;
  bullets?: number;
  skills?: number;
  education?: number;
  certifications?: number;
  errors?: string[];
  template_id?: number;
  recipe_id?: number;
}

interface UploadResponse {
  results: Array<{
    filename: string;
    status: string;
    errors?: string[];
    report?: {
      career_entries?: number;
      bullets_inserted?: number;
      skills_inserted?: number;
      education_inserted?: number;
      certifications_inserted?: number;
      template_id?: number;
      recipe_id?: number;
    };
    career_entries?: number;
    bullets_inserted?: number;
    skills_inserted?: number;
    education_inserted?: number;
    certifications_inserted?: number;
  }>;
  total: number;
  next_steps?: string[];
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const ACCEPTED = '.docx,.pdf';
const BATCH_SIZE = 5;

export default function ImportResumesModal({ isOpen, onClose }: Props) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [results, setResults] = useState<FileResult[]>([]);
  const [uploading, setUploading] = useState(false);
  const [done, setDone] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const valid = Array.from(newFiles).filter((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase();
      return ext === 'docx' || ext === 'pdf';
    });
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + f.size));
      const deduped = valid.filter((f) => !existing.has(f.name + f.size));
      return [...prev, ...deduped];
    });
  }, []);

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
    },
    [addFiles],
  );

  const uploadBatch = async (batch: File[], startIdx: number) => {
    const formData = new FormData();
    batch.forEach((f) => formData.append('files', f));
    formData.append('ai_enabled', aiEnabled ? 'true' : 'false');

    // Mark batch as uploading
    setResults((prev) => {
      const next = [...prev];
      batch.forEach((_, i) => {
        next[startIdx + i] = { ...next[startIdx + i], status: 'uploading' };
      });
      return next;
    });

    try {
      const resp = await fetch('/api/onboard/upload', {
        method: 'POST',
        body: formData,
      });
      const data: UploadResponse = await resp.json();

      setResults((prev) => {
        const next = [...prev];
        data.results.forEach((r, i) => {
          const report = r.report || r;
          next[startIdx + i] = {
            filename: r.filename,
            status: r.status === 'failed' ? 'failed' : 'success',
            career_entries: report.career_entries ?? 0,
            bullets: report.bullets_inserted ?? 0,
            skills: report.skills_inserted ?? 0,
            education: report.education_inserted ?? 0,
            certifications: report.certifications_inserted ?? 0,
            errors: r.errors,
            template_id: report.template_id,
            recipe_id: report.recipe_id,
          };
        });
        return next;
      });
    } catch (err) {
      setResults((prev) => {
        const next = [...prev];
        batch.forEach((f, i) => {
          next[startIdx + i] = {
            filename: f.name,
            status: 'failed',
            errors: [err instanceof Error ? err.message : 'Network error'],
          };
        });
        return next;
      });
    }
  };

  const startUpload = async () => {
    if (!files.length) return;
    setUploading(true);
    setDone(false);

    // Initialize all as pending
    setResults(files.map((f) => ({ filename: f.name, status: 'pending' })));

    // Upload in batches
    for (let i = 0; i < files.length; i += BATCH_SIZE) {
      const batch = files.slice(i, i + BATCH_SIZE);
      await uploadBatch(batch, i);
    }

    setUploading(false);
    setDone(true);

    // Invalidate all KB queries so data refreshes
    queryClient.invalidateQueries({ queryKey: ['skills'] });
    queryClient.invalidateQueries({ queryKey: ['education'] });
    queryClient.invalidateQueries({ queryKey: ['certifications'] });
    queryClient.invalidateQueries({ queryKey: ['languages'] });
    queryClient.invalidateQueries({ queryKey: ['summaries'] });
    queryClient.invalidateQueries({ queryKey: ['career-history'] });
    queryClient.invalidateQueries({ queryKey: ['bullets'] });
  };

  const handleClose = () => {
    if (uploading) return; // Don't close while uploading
    setFiles([]);
    setResults([]);
    setDone(false);
    onClose();
  };

  const successCount = results.filter((r) => r.status === 'success').length;
  const failCount = results.filter((r) => r.status === 'failed').length;
  const totalCareer = results.reduce((s, r) => s + (r.career_entries ?? 0), 0);
  const totalBullets = results.reduce((s, r) => s + (r.bullets ?? 0), 0);
  const totalSkills = results.reduce((s, r) => s + (r.skills ?? 0), 0);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
    >
      <div
        style={{
          background: '#1e293b', borderRadius: 12, width: '90%', maxWidth: 700,
          maxHeight: '85vh', overflow: 'hidden', display: 'flex', flexDirection: 'column',
          border: '1px solid #334155',
        }}
      >
        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>Import Resumes</h2>
          <button
            onClick={handleClose}
            disabled={uploading}
            style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: 24, cursor: uploading ? 'not-allowed' : 'pointer', lineHeight: 1 }}
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 24, overflowY: 'auto', flex: 1 }}>
          {/* AI toggle + folder browse */}
          {!done && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <div
                  onClick={() => setAiEnabled(!aiEnabled)}
                  style={{
                    width: 36, height: 20, borderRadius: 10, position: 'relative',
                    background: aiEnabled ? '#7c3aed' : '#475569', transition: 'background 0.2s',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{
                    width: 16, height: 16, borderRadius: '50%', background: '#fff',
                    position: 'absolute', top: 2,
                    left: aiEnabled ? 18 : 2, transition: 'left 0.2s',
                  }} />
                </div>
                <span style={{ fontSize: 13, color: aiEnabled ? '#c4b5fd' : '#94a3b8' }}>
                  {aiEnabled ? 'AI-Enhanced Parsing' : 'Rule-Based Parsing'}
                </span>
              </label>
              <button
                onClick={() => dirInputRef.current?.click()}
                disabled={uploading}
                style={{
                  padding: '6px 14px', fontSize: 13, color: '#94a3b8',
                  background: 'transparent', border: '1px solid #475569',
                  borderRadius: 6, cursor: 'pointer',
                }}
              >
                Browse Folder...
              </button>
              <input
                ref={dirInputRef}
                type="file"
                // @ts-expect-error webkitdirectory is non-standard but widely supported
                webkitdirectory=""
                multiple
                style={{ display: 'none' }}
                onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ''; }}
              />
            </div>
          )}

          {/* Drop zone (hide after upload starts) */}
          {!done && (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? '#3b82f6' : '#475569'}`,
                borderRadius: 10, padding: '32px 24px', textAlign: 'center',
                cursor: 'pointer', marginBottom: 20, transition: 'border-color 0.15s',
                background: dragOver ? 'rgba(59,130,246,0.05)' : 'transparent',
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED}
                multiple
                style={{ display: 'none' }}
                onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ''; }}
              />
              <div style={{ fontSize: 36, marginBottom: 8 }}>&#128196;</div>
              <p style={{ color: '#94a3b8', margin: '0 0 4px', fontSize: 15 }}>
                Drag & drop .docx or .pdf files here, or click to browse
              </p>
              <p style={{ color: '#64748b', margin: 0, fontSize: 13 }}>
                Each file will be parsed for career history, bullets, skills, education, and certifications
              </p>
            </div>
          )}

          {/* File list */}
          {files.length > 0 && !done && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ color: '#cbd5e1', fontSize: 14, fontWeight: 600 }}>
                  {files.length} file{files.length !== 1 ? 's' : ''} selected
                </span>
                {!uploading && (
                  <button
                    onClick={() => setFiles([])}
                    style={{ background: 'none', border: 'none', color: '#ef4444', fontSize: 13, cursor: 'pointer' }}
                  >
                    Clear all
                  </button>
                )}
              </div>
              <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {files.map((f, i) => {
                  const r = results[i];
                  return (
                    <div
                      key={f.name + f.size}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '6px 10px', background: '#0f172a', borderRadius: 6, fontSize: 13,
                      }}
                    >
                      <span style={{ color: '#e2e8f0', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {f.name}
                        <span style={{ color: '#64748b', marginLeft: 8 }}>
                          ({(f.size / 1024).toFixed(0)} KB)
                        </span>
                      </span>
                      {r?.status === 'uploading' && <span style={{ color: '#3b82f6', fontSize: 12 }}>Processing...</span>}
                      {r?.status === 'success' && <span style={{ color: '#22c55e', fontSize: 12 }}>Done</span>}
                      {r?.status === 'failed' && <span style={{ color: '#ef4444', fontSize: 12 }}>Failed</span>}
                      {!uploading && !r && (
                        <button
                          onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                          style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: '0 4px' }}
                        >
                          &times;
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Results summary */}
          {done && (
            <div>
              <div style={{
                padding: 16, borderRadius: 8, marginBottom: 16,
                background: failCount === 0 ? 'rgba(34,197,94,0.1)' : 'rgba(234,179,8,0.1)',
                border: `1px solid ${failCount === 0 ? '#22c55e33' : '#eab30833'}`,
              }}>
                <p style={{ color: '#f1f5f9', margin: '0 0 8px', fontWeight: 600, fontSize: 15 }}>
                  Import Complete
                </p>
                <p style={{ color: '#94a3b8', margin: 0, fontSize: 14 }}>
                  {successCount} of {results.length} files processed successfully
                  {failCount > 0 && <span style={{ color: '#ef4444' }}> ({failCount} failed)</span>}
                </p>
              </div>

              {/* Totals */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
                {[
                  { label: 'Career Entries', value: totalCareer },
                  { label: 'Bullets', value: totalBullets },
                  { label: 'Skills', value: totalSkills },
                ].map((stat) => (
                  <div key={stat.label} style={{
                    background: '#0f172a', borderRadius: 8, padding: '12px 16px', textAlign: 'center',
                  }}>
                    <div style={{ color: '#3b82f6', fontSize: 22, fontWeight: 700 }}>{stat.value}</div>
                    <div style={{ color: '#94a3b8', fontSize: 12, marginTop: 2 }}>{stat.label}</div>
                  </div>
                ))}
              </div>

              {/* Per-file results */}
              <div style={{ maxHeight: 250, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {results.map((r) => (
                  <div
                    key={r.filename}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '6px 10px', background: '#0f172a', borderRadius: 6, fontSize: 13,
                    }}
                  >
                    <span style={{ color: '#e2e8f0', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: 12 }}>
                      {r.status === 'success' ? '\u2705' : '\u274c'} {r.filename}
                    </span>
                    {r.status === 'success' && (
                      <span style={{ color: '#64748b', fontSize: 12, whiteSpace: 'nowrap' }}>
                        {r.career_entries} jobs, {r.bullets} bullets, {r.skills} skills
                      </span>
                    )}
                    {r.status === 'failed' && r.errors?.[0] && (
                      <span style={{ color: '#ef4444', fontSize: 12, whiteSpace: 'nowrap', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {r.errors[0]}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid #334155', display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          {!done ? (
            <>
              <button
                onClick={handleClose}
                disabled={uploading}
                style={{
                  padding: '8px 20px', fontSize: 14, fontWeight: 500,
                  color: '#94a3b8', background: 'transparent', border: '1px solid #475569',
                  borderRadius: 8, cursor: uploading ? 'not-allowed' : 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={startUpload}
                disabled={!files.length || uploading}
                style={{
                  padding: '8px 20px', fontSize: 14, fontWeight: 500,
                  color: '#fff',
                  background: !files.length || uploading ? '#475569' : '#3b82f6',
                  border: 'none', borderRadius: 8,
                  cursor: !files.length || uploading ? 'not-allowed' : 'pointer',
                }}
              >
                {uploading
                  ? `Processing ${results.filter((r) => r.status === 'uploading').length > 0 ? '...' : ''}`
                  : `Import ${files.length} File${files.length !== 1 ? 's' : ''}`}
              </button>
            </>
          ) : (
            <button
              onClick={handleClose}
              style={{
                padding: '8px 20px', fontSize: 14, fontWeight: 500,
                color: '#fff', background: '#3b82f6', border: 'none',
                borderRadius: 8, cursor: 'pointer',
              }}
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
