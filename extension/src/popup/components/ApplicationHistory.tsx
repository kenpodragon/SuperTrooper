/**
 * ApplicationHistory.tsx — Shows past applications at the current or searched company.
 * Fetches from GET /api/applications filtered by company.
 */

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@shared/api";

interface Application {
  id: number;
  company_name?: string;
  company?: string;
  role?: string;
  status?: string;
  date_applied?: string;
  applied_at?: string;
  source?: string;
  notes?: string;
  created_at?: string;
}

interface ApplicationsResponse {
  applications: Application[];
}

const STATUS_COLORS: Record<string, string> = {
  saved: "text-st-muted",
  applied: "text-blue-400",
  phone_screen: "text-yellow-400",
  interview: "text-orange-400",
  offer: "text-st-green",
  rejected: "text-red-400",
  withdrawn: "text-st-muted opacity-60",
};

const STATUS_LABELS: Record<string, string> = {
  saved: "Saved",
  applied: "Applied",
  phone_screen: "Phone Screen",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

function formatDate(dateStr?: string): string {
  if (!dateStr) return "Unknown";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function ApplicationHistory() {
  const [apps, setApps] = useState<Application[]>([]);
  const [company, setCompany] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchCompany, setSearchCompany] = useState("");

  const detectCompany = useCallback(async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) return null;
      const response = await chrome.tabs.sendMessage(tab.id, { type: "GET_JOB_DATA" }).catch(() => null);
      return response?.job?.company || null;
    } catch {
      return null;
    }
  }, []);

  const loadApplications = useCallback(async (companyName: string) => {
    setLoading(true);
    setError(null);
    try {
      const encoded = encodeURIComponent(companyName);
      const data = await apiFetch<ApplicationsResponse>(
        `/api/applications?company=${encoded}`
      );
      setApps(data.applications || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load applications");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    detectCompany().then((detected) => {
      if (detected) {
        setCompany(detected);
        setSearchCompany(detected);
        loadApplications(detected);
      } else {
        setLoading(false);
      }
    });
  }, [detectCompany, loadApplications]);

  const handleSearch = () => {
    if (searchCompany.trim()) {
      setCompany(searchCompany.trim());
      loadApplications(searchCompany.trim());
    }
  };

  return (
    <div className="p-3 space-y-3">
      <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
        &gt; Application History
      </h2>

      {/* Company Search */}
      <div className="flex gap-2">
        <input
          type="text"
          value={searchCompany}
          onChange={(e) => setSearchCompany(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Company name..."
          className="flex-1 bg-st-surface border border-st-border rounded px-3 py-1.5 text-xs text-st-text font-mono focus:border-st-green focus:outline-none"
        />
        <button
          onClick={handleSearch}
          className="px-3 py-1.5 rounded text-xs font-bold bg-st-green text-st-bg hover:bg-st-green-dim transition-colors"
        >
          Search
        </button>
      </div>

      {loading && (
        <div className="text-center text-st-muted text-sm animate-pulse">
          Loading applications...
        </div>
      )}

      {error && (
        <div className="text-center text-st-red text-sm">{error}</div>
      )}

      {!loading && !error && company && apps.length === 0 && (
        <div className="text-center text-st-muted text-sm py-4">
          <p className="mb-1">No applications at {company}</p>
          <p className="text-xs">Apply through the plugin to track automatically.</p>
        </div>
      )}

      {!loading && !company && (
        <div className="text-center text-st-muted text-sm py-4">
          <p className="mb-1">Search for a company</p>
          <p className="text-xs">Or navigate to a job listing to auto-detect.</p>
        </div>
      )}

      {/* Application Cards */}
      {apps.map((app) => {
        const status = app.status || "saved";
        const statusColor = STATUS_COLORS[status] || "text-st-muted";
        const appliedDate = app.date_applied || app.applied_at || app.created_at;

        return (
          <div
            key={app.id}
            className="bg-st-surface rounded p-3 border border-st-border"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1 min-w-0">
                <div className="text-st-text text-xs font-semibold truncate">
                  {app.role || "Unknown Role"}
                </div>
                <div className="text-st-muted text-[10px] truncate">
                  {app.company_name || app.company}
                </div>
              </div>
              <div className="text-right flex-shrink-0 ml-2">
                <div className={`text-[10px] font-mono font-bold ${statusColor}`}>
                  {STATUS_LABELS[status] || status}
                </div>
                <div className="text-st-muted text-[10px]">
                  {formatDate(appliedDate)}
                </div>
              </div>
            </div>

            {app.source && (
              <div className="mt-1 text-[10px] text-st-muted">
                via {app.source}
              </div>
            )}

            {app.notes && (
              <div className="mt-1 text-[10px] text-st-muted italic truncate">
                {app.notes}
              </div>
            )}
          </div>
        );
      })}

      {/* Summary */}
      {apps.length > 0 && (
        <div className="bg-st-surface rounded p-2 border border-st-border text-center">
          <span className="text-[10px] text-st-muted">
            {apps.length} application{apps.length !== 1 ? "s" : ""} at {company}
          </span>
        </div>
      )}
    </div>
  );
}
