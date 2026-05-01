import calendar
import html
import os
import threading
from datetime import date

from flask import Flask, jsonify, render_template_string, request

import db
from formatters import mood_band
from utils import today_local


app = Flask(__name__)


PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mood Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #687586;
      --line: #d9e0e8;
      --bg: #f7f4ef;
      --panel: #ffffff;
      --good: #3ba776;
      --neutral: #d7a928;
      --low: #d75f5f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    main {
      width: min(1120px, calc(100% - 32px));
      margin: 28px auto;
      display: grid;
      gap: 18px;
    }
    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 16px;
    }
    h1 { margin: 0; font-size: 30px; letter-spacing: 0; }
    .muted { color: var(--muted); }
    .layout {
      display: grid;
      grid-template-columns: 1fr 320px;
      gap: 18px;
      align-items: start;
    }
    .calendar, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .weekdays, .grid {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 8px;
    }
    .weekdays {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }
    .day {
      min-height: 92px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      background: #fbfcfd;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 4px;
      cursor: pointer;
    }
    .day.empty { visibility: hidden; cursor: default; }
    .num { color: var(--muted); font-size: 13px; }
    .emoji { font-size: 28px; align-self: center; justify-self: center; }
    .score { font-size: 13px; font-weight: 700; }
    .good { border-color: color-mix(in srgb, var(--good) 45%, var(--line)); background: #eef8f3; }
    .neutral { border-color: color-mix(in srgb, var(--neutral) 45%, var(--line)); background: #fff8df; }
    .low { border-color: color-mix(in srgb, var(--low) 45%, var(--line)); background: #fff0f0; }
    aside { display: grid; gap: 16px; }
    .stat { border-bottom: 1px solid var(--line); padding-bottom: 12px; }
    .stat:last-child { border-bottom: 0; padding-bottom: 0; }
    .value { font-size: 24px; font-weight: 750; }
    .tags { display: flex; flex-wrap: wrap; gap: 6px; }
    .tag {
      background: #edf1f5;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 13px;
    }
    @media (max-width: 820px) {
      .layout { grid-template-columns: 1fr; }
      header { align-items: start; flex-direction: column; }
      .day { min-height: 72px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{{ month_name }} {{ year }}</h1>
        <div class="muted">Mood dashboard for {{ display_name }}</div>
      </div>
      <div class="muted">{{ logged_days }} logged day{{ '' if logged_days == 1 else 's' }}</div>
    </header>

    <div class="layout">
      <section class="calendar">
        <div class="weekdays">
          <div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div><div>Sun</div>
        </div>
        <div class="grid">
          {% for item in cells %}
            {% if not item %}
              <div class="day empty"></div>
            {% else %}
              <button class="day {{ item.band }}" data-detail="{{ item.detail }}">
                <span class="num">{{ item.day }}</span>
                <span class="emoji">{{ item.emoji or '·' }}</span>
                <span class="score">{{ item.score_text }}</span>
              </button>
            {% endif %}
          {% endfor %}
        </div>
      </section>

      <aside>
        <div class="stat">
          <div class="muted">Average Mood</div>
          <div class="value">{{ average }}</div>
        </div>
        <div class="stat">
          <div class="muted">Most Common Emotion</div>
          <div class="value">{{ common_emoji }}</div>
        </div>
        <div class="stat">
          <div class="muted">Best Day</div>
          <div>{{ best_day }}</div>
        </div>
        <div class="stat">
          <div class="muted">Worst Day</div>
          <div>{{ worst_day }}</div>
        </div>
        <div class="stat">
          <div class="muted">Selected Day</div>
          <div id="detail">Click a logged day.</div>
        </div>
      </aside>
    </div>
  </main>
  <script>
    document.querySelectorAll("[data-detail]").forEach((button) => {
      button.addEventListener("click", () => {
        document.getElementById("detail").innerHTML = button.dataset.detail;
      });
    });
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    return "Mood bot dashboard is running."


@app.get("/dashboard/<user_id>")
def dashboard(user_id: str):
    today = today_local()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))
    user = db.get_user(user_id)
    display_name = user["first_name"] if user and user["first_name"] else user_id
    rows = [db.row_to_dict(row) for row in db.get_month(user_id, year, month)]
    by_day = {int(row["date"].split("-")[2]): row for row in rows}
    _, days_in_month = calendar.monthrange(year, month)
    first_weekday = date(year, month, 1).weekday()

    cells = [None] * first_weekday
    for day in range(1, days_in_month + 1):
        log = by_day.get(day)
        if log:
            tags = " ".join(f'<span class="tag">#{html.escape(tag)}</span>' for tag in log["tags"])
            note = f"<p>{html.escape(log['note'])}</p>" if log.get("note") else ""
            detail = (
                f"<strong>{log['date']}</strong>"
                f"<p>{log.get('emoji') or ''} {log['score']}/10</p>"
                f"<div class=\"tags\">{tags}</div>{note}"
            )
            cells.append(
                {
                    "day": day,
                    "emoji": log.get("emoji"),
                    "score_text": f"{log['score']}/10",
                    "band": mood_band(log["score"]),
                    "detail": detail.replace('"', "&quot;"),
                }
            )
        else:
            cells.append({"day": day, "emoji": "", "score_text": "", "band": "", "detail": "No log."})

    if rows:
        average = f"{sum(row['score'] for row in rows) / len(rows):.1f}/10"
        common_emoji = max({row.get("emoji") for row in rows if row.get("emoji")} or {"-"}, key=lambda emoji: sum(1 for row in rows if row.get("emoji") == emoji))
        best = max(rows, key=lambda row: row["score"])
        worst = min(rows, key=lambda row: row["score"])
        best_day = f"{best['date']} {best.get('emoji') or ''} {best['score']}/10"
        worst_day = f"{worst['date']} {worst.get('emoji') or ''} {worst['score']}/10"
    else:
        average = "-"
        common_emoji = "-"
        best_day = "-"
        worst_day = "-"

    return render_template_string(
        PAGE,
        display_name=display_name,
        year=year,
        month_name=calendar.month_name[month],
        cells=cells,
        logged_days=len(rows),
        average=average,
        common_emoji=common_emoji,
        best_day=best_day,
        worst_day=worst_day,
    )


@app.get("/api/month/<user_id>")
def api_month(user_id: str):
    today = today_local()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))
    return jsonify([db.row_to_dict(row) for row in db.get_month(user_id, year, month)])


@app.get("/api/day/<user_id>/<log_date>")
def api_day(user_id: str, log_date: str):
    parsed = date.fromisoformat(log_date)
    row = db.get_day(user_id, parsed)
    return jsonify(db.row_to_dict(row) if row else {})


def start() -> None:
    port = int(os.getenv("PORT", "8080"))
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    thread.start()


if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=True)
