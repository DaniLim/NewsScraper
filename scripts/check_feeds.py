#!/usr/bin/env python3
"""
Quick validator: exits 1 if any feed is unreachable or unparsable.
Run manually, as a pre-commit hook, or in CI.
"""
import asyncio, logging, sys, aiohttp
from feeds.health import load_feed_dict, validate_url

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CONCURRENCY = 12        # Tune for local v. CI speed

async def main() -> None:
    feeds = load_feed_dict()
    bad   = []

    sem   = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as sess:

        async def check(f):
            async with sem:
                ok = await validate_url(f["url"], sess)
                if not ok:
                    bad.append(f)

        await asyncio.gather(*(check(f) for f in feeds))

    # ---------- report ----------
    if bad:
        logging.error("%d feed(s) failed:", len(bad))
        for f in bad:
            logging.error(" • %-30s %s", f["source"], f["url"])
        sys.exit(1)

    logging.info("All %d feeds are healthy ✅", len(feeds))

if __name__ == "__main__":
    asyncio.run(main())
