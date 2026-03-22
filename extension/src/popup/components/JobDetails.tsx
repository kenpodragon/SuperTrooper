/**
 * JobDetails.tsx — Shows details of the currently captured job from the active tab.
 * Displays title, company, location, match score. Includes Save Job and Quick Apply buttons.
 */

import { useState, useEffect, useCallback } from "react";
import { sendToBackground, MSG } from "@shared/messages";
import type { JobExtraction, SavedJob } from "@shared/types";

interface CurrentJobState {
  job: JobExtraction | null;
  savedJob: SavedJob | null;
  alreadySaved: boolean;
}

export default function JobDetails() {
  const [state, setState] = useState<CurrentJobState>({
    job: null,
    savedJob: null,
    alreadySaved: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [fitScore, setFitScore] = useState<number | null>(null);

  const loadCurrentJob = useCallback(async () => {
    setLoading(true);
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) {
        setLoading(false);
        return;
      }

      // Ask content script for extracted job data
      const response = await chrome.tabs.sendMessage(tab.id, { type: "GET_JOB_DATA" }).catch(() => null);

      if (response?.job) {
        const job = response.job as JobExtraction;

        // Check if already saved
        const urlCheck = await sendToBackground<{ exists: boolean; saved_job?: SavedJob }>(
          MSG.CHECK_JOB_URL,
          { url: job.url }
        ).catch(() => ({ exists: false }));

        setState({
          job,
          savedJob: urlCheck.saved_job || null,
          alreadySaved: urlCheck.exists,
        });

        // Get fit score if available
        if (urlCheck.saved_job?.fit_score) {
          setFitScore(urlCheck.saved_job.fit_score);
        }
      }
    } catch (err) {
      console.warn("[SuperTroopers] Failed to get job data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCurrentJob();
  }, [loadCurrentJob]);

  const handleSave = async () => {
    if (!state.job || state.alreadySaved) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const result = await sendToBackground<{ saved_job: SavedJob; already_existed: boolean }>(
        MSG.SAVE_JOB,
        { job: state.job }
      );
      setState((prev) => ({
        ...prev,
        savedJob: result.saved_job,
        alreadySaved: true,
      }));
      setSaveMsg(result.already_existed ? "Already in your list" : "Job saved");
    } catch (err) {
      setSaveMsg("Save failed");
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 3000);
    }
  };

  const handleQuickApply = async () => {
    if (!state.job) return;
    // Open the job URL in a new tab for manual application
    chrome.tabs.create({ url: state.job.url });
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-st-muted text-sm animate-pulse">
        Checking current page...
      </div>
    );
  }

  if (!state.job) {
    return (
      <div className="p-4 text-center text-st-muted text-sm">
        <p className="text-lg mb-1">No job detected</p>
        <p className="text-xs">Navigate to a job listing on Indeed, LinkedIn, Glassdoor, or another supported board.</p>
      </div>
    );
  }

  const { job } = state;

  return (
    <div className="p-3 space-y-3">
      <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
        &gt; Current Job
      </h2>

      <div className="bg-st-surface rounded p-3 border border-st-border">
        <div className="text-st-text text-sm font-semibold">{job.title}</div>
        <div className="text-st-green text-xs font-mono mt-0.5">{job.company}</div>
        {job.location && (
          <div className="text-st-muted text-xs mt-1">{job.location}</div>
        )}
        {job.salary && (
          <div className="text-st-muted text-xs">{job.salary}</div>
        )}
        <div className="text-st-muted text-[10px] mt-1 truncate">{job.source}</div>
      </div>

      {/* Fit Score */}
      {fitScore !== null && (
        <div className="bg-st-surface rounded p-3 border border-st-border flex items-center justify-between">
          <span className="text-xs text-st-muted">Match Score</span>
          <span
            className={`text-lg font-bold font-mono ${
              fitScore >= 75
                ? "text-st-green"
                : fitScore >= 50
                ? "text-yellow-400"
                : "text-st-red"
            }`}
          >
            {fitScore}%
          </span>
        </div>
      )}

      {/* JD Preview */}
      {job.description && (
        <div className="bg-st-surface rounded p-3 border border-st-border">
          <div className="text-xs text-st-muted mb-1">Description Preview</div>
          <div className="text-xs text-st-text leading-relaxed line-clamp-4">
            {job.description.slice(0, 300)}
            {job.description.length > 300 ? "..." : ""}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving || state.alreadySaved}
          className={`flex-1 py-2 rounded text-sm font-bold transition-colors ${
            state.alreadySaved
              ? "bg-st-surface text-st-green border border-st-green cursor-default"
              : "bg-st-green text-st-bg hover:bg-st-green-dim disabled:opacity-40"
          }`}
        >
          {state.alreadySaved ? "Saved" : saving ? "Saving..." : "Save Job"}
        </button>
        <button
          onClick={handleQuickApply}
          className="flex-1 py-2 rounded text-sm font-bold border border-st-border text-st-text hover:border-st-green hover:text-st-green transition-colors"
        >
          Quick Apply
        </button>
      </div>

      {saveMsg && (
        <div className="text-center text-xs text-st-green">{saveMsg}</div>
      )}
    </div>
  );
}
