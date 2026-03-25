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
  start_date?: string;
  end_date?: string;
  location?: string;
  synopsis?: string;
  bullets?: string[];
}

interface Props {
  jobs: JobEntry[];
  resolvedJobs: ResolvedJob[];
  recipeId: number;
  onRecipeChange: (updatedExperience: JobEntry[]) => void;
  onPickBullet?: (jobIndex: number) => void;
  onAddJob?: () => void;
}

export default function ExperienceBlock({
  jobs, resolvedJobs, recipeId, onRecipeChange, onPickBullet, onAddJob,
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
        <div key={jobIdx} className="mb-6 last:mb-0">
          <div className="flex justify-between items-start mb-1">
            <div>
              <h3 className="font-bold text-base">{rJob.employer}</h3>
              <p className="text-sm text-gray-300">{rJob.title}</p>
            </div>
            <div className="text-right text-sm text-gray-400">
              <p>{rJob.start_date} - {rJob.end_date}</p>
              {rJob.location && <p>{rJob.location}</p>}
            </div>
          </div>
          {rJob.synopsis && <p className="text-sm text-gray-300 italic mb-2">{rJob.synopsis}</p>}
          <DndContext collisionDetection={closestCenter} onDragEnd={(e) => handleBulletDragEnd(jobIdx, e)}>
            <SortableContext
              items={jobs[jobIdx].bullets.map((_, i) => `bullet-${jobIdx}-${i}`)}
              strategy={verticalListSortingStrategy}
            >
              <ul className="space-y-1 ml-2">
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
          <button onClick={() => onPickBullet?.(jobIdx)} className="text-xs text-blue-400 hover:text-blue-300 mt-2 ml-6">
            + Add bullet
          </button>
        </div>
      ))}
      <button onClick={onAddJob} className="text-sm text-blue-400 hover:text-blue-300 mt-4">
        + Add job
      </button>
    </BlockWrapper>
  );
}
