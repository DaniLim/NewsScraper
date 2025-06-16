#!/usr/bin/env python3
"""
feeds.health
~~~~~~~~~~~~

Reusable helpers for validating and (optionally) discovering RSS/Atom feed URLs.

This module provides:
- `validate_url`: Asynchronously checks if a URL returns a valid feed with entries.
- `discover_feed`: Attempts HTML autodiscovery and common path probing (including known API paths).
- `load_feed_dict` / `save_feed_dict`: YAML-backed feed list I/O.
"""

from __future__ import annotations
import asyncio
import html
import logging
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import aiohttp
import feedparser
import yaml
import pathlib
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Configure module-level logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------- constants ----------------------------------------------------
TIMEOUT = 15  # seconds for HTTP requests
HEADERS = {"User-Agent": "NewsScraper/0.1 (+https://github.com/DaniLim)"}
FEEDS_YAML = pathlib.Path(__file__).resolve().parents[1] / "feeds.yaml"
FEED_MIME_RE = re.compile(r"application/(?:rss|atom)\+xml", re.I)

# Known fallback suffixes to probe, including El Norte de Castilla style
FALLBACK_SUFFIXES = (
    "rss", "RSS", "rss/", "RSS/",
    "rss/2.0", "rss/2.0/", "rss/2.0/portada", "rss/2.0/portada/",
)

# ---------- core async helpers ------------------------------------------
async def _fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    """
    Fetch text content from a URL, raising on HTTP or network errors.

    Args:
        session: Shared aiohttp ClientSession.
        url: Target URL to fetch.

    Returns:
        The response body as text.

    Raises:
        aiohttp.ClientError, asyncio.TimeoutError
    """
    try:
        async with session.get(url, timeout=TIMEOUT, headers=HEADERS) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as exc:
        logger.debug("Error fetching %s: %s", url, exc)
        raise

async def validate_url(
    url: str,
    session: aiohttp.ClientSession,
    strict: bool = True,
) -> bool:
    """
    Check if a URL returns a valid RSS/Atom feed.

    Args:
        url: Feed URL to validate.
        session: Shared aiohttp ClientSession.
        strict: If True, require ≥1 entry; if False, only check parsing success.

    Returns:
        True if feed is well-formed (and has entries when strict), False otherwise.
    """
    try:
        raw_text = await _fetch_text(session, url)
    except Exception:
        return False

    parsed = feedparser.parse(raw_text)
    if parsed.bozo:
        logger.debug("Parser error for %s: %s", url, parsed.bozo_exception)
        return False

    if strict and not parsed.entries:
        logger.debug("No entries in feed %s", url)
        return False

    return True

async def discover_feed(
    session: aiohttp.ClientSession,
    root: str
) -> Optional[str]:
    """
    Autodiscover a feed URL given a site root.

    Workflow:
    1) HTML <link rel="alternate"> autodiscovery on homepage.
    2) Probe known URL patterns (FALLBACK_SUFFIXES).

    Args:
        session: Shared aiohttp ClientSession.
        root: Base site URL (e.g. "https://example.com").

    Returns:
        First valid feed URL discovered, or None.
    """
    # 1) HTML <link> autodiscovery
    try:
        page_html = await _fetch_text(session, root)
        soup = BeautifulSoup(page_html, 'html.parser')
        for tag in soup.find_all('link', rel='alternate'):
            mime = tag.get('type', '')
            href = tag.get('href')
            if href and FEED_MIME_RE.match(mime):
                candidate = urljoin(root, href)
                logger.debug("Discovered feed via <link>: %s", candidate)
                return html.unescape(candidate)
    except Exception as exc:
        logger.debug("Autodiscovery failed on homepage %s: %s", root, exc)

    # 2) Fallback: common and known RSS paths
    for suffix in FALLBACK_SUFFIXES:
        probe_url = root.rstrip('/') + '/' + suffix
        try:
            page_html = await _fetch_text(session, probe_url)
            # both XML feeds and HTML discovery pages
            soup = BeautifulSoup(page_html, 'html.parser')
            # Try direct feed parser first
            if await validate_url(probe_url, session, strict=False):
                logger.debug("Valid feed at fallback %s", probe_url)
                return probe_url
            # Otherwise, look for <link> tags pointing to feed
            tag = soup.find('link', type=FEED_MIME_RE)
            if tag and tag.get('href'):
                candidate = urljoin(probe_url, tag['href'])
                if await validate_url(candidate, session, strict=False):
                    logger.debug("Discovered feed via fallback tag %s -> %s", probe_url, candidate)
                    return html.unescape(candidate)
        except Exception:
            continue

    logger.debug("No feed discovered for %s", root)
    return None

# ---------- YAML I/O -----------------------------------------------------
def load_feed_dict() -> List[Dict[str, Any]]:
    """
    Load the feed list from feeds.yaml. Expects a list of dicts with a 'url' key.

    Returns:
        List of feed dictionaries.
    """
    text = FEEDS_YAML.read_text(encoding="utf-8")
    return yaml.safe_load(text)


def save_feed_dict(data: Iterable[Dict[str, Any]]) -> None:
    """
    Persist the feed list back to feeds.yaml, preserving order.

    Args:
        data: Iterable of feed dicts to write.
    """
    FEEDS_YAML.write_text(
        yaml.safe_dump(list(data), allow_unicode=True, sort_keys=False),
        encoding="utf-8"
    )
