# LinkedIn Import Guide

How to get your LinkedIn data into SuperTroopers... two ways: the official data export and the scraper.

---

## Method 1: LinkedIn Data Export (ZIP Upload)

### Step 1: Export Your Data from LinkedIn

1. Go to LinkedIn Settings > Data Privacy > Get a copy of your data
2. Select the data you want (connections, messages, profile, etc.)
3. Click "Request archive"
4. Wait for LinkedIn to email you (usually 10-30 minutes)
5. Download the ZIP file from the email link

### Step 2: Upload via the UI

1. Open SuperTroopers and navigate to LinkedIn Hub > Import tab
2. Drag and drop your ZIP file into the upload zone (or click to browse)
3. Click "Upload & Import"
4. Wait for the import to finish... it processes connections, profile, messages, and applications

### What Gets Imported

| Data | Where It Goes |
|------|--------------|
| Connections | contacts table (deduped by name + company) |
| Positions | career_history + bullets tables |
| Skills | skills table |
| Messages | outreach_messages table (linked to contacts where possible) |
| Saved Jobs | applications table |

### Notes

- Duplicate connections are skipped automatically
- Messages are linked to contacts when the name matches
- Positions that already exist (same employer + title) are skipped
- The original ZIP is saved to `Originals/linkedin_export.zip`

---

## Method 2: LinkedIn Scraper (Posts & Comments)

The scraper captures your published posts and comments directly from LinkedIn. This data is not available in the official export.

### Step 1: Install Dependencies

```bash
pip install playwright
playwright install chromium
```

### Step 2: First Run

A Chrome window will open. Log in to LinkedIn when prompted.

```bash
cd local_code
python linkedin_scraper.py
```

The scraper saves your login session so you only need to log in once.

### Step 3: Subsequent Runs

Just re-run the command. It picks up where it left off.

```bash
python local_code/linkedin_scraper.py
```

### Scraper Modes

| Mode | What It Scrapes |
|------|----------------|
| `--mode posts` | Your published LinkedIn posts |
| `--mode comments` | Your comments on other people's posts |
| `--mode media` | Media attachments from your posts |
| `--mode messages` | LinkedIn messages (DMs) |

Example: `python local_code/linkedin_scraper.py --mode posts`

### Step 4: Import Scraper Results

1. Open SuperTroopers > LinkedIn Hub > Import tab
2. The "Update from Scraper" section shows which files are available and how many lines each has
3. Click "Import Latest Scrape"
4. Posts are upserted into `linkedin_scraped_posts` and bridged to the Content Dashboard
5. Comments are upserted into `linkedin_scraped_comments`

### Output Files

Scraper output lives in `Originals/LinkedIn/`:

| File | Contents |
|------|----------|
| `posts.jsonl` | One JSON object per line, each representing a post |
| `comments.jsonl` | One JSON object per line, each representing a comment |

---

## Troubleshooting

**ZIP upload fails with "Failed to extract ZIP"**
- Make sure the file is actually a .zip (LinkedIn sometimes double-zips)
- The import handler handles double-zips automatically, but corrupted files will fail

**Connections show 0 imported**
- Check that the ZIP contains `Connections.csv`
- If all connections already exist in the database, they'll show as "skipped"

**Scraper status shows "not found"**
- Run the scraper first: `python local_code/linkedin_scraper.py`
- Check that `Originals/LinkedIn/posts.jsonl` exists

**Scraper Chrome window doesn't open**
- Make sure Playwright is installed: `playwright install chromium`
- On first run, you need to be at a terminal that can display a browser window

**Import shows 0 bridged to hub**
- Posts that already exist (matched by URN) are updated, not bridged again
- Only newly imported posts get bridged to the Content Dashboard
