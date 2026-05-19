#!/usr/bin/env python3
"""
Java Coach Telegram Bot — отдельный бот для @razesdazbot.

Запуск:
  python3 bot.py                    # foreground (для теста)
  pm2 start bot.py --interpreter python3 --name java-coach  # демон

Требует TG_BOT_TOKEN в .env
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.error import URLError

BASE = Path(__file__).resolve().parent
COACH = BASE / "coach.py"
ENV_FILE = BASE / ".env"
POLL_INTERVAL = 10


def load_token():
    """Load bot token from .env or env var."""
    token = os.environ.get("TG_BOT_TOKEN", "")
    if token:
        return token
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("TG_BOT_TOKEN="):
            return line.split("=", 1)[1].strip()
    return None


def tg_api(method, data=None):
    """Call Telegram Bot API."""
    token = load_token()
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except URLError as e:
        return None
    except (json.JSONDecodeError, OSError):
        return None


def send_message(chat_id, text, parse_mode="Markdown"):
    """Send message to a chat."""
    TG_MAX = 4096
    if len(text) > TG_MAX:
        # Split into chunks
        chunks = []
        for line in text.split("\n"):
            if not chunks or len(chunks[-1]) + len(line) + 1 > TG_MAX:
                chunks.append(line)
            else:
                chunks[-1] += "\n" + line
        for i, chunk in enumerate(chunks):
            payload = {"chat_id": chat_id, "text": chunk, "disable_notification": i > 0}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            tg_api("sendMessage", payload)
        return True

    payload = {"chat_id": chat_id, "text": text, "disable_notification": False}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    r = tg_api("sendMessage", payload)
    return bool(r and r.get("ok"))


def call_coach(message):
    """Call coach.py with a message and return response."""
    try:
        r = subprocess.run(
            [sys.executable, str(COACH), message],
            capture_output=True, text=True, timeout=60,
        )
        return r.stdout.strip() or r.stderr.strip() or "❌ Нет ответа"
    except subprocess.TimeoutExpired:
        return "⏳ Превышено время ожидания. Попробуй короче вопрос."
    except Exception as e:
        return f"❌ Ошибка: {e}"


def poll_updates(offset=0):
    """Poll for new messages."""
    payload = {"offset": offset + 1, "timeout": 10, "allowed_updates": ["message"]}
    r = tg_api("getUpdates", payload)
    if not r or not r.get("ok"):
        return offset, []

    max_id = offset
    messages = []
    for upd in r.get("result", []):
        uid = upd.get("update_id", 0)
        max_id = max(max_id, uid)
        msg = upd.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")
        if text and chat_id:
            messages.append({"chat_id": chat_id, "text": text.strip(), "update_id": uid})
    return max_id, messages


def handle_message(msg):
    """Process a single message."""
    cid = msg["chat_id"]
    text = msg["text"]

    if text == "/start":
        send_message(cid,
            "🤖 *Java Coach*\n\n"
            "Персональный тьютор по Java для AQA Interview.\n\n"
            "Пиши любой вопрос по Java или команду:\n"
            "• `/java статус` — прогресс\n"
            "• `/java поехали` — начать программу\n"
            "• `/java дай задачу` — получить задачу\n"
            "• `/java давай дальше` — след. неделя\n\n"
            "Или просто спроси: `что такое final?`"
        )
        return

    if text == "/help":
        send_message(cid,
            "🤖 *Java Coach*\n\n"
            "Пиши /java <вопрос> или просто вопрос.\n\n"
            "Команды:\n"
            "• поехали — начать\n"
            "• статус — прогресс\n"
            "• дай задачу — практика\n"
            "• дальше — след. неделя\n"
            "• давай дальше — отметить неделю\n"
            "• зачёт / собес — мини-интервью"
        )
        return

    # Strip /java prefix if present
    if text.startswith("/java "):
        text = text[len("/java "):].strip()
    elif text == "/java":
        send_message(cid, "Напиши /java <вопрос>. Например: `/java что такое final?`")
        return

    if not text:
        return

    # Notify user we're processing
    send_message(cid, "⏳ Думаю...")

    # Call coach
    response = call_coach(text)
    send_message(cid, response)


def main():
    token = load_token()
    if not token:
        print("ERROR: No TG_BOT_TOKEN in .env or environment")
        sys.exit(1)

    # Verify token
    me = tg_api("getMe")
    if me and me.get("ok"):
        bot_user = me.get("result", {}).get("username", "?")
        print(f"Java Coach Bot @{bot_user} started (poll {POLL_INTERVAL}s)")
    else:
        print("WARNING: Token verification failed")

    offset = 0
    while True:
        try:
            offset, msgs = poll_updates(offset)
            if msgs:
                for msg in msgs:
                    handle_message(msg)
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(POLL_INTERVAL * 2)


if __name__ == "__main__":
    main()
