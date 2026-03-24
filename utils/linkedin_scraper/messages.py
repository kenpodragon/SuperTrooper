# local_code/scrapers/messages.py
"""Scrape LinkedIn messages - conversation list and full message history."""

import asyncio
import re
from pathlib import Path

from .base import (
    JsonlWriter, check_login_wall, handle_login_wall,
    random_delay, navigate_with_retry
)


def slugify_profile_url(profile_url):
    """Extract a slug from a LinkedIn profile URL for use as filename."""
    clean_url = profile_url.split('?')[0].split('#')[0]
    match = re.search(r'/in/([^/]+)', clean_url)
    if match:
        return match.group(1).lower()
    match = re.search(r'(ACoAA[^/]+)', clean_url)
    if match:
        return match.group(1).lower()
    parts = clean_url.rstrip('/').split('/')
    return parts[-1].lower() if parts else "unknown"


async def scrape_conversation_inline(page, conv_name, output_dir, logger, delay):
    """Scrape the currently-open conversation's message history."""
    await asyncio.sleep(1)  # Let conversation load

    # Get profile URL from thread header
    profile_url = ""
    profile_link = await page.query_selector('a.msg-thread__link-to-profile')
    if profile_link:
        profile_url = await profile_link.get_attribute("href") or ""

    # Determine filename slug
    if profile_url:
        slug = slugify_profile_url(profile_url)
    else:
        slug = re.sub(r'[^\w\-]', '_', conv_name.lower()).strip('_')
        if not slug:
            slug = "unknown_conversation"

    filepath = output_dir / "messages" / f"{slug}.jsonl"

    # Skip if already scraped (file exists with content)
    if filepath.exists() and filepath.stat().st_size > 0:
        logger.info("  Skipping %s (file already exists)", conv_name)
        return 0

    writer = JsonlWriter(filepath)

    # Write conversation header
    writer.append({
        "name": conv_name,
        "profile_url": profile_url,
    })

    # Scroll up to load full history
    msg_list = await page.query_selector('.msg-s-message-list')
    if msg_list:
        prev_count = 0
        no_new = 0
        while no_new < 3:
            await msg_list.evaluate('el => el.scrollTop = 0')
            await asyncio.sleep(0.5)
            events = await page.query_selector_all('.msg-s-message-list__event')
            current_count = len(events)
            if current_count == prev_count:
                no_new += 1
            else:
                if prev_count > 0:
                    logger.info("  Still loading messages (%d so far)...", current_count)
                no_new = 0
                prev_count = current_count

    # Extract all messages
    events = await page.query_selector_all('.msg-s-message-list__event')
    count = 0
    current_date = ""

    for event_el in events:
        try:
            # Check for date header
            date_el = await event_el.query_selector('time.msg-s-message-list__time-heading')
            if date_el:
                current_date = (await date_el.inner_text()).strip()

            # Find message content - try nested first, then direct
            msg_items = await event_el.query_selector_all('.msg-s-event-listitem')
            targets = msg_items if msg_items else [event_el]

            for msg_el in targets:
                sender_el = await msg_el.query_selector('.msg-s-message-group__name')
                sender = (await sender_el.inner_text()).strip() if sender_el else ""

                # Get sender's profile link
                sender_link_el = await msg_el.query_selector('a.msg-s-event-listitem__link')
                if not sender_link_el:
                    sender_link_el = await msg_el.query_selector('.msg-s-message-group__meta a[href*="/in/"]')
                sender_profile = ""
                if sender_link_el:
                    sender_profile = await sender_link_el.get_attribute("href") or ""

                text_el = await msg_el.query_selector('p.msg-s-event-listitem__body')
                text = (await text_el.inner_text()).strip() if text_el else ""

                time_el = await msg_el.query_selector('time.msg-s-message-group__timestamp')
                time_text = (await time_el.inner_text()).strip() if time_el else ""

                timestamp = f"{current_date} {time_text}".strip()

                if text:
                    writer.append({
                        "sender": sender,
                        "sender_profile": sender_profile,
                        "text": text,
                        "timestamp": timestamp,
                    })
                    count += 1

        except Exception as e:
            logger.error("Error extracting message: %s", e)

    logger.info("  Scraped %d messages from %s", count, conv_name)
    return count


