#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python virtual environment not found: $PYTHON"
  echo "Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if ! command -v crontab >/dev/null 2>&1; then
  echo "cron is not installed. Run: sudo apt install cron"
  exit 1
fi

mkdir -p "$PROJECT_DIR/reports" "$PROJECT_DIR/logs"
TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

(crontab -l 2>/dev/null || true) | grep -v '# MYFACE_SPORTS_NEWSROOM' > "$TMP_FILE" || true
for hour in 8 14 20; do
  printf '0 %s * * * cd "%s" && "%s" "%s/newsroom.py" --check >> "%s/logs/scheduled.log" 2>&1 # MYFACE_SPORTS_NEWSROOM\n' \
    "$hour" "$PROJECT_DIR" "$PYTHON" "$PROJECT_DIR" "$PROJECT_DIR" >> "$TMP_FILE"
done
crontab "$TMP_FILE"
echo "Installed: MyFace Sports Newsroom will check feeds daily at 08:00, 14:00, and 20:00 (system local time)."
echo "Reports: $PROJECT_DIR/reports"
echo "Logs: $PROJECT_DIR/logs/scheduled.log"
echo "To remove this schedule, run: crontab -e and delete lines marked MYFACE_SPORTS_NEWSROOM"
