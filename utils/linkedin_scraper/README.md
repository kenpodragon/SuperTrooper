# LinkedIn Scraper (Platform Copy)

Playwright-based LinkedIn content scraper. Extracts posts, comments, rich media, and messages via Chrome CDP.

**Original source:** `local_code/scrapers/` + `local_code/linkedin_scraper.py`

## Modules

| File | What it scrapes |
|------|----------------|
| `posts.py` | Activity feed posts (text, URNs, timestamps, engagement) |
| `comments.py` | Activity feed comments (text, URNs, parent post link) |
| `media.py` | Rich media from LinkedIn settings (images, documents) |
| `messages.py` | Conversations and full message history |
| `base.py` | Shared utilities: progress tracking, JSONL I/O, logging, scroll helpers |
| `cli.py` | CLI entry point with crash recovery, Chrome management, module orchestration |

## Usage

### As a package (from backend code)

```python
from utils.linkedin_scraper.cli import run_scraper, parse_args

args = parse_args(["--mode", "posts", "--max-items", "50"])
await run_scraper(args)
```

### Standalone CLI

```bash
cd code/utils/linkedin_scraper
python -m linkedin_scraper          # runs cli.main()
python -m linkedin_scraper --mode posts --delay 5
```

## Requirements

- Chrome installed locally
- Playwright (`pip install playwright`)
- Logged into LinkedIn in Chrome (or cookies injected for headless mode)

## Future: Headless Mode

See `code/docs/reqs/linkedin_content_sync.md` Part B for the planned `--headless --cookies-from-db` mode that uses extension-captured cookies instead of a live Chrome session.
