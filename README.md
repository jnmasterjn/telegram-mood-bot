# telegram-mood-bot

A Telegram bot for daily mood tracking with a web dashboard.

## Features

- Log mood with emoji, score, and tags
- Add and delete notes per day
- Automated daily reminder + follow-up nudge
- Weekly summary with pattern insights
- Monthly calendar dashboard

## Tech Stack

- Python, python-telegram-bot
- Flask (web dashboard)
- PostgreSQL
- Deployed on Railway

## Commands

| Command | Description |
|---|---|
| `/mood 😊 7 study gym` | Log mood with emoji, score (1–10), and tags |
| `/mood 😊 7 study gym 5/3` | Log mood for a past date (M/D format) |
| `/m 6 😴` | Quick log — score + emoji |
| `/note felt great` | Add a note to today's log |
| `/note felt great 5/3` | Add a note to a past date |
| `/delnote` | Clear today's note |
| `/delnote 5/3` | Clear note for a specific date |
| `/delete` | Delete today's entire mood entry |
| `/delete 5/3` | Delete a specific day's entry |
| `/week` | Weekly summary — average, best/worst day, patterns |
| `/month` | Open the monthly dashboard |

## Dashboard

Monthly calendar view with color-coded days:
- Green: score 7–10
- Yellow: score 4–6
- Red: score 1–3

Click any day to see its emoji, score, tags, and notes.

Stats panel shows average mood, most common emotion, best and worst day.

## Setup

### 1. Create a bot

Get a token from [@BotFather](https://t.me/BotFather) on Telegram.

### 2. Configure environment variables

```
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_USER_ID=your_telegram_id
MOOD_TIMEZONE=Asia/Taipei
DAILY_REMINDER_TIME=22:00
FOLLOW_UP_MINUTES=60
PORT=8080
BASE_URL=https://your-railway-domain.up.railway.app
DATABASE_URL=your_postgres_url
```

### 3. Deploy on Railway

1. Push to GitHub
2. New project → Deploy from GitHub repo
3. Add a PostgreSQL database — `DATABASE_URL` is auto-injected
4. Set the environment variables above

### 4. Run locally

```bash
pip install -r requirements.txt
python bot.py
```

## Project Structure

```
bot.py          # Telegram commands and scheduled reminders
db.py           # PostgreSQL schema and data access
dashboard.py    # Flask dashboard and JSON API
formatters.py   # Weekly summary formatting
utils.py        # Timezone and date helpers
requirements.txt
Dockerfile
.env.example
```