async def scrape_messages(page, progress, output_dir, args, logger, shutdown_event, watchdog=None):
    """Scrape messages by processing conversations as we scroll the sidebar."""
    url = "https://www.linkedin.com/messaging/"
    logger.info("Navigating to messaging...")
    if not await navigate_with_retry(page, url, logger):
        return

    if await check_login_wall(page):
        await handle_login_wall(page, logger)

    # Track what we've already scraped
    completed = set(progress.data.get("messages", {}).get("completed_conversations", []))
    count = progress.get_count("messages")
    conv_count = 0
    index_writer = JsonlWriter(output_dir / "conversations_index.jsonl")

    no_new_count = 0
    max_no_new = 10
    prev_sidebar_height = 0
    fast_scroll_count = 0
    seen_this_session = set()  # Track names seen in DOM this session

    while True:
        if shutdown_event.is_set():
            break

        if args.max_items and conv_count >= args.max_items:
            logger.info("Reached max conversations limit (%d)", args.max_items)
            break

        # Get visible conversation items in sidebar
        items = await page.query_selector_all('li.msg-conversation-listitem')
        processed_any = False
        found_new_in_dom = False  # Did we see any name not seen before this session?

        for item in items:
            if shutdown_event.is_set():
                break

            if args.max_items and conv_count >= args.max_items:
                break

            try:
                name_el = await item.query_selector('.msg-conversation-listitem__participant-names')
                if not name_el:
                    continue
                name = (await name_el.inner_text()).strip()
                if not name:
                    continue

                # Track if this is a new name in the DOM this session
                if name not in seen_this_session:
                    seen_this_session.add(name)
                    found_new_in_dom = True

                # Skip already-scraped conversations
                if name in completed:
                    continue

                # Get sidebar timestamp
                time_el = await item.query_selector('time.msg-conversation-listitem__time-stamp')
                time_text = (await time_el.inner_text()).strip() if time_el else ""

                logger.info("Opening conversation %d: %s (%s)", conv_count + 1, name, time_text)

                # Click this conversation to open it
                link = await item.query_selector('.msg-conversation-listitem__link')
                if link:
                    await link.click()
                else:
                    await item.click()

                processed_any = True
                fast_scroll_count = 0

                # Scrape the conversation
                msg_count = await scrape_conversation_inline(page, name, output_dir, logger, args.delay)
                count += msg_count
                conv_count += 1

                # Log to index
                index_writer.append({
                    "name": name,
                    "sidebar_time": time_text,
                    "message_count": msg_count,
                })

                # Mark complete
                completed.add(name)
                progress.update("messages", count=count, completed_conversations=list(completed))
                progress.save()
                if watchdog:
                    watchdog.ping()

                await random_delay(1)

            except Exception as e:
                logger.error("Error processing conversation %s: %s", name if 'name' in dir() else 'unknown', e)

        # Scroll sidebar for more conversations
        sidebar = await page.query_selector('.msg-conversations-container__conversations-list')
        if not sidebar:
            sidebar = await page.query_selector('.msg-conversations-container')
        if sidebar:
            await sidebar.evaluate('el => el.scrollTop = el.scrollHeight')
        else:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        # Fast scroll when catching up past completed conversations
        if processed_any:
            await random_delay(1)
        else:
            fast_scroll_count += 1
            await asyncio.sleep(0.3)
            if fast_scroll_count % 50 == 0:
                logger.info("Fast scrolling sidebar... (%d scrolls, %d conversations scraped, %d completed total)",
                           fast_scroll_count, conv_count, len(completed))

        if watchdog:
            watchdog.ping()

        # Check if sidebar actually grew (new conversations loaded)
        sidebar_height = 0
        if sidebar:
            sidebar_height = await sidebar.evaluate('el => el.scrollHeight')
        sidebar_grew = sidebar_height > prev_sidebar_height
        prev_sidebar_height = sidebar_height

        if not processed_any and not found_new_in_dom and not sidebar_grew:
            no_new_count += 1
            if no_new_count >= max_no_new:
                logger.info("No new conversations after %d scrolls with no sidebar growth. Done.", max_no_new)
                break
        else:
            if not processed_any and (found_new_in_dom or sidebar_grew):
                # Sidebar is growing but all visible are already completed - keep scrolling
                pass
            no_new_count = 0

    progress.update("messages", count=count, completed_conversations=list(completed))
    progress.save()
    logger.info("Messages scraping done. Total messages: %d across %d conversations", count, conv_count)
