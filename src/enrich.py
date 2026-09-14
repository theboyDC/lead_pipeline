"""Enrich a Places result with a description and email scraped from the
company's own website. Best-effort: any failure here should not break the
pipeline, since Places data alone (name/address/phone) is still useful."""
import logging
import re
import urllib.robotparser
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src import config

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_HEADERS = {"User-Agent": config.SCRAPE_USER_AGENT}


def _allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        # If robots.txt is unreachable, default to allowed rather than blocking.
        return True
    return parser.can_fetch(config.SCRAPE_USER_AGENT, url)


def _extract_description(soup: BeautifulSoup) -> str | None:
    for selector, attr in (
        ({"name": "description"}, "content"),
        ({"property": "og:description"}, "content"),
    ):
        tag = soup.find("meta", attrs=selector)
        if tag and tag.get(attr):
            text = tag[attr].strip()
            if text:
                return text

    for tag in soup.find_all(["nav", "footer", "script", "style"]):
        tag.decompose()
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) >= 60:
            return text
    return None


def _extract_email(soup: BeautifulSoup, page_text: str) -> str | None:
    for link in soup.find_all("a", href=True):
        if link["href"].lower().startswith("mailto:"):
            return link["href"].split(":", 1)[1].split("?")[0].strip()
    match = EMAIL_RE.search(page_text)
    return match.group(0) if match else None


def enrich_from_website(url: str) -> dict:
    """Returns {"description": str|None, "email": str|None}. Never raises."""
    result = {"description": None, "email": None}
    if not url:
        return result

    try:
        if not _allowed_by_robots(url):
            logger.info("robots.txt disallows fetching %s, skipping", url)
            return result

        resp = requests.get(url, headers=_HEADERS, timeout=config.REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        result["description"] = _extract_description(soup)
        result["email"] = _extract_email(soup, soup.get_text(" "))
    except requests.RequestException as exc:
        logger.warning("failed to enrich from %s: %s", url, exc)
    except Exception as exc:  # defensive: malformed HTML, etc.
        logger.warning("unexpected error enriching %s: %s", url, exc)

    return result
