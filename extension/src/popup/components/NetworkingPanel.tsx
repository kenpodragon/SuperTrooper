/**
 * NetworkingPanel.tsx — Shows contacts at the current job's company.
 * Fetches contacts from the backend filtered by company name.
 */

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@shared/api";

interface Contact {
  id: number;
  name: string;
  company?: string;
  title?: string;
  relationship_stage?: string;
  last_touchpoint?: string;
  email?: string;
  linkedin_url?: string;
  notes?: string;
}

interface ContactsResponse {
  contacts: Contact[];
}

const STAGE_COLORS: Record<string, string> = {
  cold: "text-st-muted",
  warm: "text-yellow-400",
  hot: "text-orange-400",
  connected: "text-st-green",
  referred: "text-blue-400",
  dormant: "text-st-muted opacity-60",
};

function formatDate(dateStr?: string): string {
  if (!dateStr) return "Never";
  const d = new Date(dateStr);
  const now = new Date();
  const days = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export default function NetworkingPanel() {
  const [contacts, setContacts] = useState<Contact[]>([]);
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

  const loadContacts = useCallback(async (companyName: string) => {
    setLoading(true);
    setError(null);
    try {
      const encoded = encodeURIComponent(companyName);
      const data = await apiFetch<ContactsResponse>(`/api/contacts?company=${encoded}`);
      setContacts(data.contacts || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load contacts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    detectCompany().then((detected) => {
      if (detected) {
        setCompany(detected);
        setSearchCompany(detected);
        loadContacts(detected);
      } else {
        setLoading(false);
      }
    });
  }, [detectCompany, loadContacts]);

  const handleSearch = () => {
    if (searchCompany.trim()) {
      setCompany(searchCompany.trim());
      loadContacts(searchCompany.trim());
    }
  };

  return (
    <div className="p-3 space-y-3">
      <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
        &gt; Network
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
          Loading contacts...
        </div>
      )}

      {error && (
        <div className="text-center text-st-red text-sm">{error}</div>
      )}

      {!loading && !error && company && contacts.length === 0 && (
        <div className="text-center text-st-muted text-sm py-4">
          <p className="mb-1">No contacts at {company}</p>
          <p className="text-xs">Add contacts through the main app to see them here.</p>
        </div>
      )}

      {!loading && !company && (
        <div className="text-center text-st-muted text-sm py-4">
          <p className="mb-1">Search for a company</p>
          <p className="text-xs">Or navigate to a job listing to auto-detect.</p>
        </div>
      )}

      {/* Contact Cards */}
      {contacts.map((contact) => {
        const stageColor = STAGE_COLORS[contact.relationship_stage || "cold"] || "text-st-muted";
        return (
          <div
            key={contact.id}
            className="bg-st-surface rounded p-3 border border-st-border"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1 min-w-0">
                <div className="text-st-text text-xs font-semibold truncate">
                  {contact.name}
                </div>
                {contact.title && (
                  <div className="text-st-muted text-[10px] truncate">{contact.title}</div>
                )}
              </div>
              <div className="text-right flex-shrink-0 ml-2">
                <div className={`text-[10px] font-mono font-bold capitalize ${stageColor}`}>
                  {contact.relationship_stage || "unknown"}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between mt-2 pt-2 border-t border-st-border">
              <div className="text-[10px] text-st-muted">
                Last touch: {formatDate(contact.last_touchpoint)}
              </div>
              <div className="flex gap-2">
                {contact.email && (
                  <a
                    href={`mailto:${contact.email}`}
                    className="text-[10px] text-st-green hover:underline"
                    title={contact.email}
                  >
                    Email
                  </a>
                )}
                {contact.linkedin_url && (
                  <a
                    href={contact.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] text-st-green hover:underline"
                  >
                    LinkedIn
                  </a>
                )}
              </div>
            </div>

            {contact.notes && (
              <div className="mt-1 text-[10px] text-st-muted italic truncate">
                {contact.notes}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
