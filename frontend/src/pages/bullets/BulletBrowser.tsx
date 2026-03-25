import { useState } from 'react';
import JobList from './JobList';

export default function BulletBrowser() {
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Left Panel */}
      <div className="w-[340px] border-r border-gray-700 flex flex-col overflow-y-auto bg-gray-900">
        <JobList selectedJobId={selectedJobId} onSelectJob={setSelectedJobId} />
      </div>
      {/* Right Panel - placeholder until Tasks 7-8 */}
      <div className="flex-1 flex flex-col overflow-y-auto bg-gray-900">
        {selectedJobId ? (
          <div className="p-4 text-gray-400 text-sm">
            Job {selectedJobId} selected. Synopsis and bullet editors coming next.
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Select a job from the left to view its bullets
          </div>
        )}
      </div>
    </div>
  );
}
