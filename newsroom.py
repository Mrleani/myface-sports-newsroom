import argparse
import hashlib
import html
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "sources.json"
DB_PATH = ROOT / "newsroom.db"
REPORTS_DIR = ROOT / "reports"

HEADERS = {
    "User-Agent": "MyFaceSportsNewsroom/0.1 (+personal news monitoring; contact: newsroom@example.com)"
}

CATEGORY_LABELS = {
    "formula1": "FORMULA 1",
    "ufc": "UFC",
    "football": "FOOTBALL",
}

IMPORTANT_TERMS = {
    "high": [
        "official", "confirmed", "announces", "announced", "signs", "signed",
        "transfer", "injury", "champion", "title fight", "race winner",
        "qualifying", "grand prix", "fight announced", "breaking"
    ],
    "medium": [
        "preview", "interview", "reaction", "analysis", "report",
        "contract", "returns", "suspended", "schedule", "draw"
    ],
}


def clean_text(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(entry):
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            pass
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def normalize_url(url):
    if not url:
        return ""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def priority_for(title, summary):
    text = f"{title} {summary}".lower()
    if any(term in text for term in IMPORTANT_TERMS["high"]):
        return "HIGH"
    if any(term in text for term in IMPORTANT_TERMS["medium"]):
        return "MEDIUM"
    return "LOW"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_at TEXT NOT NULL,
                new_articles INTEGER NOT NULL,
                source_errors INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                category TEXT NOT NULL,
                source TEXT NOT NULL,
                published TEXT,
                priority TEXT NOT NULL,
                first_seen TEXT NOT NULL
            )
        """)


def fetch_feed(source):
    response = requests.get(
        source["url"],
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Feed parse error: {parsed.bozo_exception}")
    return parsed.entries


def collect():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    REPORTS_DIR.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    new_articles = []
    errors = []

    with sqlite3.connect(DB_PATH) as conn:
        for source in config["sources"]:
            try:
                entries = fetch_feed(source)
                source_count = 0
                for entry in entries:
                    title = clean_text(entry.get("title"))
                    link = normalize_url(entry.get("link"))
                    if not title or not link:
                        continue

                    summary = clean_text(
                        entry.get("summary") or entry.get("description") or ""
                    )
                    published = parse_date(entry)
                    published_iso = published.isoformat() if published else None
                    priority = priority_for(title, summary)
                    first_seen = now.isoformat()

                    cursor = conn.execute("""
                        INSERT OR IGNORE INTO articles
                        (url, title, summary, category, source, published, priority, first_seen)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        link, title, summary[:1200], source["category"],
                        source["name"], published_iso, priority, first_seen
                    ))

                    if cursor.rowcount == 1:
                        source_count += 1
                        new_articles.append({
                            "title": title,
                            "summary": summary,
                            "url": link,
                            "category": source["category"],
                            "source": source["name"],
                            "published": published,
                            "priority": priority,
                        })

                print(f"[OK] {source['name']}: {len(entries)} feed items, {source_count} new")
            except Exception as exc:
                errors.append((source["name"], str(exc)))
                print(f"[ERROR] {source['name']}: {exc}")

    # Undated stories are kept, but displayed after dated stories.
    new_articles.sort(
        key=lambda item: item["published"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO scan_runs (scanned_at, new_articles, source_errors) VALUES (?, ?, ?)",
            (now.isoformat(), len(new_articles), len(errors)),
        )

    write_report(new_articles, errors, now)
    return len(new_articles), errors


def write_report(articles, errors, now):
    date_label = now.astimezone().strftime("%Y-%m-%d")
    time_label = now.astimezone().strftime("%H-%M-%S")
    report_path = REPORTS_DIR / f"news_report_{date_label}_{time_label}.md"

    lines = [
        "# MYFACE SPORTS — DAILY NEWS REPORT",
        "",
        f"Generated: {now.astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
        f"New items collected: {len(articles)}",
        "",
        "> This is an automated collection report, not a fact-check. Verify important claims against the linked original source before publishing.",
        "",
    ]

    for category in ("formula1", "ufc", "football"):
        category_items = [a for a in articles if a["category"] == category]
        lines.extend([f"## {CATEGORY_LABELS.get(category, category.upper())}", ""])
        if not category_items:
            lines.extend(["No new items collected in this run.", ""])
            continue

        for item in category_items:
            published = (
                item["published"].astimezone().strftime("%Y-%m-%d %H:%M %Z")
                if item["published"] else "Date not provided by feed"
            )
            lines.extend([
                f"### [{item['priority']}] {item['title']}",
                f"- Source: {item['source']}",
                f"- Published: {published}",
                f"- Link: {item['url']}",
            ])
            if item["summary"]:
                lines.append(f"- Summary: {item['summary']}")
            lines.append("")

    if errors:
        lines.extend(["## SOURCE ERRORS", ""])
        for source, error in errors:
            lines.append(f"- **{source}:** {error}")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport saved: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="MyFace Sports RSS news collector")
    parser.add_argument("--check", action="store_true", help="Collect new items and create a report")
    args = parser.parse_args()

    if not args.check:
        parser.print_help()
        return

    init_db()
    count, errors = collect()
    print(f"\nFinished. New articles: {count}. Source errors: {len(errors)}")


if __name__ == "__main__":
    main()
