import { useState } from 'react';
import JobList from './JobList';
import SynopsisEditor from './SynopsisEditor';
import BulletList from './BulletList';

export default function BulletBrowser() {
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [aiEnabled, setAiEnabled] = useState(false);

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Left Panel */}
      <div className="w-[340px] border-r border-gray-700 flex flex-col overflow-y-auto bg-gray-900">
        <JobList selectedJobId={selectedJobId} onSelectJob={setSelectedJobId} />
      </div>
      {/* Right Panel */}
      <div className="flex-1 flex flex-col overflow-y-auto bg-gray-900">
        {selectedJobId ? (
          <>
            <SynopsisEditor jobId={selectedJobId} aiEnabled={aiEnabled} />
            <BulletList jobId={selectedJobId} aiEnabled={aiEnabled} onAiToggle={setAiEnabled} />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Select a job from the left to view its bullets
          </div>
        )}
      </div>
    </div>
  );
}
