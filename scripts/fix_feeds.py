#!/usr/bin/env python3
"""
fix_feeds.py
============
Scan feeds.yaml, find feeds that fail validation, try to discover a working
alternate URL, and (optionally) patch feeds.yaml in-place.

Examples
--------
# Dry run – show counts & suggestions
python -m scripts.fix_feeds --debug

# Apply fixes automatically
python -m scripts.fix_feeds --apply
"""
from __future__ import annotations
import asyncio, argparse, logging, aiohttp
from urllib.parse import urlparse
from feeds.health import (
    load_feed_dict,
    save_feed_dict,
    validate_url,
    discover_feed,
)

# -----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

CONCURRENCY   = 12    # parallel HTTP requests
STRICT_CHECK  = False # skip empty-entry check for speed
# -----------------------------------------------------------------------

async def propose_fixes(feeds: list[dict]) -> tuple[dict[str, str], int]:
    """Return (fixes_dict, broken_count_total)."""
    fixes: dict[str, str] = {}
    broken_total = 0
    sem = asyncio.Semaphore(CONCURRENCY)

    async with aiohttp.ClientSession() as sess:

        async def handle(feed: dict):
            nonlocal broken_total
            async with sem:
                ok = await validate_url(feed["url"], sess, strict=STRICT_CHECK)
                if ok:
                    return
                broken_total += 1
                root = f"{urlparse(feed['url']).scheme}://{feed['source']}"
                alt  = await discover_feed(sess, root)
                if alt and await validate_url(alt, sess, strict=STRICT_CHECK):
                    fixes[feed["url"]] = alt

        await asyncio.gather(*(handle(f) for f in feeds))

    return fixes, broken_total

async def main(apply: bool, debug: bool) -> None:
    if debug:
        log.setLevel(logging.DEBUG)

    feeds = load_feed_dict()
    log.info("Checking %d feeds…", len(feeds))

    fixes, broken_total = await propose_fixes(feeds)

    if broken_total == 0:
        log.info("All feeds already valid ✅")
        return

    log.warning(
        "%d feed(s) need attention; %d have auto-repair suggestions",
        broken_total, len(fixes)
    )

    if fixes:
        log.warning("Proposed replacements:")
        for old, new in fixes.items():
            log.warning(" • %s\n   → %s", old, new)

    if apply and fixes:
        for f in feeds:
            if f["url"] in fixes:
                f["url"] = fixes[f["url"]]
        save_feed_dict(feeds)
        log.info("feeds.yaml updated (%d URLs patched)", len(fixes))

# -----------------------------------------------------------------------
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="overwrite feeds.yaml")
    p.add_argument("--debug", action="store_true", help="verbose logging")
    args = p.parse_args()
    asyncio.run(main(apply=args.apply, debug=args.debug))
