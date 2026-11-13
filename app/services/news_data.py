"""Small, best-effort external market-news reader.

The dashboard deliberately shows an empty state when the upstream RSS feed is
unavailable; it never fabricates market headlines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


FEED_URL = "https://news.google.com/rss/search?{}"
USER_AGENT = "IntelliInvest/1.0 (+market research dashboard)"


def _format_time(raw_value: str) -> str:
    if not raw_value:
        return "Time unavailable"
    try:
        parsed = parsedate_to_datetime(raw_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone().strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError, OverflowError):
        return "Time unavailable"


def get_market_news(limit: int = 10) -> list[dict[str, str]]:
    """Return recent India-market headlines from Google News RSS.

    A short timeout and empty-list fallback prevent a news provider outage
    from breaking the authenticated dashboard.
    """
    safe_limit = max(1, min(int(limit), 20))
    params = urlencode(
        {
            "q": "Indian stock market OR NSE OR BSE when:7d",
            "hl": "en-IN",
            "gl": "IN",
            "ceid": "IN:en",
        }
    )
    request = Request(FEED_URL.format(params), headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=5) as response:
            payload = response.read(1_500_000)
        root = ET.fromstring(payload)
    except (URLError, TimeoutError, OSError, ET.ParseError, ValueError):
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    items: list[dict[str, str]] = []
    for node in channel.findall("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        source_node = node.find("source")
        source = (source_node.text if source_node is not None else "") or "Google News"
        published = (node.findtext("pubDate") or "").strip()
        if not title or not link or not link.startswith("https://"):
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "source": source.strip()[:100],
                "time": _format_time(published),
            }
        )
        if len(items) >= safe_limit:
            break

    return items
