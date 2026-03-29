import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import JobList from './JobList';
import SynopsisEditor from './SynopsisEditor';
import BulletList from './BulletList';
import { HIGHLIGHTS_ID } from './MoveCloneModal';

interface CareerJobRow {
  id: number;
  employer: string;
  title: string;
  start_date?: string | null;
  end_date?: string | null;
  bullet_count?: number;
  is_company_entry?: boolean;
}

export default function BulletBrowser() {
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [aiEnabled, setAiEnabled] = useState(false);

  const isHighlights = selectedJobId === HIGHLIGHTS_ID;

  // Fetch career history + bullets for stats
  const { data: jobs = [] } = useQuery({
    queryKey: ['career-history'],
    queryFn: () => api.get<CareerJobRow[]>('/career-history?limit=200'),
  });

  const { data: allBullets = [] } = useQuery({
    queryKey: ['bullets-all'],
    queryFn: () => api.get<Array<{ id: number; career_history_id?: number | null }>>('/bullets?limit=5000'),
  });

  const bulletCountMap = useMemo(() => {
    const map: Record<number, number> = {};
    for (const b of allBullets) {
      if (b.career_history_id) {
        map[b.career_history_id] = (map[b.career_history_id] || 0) + 1;
      }
    }
    return map;
  }, [allBullets]);

  const highlightBulletCount = useMemo(
    () => allBullets.filter((b) => b.career_history_id == null).length,
    [allBullets],
  );

  const totalBullets = useMemo(
    () => Object.values(bulletCountMap).reduce((s, c) => s + c, 0) + highlightBulletCount,
    [bulletCountMap, highlightBulletCount],
  );

  const roleJobs = useMemo(() => jobs.filter((j) => !j.is_company_entry), [jobs]);

  const companyCount = useMemo(
    () => new Set(roleJobs.map((j) => j.employer)).size,
    [roleJobs],
  );

  const selectedJob = useMemo(
    () => (selectedJobId && selectedJobId > 0 ? jobs.find((j) => j.id === selectedJobId) : null),
    [selectedJobId, jobs],
  );

  const selectedJobBulletCount = isHighlights
    ? highlightBulletCount
    : selectedJob ? (bulletCountMap[selectedJob.id] || 0) : 0;

  // Stats for selected company
  const selectedCompanyStats = useMemo(() => {
    if (!selectedJob) return null;
    const companyJobs = jobs.filter((j) => j.employer === selectedJob.employer);
    const companyBullets = companyJobs.reduce((sum, j) => sum + (bulletCountMap[j.id] || 0), 0);
    return {
      employer: selectedJob.employer,
      roleCount: companyJobs.length,
      bulletCount: companyBullets,
    };
  }, [selectedJob, jobs, bulletCountMap]);

  const hasSelection = isHighlights || (selectedJobId !== null && selectedJob);

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Left Panel */}
      <div className="w-[420px] border-r border-gray-700 flex flex-col overflow-y-auto bg-gray-900">
        <JobList
          selectedJobId={selectedJobId}
          onSelectJob={setSelectedJobId}
          highlightBulletCount={highlightBulletCount}
        />
      </div>
      {/* Right Panel */}
      <div className="flex-1 flex flex-col overflow-y-auto bg-gray-900">
        {hasSelection ? (
          <>
            {/* Stats bar */}
            <div className="px-4 py-2 border-b border-gray-700 bg-gray-800/50">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-100 font-semibold truncate">
                  {isHighlights ? (
                    <span className="text-yellow-300">Top Resume Highlights</span>
                  ) : selectedJob?.is_company_entry ? (
                    <span className="text-amber-300">{selectedJob.employer} — Company Overview</span>
                  ) : (
                    selectedJob?.title
                  )}
                  <span className="text-gray-500 font-normal ml-2 text-xs">
                    {selectedJobBulletCount} bullet{selectedJobBulletCount !== 1 ? 's' : ''}
                  </span>
                </div>
                {!isHighlights && selectedCompanyStats && (
                  <div className="flex gap-3 text-xs text-gray-500 shrink-0">
                    <span>{selectedCompanyStats.employer}</span>
                    <span>{selectedCompanyStats.roleCount} role{selectedCompanyStats.roleCount !== 1 ? 's' : ''}</span>
                    <span>{selectedCompanyStats.bulletCount} bullets</span>
                  </div>
                )}
              </div>
            </div>
            <SynopsisEditor
              jobId={selectedJobId!}
              aiEnabled={aiEnabled}
              label={selectedJob?.is_company_entry ? 'Company Summary' : undefined}
            />
            <BulletList jobId={selectedJobId!} aiEnabled={aiEnabled} onAiToggle={setAiEnabled} />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            <div className="text-center">
              <div className="mb-2">Select a job from the left to view its bullets</div>
              <div className="text-xs text-gray-600">
                {companyCount} companies &middot; {roleJobs.length} roles &middot; {totalBullets} bullets
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
