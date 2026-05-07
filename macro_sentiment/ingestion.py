import html
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import PolicyDocument
from .tasks import analyze_policy_document


RBI_HOME = "https://www.rbi.org.in"
RBI_SEARCH_PAGES = [
    "https://www.rbi.org.in/scripts/annualpolicy.aspx",
    "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
    "https://www.rbi.org.in/Scripts/FS_PressRelease.aspx",
    "https://m.rbi.org.in/Scripts/WSSView.aspx?Id=27427",
    "https://m.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=20936",
]


@dataclass
class IngestedPolicy:
    document: PolicyDocument
    created: bool
    sentiment_id: int


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs = dict(attrs)
            self._href = attrs.get("href")
            self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href:
            text = " ".join("".join(self._text).split())
            self.links.append((self._href, text))
            self._href = None
            self._text = []


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip = True
        if tag.lower() in {"p", "br", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip = False
        if tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self):
        text = html.unescape(" ".join(self.parts))
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line)


def ingest_latest_rbi_policy(url=None):
    policy_url = url or getattr(settings, "RBI_POLICY_URL", "") or _discover_latest_url()
    if not policy_url:
        raise RuntimeError(
            "Could not auto-discover the latest RBI policy URL. "
            "Set RBI_POLICY_URL in settings.py or pass --url to the command."
        )

    title, content, published_date = _fetch_policy(policy_url)
    if len(content) < 500:
        raise RuntimeError("Fetched RBI policy content is too short; the page may be blocked.")

    PolicyDocument.objects.filter(
        document_type=PolicyDocument.DocumentType.RBI_MONETARY_POLICY,
        is_latest=True,
    ).update(is_latest=False)

    document, created = PolicyDocument.objects.update_or_create(
        source=policy_url,
        defaults={
            "title": title,
            "content": content,
            "published_date": published_date,
            "document_type": PolicyDocument.DocumentType.RBI_MONETARY_POLICY,
            "is_latest": True,
            "fetched_at": timezone.now(),
        },
    )
    PolicyDocument.objects.filter(
        document_type=PolicyDocument.DocumentType.RBI_MONETARY_POLICY,
    ).exclude(pk=document.pk).delete()

    sentiment = analyze_policy_document(document)
    return IngestedPolicy(document=document, created=created, sentiment_id=sentiment.id)


def _discover_latest_url():
    for page_url in RBI_SEARCH_PAGES:
        try:
            page = _fetch_url(page_url)
        except Exception:
            continue

        parser = _LinkParser()
        parser.feed(page)
        candidates = _policy_link_candidates(page_url, parser.links, page)
        if candidates:
            return candidates[0]
    return ""


def _policy_link_candidates(page_url, links, page):
    candidates = []
    for href, text in links:
        normalized = text.lower()
        if "minutes of the monetary policy committee" in normalized:
            candidates.append(urljoin(page_url, href))

    if candidates:
        return candidates

    for href, text in links:
        normalized = text.lower()
        if (
            "monetary policy statement" in normalized
            and "resolution of the monetary policy committee" in normalized
        ):
            candidates.append(urljoin(page_url, href))

    if candidates:
        return candidates

    # RBI's annualpolicy.aspx page labels the policy resolution URL as "Full Document".
    marker = "Resolution of the Monetary Policy Committee"
    marker_position = page.find(marker)
    if marker_position == -1:
        return []

    tail = page[marker_position : marker_position + 2000]
    parser = _LinkParser()
    parser.feed(tail)
    for href, text in parser.links:
        if "full document" in text.lower():
            candidates.append(urljoin(page_url, href))
    return candidates


def _fetch_policy(url):
    text = _fetch_url(url)
    parser = _TextParser()
    parser.feed(text)
    content = _clean_policy_text(parser.text())
    title = _extract_title(content)
    published_date = _extract_date(content)
    return title, content, published_date


def _clean_policy_text(content):
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    start_index = 0
    start_markers = [
        "Date :",
        "Minutes of the Monetary Policy Committee",
        "Resolution of the Monetary Policy Committee",
        "Monetary Policy Statement",
    ]
    for index, line in enumerate(lines):
        if any(marker in line for marker in start_markers):
            start_index = index
            break

    cleaned = lines[start_index:]
    end_markers = ["Press Release", "Feedback", "Top"]
    useful_lines = []
    for line in cleaned:
        if line in end_markers:
            break
        if line in {"Selected", "Home", "Search", "Press Releases"}:
            continue
        useful_lines.append(line)
    return "\n".join(useful_lines)


def _fetch_url(url):
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _extract_title(content):
    for line in content.splitlines():
        if (
            "Monetary Policy Statement" in line
            or "Minutes of the Monetary Policy Committee" in line
            or "Resolution of the Monetary Policy Committee" in line
        ):
            return line[:255]
    return "Latest RBI Monetary Policy Document"


def _extract_date(content):
    date_patterns = [
        r"Date\s*:\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
    ]
    formats = ["%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"]
    for pattern in date_patterns:
        match = re.search(pattern, content)
        if not match:
            continue
        value = match.group(1)
        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)
                return timezone.make_aware(parsed)
            except ValueError:
                pass
    return timezone.now()
