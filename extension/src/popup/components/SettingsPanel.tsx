/**
 * SettingsPanel.tsx — Enhanced plugin settings with all toggles.
 * API URL, auto-capture, notifications, ATS auto-fill.
 * Stores to chrome.storage.local via background messaging.
 */

import { useState, useEffect } from "react";
import { sendToBackground, MSG } from "@shared/messages";
import { DEFAULT_CONFIG } from "@shared/config";

interface PluginSettings {
  apiUrl: string;
  autoCapture: boolean;
  notifications: boolean;
  atsAutoFill: boolean;
}

const DEFAULT_SETTINGS: PluginSettings = {
  apiUrl: DEFAULT_CONFIG.apiUrl,
  autoCapture: true,
  notifications: true,
  atsAutoFill: false,
};

function Toggle({
  enabled,
  onChange,
  label,
  description,
}: {
  enabled: boolean;
  onChange: (val: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex-1">
        <div className="text-sm text-st-text">{label}</div>
        {description && (
          <div className="text-[10px] text-st-muted mt-0.5">{description}</div>
        )}
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
          enabled ? "bg-st-green" : "bg-st-border"
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-st-bg transition-transform ${
            enabled ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}

export default function SettingsPanel() {
  const [settings, setSettings] = useState<PluginSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    chrome.storage.local.get("pluginSettings").then((result) => {
      if (result.pluginSettings) {
        setSettings({ ...DEFAULT_SETTINGS, ...result.pluginSettings });
      } else {
        // Fall back to old settings format
        sendToBackground(MSG.GET_SETTINGS)
          .then((oldSettings: any) => {
            if (oldSettings?.apiUrl) {
              setSettings((prev) => ({ ...prev, apiUrl: oldSettings.apiUrl }));
            }
          })
          .catch(() => {});
      }
      setLoading(false);
    });
  }, []);

  const update = (patch: Partial<PluginSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
    setSaved(false);
  };

  const handleSave = async () => {
    setError(null);
    try {
      // Save to chrome.storage.local
      await chrome.storage.local.set({ pluginSettings: settings });

      // Also update backend-facing settings via messaging
      await sendToBackground(MSG.SAVE_SETTINGS, { apiUrl: settings.apiUrl }).catch(() => {});

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  };

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    setSaved(false);
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-st-muted text-sm animate-pulse">
        Loading settings...
      </div>
    );
  }

  return (
    <div className="p-3 space-y-4">
      <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
        &gt; Settings
      </h2>

      {/* API URL */}
      <div>
        <label className="block text-xs text-st-muted mb-1">Backend URL</label>
        <input
          type="text"
          value={settings.apiUrl}
          onChange={(e) => update({ apiUrl: e.target.value })}
          className="w-full bg-st-surface border border-st-border rounded px-3 py-2 text-sm text-st-text font-mono focus:border-st-green focus:outline-none"
          placeholder="http://localhost:8055"
        />
      </div>

      {/* Toggles */}
      <div className="border-t border-st-border pt-2">
        <h3 className="text-xs text-st-muted mb-1 uppercase tracking-wider">Features</h3>

        <Toggle
          enabled={settings.autoCapture}
          onChange={(val) => update({ autoCapture: val })}
          label="Auto-Capture Jobs"
          description="Automatically detect and extract job listings from supported sites"
        />

        <Toggle
          enabled={settings.notifications}
          onChange={(val) => update({ notifications: val })}
          label="Notifications"
          description="Show alerts for stale apps, new matches, follow-up reminders"
        />

        <Toggle
          enabled={settings.atsAutoFill}
          onChange={(val) => update({ atsAutoFill: val })}
          label="ATS Auto-Fill"
          description="Auto-populate application forms on Workday, Greenhouse, Lever, etc."
        />
      </div>

      {/* Save / Reset */}
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          className="flex-1 bg-st-green text-st-bg font-bold py-2 rounded text-sm hover:bg-st-green-dim transition-colors"
        >
          {saved ? "Saved" : "Save Settings"}
        </button>
        <button
          onClick={handleReset}
          className="px-4 py-2 rounded text-sm font-bold border border-st-border text-st-muted hover:border-st-red hover:text-st-red transition-colors"
        >
          Reset
        </button>
      </div>

      {error && (
        <div className="text-center text-xs text-st-red">{error}</div>
      )}

      {/* Version Info */}
      <div className="border-t border-st-border pt-3 text-center">
        <div className="text-[10px] text-st-muted">SuperTroopers Extension v0.1.0</div>
        <div className="text-[10px] text-st-muted mt-0.5">
          Backend: {settings.apiUrl}
        </div>
      </div>
    </div>
  );
}
