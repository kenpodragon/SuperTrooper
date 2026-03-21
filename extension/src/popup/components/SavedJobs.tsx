import { useState, useEffect } from "react";
import { MSG } from "@shared/messages";
import type { SavedJob } from "@shared/types";

export default function SavedJobs() {
  const [jobs, setJobs] = useState<SavedJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    chrome.runtime.sendMessage({ type: MSG.GET_SAVED_JOBS })
      .then((resp: { jobs?: SavedJob[] } | undefined) => {
        setJobs(resp?.jobs || []);
      })
      .catch(() => setJobs([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-4 text-center text-st-muted text-sm">Loading...</div>;
  }

  if (jobs.length === 0) {
    return (
      <div className="p-4 text-center text-st-muted text-sm">
        <p className="text-lg mb-2">No saved jobs yet</p>
        <p className="text-xs">Visit a job listing and click "Save to SuperTroopers"</p>
      </div>
    );
  }

  return (
    <div className="p-2 space-y-2 max-h-[400px] overflow-y-auto">
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  );
}

function JobCard({ job }: { job: SavedJob }) {
  const score = job.fit_score;
  const scoreColor = !score
    ? "text-st-muted"
    : score >= 75
    ? "text-green-400"
    : score >= 50
    ? "text-yellow-400"
    : "text-red-400";

  return (
    <div className="bg-st-surface rounded-lg p-3 border border-st-border hover:border-st-green/30 transition">
      <div className="flex justify-between items-start">
        <div className="flex-1 min-w-0">
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-st-green text-sm font-semibold hover:underline truncate block"
          >
            {job.title}
          </a>
          <div className="text-st-text text-xs mt-0.5">{job.company}</div>
          {job.location && (
            <div className="text-st-muted text-xs">{job.location}</div>
          )}
        </div>
        <div className="flex-shrink-0 ml-2 text-center">
          {score != null ? (
            <div className={`text-lg font-bold font-mono ${scoreColor}`}>
              {Math.round(score)}%
            </div>
          ) : (
            <div className="text-st-muted text-xs">--</div>
          )}
          <div className="text-st-muted text-[10px]">FIT</div>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-st-bg text-st-muted uppercase font-mono">
          {job.source}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-st-bg text-st-muted uppercase font-mono">
          {job.status}
        </span>
        {job.salary_range && (
          <span className="text-[10px] text-st-muted">{job.salary_range}</span>
        )}
      </div>
    </div>
  );
}
