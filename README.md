# MyFace Sports Newsroom

A lightweight local RSS collector and browser dashboard for Formula 1, UFC, and football.

## Features

- Collects RSS items from configured sources into a local SQLite database.
- Dashboard with category, priority, search, and date-order filters.
- Article summaries, source labels, timestamps, and links to original publishers.
- Manual refresh button in the dashboard.
- Automatic feed checks three times per day: 08:00, 14:00, and 20:00 (system local time).
- A separate timestamped report is saved for every collection run.
- Dashboard refreshes its visible data every two minutes while open.
- No additional Python packages are required for the dashboard; it uses Python's standard library.

## Debian setup

From this project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python newsroom.py --check
python server.py
```

Open `http://127.0.0.1:8765` in Firefox.

## Enable automatic checks (three times daily)

Install and start cron once:

```bash
sudo apt update
sudo apt install cron -y
sudo systemctl enable --now cron
```

From this project directory, install the schedule:

```bash
./install_schedule.sh
```

The collector will check feeds every day at **08:00, 14:00, and 20:00**, using the laptop's system timezone. The laptop must be powered on and not suspended at those times. Missed checks are not automatically replayed.

Every run saves a separate report in `reports/` and appends its output to `logs/scheduled.log`. The SQLite database keeps all collected articles. When the dashboard is open, it reloads the latest database data every two minutes.

Check the schedule:

```bash
crontab -l
```

Read the latest scheduled log:

```bash
tail -n 60 logs/scheduled.log
```

Remove the schedule by running `crontab -e` and deleting the lines marked `MYFACE_SPORTS_NEWSROOM`.

## Stop the dashboard

Return to the terminal running `python server.py` and press `Ctrl+C`.

## Notes

- The dashboard is local to this computer and listens only on `127.0.0.1`.
- RSS summaries may be partial. The dashboard links to the original publisher; verify important claims before publishing.
- Priority is a basic keyword heuristic, not editorial verification.
- Source availability and feed formats can change. Errors are reported in the run report and log.
- Scheduled collection stores stories in the local dashboard and report files. It does not send email, Telegram, or phone push notifications.
