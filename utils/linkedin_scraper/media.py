# local_code/scrapers/media.py
"""Scrape rich media from LinkedIn settings page."""

import asyncio
from pathlib import Path
from urllib.parse import urlparse, unquote

from .base import (
    JsonlWriter, check_login_wall, handle_login_wall,
    random_delay, download_media, navigate_with_retry
)


async def scrape_media(page, progress, output_dir, args, logger, shutdown_event, watchdog=None):
    """Main rich media scraping loop."""
    url = "https://www.linkedin.com/mypreferences/d/rich-media"
    writer = JsonlWriter(output_dir / "rich_media.jsonl")
    media_dir = output_dir / "media" / "rich-media"
    media_dir.mkdir(parents=True, exist_ok=True)
    count = progress.get_count("rich_media")
    start_page = progress.get_field("rich_media", "last_page") or 0

    logger.info("Navigating to rich media page...")
    if not await navigate_with_retry(page, url, logger):
        return

    if await check_login_wall(page):
        await handle_login_wall(page, logger)

    # Verify page exists and has expected content
    content = await page.content()
    if "rich-media" not in content.lower() and "media" not in page.url.lower():
        logger.warning("Rich media page may have moved. URL: %s. Skipping.", page.url)
        progress.update("rich_media", status="skipped", note="Page not found or relocated")
        progress.save()
        return

    page_num = 0
    while True:
        if shutdown_event.is_set():
            break

        page_num += 1
        if page_num <= start_page:
            if page_num == 1 and start_page > 1:
                # Jump directly to the resume page by clicking its page button
                target_page = start_page + 1
                page_btn = await page.query_selector(f'button[aria-label="Page {target_page}"]')
                if page_btn:
                    await page_btn.click()
                    await random_delay(args.delay)
                    page_num = target_page
                    continue
                # Fallback: click Next repeatedly
                next_btn = await page.query_selector('button._nextBtn_156gez, button:has-text("Next")')
                if next_btn:
                    await next_btn.click()
                    await random_delay(args.delay)
            else:
                next_btn = await page.query_selector('button._nextBtn_156gez, button:has-text("Next")')
                if next_btn:
                    await next_btn.click()
                    await random_delay(args.delay)
            continue

        logger.info("Processing page %d...", page_num)

        # Find all rich media entries on the current page
        media_entries = await page.query_selector_all('li.rich-media-entry-container')

        if not media_entries:
            logger.info("No media entries found on page %d.", page_num)

        for entry in media_entries:
            if shutdown_event.is_set():
                break

            if args.max_items and count >= args.max_items:
                break

            try:
                # Get date and description
                labels = await entry.query_selector_all('p.rich-media-entry__label')
                date_text = ""
                if labels:
                    date_text = (await labels[0].inner_text()).strip()

                desc_el = await entry.query_selector('p[data-teset-rich-media-entry-uploaded-description], p[data-test-rich-media-entry-uploaded-description]')
                description = ""
                if desc_el:
                    description = (await desc_el.inner_text()).strip()

                # Get download link
                download_link = await entry.query_selector('a[data-test-rich-media-entry-download-link]')
                if not download_link:
                    continue

                src = await download_link.get_attribute("href") or ""
                if not src:
                    continue

                # Determine filename from URL path + add extension based on URL
                parsed = urlparse(src)
                path_parts = parsed.path.split('/')
                # URL structure: /dms/prv/image/v2/.../article-cover_image-.../0/timestamp
                raw_name = path_parts[-1] if path_parts else f"media_{count}"

                # Guess extension from URL
                ext = ".jpg"  # default
                if "video" in src.lower():
                    ext = ".mp4"
                elif "document" in src.lower() or "pdf" in src.lower():
                    ext = ".pdf"

                # Build a descriptive filename
                date_slug = date_text.replace(",", "").replace(" ", "_").replace(":", "")[:20] if date_text else f"page{page_num}"
                filename = f"{date_slug}_{count}{ext}"

                save_path = media_dir / filename

                if save_path.exists():
                    logger.info("Skipping (already exists): %s", filename)
                    continue

                if await download_media(page, src, save_path, logger):
                    writer.append({
                        "filename": filename,
                        "download_path": str(save_path.relative_to(output_dir)),
                        "page_number": page_num,
                        "date": date_text,
                        "description": description,
                        "source_url": src,
                    })
                    count += 1
                    logger.info("Media %d: %s - %s (page %d)", count, filename, description, page_num)
                    if watchdog:
                        watchdog.ping()
            except Exception as e:
                logger.error("Error processing media entry: %s", e)

        progress.update("rich_media", count=count, last_page=page_num)
        progress.save()

        if args.max_items and count >= args.max_items:
            logger.info("Reached max items limit (%d)", args.max_items)
            break

        # Try to go to next page - click the Next button
        next_btn = await page.query_selector('button._nextBtn_156gez')
        if not next_btn:
            # Fallback selectors
            next_btn = await page.query_selector('button:has-text("Next")')
        if not next_btn:
            logger.info("No next page button found. Done with rich media.")
            break

        # Check if Next is disabled (last page)
        is_disabled = await next_btn.get_attribute("disabled")
        if is_disabled is not None:
            logger.info("Next button disabled. Reached last page.")
            break

        try:
            await next_btn.click()
            await random_delay(args.delay)
        except Exception:
            logger.info("Could not navigate to next page. Done.")
            break

    # Detect total pages from the select dropdown
    page_options = await page.query_selector_all('nav._pagination_156gez select option')
    if page_options:
        total_pages = len(page_options)
        progress.update("rich_media", total_pages=total_pages)

    progress.update("rich_media", count=count)
    progress.save()
    logger.info("Rich media scraping done. Total: %d", count)
