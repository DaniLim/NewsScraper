import asyncio, hashlib, sqlite3, yaml, feedparser, aiohttp, re, html
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from pathlib import Path
import argparse, sys

DB_PATH    = Path("news.db")
FEEDS_YAML = Path("feeds.yaml")
SCHEMA_SQL = Path("schema.sql")
CONCURRENCY = 10

def ensure_db():
    """Create DB & schema if first run."""
    if not DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
        conn.close()

def clean_summary(entry, char_limit=500):
    """Return a plain-text summary ≤ char_limit, stripped of HTML/whitespace."""
    # 1. choose best raw HTML snippet
    raw = entry.get("summary") or \
          (entry.get("content") and entry.content[0].value) or ""
    # 2. decode HTML entities (&amp; → &, &#39; → ')
    raw = html.unescape(raw)
    # 3. strip tags & images
    # Use the built in HTML parser to avoid requiring the external ``lxml``
    # dependency. ``lxml`` is not listed in ``requirements.txt`` and using it
    # would cause runtime errors on a fresh install.
    text = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)
    # 4. collapse multiple spaces / newlines
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    # 5. soft-trim: keep whole sentence if it fits char_limit
    if len(text) > char_limit:
        cut = text.rfind(".", 0, char_limit)
        text = (text[: cut + 1] if cut != -1 else text[:char_limit].rstrip()) + "…"
    return text

async def fetch(session, url, timeout=15):
    async with session.get(url, timeout=timeout) as r:
        return await r.read()

async def process_feed(session, db, feed_def, max_items):
    raw = await fetch(session, feed_def["url"])
    parsed = feedparser.parse(raw)
    source = feed_def.get("source") or parsed.feed.get("link", "?")

    for entry in parsed.entries[:max_items]:
        ts = entry.get("published_parsed") or entry.get("updated_parsed")
        if not ts:
            continue
        summary = clean_summary(entry)
        published = datetime(*ts[:6], tzinfo=timezone.utc).isoformat()
        url_hash = hashlib.md5((entry.title + entry.link).encode()).hexdigest()
        try:
            db.execute("INSERT INTO article_hashes(url_hash) VALUES (?)", (url_hash,))
            db.execute("""INSERT INTO articles(rowid,title,summary,url,
                                            source,published_iso)
                        VALUES(NULL,?,?,?,?,?)""",
                    (entry.title[:250],
                        summary,
                        entry.link, source, published))
        except sqlite3.IntegrityError:
            pass  # duplicate


async def ingest(max_items):
    ensure_db()
    feeds = yaml.safe_load(FEEDS_YAML.read_text(encoding="utf-8"))
    db = sqlite3.connect(DB_PATH)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = [
            worker(session, db, f, max_items, sem)
            for f in feeds
        ]
        await asyncio.gather(*tasks)
    db.commit()

async def worker(session, db, feed_def, max_items, sem):
    async with sem:
        try:
            await process_feed(session, db, feed_def, max_items)
        except Exception as e:
            print("⚠️ Error:", feed_def['url'], '→', e, file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-feed", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(ingest(args.max_per_feed))
