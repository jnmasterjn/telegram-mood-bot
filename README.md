# Mood Tracking Telegram Bot + Dashboard

## Overview

This project is a Telegram-based mood tracking system with a web dashboard for monthly visualization and insights.

The system allows users to:

- Log daily mood using simple commands
- Track emotions, sleep, and activities
- Receive automated daily reminders
- View monthly summaries via a web page

Goal:

Build a lightweight, daily-use system that turns personal mood data into meaningful insights.

## Architecture

```text
Telegram Bot -> Backend (Python) -> Database -> Web Dashboard
```

- Telegram Bot: user input and reminders
- Backend: processing and logic
- Database: stores mood data
- Web Dashboard: visualization and monthly view

## Tech Stack

- Python
- python-telegram-bot
- Flask
- SQLite
- HTML/CSS with small vanilla JavaScript
- Chart.js for future optional charts

Use `JobQueue` for scheduling daily messages.

## Telegram Bot Features

### 1. Daily Mood Logging

Command:

```text
/mood 😊 7 sleep=6 study gym
```

Parsed as:

- emoji = 😊
- score = 7
- sleep = 6
- tags = `["study", "gym"]`

### 2. Quick Logging

Command:

```text
/m 6 😴
```

Minimal input for fast usage.

### 3. Daily Reminder

- Bot sends a message at default 10:00 PM
- Uses scheduled job system

Message format:

```text
How was your day? (1-10)
Emotion? (emoji)
Sleep hours?
Tags?
```

### 4. Follow-up Reminder

If no response within about 1 hour:

```text
👀 you forgot to log today
```

### 5. Weekly Summary

Command:

```text
/week
```

Returns:

- average mood
- best/worst day
- detected patterns

### 6. Monthly Dashboard Link

Command:

```text
/month
```

Returns:

```text
https://yourapp.com/dashboard/<user_id>
```

### 7. Notes

Optional command:

```text
/note felt stressed today
```

## Database Schema

Table: `mood_logs`

```sql
id INTEGER PRIMARY KEY
user_id TEXT
date DATE
score INTEGER
emoji TEXT
label TEXT
sleep REAL
tags TEXT
note TEXT
```

## Web Dashboard Features

### 1. Monthly Calendar View

- Display all days of month
- Each day shows emoji

Example:

```text
😊 😐 😢 😴 😊 😡 😊
😊 😊 😐 😐 😢 😊 😊
```

### 2. Color Coding

- Green: good days, scores 7-10
- Yellow: neutral days, scores 4-6
- Red: bad days, scores 1-3

### 3. Statistics Panel

- average mood
- most common emotion
- best/worst day

### 4. Pattern Insights

Examples:

- Sleep under 6h -> lower mood
- Gym days -> higher mood

### 5. Day Detail View

Click a day to show:

- mood
- tags
- notes

## Data Flow

1. User sends `/mood` command
2. Bot parses input
3. Backend stores data in database
4. Dashboard fetches data via API
5. User views monthly insights

## Key Implementation Details

### Telegram Scheduling

Use `JobQueue` to:

- schedule daily reminder
- schedule follow-up ping

This allows periodic tasks in bot logic.

### Command Parsing

Input format:

```text
/mood <emoji> <score> [key=value] [tags...]
```

Example parsing logic:

- first arg = emoji
- second arg = score
- `key=value` pairs become structured fields
- remaining values become tags

### API Endpoints

```text
GET /api/month/<user_id>
GET /api/day/<user_id>/<date>
```

## Project Structure

```text
bot.py            # Telegram commands and JobQueue reminders
db.py             # SQLite schema and data access
dashboard.py      # Flask dashboard and JSON API
formatters.py     # Telegram summary formatting
utils.py          # timezone and date helpers
requirements.txt
Dockerfile
.env.example
```

## Setup

Create a bot token with Telegram's BotFather, then configure the project:

```bash
cp .env.example .env
```

Fill in `.env`:

```text
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_USER_ID=optional_private_user_id
BASE_URL=http://localhost:8080
MOOD_TIMEZONE=Asia/Taipei
DAILY_REMINDER_TIME=22:00
FOLLOW_UP_MINUTES=60
DATABASE_PATH=mood.db
PORT=8080
```

Run locally:

```bash
pip install -r requirements.txt
python bot.py
```

Open the local dashboard at:

```text
http://localhost:8080/dashboard/<your_telegram_user_id>
```

## MVP Scope

Build only:

- `/mood`
- `/m`
- daily reminder
- monthly dashboard with basic grid

Skip initially:

- fancy UI
- authentication
- advanced AI analysis

## Design Principles

- fast input over perfect input
- consistency over complexity
- insight over UI design

## Future Improvements

- emotion auto-suggestions
- AI pattern detection
- habit correlation
- export data as CSV
- mobile-friendly dashboard

## Purpose

This is not just a bot.

It is a personal dataset system that helps users understand how their behavior affects their mood.
# telegram-mood-bot
