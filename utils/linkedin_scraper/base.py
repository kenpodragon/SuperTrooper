"""Base scraper utilities: progress tracking, JSONL I/O, logging, scroll helpers."""

import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path


class ActivityWatchdog:
    """Tracks scraper activity and raises if stalled too long."""

    def __init__(self, timeout_seconds=120):
        self.timeout = timeout_seconds
        self.last_activity = time.time()

    def ping(self):
        """Call this whenever the scraper does something (scrapes an item, scrolls, etc.)."""
        self.last_activity = time.time()

    def check(self):
        """Check if we've stalled. Raises TimeoutError if no activity for timeout seconds."""
        elapsed = time.time() - self.last_activity
        if elapsed > self.timeout:
            raise TimeoutError(
                f"Scraper stalled: no activity for {elapsed:.0f}s (timeout: {self.timeout}s)"
            )


class ProgressTracker:
    """Tracks scraping progress across modules. Persists to progress.json."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = {}
        self._scraped_sets = {}
        if self.path.exists():
            with open(self.path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            # Build internal sets from loaded data
            for module in self.data:
                if "scraped_ids" in self.data[module]:
                    self._scraped_sets[module] = set(self.data[module]["scraped_ids"])

    def get_status(self, module):
        return self.data.get(module, {}).get("status", "pending")

    def get_count(self, module):
        return self.data.get(module, {}).get("count", 0)

    def get_field(self, module, field):
        return self.data.get(module, {}).get(field)

    def update(self, module, **kwargs):
        if module not in self.data:
            self.data[module] = {}
        self.data[module].update(kwargs)

    def add_scraped_id(self, module, item_id):
        if module not in self.data:
            self.data[module] = {}
        if "scraped_ids" not in self.data[module]:
            self.data[module]["scraped_ids"] = []
        if module not in self._scraped_sets:
            self._scraped_sets[module] = set(self.data[module]["scraped_ids"])
        if item_id not in self._scraped_sets[module]:
            self._scraped_sets[module].add(item_id)
            self.data[module]["scraped_ids"].append(item_id)

    def is_scraped(self, module, item_id):
        if module not in self._scraped_sets:
            self._scraped_sets[module] = set(self.data.get(module, {}).get("scraped_ids", []))
        return item_id in self._scraped_sets[module]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)


class JsonlWriter:
    """Append-only JSONL file writer for crash-safe incremental writes."""

    def __init__(self, path):
        self.path = Path(path)

    def append(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def read_all(self):
        if not self.path.exists():
            return []
        records = []
        with open(self.path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records


def setup_logging(log_dir):
    """Configure logging to both console and file."""
    log_path = Path(log_dir) / "scrape.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("linkedin_scraper")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on re-init
    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger


async def random_delay(base_delay=3):
    """Async sleep for a random duration centered on base_delay (jitter +/- 1s)."""
    delay = base_delay + random.uniform(-1, 1)
    delay = max(1, delay)
    await asyncio.sleep(delay)


async def check_login_wall(page):
    """Check if LinkedIn is showing a login wall or auth gate. Returns True if blocked."""
    url = page.url
    if '/login' in url or '/authwall' in url or '/checkpoint' in url:
        return True
    sign_in = await page.query_selector('button[data-tracking-control-name="auth_wall_desktop_profile-login-toggle"]')
    if sign_in:
        return True
    return False


async def handle_login_wall(page, logger):
    """Pause and wait for user to log in manually."""
    logger.warning("Login wall detected. Please log in manually in the browser.")
    input("Press Enter after you have logged in...")
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    # Give LinkedIn a moment to settle, but don't wait for networkidle
    # (LinkedIn never stops making background requests)
    await asyncio.sleep(3)


async def navigate_with_retry(page, url, logger, max_retries=3):
    """Navigate to a URL with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(1)  # Let LinkedIn JS render
            return True
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("Navigation failed (attempt %d/%d): %s. Retrying in %ds...",
                          attempt + 1, max_retries, e, wait)
            if attempt < max_retries - 1:
                await asyncio.sleep(wait)
    logger.error("Failed to navigate to %s after %d attempts", url, max_retries)
    return False


async def download_media(page, url, save_path, logger, max_size_mb=100):
    """Download a media file from a URL. Skips if over max_size_mb."""
    try:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        response = await page.request.get(url)
        if response.status != 200:
            logger.warning("Failed to download %s: HTTP %d", url, response.status)
            return False

        body = await response.body()
        size_mb = len(body) / (1024 * 1024)
        if size_mb > max_size_mb:
            logger.warning("Skipping large file (%.1fMB > %dMB): %s", size_mb, max_size_mb, url)
            return False

        with open(save_path, 'wb') as f:
            f.write(body)
        logger.info("Downloaded: %s (%.1fMB)", save_path, size_mb)
        return True
    except Exception as e:
        logger.error("Error downloading %s: %s", url, e)
        return False
