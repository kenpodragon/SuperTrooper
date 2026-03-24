import { useState, useEffect } from "react";
import { usePipeline, useHealth } from "../hooks/useBackend";
import LinkedInCompose from "./LinkedInCompose";

export default function Dashboard() {
  const { health } = useHealth();
  const { pipeline, loading } = usePipeline();

  const [unreadCount, setUnreadCount] = useState(0);
  const [autoApplyAI, setAutoApplyAI] = useState(false);
  const [showCompose, setShowCompose] = useState(false);

  useEffect(() => {
    fetch("http://localhost:8055/api/notifications?limit=50")
      .then((r) => r.json())
      .then((data) => {
        const list = data.notifications || data || [];
        setUnreadCount(list.filter((n: { read: boolean }) => !n.read).length);
      })
      .catch(() => {});

    // Load AI toggle state
    chrome.storage.local.get("autoApplyAI").then((result) => {
      if (result.autoApplyAI !== undefined) setAutoApplyAI(result.autoApplyAI);
    });
  }, []);

  const toggleAutoApplyAI = (val: boolean) => {
    setAutoApplyAI(val);
    chrome.storage.local.set({ autoApplyAI: val });
  };

  if (!health?.connected) {
    return (
      <div className="p-4 text-center">
        <div className="text-st-red text-3xl mb-3">&#x26A1;</div>
        <h2 className="text-lg font-bold text-st-text mb-2">Backend Offline</h2>
        <p className="text-sm text-st-muted mb-4">
          SuperTroopers backend is not running. Start Docker:
        </p>
        <code className="block bg-st-surface text-st-green text-xs p-3 rounded font-mono">
          cd code && docker compose up -d
        </code>
      </div>
    );
  }

  if (loading || !pipeline) {
    return (
      <div className="p-4 text-center text-st-muted">
        <div className="animate-pulse">Loading pipeline...</div>
      </div>
    );
  }

  const FRONTEND = "http://localhost:5175";

  const stats = [
    { label: "Saved", value: pipeline.saved || 0, color: "text-st-muted", path: "/saved-jobs" },
    { label: "Applied", value: pipeline.applied || 0, color: "text-blue-400", path: "/applications" },
    { label: "Interviewing", value: pipeline.interviewing || 0, color: "text-yellow-400", path: "/interviews" },
    { label: "Offered", value: pipeline.offered || 0, color: "text-st-green", path: "/applications?status=offered" },
  ];

  return (
    <div className="p-3 space-y-3">
      {/* Pipeline Stats */}
      <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
        &gt; Pipeline
      </h2>
      <div className="grid grid-cols-4 gap-2">
        {stats.map((s) => (
          <button
            key={s.label}
            onClick={() => chrome.tabs.create({ url: `${FRONTEND}${s.path}` })}
            className="bg-st-surface rounded p-2 border border-st-border text-center hover:border-st-green transition-colors cursor-pointer"
          >
            <div className={`text-lg font-bold font-mono ${s.color}`}>{s.value}</div>
            <div className="text-[10px] text-st-muted">{s.label}</div>
          </button>
        ))}
      </div>

      {/* Total + Notifications row */}
      <div className="flex gap-2">
        <button
          onClick={() => chrome.tabs.create({ url: `${FRONTEND}/applications` })}
          className="flex-1 bg-st-surface rounded p-2 border border-st-border text-center hover:border-st-green transition-colors cursor-pointer"
        >
          <div className="text-lg font-bold font-mono text-st-text">
            {(pipeline.saved || 0) + (pipeline.applied || 0) + (pipeline.interviewing || 0) + (pipeline.offered || 0)}
          </div>
          <div className="text-[10px] text-st-muted">Total Active</div>
        </button>
        {unreadCount > 0 && (
          <button
            onClick={() => chrome.tabs.create({ url: `${FRONTEND}/notifications` })}
            className="flex-1 bg-st-surface rounded p-2 border border-st-border text-center hover:border-st-green transition-colors cursor-pointer flex items-center justify-center gap-2"
          >
            <span className="bg-st-green text-st-bg text-[10px] font-bold font-mono rounded-full w-5 h-5 flex items-center justify-center">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
            <span className="text-[10px] text-st-text">notifications</span>
          </button>
        )}
      </div>

      {/* Auto Apply Section */}
      <div className="border-t border-st-border pt-3">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
            &gt; Auto Apply
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-st-muted">AI</span>
            <button
              onClick={() => toggleAutoApplyAI(!autoApplyAI)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                autoApplyAI ? "bg-st-green" : "bg-st-border"
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-st-bg transition-transform ${
                  autoApplyAI ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>
        </div>

        <div className="bg-st-surface rounded p-3 border border-st-border">
          <p className="text-xs text-st-muted mb-2">
            Auto-fill ATS forms on Workday, Greenhouse, Lever, LinkedIn Easy Apply and more.
          </p>
          <div className="flex items-center gap-2 text-[10px]">
            <span className={`px-2 py-0.5 rounded font-mono ${autoApplyAI ? "bg-st-green/10 text-st-green border border-st-green/30" : "bg-st-surface text-st-muted border border-st-border"}`}>
              {autoApplyAI ? "AI Enhanced" : "Rules Only"}
            </span>
            <span className="text-st-muted">
              {autoApplyAI ? "AI fills unknown fields intelligently" : "Fills known fields from your profile"}
            </span>
          </div>
        </div>
      </div>

      {/* LinkedIn Compose Section */}
      <div className="border-t border-st-border pt-3">
        {!showCompose ? (
          <button
            onClick={() => setShowCompose(true)}
            className="w-full bg-st-surface rounded p-3 border border-st-border hover:border-st-green transition-colors cursor-pointer flex items-center gap-2"
          >
            <svg className="w-4 h-4 text-st-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <div className="text-left">
              <div className="text-xs font-bold text-st-green font-mono tracking-wider">COMPOSE LINKEDIN MESSAGE</div>
              <div className="text-[10px] text-st-muted">Draft and send messages to your network contacts</div>
            </div>
          </button>
        ) : (
          <div className="bg-st-surface rounded p-3 border border-st-border">
            <LinkedInCompose onClose={() => setShowCompose(false)} />
          </div>
        )}
      </div>
    </div>
  );
}
