import os
import logging
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import dashboard
import db
import formatters as fmt
from utils import TIMEZONE, parse_hhmm, today_local


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_USER_ID", "").strip()
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080").rstrip("/")
FOLLOW_UP_MINUTES = int(os.getenv("FOLLOW_UP_MINUTES", "60"))
REMINDER_JOB = "daily_mood_reminder"
FOLLOW_UP_JOB = "mood_follow_up"
TIMEZONE_LABEL = getattr(TIMEZONE, "key", str(TIMEZONE))


def _authorized(update: Update) -> bool:
    return not ALLOWED_USER_ID or str(update.effective_user.id) == ALLOWED_USER_ID


async def _guard(update: Update) -> bool:
    if _authorized(update):
        return True
    if update.message:
        await update.message.reply_text("This bot is private.")
    return False


def _remember_user(update: Update) -> None:
    user = update.effective_user
    chat = update.effective_chat
    db.upsert_user(str(user.id), str(chat.id), user.first_name or "")


def _parse_mood_args(args: list[str], quick: bool = False) -> dict:
    if quick:
        if not args:
            raise ValueError("Usage: /m 6 😴")
        score = _parse_score(args[0])
        emoji = args[1] if len(args) > 1 else ""
        rest = args[2:]
    else:
        if len(args) < 2:
            raise ValueError("Usage: /mood 😊 7 study gym")
        emoji = args[0]
        score = _parse_score(args[1])
        rest = args[2:]

    label = ""
    tags = []
    note_parts = []
    log_date = None

    for item in rest:
        if "=" in item:
            key, value = item.split("=", 1)
            key = key.lower().strip()
            value = value.strip()
            if key == "label":
                label = value
            elif key == "note":
                note_parts.append(value)
            elif key == "date":
                try:
                    log_date = date.fromisoformat(value)
                except ValueError:
                    raise ValueError(f"Invalid date '{value}'. Use date=YYYY-MM-DD.")
            else:
                tags.append(f"{key}:{value}")
        else:
            tags.append(item.strip("#"))

    return {
        "score": score,
        "emoji": emoji,
        "label": label,
        "tags": [tag for tag in tags if tag],
        "note": " ".join(note_parts),
        "log_date": log_date,
    }


def _parse_score(value: str) -> int:
    score = int(value)
    if not 1 <= score <= 10:
        raise ValueError("Mood score must be from 1 to 10.")
    return score


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    await update.message.reply_text(
        "Mood Track Bot is live.\n\n"
        "Commands:\n"
        "/mood 😊 7 study gym\n"
        "/m 6 😴\n"
        "/note felt stressed today\n"
        "/week\n"
        "/month\n"
        "/status"
    )


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    try:
        parsed = _parse_mood_args(context.args)
    except Exception as exc:
        await update.message.reply_text(str(exc) or "Usage: /mood 😊 7 sleep=6 study gym")
        return

    user_id = str(update.effective_user.id)
    log_date = parsed.pop("log_date") or today_local()
    db.save_mood(user_id=user_id, log_date=log_date, **parsed)
    row = db.get_day(user_id, log_date)
    await update.message.reply_text(fmt.format_saved(db.row_to_dict(row)))


async def cmd_quick_mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    try:
        parsed = _parse_mood_args(context.args, quick=True)
    except Exception as exc:
        await update.message.reply_text(str(exc) or "Usage: /m 6 😴")
        return

    user_id = str(update.effective_user.id)
    log_date = parsed.pop("log_date") or today_local()
    db.save_mood(user_id=user_id, log_date=log_date, **parsed)
    row = db.get_day(user_id, log_date)
    await update.message.reply_text(fmt.format_saved(db.row_to_dict(row)))


async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    note = " ".join(context.args).strip()
    if not note:
        await update.message.reply_text("Usage: /note felt stressed today")
        return

    if db.append_note(str(update.effective_user.id), today_local(), note):
        await update.message.reply_text("Added that note to today's mood log.")
    else:
        await update.message.reply_text("Log your mood first, then add a note.")


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    rows = db.get_recent(str(update.effective_user.id), days=7)
    await update.message.reply_text(fmt.format_week(rows))


async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    user_id = str(update.effective_user.id)
    await update.message.reply_text(f"{BASE_URL}/dashboard/{user_id}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    reminder_time = parse_hhmm(os.getenv("DAILY_REMINDER_TIME", "22:00"))
    await update.message.reply_text(
        f"Daily reminder: {reminder_time.strftime('%H:%M')} {TIMEZONE_LABEL}\n"
        f"Dashboard: {BASE_URL}/dashboard/{update.effective_user.id}"
    )


async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = today_local()
    sent_any = False
    for user in db.list_users():
        if db.get_day(user["user_id"], today):
            continue
        await context.bot.send_message(
            chat_id=int(user["chat_id"]),
            text=(
                "How was your day? (1-10)\n"
                "Emotion? (emoji)\n"
                "Tags?\n\n"
                "Fast log: /mood 😊 7 study gym"
            ),
        )
        sent_any = True

    if sent_any:
        context.job_queue.run_once(
            send_follow_up,
            when=FOLLOW_UP_MINUTES * 60,
            data={"date": today.isoformat()},
            name=FOLLOW_UP_JOB,
        )


async def send_follow_up(context: ContextTypes.DEFAULT_TYPE) -> None:
    raw_date = (context.job.data or {}).get("date")
    check_date = date.fromisoformat(raw_date) if raw_date else today_local()
    for user in db.list_users():
        if db.get_day(user["user_id"], check_date):
            continue
        await context.bot.send_message(chat_id=int(user["chat_id"]), text="👀 you forgot to log today")


def main() -> None:
    if not TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in your environment or .env file.")

    db.init_db()
    dashboard.start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("mood", cmd_mood))
    app.add_handler(CommandHandler("m", cmd_quick_mood))
    app.add_handler(CommandHandler("note", cmd_note))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("month", cmd_month))
    app.add_handler(CommandHandler("status", cmd_status))

    reminder_time = parse_hhmm(os.getenv("DAILY_REMINDER_TIME", "22:00"))
    app.job_queue.run_daily(send_daily_reminder, time=reminder_time, name=REMINDER_JOB)

    log.info("Mood bot started. Daily reminder at %s %s", reminder_time.strftime("%H:%M"), TIMEZONE_LABEL)
    app.run_polling()


if __name__ == "__main__":
    main()
