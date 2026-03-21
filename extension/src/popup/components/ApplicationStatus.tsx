/**
 * ApplicationStatus.tsx — Recent applications list with quick status updates.
 * Popup component (React functional component).
 */

import { useState, useEffect, useCallback } from "react";

interface Application {
  id: number;
  company: string;
  role: string;
  status: string;
  applied_at: string;
  url?: string;
}

type AppStatus = "applied" | "phone_screen" | "interview" | "offer" | "rejected";

const STATUS_FLOW: AppStatus[] = ["applied", "phone_screen", "interview", "offer"];

const STATUS_LABELS: Record<string, string> = {
  applied: "Applied",
  phone_screen: "Phone",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

const STATUS_COLORS: Record<string, string> = {
  applied: "text-blue-400",
  phone_screen: "text-yellow-400",
  interview: "text-orange-400",
  offer: "text-st-green",
  rejected: "text-red-400",
};

function daysSince(dateStr: string): number {
  const d = new Date(dateStr);
  const now = new Date();
  return Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
}

function nextStatus(current: string): AppStatus | null {
  const idx = STATUS_FLOW.indexOf(current as AppStatus);
  if (idx === -1 || idx >= STATUS_FLOW.length - 1) return null;
  return STATUS_FLOW[idx + 1];
}

async function fetchApplications(): Promise<Application[]> {
  try {
    const res = await fetch("http://localhost:8055/api/applications?limit=10&sort=-applied_at", {
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.applications || data || [];
  } catch {
    return [];
  }
}

async function updateApplicationStatus(id: number, status: string): Promise<boolean> {
  try {
    const res = await fetch(`http://localhost:8055/api/applications/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export default function ApplicationStatus() {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const data = await fetchApplications();
    setApps(data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdvance = async (app: Application) => {
    const next = nextStatus(app.status);
    if (!next) return;
    setUpdating(app.id);
    const ok = await updateApplicationStatus(app.id, next);
    if (ok) {
      setApps((prev) =>
        prev.map((a) => (a.id === app.id ? { ...a, status: next } : a))
      );
    }
    setUpdating(null);
  };

  if (loading) {
    return <div className="p-4 text-center text-st-muted text-sm animate-pulse">Loading...</div>;
  }

  if (apps.length === 0) {
    return (
      <div className="p-4 text-center text-st-muted text-sm">
        <p className="text-lg mb-1">No applications yet</p>
        <p className="text-xs">Applications tracked automatically when you submit.</p>
      </div>
    );
  }

  return (
    <div className="p-2 space-y-2">
      <h2 className="text-xs font-bold text-st-green tracking-wider uppercase px-1">
        &gt; Recent Applications
      </h2>
      {apps.map((app) => {
        const days = daysSince(app.applied_at);
        const next = nextStatus(app.status);
        const statusColor = STATUS_COLORS[app.status] || "text-st-muted";
        const isUpdating = updating === app.id;

        return (
          <div
            key={app.id}
            className="bg-st-surface rounded p-3 border border-st-border"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1 min-w-0">
                <div className="text-st-text text-xs font-semibold truncate">
                  {app.company}
                </div>
                <div className="text-st-muted text-[10px] truncate">{app.role}</div>
              </div>
              <div className="text-right flex-shrink-0 ml-2">
                <div className={`text-[10px] font-mono font-bold ${statusColor}`}>
                  {STATUS_LABELS[app.status] || app.status}
                </div>
                <div className="text-st-muted text-[10px]">
                  {days === 0 ? "Today" : `${days}d ago`}
                </div>
              </div>
            </div>

            {next && (
              <button
                onClick={() => handleAdvance(app)}
                disabled={isUpdating}
                className="mt-2 w-full text-[10px] font-mono py-1 px-2 rounded border border-st-border text-st-muted hover:border-st-green hover:text-st-green transition disabled:opacity-40"
              >
                {isUpdating ? "..." : `Advance to ${STATUS_LABELS[next]}`}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
