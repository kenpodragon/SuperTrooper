# SuperTroopers Chrome Extension

Browser plugin that connects to your local SuperTroopers backend for job search superpowers.

## Prerequisites

- Node.js (LTS)
- Chrome browser
- SuperTroopers backend running (`cd code && docker compose up -d`)

## Setup

```bash
# Install dependencies
npm install

# Build the extension
npm run build

# Dev mode (watch for changes)
npm run dev
```

## Load in Chrome

1. Open `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select the `dist/` folder inside this directory
5. The SuperTroopers extension should appear with a green icon

## After Code Changes

- If using `npm run dev` (watch mode), the `dist/` folder updates automatically
- Go to `chrome://extensions/` and click the refresh icon on the SuperTroopers card
- Or press Ctrl+Shift+I in the popup to open DevTools for the popup

## Architecture

```
src/
  background/     Service worker — API calls, message routing, alarms
  content/        Content script — injected on job board pages
  popup/          React popup UI — dark theme, pipeline dashboard
  shared/         Types, message constants, config
  config/         siteConfig.json — job board URL patterns + selectors
```

### Message Flow
```
Content Script  -->  chrome.runtime.sendMessage  -->  Background Worker
Background      -->  fetch(localhost:8055/api/...)  -->  Flask API
Flask API       -->  response  -->  Background Worker
Background      -->  chrome.tabs.sendMessage  -->  Content Script
```

## Adding Job Board Support

Edit `src/config/siteConfig.json`:

1. Add a new entry under `boards` with the board ID
2. Set `hostPattern` to match the domain
3. Set `jobListingPaths` for URL paths that indicate a job listing
4. Add `extractors` with CSS selectors for title, company, location, salary, description
5. Add URL patterns to `manifest.json` under `content_scripts.matches`
6. Rebuild: `npm run build`

## Current Job Boards

- Indeed (`indeed.com`)
- LinkedIn Jobs (`linkedin.com/jobs`)
- Glassdoor (`glassdoor.com`)
- ZipRecruiter (`ziprecruiter.com`)
- Dice (`dice.com`)

## Theme

Dark background with terminal green (#00FF41) accent. Monospace fonts (JetBrains Mono / Fira Code / Consolas).
