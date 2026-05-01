from collections import Counter, defaultdict

from db import row_to_dict


def mood_band(score: int) -> str:
    if score >= 7:
        return "good"
    if score >= 4:
        return "neutral"
    return "low"


def format_saved(log: dict) -> str:
    tags = " ".join(f"#{tag}" for tag in log.get("tags", []))
    sleep = log.get("sleep")
    sleep_text = f"\nSleep: {sleep:g}h" if sleep is not None else ""
    note = log.get("note")
    note_text = f"\nNote: {note}" if note else ""
    return (
        f"Saved {log.get('emoji') or 'mood'} at {log['score']}/10 for today.\n"
        f"{tags or 'No tags yet.'}"
        f"{sleep_text}"
        f"{note_text}"
    )


def format_week(rows) -> str:
    if not rows:
        return "No mood logs in the last 7 days yet. Try /mood 😊 7 sleep=6 study gym"

    logs = [row_to_dict(row) for row in rows]
    avg = sum(log["score"] for log in logs) / len(logs)
    best = max(logs, key=lambda item: item["score"])
    worst = min(logs, key=lambda item: item["score"])
    tags = Counter(tag for log in logs for tag in log["tags"])
    lines = [
        "Weekly mood summary",
        f"Average: {avg:.1f}/10 across {len(logs)} log(s)",
        f"Best: {best['date']} {best.get('emoji') or ''} {best['score']}/10",
        f"Worst: {worst['date']} {worst.get('emoji') or ''} {worst['score']}/10",
    ]
    if tags:
        lines.append("Top tags: " + ", ".join(tag for tag, _ in tags.most_common(3)))

    insights = _basic_insights(logs)
    if insights:
        lines.append("")
        lines.append("Patterns:")
        lines.extend(f"- {insight}" for insight in insights)

    return "\n".join(lines)


def _basic_insights(logs: list[dict]) -> list[str]:
    insights = []
    with_sleep = [log for log in logs if log.get("sleep") is not None]
    low_sleep = [log for log in with_sleep if log["sleep"] < 6]
    enough_sleep = [log for log in with_sleep if log["sleep"] >= 6]
    if low_sleep and enough_sleep:
        low_avg = sum(log["score"] for log in low_sleep) / len(low_sleep)
        enough_avg = sum(log["score"] for log in enough_sleep) / len(enough_sleep)
        if low_avg + 0.75 < enough_avg:
            insights.append("Sleep under 6h is showing lower mood.")

    by_tag = defaultdict(list)
    for log in logs:
        for tag in log["tags"]:
            by_tag[tag].append(log["score"])
    for tag, scores in by_tag.items():
        if len(scores) >= 2 and sum(scores) / len(scores) >= 7:
            insights.append(f"{tag} days are trending positive.")
            break
    return insights

