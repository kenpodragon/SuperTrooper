# Phase F0: Browser Plugin Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Working Chrome extension that connects to the local SuperTroopers backend, shows connection status, pipeline summary, and has the content script + message passing infrastructure ready for Phase 1 features.

**Architecture:** Manifest V3 Chrome extension with TypeScript + Vite + React popup. Background service worker handles all API calls to localhost:8055. Content scripts inject on matched job board URLs. Message passing layer connects content scripts <-> background <-> popup. Dark theme with terminal green (#00FF41).

**Tech Stack:** TypeScript, Vite (multi-entry with vite-plugin-static-copy), React 18, Tailwind CSS v3, Chrome Extension Manifest V3

**Spec:** `code/docs/reqs/14_BROWSER_PLUGIN.md` (Phase 0: 14.13.1–14.13.11)

---

## CRITICAL: Architecture Decisions

### Backend Communication
- ALL API calls go through the background service worker (not content scripts)
- Base URL: `http://localhost:8055` (configurable in settings)
- No auth needed — localhost only
- Health check on startup + alarm every 5 minutes

### Message Passing Pattern
```
Content Script --> chrome.runtime.sendMessage({type, data}) --> Background Service Worker
Background Service Worker --> fetch(localhost:8055/api/...) --> Flask API
Flask API --> response --> Background Service Worker
Background Service Worker --> chrome.tabs.sendMessage(tabId, {type, data}) --> Content Script
```

### Permissions (Minimal)
```json
{
  "permissions": ["activeTab", "storage", "alarms", "tabs", "webNavigation"],
  "host_permissions": ["http://localhost:8055/*", "http://localhost:8056/*"]
}
```

### Theme
- Background: `#1a1a2e`
- Surface: `#16213e`
- Text: `#e0e0e0`
- Accent: `#00FF41` (terminal green)
- Error: `#ff4444`

---

## File Structure

```
code/extension/
├── manifest.json
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── src/
│   ├── background/
│   │   ├── index.ts              # Service worker entry
│   │   ├── api.ts                # Backend API client
│   │   ├── messages.ts           # Message handler routing
│   │   ├── alarms.ts             # Scheduled tasks (health, badge)
│   │   └── cache.ts              # Chrome storage cache manager
│   ├── content/
│   │   ├── index.ts              # Content script entry
│   │   ├── detector.ts           # Page type detection (job board, ATS, etc.)
│   │   └── shadow.ts             # Shadow DOM component factory
│   ├── popup/
│   │   ├── index.html            # Popup HTML shell
│   │   ├── index.tsx             # React entry
│   │   ├── App.tsx               # Main app with routing
│   │   ├── components/
│   │   │   ├── StatusBar.tsx     # Connection status indicator
│   │   │   ├── Dashboard.tsx     # Pipeline summary
│   │   │   └── Settings.tsx      # Backend URL config
│   │   └── hooks/
│   │       └── useBackend.ts     # Message-based API hook
│   ├── shared/
│   │   ├── types.ts              # Shared TypeScript types
│   │   ├── messages.ts           # Message type constants + helpers
│   │   └── config.ts             # Default config values
│   └── config/
│       └── siteConfig.json       # Job board URL patterns (scaffold)
├── assets/
│   └── icons/                    # Extension icons
├── dist/                         # Build output
└── README.md                     # Dev setup + load unpacked instructions
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `code/extension/package.json`
- Create: `code/extension/tsconfig.json`
- Create: `code/extension/vite.config.ts`
- Create: `code/extension/tailwind.config.js`
- Create: `code/extension/manifest.json`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "supertroopers-extension",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite build --watch --mode development",
    "build": "vite build",
    "clean": "rm -rf dist"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/chrome": "^0.0.270",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.2",
    "vite": "^6.0.0",
    "vite-plugin-static-copy": "^2.2.0"
  }
}
```

Save to `code/extension/package.json`.

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "outDir": "dist",
    "rootDir": "src",
    "baseUrl": ".",
    "paths": {
      "@shared/*": ["src/shared/*"],
      "@config/*": ["src/config/*"]
    }
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 3: Create vite.config.ts**

Vite config with separate entry points for background, content script, and popup:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";
import { resolve } from "path";

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        { src: "manifest.json", dest: "." },
        { src: "assets/**/*", dest: "assets" },
      ],
    }),
  ],
  build: {
    outDir: "dist",
    emptyDir: true,
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "src/popup/index.html"),
        background: resolve(__dirname, "src/background/index.ts"),
        content: resolve(__dirname, "src/content/index.ts"),
      },
      output: {
        entryFileNames: "[name].js",
        // No code splitting — service workers can't handle dynamic imports
        chunkFileNames: "[name].js",
        assetFileNames: "assets/[name][extname]",
        // Inline all shared code into each entry to avoid chunk issues
        manualChunks: undefined,
      },
    },
  },
  resolve: {
    alias: {
      "@shared": resolve(__dirname, "src/shared"),
      "@config": resolve(__dirname, "src/config"),
    },
  },
});
```

- [ ] **Step 4: Create tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/popup/**/*.{tsx,ts,html}"],
  theme: {
    extend: {
      colors: {
        st: {
          bg: "#1a1a2e",
          surface: "#16213e",
          border: "#1f3460",
          text: "#e0e0e0",
          muted: "#8899aa",
          green: "#00FF41",
          "green-dim": "#00cc33",
          red: "#ff4444",
        },
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 5: Create manifest.json**

```json
{
  "manifest_version": 3,
  "name": "SuperTroopers",
  "version": "0.1.0",
  "description": "AI-powered reverse recruiting command center",
  "minimum_chrome_version": "116",

  "permissions": [
    "activeTab",
    "storage",
    "alarms",
    "tabs",
    "webNavigation"
  ],

  "host_permissions": [
    "http://localhost:8055/*",
    "http://localhost:8056/*"
  ],

  "background": {
    "service_worker": "background.js",
    "type": "module"
  },

  "action": {
    "default_popup": "popup/index.html",
    "default_icon": {
      "16": "assets/icon-16.png",
      "32": "assets/icon-32.png",
      "48": "assets/icon-48.png",
      "128": "assets/icon-128.png"
    }
  },

  "content_scripts": [
    {
      "matches": [
        "*://*.indeed.com/*",
        "*://*.linkedin.com/jobs/*",
        "*://*.glassdoor.com/job-listing/*",
        "*://*.glassdoor.com/Job/*",
        "*://*.ziprecruiter.com/jobs/*",
        "*://*.dice.com/job-detail/*"
      ],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ],

  "icons": {
    "16": "assets/icon-16.png",
    "32": "assets/icon-32.png",
    "48": "assets/icon-48.png",
    "128": "assets/icon-128.png"
  }
}
```

- [ ] **Step 6: Install dependencies**

```bash
cd code/extension && npm install
```

---

## Task 2: Shared Types & Message Layer

**Files:**
- Create: `code/extension/src/shared/types.ts`
- Create: `code/extension/src/shared/messages.ts`
- Create: `code/extension/src/shared/config.ts`

- [ ] **Step 1: Create shared types**

```typescript
// src/shared/types.ts

export interface HealthStatus {
  connected: boolean;
  status: string;
  db: string;
  timestamp: number;
}

export interface PipelineSummary {
  saved: number;
  applied: number;
  interviewing: number;
  offered: number;
  total: number;
}

export interface BackendConfig {
  apiUrl: string;
  healthCheckInterval: number; // minutes
  badgeUpdateInterval: number; // minutes
}

export interface SavedJob {
  id: number;
  url: string;
  title: string;
  company: string;
  location?: string;
  salary_range?: string;
  source: string;
  jd_text?: string;
  fit_score?: number;
  status: string;
  created_at: string;
}

export interface PageContext {
  url: string;
  type: "job_listing" | "ats_form" | "company_page" | "unknown";
  board?: string; // "indeed", "linkedin", etc.
  data?: Record<string, string>;
}
```

- [ ] **Step 2: Create message types and helpers**

```typescript
// src/shared/messages.ts

// --- Message Types ---
export const MSG = {
  // Health
  HEALTH_CHECK: "HEALTH_CHECK",
  HEALTH_STATUS: "HEALTH_STATUS",

  // Pipeline
  GET_PIPELINE: "GET_PIPELINE",
  PIPELINE_DATA: "PIPELINE_DATA",

  // Jobs (Phase 1)
  SAVE_JOB: "SAVE_JOB",
  JOB_SAVED: "JOB_SAVED",
  CHECK_JOB_URL: "CHECK_JOB_URL",
  JOB_URL_STATUS: "JOB_URL_STATUS",

  // Gap Analysis (Phase 1)
  RUN_GAP_ANALYSIS: "RUN_GAP_ANALYSIS",
  GAP_RESULT: "GAP_RESULT",

  // Content Script
  PAGE_CONTEXT: "PAGE_CONTEXT",

  // Settings
  GET_SETTINGS: "GET_SETTINGS",
  SAVE_SETTINGS: "SAVE_SETTINGS",
  SETTINGS_DATA: "SETTINGS_DATA",
} as const;

export type MessageType = (typeof MSG)[keyof typeof MSG];

export interface Message<T = unknown> {
  type: MessageType;
  data?: T;
}

// --- Helpers ---
export function sendToBackground<T = unknown>(
  type: MessageType,
  data?: unknown
): Promise<T> {
  return chrome.runtime.sendMessage({ type, data });
}

export function sendToTab<T = unknown>(
  tabId: number,
  type: MessageType,
  data?: unknown
): Promise<T> {
  return chrome.tabs.sendMessage(tabId, { type, data });
}
```

- [ ] **Step 3: Create default config**

```typescript
// src/shared/config.ts

import type { BackendConfig } from "./types";

export const DEFAULT_CONFIG: BackendConfig = {
  apiUrl: "http://localhost:8055",
  healthCheckInterval: 5, // minutes
  badgeUpdateInterval: 30, // minutes
};

export const THEME = {
  bg: "#1a1a2e",
  surface: "#16213e",
  border: "#1f3460",
  text: "#e0e0e0",
  muted: "#8899aa",
  green: "#00FF41",
  greenDim: "#00cc33",
  red: "#ff4444",
} as const;
```

---

## Task 3: Background Service Worker

**Files:**
- Create: `code/extension/src/background/index.ts`
- Create: `code/extension/src/background/api.ts`
- Create: `code/extension/src/background/messages.ts`
- Create: `code/extension/src/background/alarms.ts`
- Create: `code/extension/src/background/cache.ts`

- [ ] **Step 1: Create the API client**

```typescript
// src/background/api.ts

import { DEFAULT_CONFIG } from "@shared/config";

let baseUrl = DEFAULT_CONFIG.apiUrl;

export function setBaseUrl(url: string) {
  baseUrl = url;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function checkHealth(): Promise<{ connected: boolean; status: string; db: string }> {
  try {
    const data = await apiGet<{ status: string; db: string }>("/api/health");
    return { connected: true, ...data };
  } catch {
    return { connected: false, status: "unreachable", db: "unknown" };
  }
}

export async function getPipelineSummary() {
  try {
    const data = await apiGet<Record<string, unknown>>("/api/analytics/summary");
    return data;
  } catch {
    return null;
  }
}
```

- [ ] **Step 2: Create the cache manager**

```typescript
// src/background/cache.ts

interface CacheEntry<T> {
  data: T;
  expiry: number;
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  const result = await chrome.storage.local.get(key);
  const entry = result[key] as CacheEntry<T> | undefined;
  if (!entry) return null;
  if (Date.now() > entry.expiry) {
    await chrome.storage.local.remove(key);
    return null;
  }
  return entry.data;
}

export async function cacheSet<T>(key: string, data: T, ttlMinutes: number): Promise<void> {
  const entry: CacheEntry<T> = {
    data,
    expiry: Date.now() + ttlMinutes * 60 * 1000,
  };
  await chrome.storage.local.set({ [key]: entry });
}

export async function cacheClear(prefix?: string): Promise<void> {
  if (!prefix) {
    await chrome.storage.local.clear();
    return;
  }
  const all = await chrome.storage.local.get(null);
  const keys = Object.keys(all).filter((k) => k.startsWith(prefix));
  if (keys.length) await chrome.storage.local.remove(keys);
}
```

- [ ] **Step 3: Create alarm handlers**

```typescript
// src/background/alarms.ts

import { checkHealth, getPipelineSummary } from "./api";
import { cacheSet } from "./cache";

export const ALARMS = {
  HEALTH_CHECK: "health-check",
  BADGE_UPDATE: "badge-update",
} as const;

export function setupAlarms() {
  chrome.alarms.create(ALARMS.HEALTH_CHECK, { periodInMinutes: 5 });
  chrome.alarms.create(ALARMS.BADGE_UPDATE, { periodInMinutes: 30 });
}

export async function handleAlarm(alarm: chrome.alarms.Alarm) {
  switch (alarm.name) {
    case ALARMS.HEALTH_CHECK:
      await runHealthCheck();
      break;
    case ALARMS.BADGE_UPDATE:
      await updateBadge();
      break;
  }
}

export async function runHealthCheck() {
  const health = await checkHealth();
  await cacheSet("health", { ...health, timestamp: Date.now() }, 10);

  // Update icon based on health
  const color = health.connected ? "#00FF41" : "#ff4444";
  chrome.action.setBadgeBackgroundColor({ color });

  if (!health.connected) {
    chrome.action.setBadgeText({ text: "!" });
  }
}

export async function updateBadge() {
  const summary = await getPipelineSummary();
  if (!summary) return;

  // Count active applications
  const counts = summary as Record<string, number>;
  const active = (counts.applied || 0) + (counts.interviewing || 0) + (counts.phone_screen || 0);
  chrome.action.setBadgeText({ text: active > 0 ? String(active) : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#00FF41" });

  await cacheSet("pipeline", summary, 30);
}
```

- [ ] **Step 4: Create message handler**

```typescript
// src/background/messages.ts

import { MSG, type Message } from "@shared/messages";
import { checkHealth, getPipelineSummary } from "./api";
import { cacheGet } from "./cache";

export function handleMessage(
  message: Message,
  _sender: chrome.runtime.MessageSender,
  sendResponse: (response: unknown) => void
): boolean {
  // Return true to indicate async response
  handleAsync(message).then(sendResponse);
  return true;
}

async function handleAsync(message: Message): Promise<unknown> {
  switch (message.type) {
    case MSG.HEALTH_CHECK: {
      const cached = await cacheGet("health");
      if (cached) return cached;
      const health = await checkHealth();
      return { ...health, timestamp: Date.now() };
    }

    case MSG.GET_PIPELINE: {
      const cached = await cacheGet("pipeline");
      if (cached) return cached;
      return await getPipelineSummary();
    }

    case MSG.GET_SETTINGS: {
      const result = await chrome.storage.local.get("settings");
      return result.settings || {};
    }

    case MSG.SAVE_SETTINGS: {
      await chrome.storage.local.set({ settings: message.data });
      return { ok: true };
    }

    case MSG.PAGE_CONTEXT: {
      // Store current tab context for future use (Phase 1+)
      console.log("[SuperTroopers] Page context:", message.data);
      return { ok: true };
    }

    default:
      return { error: `Unknown message type: ${message.type}` };
  }
}
```

- [ ] **Step 5: Create service worker entry**

```typescript
// src/background/index.ts

import { handleMessage } from "./messages";
import { setupAlarms, handleAlarm, runHealthCheck, updateBadge } from "./alarms";

// --- Lifecycle ---
chrome.runtime.onInstalled.addListener(() => {
  console.log("[SuperTroopers] Extension installed");
  setupAlarms();
  runHealthCheck();
  updateBadge();
});

chrome.runtime.onStartup.addListener(() => {
  console.log("[SuperTroopers] Browser started");
  setupAlarms();
  runHealthCheck();
  updateBadge();
});

// --- Message handling ---
chrome.runtime.onMessage.addListener(handleMessage);

// --- Alarm handling ---
chrome.alarms.onAlarm.addListener(handleAlarm);
```

---

## Task 4: Popup UI

**Files:**
- Create: `code/extension/src/popup/index.html`
- Create: `code/extension/src/popup/index.tsx`
- Create: `code/extension/src/popup/App.tsx`
- Create: `code/extension/src/popup/index.css`
- Create: `code/extension/src/popup/components/StatusBar.tsx`
- Create: `code/extension/src/popup/components/Dashboard.tsx`
- Create: `code/extension/src/popup/components/Settings.tsx`
- Create: `code/extension/src/popup/hooks/useBackend.ts`

- [ ] **Step 1: Create popup HTML shell**

```html
<!-- src/popup/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SuperTroopers</title>
</head>
<body class="w-[380px] h-[500px] bg-st-bg text-st-text">
  <div id="root"></div>
  <script type="module" src="./index.tsx"></script>
</body>
</html>
```

- [ ] **Step 2: Create React entry + CSS**

```typescript
// src/popup/index.tsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

const root = createRoot(document.getElementById("root")!);
root.render(<App />);
```

```css
/* src/popup/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

/* Scrollbar styling */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1a1a2e; }
::-webkit-scrollbar-thumb { background: #1f3460; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #00FF41; }
```

- [ ] **Step 3: Create useBackend hook**

```typescript
// src/popup/hooks/useBackend.ts
import { useState, useEffect, useCallback } from "react";
import { sendToBackground, MSG } from "@shared/messages";
import type { HealthStatus, PipelineSummary } from "@shared/types";

export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    const result = await sendToBackground<HealthStatus>(MSG.HEALTH_CHECK);
    setHealth(result);
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { health, loading, refresh };
}

export function usePipeline() {
  const [pipeline, setPipeline] = useState<PipelineSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    sendToBackground<PipelineSummary>(MSG.GET_PIPELINE).then((data) => {
      setPipeline(data);
      setLoading(false);
    });
  }, []);

  return { pipeline, loading };
}
```

- [ ] **Step 4: Create StatusBar component**

```tsx
// src/popup/components/StatusBar.tsx
import { useHealth } from "../hooks/useBackend";

export default function StatusBar() {
  const { health, loading, refresh } = useHealth();

  const connected = health?.connected ?? false;

  return (
    <div className="flex items-center justify-between px-3 py-2 bg-st-surface border-b border-st-border">
      <div className="flex items-center gap-2">
        <div
          className={`w-2.5 h-2.5 rounded-full ${
            loading ? "bg-yellow-400 animate-pulse" : connected ? "bg-st-green" : "bg-st-red"
          }`}
        />
        <span className="text-xs text-st-muted">
          {loading ? "Connecting..." : connected ? "Backend Online" : "Backend Offline"}
        </span>
      </div>
      <button
        onClick={refresh}
        className="text-xs text-st-muted hover:text-st-green transition-colors"
        title="Refresh connection"
      >
        ↻
      </button>
    </div>
  );
}
```

- [ ] **Step 5: Create Dashboard component**

```tsx
// src/popup/components/Dashboard.tsx
import { usePipeline, useHealth } from "../hooks/useBackend";

export default function Dashboard() {
  const { health } = useHealth();
  const { pipeline, loading } = usePipeline();

  if (!health?.connected) {
    return (
      <div className="p-4 text-center">
        <div className="text-st-red text-3xl mb-3">⚡</div>
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

  const stats = [
    { label: "Saved", value: pipeline.saved || 0, color: "text-st-muted" },
    { label: "Applied", value: pipeline.applied || 0, color: "text-blue-400" },
    { label: "Interviewing", value: pipeline.interviewing || 0, color: "text-yellow-400" },
    { label: "Offered", value: pipeline.offered || 0, color: "text-st-green" },
  ];

  return (
    <div className="p-4">
      <h2 className="text-sm font-bold text-st-green mb-3 tracking-wider uppercase">
        &gt; Pipeline
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-st-surface rounded p-3 border border-st-border">
            <div className={`text-2xl font-bold font-mono ${s.color}`}>{s.value}</div>
            <div className="text-xs text-st-muted mt-1">{s.label}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 bg-st-surface rounded p-3 border border-st-border">
        <div className="text-2xl font-bold font-mono text-st-text">
          {(pipeline.saved || 0) + (pipeline.applied || 0) + (pipeline.interviewing || 0) + (pipeline.offered || 0)}
        </div>
        <div className="text-xs text-st-muted mt-1">Total Active</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create Settings component**

```tsx
// src/popup/components/Settings.tsx
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
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Create main App with tab navigation**

```tsx
// src/popup/App.tsx
import { useState } from "react";
import StatusBar from "./components/StatusBar";
import Dashboard from "./components/Dashboard";
import Settings from "./components/Settings";

type Tab = "dashboard" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  const tabs: { id: Tab; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "settings", label: "Settings" },
  ];

  return (
    <div className="flex flex-col h-full bg-st-bg">
      {/* Header */}
      <div className="px-3 py-2 bg-st-surface border-b border-st-border">
        <h1 className="text-sm font-bold text-st-green tracking-widest font-mono">
          SUPERTROOPERS
        </h1>
      </div>

      <StatusBar />

      {/* Tabs */}
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === "dashboard" && <Dashboard />}
        {tab === "settings" && <Settings />}
      </div>

      {/* Footer */}
      <div className="px-3 py-1 text-center text-[10px] text-st-muted border-t border-st-border">
        SuperTroopers v0.1.0
      </div>
    </div>
  );
}
```

---

## Task 5: Content Script Foundation

**Files:**
- Create: `code/extension/src/content/index.ts`
- Create: `code/extension/src/content/detector.ts`
- Create: `code/extension/src/content/shadow.ts`
- Create: `code/extension/src/config/siteConfig.json`

- [ ] **Step 1: Create siteConfig.json scaffold**

```json
{
  "version": "0.1.0",
  "boards": {
    "indeed": {
      "hostPattern": "indeed.com",
      "jobListingPaths": ["/viewjob", "/m/basecamp/viewjob"],
      "extractors": {
        "title": { "selector": "h1.jobsearch-JobInfoHeader-title, h2.jobTitle", "attribute": "textContent" },
        "company": { "selector": "[data-company-name], .css-1h7lukg", "attribute": "textContent" },
        "location": { "selector": "[data-testid='job-location'], .css-6z8o9s", "attribute": "textContent" },
        "salary": { "selector": "#salaryInfoAndJobType, .css-18z4q2i", "attribute": "textContent" },
        "description": { "selector": "#jobDescriptionText, .jobsearch-jobDescriptionText", "attribute": "textContent" }
      }
    },
    "linkedin": {
      "hostPattern": "linkedin.com",
      "jobListingPaths": ["/jobs/view/", "/jobs/collections/"],
      "extractors": {
        "title": { "selector": ".job-details-jobs-unified-top-card__job-title, .topcard__title", "attribute": "textContent" },
        "company": { "selector": ".job-details-jobs-unified-top-card__company-name a, .topcard__org-name-link", "attribute": "textContent" },
        "location": { "selector": ".job-details-jobs-unified-top-card__bullet, .topcard__flavor--bullet", "attribute": "textContent" },
        "salary": { "selector": ".salary-main-rail__current-range", "attribute": "textContent" },
        "description": { "selector": ".jobs-description__content, .show-more-less-html__markup", "attribute": "textContent" }
      }
    },
    "glassdoor": {
      "hostPattern": "glassdoor.com",
      "jobListingPaths": ["/job-listing/", "/Job/"],
      "extractors": {
        "title": { "selector": "[data-test='job-title'], .css-w04er8", "attribute": "textContent" },
        "company": { "selector": "[data-test='employer-name'], .css-16nw49e", "attribute": "textContent" },
        "location": { "selector": "[data-test='location'], .css-56kyx5", "attribute": "textContent" },
        "salary": { "selector": "[data-test='detailSalary']", "attribute": "textContent" },
        "description": { "selector": ".jobDescriptionContent, .desc", "attribute": "textContent" }
      }
    },
    "ziprecruiter": {
      "hostPattern": "ziprecruiter.com",
      "jobListingPaths": ["/jobs/"],
      "extractors": {
        "title": { "selector": ".job_title, h1.title", "attribute": "textContent" },
        "company": { "selector": ".hiring_company_text, .company_name", "attribute": "textContent" },
        "location": { "selector": ".job_location, .location", "attribute": "textContent" },
        "salary": { "selector": ".salary_range", "attribute": "textContent" },
        "description": { "selector": ".jobDescriptionSection, .job_description", "attribute": "textContent" }
      }
    },
    "dice": {
      "hostPattern": "dice.com",
      "jobListingPaths": ["/job-detail/"],
      "extractors": {
        "title": { "selector": "h1[data-cy='jobTitle'], .jobTitle", "attribute": "textContent" },
        "company": { "selector": "[data-cy='companyNameLink'], .companyName", "attribute": "textContent" },
        "location": { "selector": "[data-cy='location'], .location", "attribute": "textContent" },
        "salary": { "selector": "[data-cy='compensationText']", "attribute": "textContent" },
        "description": { "selector": "[data-cy='jobDescription'], .job-description", "attribute": "textContent" }
      }
    }
  }
}
```

- [ ] **Step 2: Create page detector**

```typescript
// src/content/detector.ts
import siteConfig from "@config/siteConfig.json";
import type { PageContext } from "@shared/types";

export function detectPage(): PageContext {
  const url = window.location.href;
  const hostname = window.location.hostname;

  for (const [boardId, config] of Object.entries(siteConfig.boards)) {
    if (!hostname.includes(config.hostPattern)) continue;

    const path = window.location.pathname;
    const isJobListing = config.jobListingPaths.some((p: string) => path.includes(p));

    if (isJobListing) {
      return { url, type: "job_listing", board: boardId };
    }
  }

  return { url, type: "unknown" };
}

export function extractJobData(board: string): Record<string, string> | null {
  const config = (siteConfig.boards as Record<string, any>)[board];
  if (!config?.extractors) return null;

  const data: Record<string, string> = {};
  for (const [field, ext] of Object.entries(config.extractors as Record<string, any>)) {
    const el = document.querySelector(ext.selector);
    if (el) {
      data[field] = (el as HTMLElement)[ext.attribute as keyof HTMLElement]?.toString().trim() || "";
    }
  }

  data.url = window.location.href;
  data.source = board;

  return Object.keys(data).length > 2 ? data : null; // url + source minimum
}
```

- [ ] **Step 3: Create Shadow DOM factory**

```typescript
// src/content/shadow.ts
import { THEME } from "@shared/config";

export function createShadowContainer(id: string): { host: HTMLElement; root: ShadowRoot } {
  // Remove existing if present
  const existing = document.getElementById(id);
  if (existing) existing.remove();

  const host = document.createElement("div");
  host.id = id;
  host.style.cssText = "all: initial; position: relative; z-index: 999999;";

  const root = host.attachShadow({ mode: "open" });

  // Inject base styles
  const style = document.createElement("style");
  style.textContent = `
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Consolas', 'Fira Code', monospace; }
    .st-btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 14px; border-radius: 4px; border: 1px solid ${THEME.green};
      background: ${THEME.bg}; color: ${THEME.green};
      font-size: 12px; font-weight: bold; cursor: pointer;
      transition: all 0.2s;
    }
    .st-btn:hover { background: ${THEME.green}; color: ${THEME.bg}; }
    .st-btn.saved { border-color: ${THEME.muted}; color: ${THEME.muted}; cursor: default; }
    .st-badge {
      display: inline-flex; align-items: center; justify-content: center;
      width: 36px; height: 36px; border-radius: 50%;
      background: ${THEME.bg}; border: 2px solid ${THEME.green};
      color: ${THEME.green}; font-size: 11px; font-weight: bold;
    }
  `;
  root.appendChild(style);

  return { host, root };
}
```

- [ ] **Step 4: Create content script entry**

```typescript
// src/content/index.ts
import { detectPage } from "./detector";
import { MSG, sendToBackground } from "@shared/messages";
import type { PageContext } from "@shared/types";

let currentContext: PageContext | null = null;

function init() {
  currentContext = detectPage();

  if (currentContext.type === "unknown") return;

  console.log(`[SuperTroopers] Detected: ${currentContext.type} on ${currentContext.board}`);

  // Notify background of page context
  sendToBackground(MSG.PAGE_CONTEXT, currentContext);

  // Phase 1 will add: job save button injection, gap analysis trigger
}

// Listen for messages from background
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  // Phase 1 will add: JOB_SAVED, GAP_RESULT handlers
  console.log(`[SuperTroopers] Content received: ${message.type}`);
  sendResponse({ ok: true });
  return true;
});

