import { useState, useEffect } from "react";
import StatusBar from "./components/StatusBar";
import Dashboard from "./components/Dashboard";
import SavedJobs from "./components/SavedJobs";
import JobDetails from "./components/JobDetails";
import GapAnalysis from "./components/GapAnalysis";
import ResumeSelector from "./components/ResumeSelector";
import NetworkingPanel from "./components/NetworkingPanel";
import ApplicationHistory from "./components/ApplicationHistory";
import SettingsPanel from "./components/SettingsPanel";

type Tab = "dashboard" | "job" | "gaps" | "resume" | "saved" | "network" | "history" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [mcpAvailable, setMcpAvailable] = useState(false);

  useEffect(() => {
    chrome.runtime.sendMessage({ type: "GET_MCP_STATUS" }).then((resp) => {
      if (resp?.available) setMcpAvailable(true);
    }).catch(() => {});
  }, []);

  const primaryTabs: { id: Tab; label: string }[] = [
    { id: "dashboard", label: "Home" },
    { id: "job", label: "Job" },
    { id: "gaps", label: "Fit" },
    { id: "resume", label: "Resume" },
  ];

  const secondaryTabs: { id: Tab; label: string }[] = [
    { id: "saved", label: "Saved" },
    { id: "network", label: "Network" },
    { id: "history", label: "History" },
    { id: "settings", label: "Settings" },
  ];

  return (
    <div className="flex flex-col h-full bg-st-bg">
      <div className="px-3 py-2 bg-st-surface border-b border-st-border flex items-center justify-between">
        <h1 className="text-sm font-bold text-st-green tracking-widest font-mono">
          SUPERTROOPERS
        </h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => chrome.tabs.create({ url: "http://localhost:5175/profile" })}
            title="Open Profile"
            className="text-[10px] font-mono text-st-muted hover:text-st-green transition-colors px-1.5 py-0.5 border border-st-border rounded hover:border-st-green"
          >
            Profile
          </button>
          <button
            onClick={() => chrome.tabs.create({ url: "http://localhost:5175" })}
            title="Open Dashboard"
            className="text-[10px] font-mono text-st-muted hover:text-st-green transition-colors px-1.5 py-0.5 border border-st-border rounded hover:border-st-green"
          >
            Dashboard
          </button>
          <span
            title={mcpAvailable ? "AI analysis available" : "AI analysis unavailable"}
            className={`text-xs font-mono ${mcpAvailable ? "text-st-green" : "text-st-muted opacity-40"}`}
          >
            &#x2317;
          </span>
        </div>
      </div>

      <StatusBar />

      {/* Primary tabs */}
      <div className="flex border-b border-st-border">
        {primaryTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-1.5 text-[10px] font-mono tracking-wider transition-colors ${
              tab === t.id
                ? "text-st-green border-b-2 border-st-green"
                : "text-st-muted hover:text-st-text"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Secondary tabs */}
      <div className="flex border-b border-st-border bg-st-surface/50">
        {secondaryTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-1 text-[10px] font-mono tracking-wider transition-colors ${
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
        {tab === "job" && <JobDetails />}
        {tab === "gaps" && <GapAnalysis />}
        {tab === "resume" && <ResumeSelector />}
        {tab === "saved" && <SavedJobs />}
        {tab === "network" && <NetworkingPanel />}
        {tab === "history" && <ApplicationHistory />}
        {tab === "settings" && <SettingsPanel />}
      </div>

      <div className="px-3 py-1 text-center text-[10px] text-st-muted border-t border-st-border">
        SuperTroopers v0.1.0
      </div>
    </div>
  );
}
