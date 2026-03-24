"""
LinkedIn Content Scraper (Platform Copy)
Extracts posts, comments, rich media, and messages from LinkedIn
using Playwright browser automation via CDP.

This is the platform-integrated copy of the scraper, living inside the
SuperTroopers codebase at code/utils/linkedin_scraper/. The original
standalone version is at local_code/linkedin_scraper.py.

Usage (from code/utils/linkedin_scraper/):
    python cli.py                    # all modes (default)
    python cli.py --mode posts       # single mode
    python cli.py --delay 5          # custom delay
    python cli.py --reset            # clear progress, start fresh
    python cli.py --max-items 50     # limit items (for testing)
"""

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from .base import ProgressTracker, setup_logging, ActivityWatchdog

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
# Platform root is code/ (two levels up from code/utils/linkedin_scraper/)
PLATFORM_ROOT = SCRIPT_DIR.parent.parent
# Default output dir — can be overridden for headless/scheduled mode
OUTPUT_DIR = PLATFORM_ROOT.parent / "Originals" / "LinkedIn"
CHROME_USER_DATA = r"C:\Users\ssala\AppData\Local\ms-playwright\linkedin-scraper"
CDP_PORT = 9223
CDP_URL = f"http://localhost:{CDP_PORT}"

# Execution order
MODULE_ORDER = ["posts", "comments", "media", "messages"]

# Shared shutdown event - passed to all scraper modules
shutdown_event = asyncio.Event()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="LinkedIn Content Scraper")
    parser.add_argument("--mode", choices=["all", "posts", "comments", "media", "messages"],
                        default="all", help="Scraping mode (default: all)")
    parser.add_argument("--delay", type=int, default=3,
                        help="Base delay between actions in seconds (default: 3)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Page load timeout in seconds (default: 30)")
    parser.add_argument("--reset", action="store_true",
                        help="Clear progress and start fresh")
    parser.add_argument("--max-items", type=int, default=None,
                        help="Max items per module (for testing)")
    return parser.parse_args(argv)


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    shutdown_event.set()
    logger = logging.getLogger("linkedin_scraper")
    logger.warning("Shutdown requested (Ctrl+C). Finishing current item and saving progress...")


def find_chrome_exe():
    """Find the Chrome executable path."""
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in chrome_paths:
        if os.path.exists(p):
            return p
    return None


async def kill_chrome_on_port():
    """Kill any Chrome process using our CDP port."""
    logger = logging.getLogger("linkedin_scraper")
    try:
        # Find and kill Chrome processes using our user data dir
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "chrome.exe"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            logger.info("Killed existing Chrome processes.")
        await asyncio.sleep(2)  # Wait for processes to die
    except Exception as e:
        logger.warning("Could not kill Chrome: %s", e)


async def ensure_chrome_running(force_restart=False):
    """Launch Chrome with CDP. If force_restart, kill existing Chrome first."""
    logger = logging.getLogger("linkedin_scraper")

    if force_restart:
        await kill_chrome_on_port()
    else:
        # Check if Chrome is already running and usable on the CDP port
        try:
            import urllib.request
            urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2)
            logger.info("Chrome already running on port %d", CDP_PORT)
            return None
        except Exception:
            pass

    chrome_exe = find_chrome_exe()
    if not chrome_exe:
        logger.error("Chrome not found. Please install Google Chrome.")
        sys.exit(1)

    logger.info("Launching Chrome with remote debugging on port %d...", CDP_PORT)
    process = subprocess.Popen([
        chrome_exe,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_USER_DATA}",
        "--no-first-run",
        "--no-default-browser-check",
    ])
    await asyncio.sleep(3)
    return process


async def connect_to_chrome(p, logger, force_restart=False):
    """Connect to Chrome via CDP. Returns (browser, page, chrome_process)."""
    chrome_process = await ensure_chrome_running(force_restart=force_restart)
    browser = await p.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    # Always create a fresh page to avoid stale tab issues
    page = await context.new_page()
    logger.info("Connected to Chrome. New page created.")
    return browser, page, chrome_process


async def check_browser_alive(page, logger):
    """Check if the browser/page is still responsive."""
    try:
        result = await page.evaluate("1 + 1")
        logger.info("Browser alive check OK (page URL: %s)", page.url)
        return True
    except Exception as e:
        logger.warning("Browser alive check FAILED: %s", e)
        return False


async def run_module(module_name, page, progress, args, logger, shutdown_event, watchdog):
    """Run a single scraper module."""
    if module_name == "posts":
        from .posts import scrape_posts
        await scrape_posts(page, progress, OUTPUT_DIR, args, logger, shutdown_event, watchdog)
    elif module_name == "comments":
        from .comments import scrape_comments
        await scrape_comments(page, progress, OUTPUT_DIR, args, logger, shutdown_event, watchdog)
    elif module_name == "media":
        from .media import scrape_media
        await scrape_media(page, progress, OUTPUT_DIR, args, logger, shutdown_event, watchdog)
    elif module_name == "messages":
        from .messages import scrape_messages
        await scrape_messages(page, progress, OUTPUT_DIR, args, logger, shutdown_event, watchdog)


async def watchdog_monitor(watchdog, logger, shutdown_event):
    """Background task that checks the watchdog every 30 seconds."""
    while not shutdown_event.is_set():
        await asyncio.sleep(30)
        try:
            watchdog.check()
        except TimeoutError as e:
            logger.error("Watchdog triggered: %s", e)
            raise


MAX_CRASH_RETRIES = 5
CRASH_RECOVERY_DELAY = 10  # seconds


