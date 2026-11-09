import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "newsroom.db"
CONFIG_PATH = ROOT / "sources.json"
OUTPUT_PATH = ROOT / "web" / "data.json"

config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    categories = {
        row["category"]: row["count"]
        for row in conn.execute(
            "SELECT category, COUNT(*) AS count FROM articles GROUP BY category"
        )
    }

    priorities = {
        row["priority"]: row["count"]
        for row in conn.execute(
            "SELECT priority, COUNT(*) AS count FROM articles GROUP BY priority"
        )
    }

    last_scan = conn.execute(
        "SELECT scanned_at, new_articles, source_errors "
        "FROM scan_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()

    articles = [
        dict(row)
        for row in conn.execute(
            "SELECT url, title, summary, category, source, published, priority, first_seen "
            "FROM articles ORDER BY COALESCE(published, first_seen) DESC"
        )
    ]

data = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "stats": {
        "total": total,
        "categories": categories,
        "priorities": priorities,
        "sources": len(config["sources"]),
        "last_scan": last_scan["scanned_at"] if last_scan else None,
        "last_scan_new": last_scan["new_articles"] if last_scan else 0,
        "last_scan_errors": last_scan["source_errors"] if last_scan else 0
    },
    "articles": articles
}

OUTPUT_PATH.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(f"Export complete: {total} articles")
print(f"Sources: {len(config['sources'])}")
print(f"Saved to: {OUTPUT_PATH}")
