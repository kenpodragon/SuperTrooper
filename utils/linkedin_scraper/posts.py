# local_code/scrapers/posts.py
"""Scrape LinkedIn posts from the activity feed."""

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path

from .base import (
    JsonlWriter, check_login_wall, handle_login_wall,
    random_delay, download_media, navigate_with_retry
)


# LinkedIn activity IDs are snowflake-like: top bits encode a timestamp
# The epoch and bit shift were reverse-engineered from known posts
LINKEDIN_EPOCH_MS = 0  # LinkedIn uses Unix epoch

def urn_to_timestamp(urn):
    """Extract approximate timestamp from a LinkedIn activity URN.
    LinkedIn activity IDs encode creation time in the upper bits (42-bit timestamp, milliseconds)."""
    match = re.search(r'(\d+)$', urn)
    if not match:
        return ""
    activity_id = int(match.group(1))
    # LinkedIn uses a 42-bit ms timestamp in upper bits, shifted left by 22
    timestamp_ms = activity_id >> 22
    try:
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        # Sanity check: should be between 2010 and 2030
        if 2010 <= dt.year <= 2030:
            return dt.isoformat()
    except (ValueError, OSError, OverflowError):
        pass
    return ""


async def extract_post_data(post_element, page, media_dir, logger):
    """Extract structured data from a single post element."""
    data = {
        "text": "",
        "timestamp": "",
        "post_type": "text",
        "likes": 0,
        "comments": 0,
        "reposts": 0,
        "media_files": [],
        "url": "",
        "urn": "",
        "original_author": None,
    }

    # Expand truncated text by clicking "see more" / "...more" button
    # Expand truncated text - try both button variants
    see_more = await post_element.query_selector('button[data-testid="expandable-text-button"]')
    if not see_more:
        see_more = await post_element.query_selector('button.feed-shared-inline-show-more-text__see-more-less-toggle')
    if see_more:
        try:
            await see_more.click()
            await asyncio.sleep(0.5)
        except Exception:
            pass

    # Text content (now expanded)
    text_el = await post_element.query_selector('.feed-shared-update-v2__description, .update-components-text')
    if text_el:
        data["text"] = (await text_el.inner_text()).strip()

    # URN - try data attribute first, then look in links
    urn_attr = await post_element.get_attribute("data-urn") or ""
    if urn_attr:
        data["urn"] = urn_attr
    if not data["urn"]:
        link_el = await post_element.query_selector('a[href*="activity"]')
        if link_el:
            href = await link_el.get_attribute("href") or ""
            urn_match = re.search(r'(urn:li:activity:\d+)', href)
            if urn_match:
                data["urn"] = urn_match.group(1)

    # Timestamp - derive from URN
    if data["urn"]:
        data["timestamp"] = urn_to_timestamp(data["urn"])

    # URL - construct from URN
    if data["urn"]:
        data["url"] = f"https://www.linkedin.com/feed/update/{data['urn']}"

    # Engagement counts - reactions (likes)
    reactions_el = await post_element.query_selector('.social-details-social-counts__social-proof-fallback-number')
    if reactions_el:
        reactions_text = (await reactions_el.inner_text()).strip()
        reactions_text = reactions_text.replace(',', '')
        if reactions_text.isdigit():
            data["likes"] = int(reactions_text)

    # Comments count
    comments_btn = await post_element.query_selector('button[aria-label*="comment"]')
    if comments_btn:
        aria = await comments_btn.get_attribute("aria-label") or ""
        match = re.search(r'(\d[\d,]*)\s*comment', aria, re.I)
        if match:
            data["comments"] = int(match.group(1).replace(',', ''))

    # Reposts count
    reposts_btn = await post_element.query_selector('button[aria-label*="repost"]')
    if reposts_btn:
        aria = await reposts_btn.get_attribute("aria-label") or ""
        match = re.search(r'(\d[\d,]*)\s*repost', aria, re.I)
        if match:
            data["reposts"] = int(match.group(1).replace(',', ''))

    # Detect post type and media
    img_elements = await post_element.query_selector_all('.update-components-image__image img, .feed-shared-image__image img')
    video_elements = await post_element.query_selector_all('video')
    doc_elements = await post_element.query_selector_all('.feed-shared-document')

    if video_elements:
        data["post_type"] = "video"
    elif doc_elements:
        data["post_type"] = "document"
    elif img_elements:
        data["post_type"] = "image"

    # Check for repost
    reshare = await post_element.query_selector('.feed-shared-update-v2__update-content-wrapper--repost, .update-components-mini-update-v2')
    if reshare:
        data["post_type"] = "repost"
        author_el = await reshare.query_selector('.update-components-actor__name')
        if author_el:
            data["original_author"] = (await author_el.inner_text()).strip()

    # Download images
    for i, img in enumerate(img_elements):
        src = await img.get_attribute("src")
        if src and not src.startswith("data:"):
            timestamp_slug = data["timestamp"][:10] if data["timestamp"] else "unknown"
            filename = f"{timestamp_slug}_{i}.jpg"
            save_path = media_dir / "posts" / filename
            if await download_media(page, src, save_path, logger):
                data["media_files"].append(str(save_path.relative_to(media_dir.parent)))

    return data


