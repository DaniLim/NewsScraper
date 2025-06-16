#!/usr/bin/env python3
"""
feeds.health – helper utilities
==============================
Robust RSS/Atom discovery & validation for **NewsScraper**.

Key refinements in this release
------------------------------
* **Binary‑safe fetch** – we now read raw *bytes* (`resp.read()`), letting
  *feedparser* determine the encoding from the XML prolog. This fixes feeds such
  as *Superdeporte* that serve ISO‑8859‑1.
* **Smarter HTTP headers** – explicit `Accept` hints encourage servers to return
  XML rather than an HTML landing page.
* **Alt‑host & deep‑path probing** – unchanged from previous version, but now
  aided by the more forgiving validator.
"""
from __future__ import annotations

import asyncio, html, logging, pathlib, re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp, feedparser, yaml
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TIMEOUT = 15  # seconds
HEADERS = {
    "User-Agent": "NewsScraper/0.3 (+https://github.com/DaniLim)",
    # Prefer XML/RSS but fall back gracefully
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
}
FEEDS_YAML = pathlib.Path(__file__).resolve().parents[1] / "feeds.yaml"

# MIME & URL heuristics
FEED_MIME_RE = re.compile(r"(?:application|text)/(?:rss|atom)\+xml(?:;.*)?", re.I)
URL_FEED_RE  = re.compile(r"rss|feeds?|\.xml|\.rss|\.atom", re.I)

# Common path probes
GENERIC_PROBES = [
    "feed", "feed/", "feed.xml", "feeds", "feeds/", "feeds/index.xml",
    "rss", "rss/", "rss.xml", "rss/index.xml", "atom", "atom.xml", "index.xml",
]
SPECIFIC_PROBES = [
    "rss/rss_ee.xml",                        # eleconomista.es
    "RSS-portlet/feed/la-razon/portada",     # larazon.es
    "rss/portada.xml", "rss/section/portada",
    "rss/2.0", "rss/2.0/", "rss/2.0/portada",
]
COMMON_FEED_PATHS = GENERIC_PROBES + SPECIFIC_PROBES

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
async def _fetch_raw(session: aiohttp.ClientSession, url: str) -> bytes:
    """Return body **bytes**; raises on error."""
    async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        return await resp.read()

async def _fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    """Return body decoded as text using aiohttp auto‑detection."""
    async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        return await resp.text()

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
async def validate_url(url: str, session: aiohttp.ClientSession, *, strict: bool = True) -> bool:
    """
    True if *url* is a well‑formed feed.

    • Uses raw bytes to let feedparser honour the XML prolog’s charset.
    • Accepts feeds with non‑fatal *bozo* issues so long as entries exist
      (or *strict* is False).
    """
    try:
        raw = await _fetch_raw(session, url)
    except Exception:
        return False

    parsed = feedparser.parse(raw)
    if parsed.bozo and not parsed.entries:
        return False
    if strict and not parsed.entries:
        return False
    return True

# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------
async def _extract_feed_urls(html_text: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    candidates: List[str] = []
    for tag in soup.find_all(True):
        for val in (tag.attrs.get("href"), tag.attrs.get("src")):
            if isinstance(val, str) and URL_FEED_RE.search(val):
                candidates.append(urljoin(base_url, val))
    # Deduplicate
    seen: set[str] = set()
    uniq = [c for c in candidates if not (c in seen or seen.add(c))]
    return uniq

async def _probe_candidate(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    return url if await validate_url(url, session, strict=False) else None

async def _alt_hosts(url: str) -> List[str]:
    p = urlparse(url)
    naked = p.netloc.lstrip("www.")
    return list(dict.fromkeys([f"{p.scheme}://{naked}", f"{p.scheme}://www.{naked}"]))

async def discover_feed(session: aiohttp.ClientSession, root: str) -> Optional[str]:
    """Return first valid feed URL discovered for *root*, else *None*."""
    for host in await _alt_hosts(root):
        # 1) Homepage scrape
        try:
            html_text = await _fetch_text(session, host)
            for cand in await _extract_feed_urls(html_text, host):
                if await _probe_candidate(session, cand):
                    logger.debug("Feed via homepage %s → %s", host, cand)
                    return html.unescape(cand)
        except Exception:
            pass

        # 2) Common paths & their inner pages
        for suf in COMMON_FEED_PATHS:
            probe = host.rstrip("/") + "/" + suf.lstrip("/")
            if await _probe_candidate(session, probe):
                logger.debug("Feed via path %s", probe)
                return probe
            try:
                probe_html = await _fetch_text(session, probe)
                for cand in await _extract_feed_urls(probe_html, probe):
                    if await _probe_candidate(session, cand):
                        logger.debug("Feed inside %s → %s", probe, cand)
                        return html.unescape(cand)
            except Exception:
                continue
    return None

# ---------------------------------------------------------------------------
# YAML I/O
# ---------------------------------------------------------------------------

def load_feed_dict() -> List[Dict[str, Any]]:
    return yaml.safe_load(FEEDS_YAML.read_text(encoding="utf-8")) or []

def save_feed_dict(data: Iterable[Dict[str, Any]]) -> None:
    FEEDS_YAML.write_text(
        yaml.safe_dump(list(data), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
