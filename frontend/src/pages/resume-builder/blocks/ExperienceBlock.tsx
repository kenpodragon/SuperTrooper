import { DndContext, closestCenter, type DragEndEvent } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, arrayMove } from '@dnd-kit/sortable';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../../api/client';
import BlockWrapper from './BlockWrapper';
import BulletItem from './BulletItem';

interface BulletRef {
  ref?: string;
  id?: number;
  literal?: string;
}

interface JobEntry {
  ref?: string;
  id?: number;
  synopsis?: BulletRef;
  bullets: BulletRef[];
}

interface ResolvedJob {
  id?: number;
  employer?: string;
  title?: string;
  subheading?: string;
  start_date?: string;
  end_date?: string;
  location?: string;
  synopsis?: string;
  bullets?: string[];
  dates?: string;
}

interface Props {
  jobs: JobEntry[];
  resolvedJobs: ResolvedJob[];
  recipeId: number;
  onRecipeChange: (updatedExperience: JobEntry[]) => void;
  onPickBullet?: (jobIndex: number) => void;
  onAddJob?: () => void;
  onAiGenerate?: (jobIndex: number) => void;
}

export default function ExperienceBlock({
  jobs, resolvedJobs, recipeId, onRecipeChange, onPickBullet, onAddJob, onAiGenerate,
}: Props) {
  const qc = useQueryClient();

  const cloneMutation = useMutation({
    mutationFn: (body: { table: string; id: number }) =>
      api.post<{ id: number; table: string; text: string }>(`/resume/recipes/${recipeId}/clone-item`, body),
  });

  const editBulletMutation = useMutation({
    mutationFn: ({ bulletId, text }: { bulletId: number; text: string }) =>
      api.put(`/bullets/${bulletId}`, { text }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['recipe-builder'] }),
  });

  const handleBulletDragEnd = (jobIndex: number, event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const job = jobs[jobIndex];
    const oldIndex = job.bullets.findIndex((_, i) => `bullet-${jobIndex}-${i}` === active.id);
    const newIndex = job.bullets.findIndex((_, i) => `bullet-${jobIndex}-${i}` === over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    const updated = [...jobs];
    updated[jobIndex] = { ...job, bullets: arrayMove(job.bullets, oldIndex, newIndex) };
    onRecipeChange(updated);
  };

  const handleBulletEdit = (jobIndex: number, bulletIndex: number, text: string) => {
    const bullet = jobs[jobIndex].bullets[bulletIndex];
    if (bullet.ref === 'bullets' && bullet.id) {
      editBulletMutation.mutate({ bulletId: bullet.id, text });
    } else {
      const updated = [...jobs];
      updated[jobIndex] = {
        ...updated[jobIndex],
        bullets: updated[jobIndex].bullets.map((b, i) => i === bulletIndex ? { literal: text } : b),
      };
      onRecipeChange(updated);
    }
  };

  const handleBulletClone = async (jobIndex: number, bulletIndex: number) => {
    const bullet = jobs[jobIndex].bullets[bulletIndex];
    if (bullet.ref === 'bullets' && bullet.id) {
      const result = await cloneMutation.mutateAsync({ table: 'bullets', id: bullet.id });
      const updated = [...jobs];
      updated[jobIndex] = {
        ...updated[jobIndex],
        bullets: updated[jobIndex].bullets.map((b, i) => i === bulletIndex ? { ref: 'bullets', id: result.id } : b),
      };
      onRecipeChange(updated);
    }
  };

  const handleBulletDelete = (jobIndex: number, bulletIndex: number) => {
    const updated = [...jobs];
    updated[jobIndex] = {
      ...updated[jobIndex],
      bullets: updated[jobIndex].bullets.filter((_, i) => i !== bulletIndex),
    };
    onRecipeChange(updated);
  };

  return (
    <BlockWrapper label="Experience">
      {resolvedJobs.map((rJob, jobIdx) => (
        <div key={jobIdx} style={{ marginBottom: 16, paddingBottom: 8 }}>
          {/* Job header — employer/title left, dates/location right */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 'var(--font-size-body, 10.5pt)', color: '#111' }}>
                {rJob.employer || '[Employer]'}
              </div>
              {rJob.title && (
                <div style={{ fontSize: 'var(--font-size-body, 10.5pt)', color: '#333', fontStyle: 'italic' }}>
                  {rJob.title}
                </div>
              )}
              {rJob.subheading && (
                <div style={{ fontSize: 'var(--font-size-body, 10.5pt)', color: '#333', fontWeight: 600, marginTop: 2 }}>
                  {rJob.subheading}
                </div>
              )}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontSize: '9.5pt', color: '#444' }}>
                {rJob.dates || (rJob.start_date && `${rJob.start_date} \u2013 ${rJob.end_date || 'Present'}`)}
              </div>
              {rJob.location && (
                <div style={{ fontSize: '9pt', color: '#666' }}>{rJob.location}</div>
              )}
            </div>
          </div>

          {/* Synopsis / intro */}
          {rJob.synopsis && (
            <p style={{ fontSize: 'var(--font-size-body, 10.5pt)', color: '#333', fontStyle: 'italic', margin: '4px 0 6px', lineHeight: 1.4 }}>
              {rJob.synopsis}
            </p>
          )}

          {/* Bullets */}
          <DndContext collisionDetection={closestCenter} onDragEnd={(e) => handleBulletDragEnd(jobIdx, e)}>
            <SortableContext
              items={jobs[jobIdx].bullets.map((_, i) => `bullet-${jobIdx}-${i}`)}
              strategy={verticalListSortingStrategy}
            >
              <ul style={{ margin: 0, paddingLeft: 18, listStyleType: 'disc' }}>
                {jobs[jobIdx].bullets.map((bullet, bIdx) => (
                  <BulletItem
                    key={`bullet-${jobIdx}-${bIdx}`}
                    sortableId={`bullet-${jobIdx}-${bIdx}`}
                    bullet={bullet}
                    resolvedText={rJob.bullets?.[bIdx] ?? ''}
                    index={bIdx}
                    onEdit={(text) => handleBulletEdit(jobIdx, bIdx, text)}
                    onClone={() => handleBulletClone(jobIdx, bIdx)}
                    onDelete={() => handleBulletDelete(jobIdx, bIdx)}
                  />
                ))}
              </ul>
            </SortableContext>
          </DndContext>

          {/* Action buttons — visible on hover */}
          <div className="group/job" style={{ marginLeft: 18, marginTop: 4 }}>
            <div style={{ display: 'flex', gap: 12, opacity: 0.6 }} className="group-hover/job:!opacity-100">
              <button
                onClick={() => onPickBullet?.(jobIdx)}
                style={{ fontSize: 11, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}
              >
                + Add bullet
              </button>
              <button
                onClick={() => onAiGenerate?.(jobIdx)}
                style={{ fontSize: 11, color: '#7c3aed', background: 'none', border: 'none', cursor: 'pointer' }}
              >
                AI Generate
              </button>
            </div>
          </div>
        </div>
      ))}
      <button
        onClick={onAddJob}
        style={{ fontSize: 12, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', marginTop: 8 }}
      >
        + Add job
      </button>
    </BlockWrapper>
  );
}