// Listen for SPA navigation (LinkedIn, Glassdoor)
let lastUrl = window.location.href;
const observer = new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    console.log(`[SuperTroopers] SPA navigation detected: ${lastUrl}`);
    init();
  }
});
observer.observe(document.body, { childList: true, subtree: true });

// Initial detection
init();
```

---

## Task 6: Extension Icons + Build

**Files:**
- Create: `code/extension/assets/icons/` (4 PNG icons)
- Create: `code/extension/postcss.config.js`
- Modify: `code/extension/vite.config.ts` (if needed for build fixes)

- [ ] **Step 1: Generate extension icons**

Create simple terminal-green-on-dark icons. Use a Python script or generate programmatically:

```bash
cd code/extension && mkdir -p assets/icons
```

Create a simple script to generate placeholder icons (green "ST" on dark background) at 16, 32, 48, 128px. Or use any image tool. The icons need to be PNG files at:
- `assets/icons/icon-16.png`
- `assets/icons/icon-32.png`
- `assets/icons/icon-48.png`
- `assets/icons/icon-128.png`

Update manifest.json icon paths to match: `assets/icons/icon-16.png` etc.

- [ ] **Step 2: Create postcss.config.js**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 3: Build the extension**

```bash
cd code/extension && npm run build
```

Verify `dist/` contains:
- `background.js`
- `content.js`
- `popup/index.html` + JS/CSS assets
- `assets/icons/*`
- Manifest is copied to dist (may need a vite plugin or manual copy step)

- [ ] **Step 4: Load in Chrome and test**

1. Open `chrome://extensions/`
2. Enable Developer Mode
3. Click "Load unpacked"
4. Select `code/extension/dist/`
5. Extension should appear with icon
6. Click icon — popup should show dark theme with "SUPERTROOPERS" header
7. If Docker is running: green dot, pipeline counts
8. If Docker is stopped: red dot, "Backend Offline" with Docker instructions

---

## Task 7: Backend Plugin Health Endpoint

**Files:**
- Modify: `code/backend/routes/settings.py`
- Rebuild: Docker backend container

- [ ] **Step 1: Add plugin health endpoint**

Read `code/backend/routes/settings.py` and append:

```python
@bp.route("/api/plugin/health", methods=["GET"])
def plugin_health():
    """Plugin-specific health check with version and feature info."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM applications WHERE status NOT IN ('Rejected', 'Ghosted', 'Withdrawn')")
    active = cur.fetchone()[0]
    cur.close()
    return jsonify({
        "status": "healthy",
        "version": "0.1.0",
        "active_applications": active,
        "features": {
            "job_capture": True,
            "gap_analysis": True,
            "auto_apply": False,
            "networking": False,
        },
    })
```

- [ ] **Step 2: Rebuild backend container**

```bash
cd code && docker compose up -d --build backend
```

- [ ] **Step 3: Verify endpoint**

```bash
curl http://localhost:8055/api/plugin/health
```

Expected: JSON with status, version, active_applications, features.

---

## Task 8: Documentation + Dev Workflow

**Files:**
- Create: `code/extension/README.md`

- [ ] **Step 1: Write extension README**

Cover:
- Prerequisites (Node.js, Chrome)
- Install deps: `npm install`
- Build: `npm run build`
- Dev mode: `npm run dev` (watch mode)
- Load in Chrome: `chrome://extensions` -> Load unpacked -> select `dist/`
- After code changes: click refresh icon on the extension card in `chrome://extensions`
- Architecture overview (background, content, popup, shared, config)
- Adding new job board support (edit siteConfig.json)

---

## Task Dependency Order

```
Task 1 (scaffold) → Task 2 (shared types) → Task 3 (background) → Task 4 (popup) → Task 5 (content) → Task 6 (build + test) → Task 7 (backend endpoint) → Task 8 (docs)
```

All tasks are sequential — each builds on the previous. Task 7 (backend endpoint) is independent and can be done in parallel with Tasks 4-6.
