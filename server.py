import json
import sqlite3
import threading
from contextlib import redirect_stdout
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import newsroom

HOST = "127.0.0.1"
PORT = 8765
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "newsroom.db"
REFRESH_LOCK = threading.Lock()

CATEGORY_LABELS = {
    "formula1": "Formula 1",
    "ufc": "UFC",
    "football": "Football",
}


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_stats():
    with db_connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        by_category = {
            row["category"]: row["count"]
            for row in conn.execute(
                "SELECT category, COUNT(*) AS count FROM articles GROUP BY category"
            )
        }
        by_priority = {
            row["priority"]: row["count"]
            for row in conn.execute(
                "SELECT priority, COUNT(*) AS count FROM articles GROUP BY priority"
            )
        }
        latest = conn.execute(
            "SELECT MAX(first_seen) FROM articles"
        ).fetchone()[0]
        last_scan = conn.execute(
            "SELECT scanned_at, new_articles, source_errors FROM scan_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {
        "total": total,
        "categories": by_category,
        "priorities": by_priority,
        "sources": len(json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))["sources"]),
        "last_update": latest,
        "last_scan": last_scan["scanned_at"] if last_scan else None,
        "last_scan_new": last_scan["new_articles"] if last_scan else 0,
        "last_scan_errors": last_scan["source_errors"] if last_scan else 0,
    }


def get_articles(params):
    category = params.get("category", ["all"])[0]
    priority = params.get("priority", ["all"])[0]
    query = params.get("q", [""])[0].strip()
    sort = params.get("sort", ["newest"])[0]
    try:
        limit = min(max(int(params.get("limit", ["100"])[0]), 1), 500)
        offset = max(int(params.get("offset", ["0"])[0]), 0)
    except ValueError:
        limit, offset = 100, 0

    clauses = []
    values = []
    if category in CATEGORY_LABELS:
        clauses.append("category = ?")
        values.append(category)
    if priority in ("HIGH", "MEDIUM", "LOW"):
        clauses.append("priority = ?")
        values.append(priority)
    if query:
        clauses.append("(title LIKE ? OR summary LIKE ? OR source LIKE ?)")
        pattern = f"%{query}%"
        values.extend([pattern, pattern, pattern])

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    order = "COALESCE(published, first_seen) DESC" if sort == "newest" else "COALESCE(published, first_seen) ASC"

    with db_connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM articles{where}", values
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT url, title, summary, category, source, published, priority, first_seen "
            f"FROM articles{where} ORDER BY {order} LIMIT ? OFFSET ?",
            values + [limit, offset],
        ).fetchall()

    return {
        "total": total,
        "articles": [dict(row) for row in rows],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[dashboard] {self.address_string()} - {fmt % args}")

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/stats":
            self.send_json(get_stats())
            return
        if parsed.path == "/api/articles":
            self.send_json(get_articles(parse_qs(parsed.query)))
            return
        if parsed.path in ("/", "/index.html"):
            target = ROOT / "web" / "index.html"
            content_type = "text/html; charset=utf-8"
        elif parsed.path == "/styles.css":
            target = ROOT / "web" / "styles.css"
            content_type = "text/css; charset=utf-8"
        elif parsed.path == "/app.js":
            target = ROOT / "web" / "app.js"
            content_type = "text/javascript; charset=utf-8"
        else:
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/api/refresh":
            self.send_error(404)
            return
        if not REFRESH_LOCK.acquire(blocking=False):
            self.send_json({"ok": False, "message": "A refresh is already running."}, 409)
            return
        try:
            newsroom.init_db()
            output = StringIO()
            with redirect_stdout(output):
                new_count, errors = newsroom.collect()
            self.send_json({
                "ok": True,
                "new_articles": new_count,
                "errors": [{"source": name, "message": message} for name, message in errors],
                "log": output.getvalue(),
                "stats": get_stats(),
            })
        except Exception as exc:
            self.send_json({"ok": False, "message": str(exc)}, 500)
        finally:
            REFRESH_LOCK.release()


def main():
    newsroom.init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"MyFace Sports Newsroom is running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop the dashboard.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
