/**
 * GapAnalysis.tsx — Shows gap analysis results for the current job listing.
 * Calls backend gap analysis endpoint and displays matched/missing skills with fit score.
 */

import { useState, useEffect, useCallback } from "react";
import { sendToBackground, MSG } from "@shared/messages";
import type { GapAnalysisResult } from "@shared/types";

export default function GapAnalysis() {
  const [result, setResult] = useState<GapAnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState(false);

  const runAnalysis = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) {
        setError("No active tab");
        setLoading(false);
        return;
      }

      // Get job data from content script
      const response = await chrome.tabs.sendMessage(tab.id, { type: "GET_JOB_DATA" }).catch(() => null);

      if (!response?.job?.description) {
        setError("No job description found on this page");
        setLoading(false);
        return;
      }

      const gapResponse = await sendToBackground<{
        result: GapAnalysisResult;
        from_cache: boolean;
      }>(MSG.RUN_GAP_ANALYSIS, {
        jd_text: response.job.description,
        job_url: response.job.url || tab.url,
        force_refresh: forceRefresh,
        mode: "auto",
      });

      setResult(gapResponse.result);
      setFromCache(gapResponse.from_cache);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gap analysis failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    runAnalysis();
  }, [runAnalysis]);

  if (loading) {
    return (
      <div className="p-4 text-center text-st-muted text-sm">
        <div className="animate-pulse mb-2">Analyzing job fit...</div>
        <div className="text-[10px]">Comparing your profile against the JD</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-st-red text-sm mb-2">{error}</p>
        <p className="text-st-muted text-xs mb-3">
          Navigate to a job listing page to run gap analysis.
        </p>
        <button
          onClick={() => runAnalysis(true)}
          className="text-xs text-st-green hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!result) return null;

  const scoreColor =
    result.fit_score >= 75
      ? "text-st-green"
      : result.fit_score >= 50
      ? "text-yellow-400"
      : "text-st-red";

  return (
    <div className="p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
          &gt; Gap Analysis
        </h2>
        <div className="flex items-center gap-2">
          {fromCache && (
            <span className="text-[10px] text-st-muted italic">cached</span>
          )}
          <span className="text-[10px] text-st-muted font-mono">
            {result.analysis_mode === "ai" ? "AI" : "Rules"}
          </span>
          <button
            onClick={() => runAnalysis(true)}
            className="text-[10px] text-st-green hover:underline"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Overall Score */}
      <div className="bg-st-surface rounded p-4 border border-st-border text-center">
        <div className={`text-3xl font-bold font-mono ${scoreColor}`}>
          {result.fit_score}%
        </div>
        <div className="text-xs text-st-muted mt-1">Overall Fit</div>
      </div>

      {/* Strong Matches */}
      {result.strong_matches.length > 0 && (
        <div className="bg-st-surface rounded p-3 border border-st-border">
          <h3 className="text-xs text-st-green font-mono mb-2">
            Strong Matches ({result.strong_matches.length})
          </h3>
          <div className="flex flex-wrap gap-1">
            {result.strong_matches.map((skill) => (
              <span
                key={skill}
                className="text-[10px] px-2 py-0.5 rounded bg-st-green/10 text-st-green border border-st-green/30"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Partial Matches */}
      {result.partial_matches.length > 0 && (
        <div className="bg-st-surface rounded p-3 border border-st-border">
          <h3 className="text-xs text-yellow-400 font-mono mb-2">
            Partial Matches ({result.partial_matches.length})
          </h3>
          <div className="flex flex-wrap gap-1">
            {result.partial_matches.map((skill) => (
              <span
                key={skill}
                className="text-[10px] px-2 py-0.5 rounded bg-yellow-400/10 text-yellow-400 border border-yellow-400/30"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Gaps */}
      {result.gaps.length > 0 && (
        <div className="bg-st-surface rounded p-3 border border-st-border">
          <h3 className="text-xs text-st-red font-mono mb-2">
            Gaps ({result.gaps.length})
          </h3>
          <div className="flex flex-wrap gap-1">
            {result.gaps.map((skill) => (
              <span
                key={skill}
                className="text-[10px] px-2 py-0.5 rounded bg-red-400/10 text-st-red border border-red-400/30"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {result.recommendations.length > 0 && (
        <div className="bg-st-surface rounded p-3 border border-st-border">
          <h3 className="text-xs text-st-muted font-mono mb-2">Recommendations</h3>
          <ul className="space-y-1">
            {result.recommendations.map((rec, i) => (
              <li key={i} className="text-[10px] text-st-text flex gap-1">
                <span className="text-st-green flex-shrink-0">-</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
