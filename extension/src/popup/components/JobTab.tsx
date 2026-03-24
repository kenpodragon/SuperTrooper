/**
 * JobTab.tsx — Consolidated job context tab with sub-tabs.
 * Sub-tabs: Save (job details + save), Fit (gap analysis), Resume (recipe selector), Network (contacts).
 * All sub-tabs are context-aware — they pull data from the current page's job listing.
 */

import { useState } from "react";
import JobDetails from "./JobDetails";
import GapAnalysis from "./GapAnalysis";
import ResumeSelector from "./ResumeSelector";
import NetworkingPanel from "./NetworkingPanel";

type SubTab = "save" | "fit" | "resume" | "contacts";

export default function JobTab() {
  const [subTab, setSubTab] = useState<SubTab>("save");

  const subTabs: { id: SubTab; label: string }[] = [
    { id: "save", label: "Save" },
    { id: "fit", label: "Fit" },
    { id: "resume", label: "Resume" },
    { id: "contacts", label: "Contacts" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Sub-tab bar */}
      <div className="flex border-b border-st-border bg-st-surface/50">
        {subTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id)}
            className={`flex-1 py-1 text-[10px] font-mono tracking-wider transition-colors ${
              subTab === t.id
                ? "text-st-green border-b-2 border-st-green"
                : "text-st-muted hover:text-st-text"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Sub-tab content */}
      <div className="flex-1 overflow-y-auto">
        {subTab === "save" && <JobDetails />}
        {subTab === "fit" && <GapAnalysis />}
        {subTab === "resume" && <ResumeSelector />}
        {subTab === "contacts" && <NetworkingPanel />}
      </div>
    </div>
  );
}
