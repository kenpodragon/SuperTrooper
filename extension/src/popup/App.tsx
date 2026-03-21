import { useState } from "react";
import StatusBar from "./components/StatusBar";
import Dashboard from "./components/Dashboard";
import Settings from "./components/Settings";
import SavedJobs from "./components/SavedJobs";

type Tab = "dashboard" | "saved" | "network" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  const tabs: { id: Tab; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "saved", label: "Jobs" },
    { id: "network", label: "Network" },
    { id: "settings", label: "Settings" },
  ];

  return (
    <div className="flex flex-col h-full bg-st-bg">
      <div className="px-3 py-2 bg-st-surface border-b border-st-border">
        <h1 className="text-sm font-bold text-st-green tracking-widest font-mono">
          SUPERTROOPERS
        </h1>
      </div>

      <StatusBar />

      <div className="flex border-b border-st-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-2 text-xs font-mono tracking-wider transition-colors ${
              tab === t.id
                ? "text-st-green border-b-2 border-st-green"
                : "text-st-muted hover:text-st-text"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === "dashboard" && <Dashboard />}
        {tab === "saved" && <SavedJobs />}
        {tab === "network" && (
          <div className="p-4 text-center text-st-muted text-sm">
            <p className="text-st-green mb-2">Phase 4</p>
            Networking features coming soon.
          </div>
        )}
        {tab === "settings" && <Settings />}
      </div>

      <div className="px-3 py-1 text-center text-[10px] text-st-muted border-t border-st-border">
        SuperTroopers v0.1.0
      </div>
    </div>
  );
}
