import os
import logging
import re
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
            raise ValueError("Usage: /m 6 😴 drink 5/3")
        score = _parse_score(args[0])
        emoji = args[1] if len(args) > 1 else ""
        rest = args[2:]
    else:
        if len(args) < 2:
            raise ValueError("Usage: /mood 😊 7 study gym 5/3")
        emoji = args[0]
        score = _parse_score(args[1])
        rest = args[2:]

    label = ""
    tags = []
    note_parts = []
    log_date = None

    for item in rest:
        if _DATE_SHORT.match(item):
            log_date = _parse_short_date(item)
        elif "=" in item:
            key, value = item.split("=", 1)
            key = key.lower().strip()
            value = value.strip()
            if key == "label":
                label = value
            elif key == "note":
                note_parts.append(value)
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


_DATE_SHORT = re.compile(r'^\d{1,2}/\d{1,2}$')


def _parse_short_date(value: str) -> date:
    month, day = map(int, value.split('/'))
    try:
        return date(today_local().year, month, day)
    except ValueError:
        raise ValueError(f"Invalid date '{value}'.")


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
        "/month"
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
    args = context.args or []
    log_date = today_local()
    note_parts = []
    for arg in args:
        if _DATE_SHORT.match(arg):
            try:
                log_date = _parse_short_date(arg)
            except ValueError:
                await update.message.reply_text("Invalid date. Use M/D like 5/3.")
                return
        else:
            note_parts.append(arg)
    note = " ".join(note_parts).strip()
    if not note:
        await update.message.reply_text("Usage: /note felt stressed 5/3")
        return

    if db.append_note(str(update.effective_user.id), log_date, note):
        await update.message.reply_text(f"Added note to {log_date}.")
    else:
        await update.message.reply_text("No mood log found for that date. Log your mood first.")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    args = context.args or []
    log_date = today_local()
    if args and _DATE_SHORT.match(args[0]):
        try:
            log_date = _parse_short_date(args[0])
        except ValueError:
            await update.message.reply_text("Invalid date. Use M/D like 5/3.")
            return

    if db.delete_log(str(update.effective_user.id), log_date):
        await update.message.reply_text(f"Deleted mood log for {log_date}.")
    else:
        await update.message.reply_text(f"No log found for {log_date}.")


async def cmd_delnote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    args = context.args or []
    log_date = today_local()
    if args and _DATE_SHORT.match(args[0]):
        try:
            log_date = _parse_short_date(args[0])
        except ValueError:
            await update.message.reply_text("Invalid date. Use M/D like 5/3.")
            return

    if db.clear_note(str(update.effective_user.id), log_date):
        await update.message.reply_text(f"Cleared note for {log_date}.")
    else:
        await update.message.reply_text(f"No log found for {log_date}.")


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    rows = db.get_recent(str(update.effective_user.id), days=7)
    await update.message.reply_text(fmt.format_week(rows))


def _dashboard_button(user_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Open Dashboard", url=f"{BASE_URL}/dashboard/{user_id}")
    ]])


async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    _remember_user(update)
    user_id = str(update.effective_user.id)
    await update.message.reply_text("Your mood dashboard:", reply_markup=_dashboard_button(user_id))



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
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("delnote", cmd_delnote))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("month", cmd_month))

    reminder_time = parse_hhmm(os.getenv("DAILY_REMINDER_TIME", "22:00"))
    app.job_queue.run_daily(send_daily_reminder, time=reminder_time, name=REMINDER_JOB)

    log.info("Mood bot started. Daily reminder at %s %s", reminder_time.strftime("%H:%M"), TIMEZONE_LABEL)
    app.run_polling()


if __name__ == "__main__":
    main()