async def run_scraper(args):
    """Main scraper orchestration with crash recovery."""
    logger = setup_logging(OUTPUT_DIR)
    logger.info("=" * 60)
    logger.info("LinkedIn Scraper starting - mode: %s", args.mode)

    # Setup output directories
    for d in ["media/posts", "media/rich-media", "messages"]:
        (OUTPUT_DIR / d).mkdir(parents=True, exist_ok=True)

    # Progress tracking
    progress = ProgressTracker(OUTPUT_DIR / "progress.json")
    if args.reset:
        logger.info("Resetting progress (--reset flag)")
        progress.data = {}
        progress._scraped_sets = {}
        progress.save()

    modules = MODULE_ORDER if args.mode == "all" else [args.mode]
    chrome_process = None

    async with async_playwright() as p:
        browser, page, chrome_process = await connect_to_chrome(p, logger)
        page.set_default_timeout(args.timeout * 1000)

        for module_name in modules:
            if shutdown_event.is_set():
                logger.info("Shutdown requested, stopping before module: %s", module_name)
                break

            status = progress.get_status(module_name)
            if status == "complete":
                logger.info("Skipping %s (already complete)", module_name)
                continue
            if status == "memory_limit":
                logger.warning("Skipping %s (hit memory crash limit - %d items captured)",
                              module_name, progress.get_count(module_name))
                continue

            logger.info("Starting module: %s", module_name)

            # Track cumulative crash count across runs (persisted in progress.json)
            cumulative_crashes = progress.get_field(module_name, "crash_count") or 0
            MAX_CUMULATIVE_CRASHES = 3

            if cumulative_crashes >= MAX_CUMULATIVE_CRASHES:
                logger.warning("Module %s has crashed %d times across runs. Marking as memory_limit.",
                              module_name, cumulative_crashes)
                progress.update(module_name, status="memory_limit",
                              note=f"Hit memory crash limit after {cumulative_crashes} crashes. {progress.get_count(module_name)} items captured.")
                progress.save()
                continue

            progress.update(module_name, status="in_progress")
            progress.save()

            crash_retries = 0
            watchdog = ActivityWatchdog(timeout_seconds=120)

            while crash_retries < MAX_CRASH_RETRIES:
                try:
                    # Check if browser is still alive before starting
                    if not await check_browser_alive(page, logger):
                        raise Exception("Browser not responsive")

                    # Run module with watchdog monitor in parallel
                    # If watchdog fires, it cancels the module task
                    watchdog.ping()  # Reset timer before starting
                    module_task = asyncio.create_task(
                        run_module(module_name, page, progress, args, logger, shutdown_event, watchdog)
                    )
                    monitor_task = asyncio.create_task(
                        watchdog_monitor(watchdog, logger, shutdown_event)
                    )

                    # Wait for either to finish - if monitor dies first, cancel module
                    done, pending = await asyncio.wait(
                        [module_task, monitor_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # Cancel whichever is still running
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, TimeoutError):
                            pass

                    # Check if the completed task raised an exception
                    for task in done:
                        if task.exception():
                            raise task.exception()

                    # Module completed successfully - reset crash count
                    progress.update(module_name, crash_count=0)
                    break

                except Exception as e:
                    crash_retries += 1
                    cumulative_crashes += 1
                    progress.update(module_name, crash_count=cumulative_crashes)
                    progress.save()

                    if shutdown_event.is_set():
                        logger.info("Shutdown requested during crash recovery.")
                        break

                    if cumulative_crashes >= MAX_CUMULATIVE_CRASHES:
                        logger.error("Module %s has crashed %d times total. Marking as memory_limit to prevent infinite retry loops.",
                                    module_name, cumulative_crashes)
                        progress.update(module_name, status="memory_limit",
                                      note=f"Hit memory crash limit after {cumulative_crashes} crashes. {progress.get_count(module_name)} items captured.")
                        progress.save()
                        break

                    if crash_retries >= MAX_CRASH_RETRIES:
                        logger.error("Module %s failed after %d crash recoveries this session. Will retry next run.",
                                    module_name, MAX_CRASH_RETRIES)
                        break

                    logger.warning("Browser crashed during %s (session attempt %d/%d, total crashes %d/%d): %s",
                                  module_name, crash_retries, MAX_CRASH_RETRIES,
                                  cumulative_crashes, MAX_CUMULATIVE_CRASHES, e)
                    logger.info("Waiting %ds before restarting Chrome...", CRASH_RECOVERY_DELAY)
                    await asyncio.sleep(CRASH_RECOVERY_DELAY)

                    # Reconnect with force restart (kills old Chrome, launches fresh)
                    try:
                        logger.info("Force-restarting Chrome...")
                        browser, page, chrome_process = await connect_to_chrome(p, logger, force_restart=True)
                        page.set_default_timeout(args.timeout * 1000)
                        logger.info("Chrome restarted. Resuming %s...", module_name)
                    except Exception as reconnect_err:
                        logger.error("Failed to reconnect: %s. Will retry...", reconnect_err)
                        await asyncio.sleep(CRASH_RECOVERY_DELAY)

            if not shutdown_event.is_set() and not args.max_items and crash_retries < MAX_CRASH_RETRIES and cumulative_crashes < MAX_CUMULATIVE_CRASHES:
                progress.update(module_name, status="complete", crash_count=0)
                progress.save()
                logger.info("Completed module: %s (count: %d)", module_name, progress.get_count(module_name))

        logger.info("Scraper finished.")
        progress.save()
        logger.info("Progress saved.")
        if chrome_process:
            chrome_process.terminate()


def main():
    signal.signal(signal.SIGINT, signal_handler)
    args = parse_args()
    asyncio.run(run_scraper(args))


if __name__ == "__main__":
    main()
