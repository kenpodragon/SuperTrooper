import { useState, useEffect } from "react";
import { sendToBackground, MSG } from "@shared/messages";
import { DEFAULT_CONFIG } from "@shared/config";

export default function Settings() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_CONFIG.apiUrl);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    sendToBackground(MSG.GET_SETTINGS).then((settings: any) => {
      if (settings?.apiUrl) setApiUrl(settings.apiUrl);
    });
  }, []);

  const save = async () => {
    await sendToBackground(MSG.SAVE_SETTINGS, { apiUrl });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const features = [
    { id: "job_capture", label: "Job Capture", enabled: false },
    { id: "gap_analysis", label: "Gap Analysis", enabled: false },
    { id: "auto_apply", label: "Auto-Apply", enabled: false },
    { id: "networking", label: "Networking Overlay", enabled: false },
  ];

  return (
    <div className="p-4">
      <h2 className="text-sm font-bold text-st-green mb-3 tracking-wider uppercase">
        &gt; Settings
      </h2>
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-st-muted mb-1">Backend URL</label>
          <input
            type="text"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            className="w-full bg-st-surface border border-st-border rounded px-3 py-2 text-sm text-st-text font-mono focus:border-st-green focus:outline-none"
          />
        </div>
        <button
          onClick={save}
          className="w-full bg-st-green text-st-bg font-bold py-2 rounded text-sm hover:bg-st-green-dim transition-colors"
        >
          {saved ? "✓ Saved" : "Save Settings"}
        </button>

        <div className="pt-2 border-t border-st-border">
          <h3 className="text-xs text-st-muted mb-2 uppercase tracking-wider">Features</h3>
          {features.map((f) => (
            <div key={f.id} className="flex items-center justify-between py-1.5">
              <span className="text-sm text-st-text">{f.label}</span>
              <span className="text-xs text-st-muted italic">Coming soon</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