async def scrape_posts(page, progress, output_dir, args, logger, shutdown_event, watchdog=None):
    """Main posts scraping loop."""
    url = "https://www.linkedin.com/in/ssalaka/recent-activity/all/"
    writer = JsonlWriter(output_dir / "posts.jsonl")
    media_dir = output_dir / "media"
    count = progress.get_count("posts")

    logger.info("Navigating to posts feed...")
    if not await navigate_with_retry(page, url, logger):
        return

    # Check for login wall
    if await check_login_wall(page):
        await handle_login_wall(page, logger)

    no_new_count = 0
    max_no_new = 10
    prev_page_height = 0
    fast_scroll_count = 0

    while True:
        if shutdown_event.is_set():
            break

        if args.max_items and count >= args.max_items:
            logger.info("Reached max items limit (%d)", args.max_items)
            break

        # Get all post elements currently in the DOM
        posts = await page.query_selector_all('.feed-shared-update-v2')
        new_found = False

        for post_el in posts:
            if shutdown_event.is_set():
                break

            # Try to get a unique identifier
            urn = await post_el.get_attribute("data-urn") or ""
            if not urn:
                link = await post_el.query_selector('a[href*="activity"]')
                if link:
                    href = await link.get_attribute("href") or ""
                    match = re.search(r'(urn:li:activity:\d+)', href)
                    if match:
                        urn = match.group(1)

            if urn and progress.is_scraped("posts", urn):
                continue

            # Extract post data
            try:
                data = await extract_post_data(post_el, page, media_dir, logger)
                if data["text"] or data["media_files"]:
                    writer.append(data)
                    count += 1
                    new_found = True
                    fast_scroll_count = 0
                    if urn:
                        progress.add_scraped_id("posts", urn)
                    progress.update("posts", count=count, last_timestamp=data["timestamp"])
                    logger.info("Post %d: %s... [%s]", count, data["text"][:50], data["post_type"])
                    if watchdog:
                        watchdog.ping()

                    if count % 10 == 0:
                        progress.save()
            except Exception as e:
                logger.error("Error extracting post: %s", e)

        # Fast scroll mode tracking
        if not new_found:
            fast_scroll_count += 1
            if fast_scroll_count % 50 == 0:
                logger.info("Fast scrolling... (%d scrolls, height: %d, %d items scraped so far)",
                           fast_scroll_count, prev_page_height, count)

        # Scroll down
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        # Use fast scroll (0.3s) when catching up, normal delay (1s) when scraping
        if new_found:
            await random_delay(1)
        else:
            await asyncio.sleep(0.3)

        if watchdog:
            watchdog.ping()

        # Check for various "load more" buttons
        for selector in [
            'button.scaffold-finite-scroll__load-button',
            'button:has-text("Show more results")',
            'button:has-text("Load more")',
        ]:
            load_more = await page.query_selector(selector)
            if load_more:
                try:
                    await load_more.click()
                    await asyncio.sleep(0.5)
                    if watchdog:
                        watchdog.ping()
                except Exception:
                    pass
                break

        # Check if page actually grew
        current_height = await page.evaluate("document.body.scrollHeight")
        page_grew = current_height > prev_page_height
        prev_page_height = current_height

        if not new_found and not page_grew:
            no_new_count += 1
            if no_new_count >= max_no_new:
                logger.info("No new posts found after %d scrolls with no page growth, finishing.", max_no_new)
                break
        else:
            no_new_count = 0

    progress.update("posts", count=count)
    progress.save()
    logger.info("Posts scraping done. Total: %d", count)
