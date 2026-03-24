# local_code/scrapers/comments.py
"""Scrape LinkedIn comments from the activity feed."""

import asyncio
import re

from .base import (
    JsonlWriter, check_login_wall, handle_login_wall,
    random_delay, navigate_with_retry
)
from .posts import urn_to_timestamp


async def extract_comment_data(comment_element):
    """Extract structured data from a single comment activity entry."""
    data = {
        "original_author": "",
        "original_snippet": "",
        "original_post_url": "",
        "comment_text": "",
        "timestamp": "",
        "comment_url": "",
    }

    # Expand truncated text before extracting
    # 1. "...more" on post text (expandable-text-button)
    see_more = await comment_element.query_selector('button[data-testid="expandable-text-button"]')
    if see_more:
        try:
            await see_more.click()
            await asyncio.sleep(0.3)
        except Exception:
            pass

    # 2. "...more" on comment text (feed-shared-inline)
    see_more_comment = await comment_element.query_selector('button.feed-shared-inline-show-more-text__see-more-less-toggle')
    if see_more_comment:
        try:
            await see_more_comment.click()
            await asyncio.sleep(0.3)
        except Exception:
            pass

    # Original post author - try multiple selectors
    author_el = await comment_element.query_selector('.update-components-actor__name span[aria-hidden="true"]')
    if not author_el:
        author_el = await comment_element.query_selector('.update-components-actor__name')
    if not author_el:
        # Try the actor title/link area
        author_el = await comment_element.query_selector('.update-components-actor__title span[dir="ltr"] span[aria-hidden="true"]')
    if not author_el:
        author_el = await comment_element.query_selector('a.update-components-actor__container-link span[aria-hidden="true"]')
    if author_el:
        data["original_author"] = (await author_el.inner_text()).strip()

    # Original post snippet (after expanding)
    post_text_el = await comment_element.query_selector('.feed-shared-update-v2__description, .update-components-text')
    if post_text_el:
        full_text = (await post_text_el.inner_text()).strip()
        data["original_snippet"] = full_text[:200]

    # URN from the post element - for both URL construction and timestamp
    urn = ""
    urn_attr = await comment_element.get_attribute("data-urn") or ""
    if urn_attr:
        urn = urn_attr
    if not urn:
        link = await comment_element.query_selector('a[href*="activity"]')
        if link:
            href = await link.get_attribute("href") or ""
            urn_match = re.search(r'(urn:li:activity:\d+)', href)
            if urn_match:
                urn = urn_match.group(1)

    # Original post URL - construct from URN
    if urn:
        data["original_post_url"] = f"https://www.linkedin.com/feed/update/{urn}"

    # Timestamp - derive from URN
    if urn:
        data["timestamp"] = urn_to_timestamp(urn)

    # Stephen's comment text - try multiple selectors
    comment_text_el = await comment_element.query_selector('.comments-comment-item__main-content')
    if not comment_text_el:
        comment_text_el = await comment_element.query_selector('.feed-shared-main-content--comment')
    if not comment_text_el:
        comment_text_el = await comment_element.query_selector('.feed-shared-main-content')
    if comment_text_el:
        data["comment_text"] = (await comment_text_el.inner_text()).strip()

    # Comment URL - construct from URN with comment anchor
    if urn:
        data["comment_url"] = f"https://www.linkedin.com/feed/update/{urn}"

    return data


async def scrape_comments(page, progress, output_dir, args, logger, shutdown_event, watchdog=None):
    """Main comments scraping loop."""
    url = "https://www.linkedin.com/in/ssalaka/recent-activity/comments/"
    writer = JsonlWriter(output_dir / "comments.jsonl")
    count = progress.get_count("comments")

    logger.info("Navigating to comments feed...")
    if not await navigate_with_retry(page, url, logger):
        return

    if await check_login_wall(page):
        await handle_login_wall(page, logger)

    no_new_count = 0
    max_no_new = 10  # Higher threshold - LinkedIn can be slow loading old content
    prev_page_height = 0
    seen_urls = set()

    # Load previously scraped URLs from progress
    for url_id in progress.data.get("comments", {}).get("scraped_ids", []):
        seen_urls.add(url_id)

    fast_scroll_count = 0

    while True:
        if shutdown_event.is_set():
            break

        if args.max_items and count >= args.max_items:
            logger.info("Reached max items limit (%d)", args.max_items)
            break

        # Only check the LAST batch of entries (bottom of page) instead of all
        entries = await page.query_selector_all('.feed-shared-update-v2')
        new_found = False

        # Check entries from the end (newest loaded at bottom)
        # Only look at entries we haven't checked yet
        for entry in entries:
            if shutdown_event.is_set():
                break

            # Get a unique ID for dedup - use URN
            entry_id = await entry.get_attribute("data-urn") or ""
            if not entry_id:
                link = await entry.query_selector('a[href*="activity"]')
                if link:
                    href = await link.get_attribute("href") or ""
                    urn_match = re.search(r'(urn:li:activity:\d+)', href)
                    if urn_match:
                        entry_id = urn_match.group(1)

            if entry_id and entry_id in seen_urls:
                continue

            try:
                data = await extract_comment_data(entry)
                if data["comment_text"]:
                    writer.append(data)
                    count += 1
                    new_found = True
                    fast_scroll_count = 0  # Reset fast scroll when we find new content
                    if entry_id:
                        seen_urls.add(entry_id)
                        progress.add_scraped_id("comments", entry_id)
                    progress.update("comments", count=count, last_timestamp=data["timestamp"])
                    logger.info("Comment %d: %s...", count, data["comment_text"][:50])
                    if watchdog:
                        watchdog.ping()

                    if count % 10 == 0:
                        progress.save()
            except Exception as e:
                logger.error("Error extracting comment: %s", e)

        # Fast scroll mode: if no new content found, scroll quickly
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

        # Check for various "load more" / "show more" buttons
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

        # Check if the page actually grew (new content loaded)
        current_height = await page.evaluate("document.body.scrollHeight")
        page_grew = current_height > prev_page_height
        prev_page_height = current_height

        if not new_found and not page_grew:
            no_new_count += 1
            if no_new_count >= max_no_new:
                logger.info("No new comments found after %d scrolls with no page growth, finishing.", max_no_new)
                break
        else:
            no_new_count = 0

    progress.update("comments", count=count)
    progress.save()
    logger.info("Comments scraping done. Total: %d", count)
