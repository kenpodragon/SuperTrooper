import { useState, useRef, useCallback, useEffect } from "react";

const API = "http://localhost:8055";

type OutreachType = "cold" | "warm" | "follow_up";

interface Draft {
  id: number;
  subject?: string;
  body?: string;
  contact_id?: number;
  contact_name?: string;
}

export default function LinkedInCompose({ onClose }: { onClose: () => void }) {
  const [to, setTo] = useState("");
  const [contactId, setContactId] = useState<number | null>(null);
  const [contactMatch, setContactMatch] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [outreachType, setOutreachType] = useState<OutreachType>("cold");
  const [useAi, setUseAi] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [showHelp, setShowHelp] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [statusColor, setStatusColor] = useState("#8899aa");
  const [draftId, setDraftId] = useState<number | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const lastSaved = useRef("");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Search for contact by name
  const searchContact = useCallback(async (name: string) => {
    if (name.trim().length < 2) { setContactId(null); setContactMatch(null); return; }
    try {
      const res = await fetch(`${API}/api/contacts?q=${encodeURIComponent(name)}&limit=1`);
      const data = await res.json();
      const contacts = data.contacts || data || [];
      if (contacts.length > 0) {
        setContactId(contacts[0].id);
        setContactMatch(`${contacts[0].name}${contacts[0].company ? ` - ${contacts[0].company}` : ""}`);
      } else {
        setContactId(null);
        setContactMatch(null);
      }
    } catch { setContactId(null); setContactMatch(null); }
  }, []);

  // Debounce contact search
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleToChange = (val: string) => {
    setTo(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => searchContact(val), 400);
  };

  // Auto-save draft
  const saveDraft = useCallback(async (newBody?: string) => {
    const b = newBody ?? body;
    if (!b.trim() || b === lastSaved.current) return;
    try {
      if (draftId) {
        await fetch(`${API}/api/crm/drafts/${draftId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: b, subject: "", action: "update" }),
        });
      } else if (contactId) {
        const res = await fetch(`${API}/api/crm/send-message`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ contact_id: contactId, channel: "linkedin", action: "draft", subject: "", body: b }),
        });
        const data = await res.json();
        if (data.outreach?.id) setDraftId(data.outreach.id);
      }
      lastSaved.current = b;
      flash("Draft saved", "#00FF41");
    } catch {}
  }, [body, draftId, contactId]);

  useEffect(() => {
    if (!body.trim() || body === lastSaved.current) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => saveDraft(), 2000);
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, [body, saveDraft]);

  function flash(msg: string, color = "#8899aa") {
    setStatus(msg); setStatusColor(color);
    setTimeout(() => setStatus(null), 2500);
  }

  // Generate message (includes AI prompt + existing body when AI is on)
  const handleGenerate = async () => {
    setIsBusy(true);
    flash(useAi ? "AI generating..." : "Generating...", useAi ? "#a855f7" : "#8899aa");
    try {
      const payload: Record<string, unknown> = {
        contact_id: contactId, type: outreachType, use_ai: useAi,
        channel: "linkedin",
      };
      if (useAi) {
        payload.prompt = aiPrompt;
        payload.existing_body = body;
      }
      const res = await fetch(`${API}/api/crm/generate-outreach`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.error) { flash(data.error, "#ff4444"); return; }
      const b = data.outreach?.body || "";
      setBody(b);
      flash(data.outreach?.mode === "ai" ? "AI generated" : "Template generated", "#00FF41");
      if (b.trim()) saveDraft(b);
    } catch (e: any) { flash(e.message || "Failed", "#ff4444"); }
    finally { setIsBusy(false); }
  };

  // Ask AI (with prompt + existing body)
  const handleAskAi = async () => {
    setIsBusy(true);
    flash("AI thinking...", "#a855f7");
    try {
      const res = await fetch(`${API}/api/crm/generate-outreach`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contact_id: contactId, type: outreachType, use_ai: true,
          channel: "linkedin", prompt: aiPrompt, existing_body: body,
        }),
      });
      const data = await res.json();
      if (data.error) { flash(data.error, "#ff4444"); return; }
      const b = data.outreach?.body || "";
      setBody(b);
      flash("AI response ready", "#00FF41");
      if (b.trim()) saveDraft(b);
    } catch (e: any) { flash(e.message || "Failed", "#ff4444"); }
    finally { setIsBusy(false); }
  };

  // AI Wordsmith
  const handleWordsmith = async () => {
    if (!body.trim()) return;
    setIsBusy(true);
    flash("Wordsmithing...", "#a855f7");
    try {
      const res = await fetch(`${API}/api/crm/wordsmith`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body, contact_id: contactId, channel: "linkedin" }),
      });
      const data = await res.json();
      if (data.body) {
        setBody(data.body);
        flash("AI polished", "#00FF41");
        saveDraft(data.body);
      } else { flash("AI unavailable", "#ff4444"); }
    } catch { flash("Wordsmith failed", "#ff4444"); }
    finally { setIsBusy(false); }
  };

  // Copy to clipboard
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(body);
      flash("Copied to clipboard!", "#00FF41");
    } catch { flash("Copy failed", "#ff4444"); }
  };

  // Delete draft
  const handleDelete = async () => {
    if (!draftId) return;
    try {
      await fetch(`${API}/api/crm/drafts/${draftId}`, { method: "DELETE" });
      setBody(""); setDraftId(null); lastSaved.current = "";
      flash("Draft deleted", "#00FF41");
    } catch { flash("Delete failed", "#ff4444"); }
  };

  const S = {
    input: "w-full bg-[#0f172a] border border-[#1f3460] rounded px-2 py-1.5 text-xs text-[#e0e0e0] font-mono focus:outline-none focus:border-[#00FF41]",
    btn: "px-2.5 py-1 text-[10px] font-bold font-mono rounded border cursor-pointer transition-all disabled:opacity-40",
    btnGreen: "border-[#00FF41] bg-[#1a1a2e] text-[#00FF41] hover:bg-[#00FF41] hover:text-[#1a1a2e]",
    btnPurple: "border-[#a855f7] bg-[#1a1a2e] text-[#a855f7] hover:bg-[#a855f7] hover:text-[#1a1a2e]",
    btnMuted: "border-[#1f3460] bg-[#16213e] text-[#8899aa] hover:border-[#8899aa]",
  };

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-bold text-[#00FF41] tracking-wider uppercase">&gt; LinkedIn Message</h3>
          {status && <span className="text-[9px] font-mono" style={{ color: statusColor }}>{status}</span>}
        </div>
        <button onClick={onClose} className="text-[#8899aa] hover:text-[#e0e0e0] text-sm">&times;</button>
      </div>

      {/* TO field */}
      <div>
        <label className="text-[10px] text-[#8899aa] font-mono mb-0.5 block">TO:</label>
        <input
          type="text" value={to} onChange={(e) => handleToChange(e.target.value)}
          placeholder="Contact name..."
          className={S.input}
        />
        {contactMatch && (
          <div className="text-[9px] text-[#00FF41] mt-0.5 font-mono">Found: {contactMatch}</div>
        )}
        {to.trim().length >= 2 && !contactMatch && (
          <div className="text-[9px] text-[#ff4444] mt-0.5 font-mono">No matching contact</div>
        )}
      </div>

      {/* Type + Generate + AI toggle */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <select value={outreachType} onChange={(e) => setOutreachType(e.target.value as OutreachType)}
          className="bg-[#0f172a] border border-[#1f3460] rounded px-1.5 py-1 text-[10px] text-[#e0e0e0] font-mono focus:outline-none">
          <option value="cold">Cold</option>
          <option value="warm">Warm</option>
          <option value="follow_up">Follow-up</option>
        </select>
        <button onClick={handleGenerate} disabled={isBusy || !contactId}
          className={`${S.btn} ${useAi ? S.btnPurple : S.btnMuted} flex items-center gap-1`}>
          {isBusy && !useAi ? "..." : "Generate"}
        </button>
        <div className="ml-auto flex items-center gap-1.5">
          <button onClick={() => setUseAi(!useAi)}
            className={`relative w-7 h-[14px] rounded-full transition-colors ${useAi ? "bg-[#581c87]" : "bg-[#1f3460]"}`}>
            <div className={`absolute top-[2px] w-[10px] h-[10px] rounded-full transition-transform ${useAi ? "translate-x-[15px] bg-[#a855f7]" : "translate-x-[2px] bg-[#8899aa]"}`} />
          </button>
          <span className={`text-[10px] font-mono ${useAi ? "text-[#a855f7]" : "text-[#8899aa]"}`}>AI</span>
        </div>
      </div>

      {/* AI Instructions */}
      {useAi && (
        <div className="border border-[#7e22ce] rounded bg-[#3b0764]/50 p-2 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-[#a855f7] font-mono">AI Instructions</span>
            <button onClick={() => setShowHelp(!showHelp)} className="text-[#a855f7] hover:text-[#c084fc]">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </button>
          </div>
          {showHelp && (
            <p className="text-[9px] text-[#a855f7] bg-[#581c87]/50 rounded px-2 py-1">
              AI uses your message + these instructions + contact data (history, company, jobs) to generate or refine.
            </p>
          )}
          <textarea value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
            placeholder="e.g. Mention the VP role, keep it casual..."
            rows={2}
            className={`${S.input} resize-none`}
          />
          <div className="flex justify-end">
            <button onClick={handleAskAi} disabled={isBusy || !contactId}
              className={`${S.btn} ${S.btnPurple} flex items-center gap-1`}>
              {isBusy ? (
                <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              )}
              {isBusy ? "Thinking..." : "Ask AI"}
            </button>
          </div>
        </div>
      )}

      {/* Message body */}
      <textarea value={body} onChange={(e) => setBody(e.target.value)}
        placeholder="Type your LinkedIn message..."
        rows={5}
        className={`${S.input} resize-none`}
      />

      {/* Action buttons */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {useAi && body.trim() && (
            <button onClick={handleWordsmith} disabled={isBusy}
              className={`${S.btn} ${S.btnPurple}`}>
              {isBusy ? "..." : "Wordsmith"}
            </button>
          )}
          {draftId && (
            <button onClick={handleDelete} disabled={isBusy}
              className={`${S.btn} border-[#ff4444] text-[#ff4444] bg-[#1a1a2e] hover:bg-[#ff4444] hover:text-[#1a1a2e]`}
              title="Delete draft">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={handleCopy} disabled={!body.trim() || isBusy}
            className={`${S.btn} ${S.btnGreen} flex items-center gap-1`}>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}>
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
            </svg>
            Copy
          </button>
        </div>
      </div>
    </div>
  );
}
