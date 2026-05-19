#!/usr/bin/env python3
"""
Researcher — nightly article curation for Java Coach.

Читает текущую неделю из memory.json, находит 3 статьи:
  2 — прямо по теме (практика, туториалы)
  1 — теория/собесы (JVM, best practices, лайфхаки)

Запуск:
  python3 researcher.py                # консоль
  python3 researcher.py --send         # отправить в Telegram
  python3 researcher.py --send --dry   # тест без отправки

Cron: 0 3 * * * cd /root/java-tutor && python3 researcher.py --send
"""

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
COACH_DIR = BASE
MEMORY_FILE = COACH_DIR / "memory.json"


# ── Curriculum (same as in coach.py) ───────────────────────────────

PHASES = [
    {
        "name": "Фаза 0: Фундамент",
        "weeks": [
            (1, "Переменные, типы, операторы, массивы, циклы"),
            (2, "String, StringBuilder, методы, return"),
            (3, "Классы, объекты, конструкторы, ООП (инкапсуляция)"),
            (4, "Наследование, полиморфизм, интерфейсы, абстрактные классы"),
        ],
    },
    {
        "name": "Фаза 1: Core для собеса",
        "weeks": [
            (5, "Исключения, дженерики, Collections (List, Set, Map)"),
            (6, "Многопоточность: Thread, Runnable, synchronized, volatile"),
            (7, "ConcurrentHashMap, Concurrent коллекции, race conditions"),
            (8, "CompletableFuture, Lambda, Streams"),
        ],
    },
    {
        "name": "Фаза 2: Инструменты тестирования",
        "weeks": [
            (9, "Awaitility, асинхронные тесты без Thread.sleep"),
            (10, "RestAssured: пагинация, таймауты, параллельные запросы"),
            (11, "JUnit 5 + Mockito для собеса"),
        ],
    },
    {
        "name": "Фаза 3: Алгоритмы лайт",
        "weeks": [
            (12, "Two Sum, Reverse array, Duplicates, Two Pointers"),
            (13, "Стек, очередь, базовая сортировка, Big O"),
        ],
    },
    {
        "name": "Фаза 4: System Design",
        "weeks": [
            (14, "Нагрузочное тестирование: k6/Gatling, rate limiting"),
            (15, "CI-стратегия: @StressTest, изолированные стенды"),
        ],
    },
    {
        "name": "Фаза 5: Mock-сессии",
        "weeks": [
            (16, "Mock-сессия #1 (полный собес 1 час)"),
            (17, "Разбор ошибок + Mock-сессия #2"),
            (18, "Финальная Mock-сессия"),
        ],
    },
]


def find_week(num):
    for phase in PHASES:
        for w_num, topic in phase["weeks"]:
            if w_num == num:
                return phase["name"], topic
    return None, None


# ── Memory ──────────────────────────────────────────────────────────

def load_memory():
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"current_week": 0, "completed_weeks": []}


# ── DeepSeek ────────────────────────────────────────────────────────

def load_key():
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("DEEPSEEK_API_KEY", "")


def call_deepseek(system, user, temp=0.7, max_tokens=2048):
    key = load_key()
    if not key:
        return "ERROR: No API key"

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
    }).encode()

    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


# ── Research ────────────────────────────────────────────────────────

def research_articles(week_num, topic, phase_name):
    """Find 3 articles: 2 practical + 1 theory for current week."""
    system = (
        "You are a Java learning curator. You find high-quality articles "
        "for a QA engineer learning Java for an AQA interview.\n\n"
        "Rules:\n"
        "- Articles must be real, well-known sources (Baeldung, Vogella, "
        "Jenkov, Oracle docs, Medium/Java, Dev.to, JavaRush, "
        "Habr, Хекслет, Metanit, etc.)\n"
        "- Match the reader's level — NOT too basic, NOT too advanced\n"
        "- URLs should be realistic paths on these domains\n"
        "- Respond in Russian. Title can be in original language\n\n"
        "Return 3 articles:\n"
        "1-2: Practical tutorial directly on the topic (with code examples)\n"
        "3: Theory/Interview/Bonus — JVM internals, best practices, "
        "or interview lifehack relevant to this stage\n\n"
        "Format each as:\n"
        "📘 Заголовок\n"
        "Источник: domain.com\n"
        "Ссылка: https://...\n"
        "Почему: 1 sentence why it's useful at this stage\n"
    )

    user = (
        f"Студент на этапе: {phase_name}\n"
        f"Неделя {week_num}: {topic}\n\n"
        f"Найди 3 статьи:\n"
        f"1-2 — практические туториалы прямо по теме\n"
        f"3 — теоретическая / собесы / лайфхак\n\n"
        f"Уровень: AQA-инженер, учит Java для прохождения собеса. "
        f"Не слишком базово, но и не advanced Java."
    )

    result = call_deepseek(system, user, temp=0.8, max_tokens=2048)

    if result.startswith("ERROR"):
        return result

    # Split into practical vs theory sections by parsing
    return result


# ── Build Message ───────────────────────────────────────────────────

def build_research_message(week_num, topic, phase_name):
    """Generate the morning research digest."""
    today = datetime.now().strftime("%d.%m.%Y")

    lines = [
        f"🌅 *Java Coach · Утренний дайджест*",
        f"📅 {today}\n",
    ]

    if week_num == 0:
        lines.append(
            "*Программа ещё не начата*\n"
            "Напиши «поехали» в @razesdazbot — и я начну подбирать "
            "статьи под твой уровень."
        )
        return "\n".join(lines)

    lines.append(f"📖 *Неделя {week_num}: {topic}*")
    lines.append(f"📁 {phase_name}\n")

    articles = research_articles(week_num, topic, phase_name)

    if articles.startswith("ERROR"):
        lines.append("❌ Researcher временно недоступен.")
    else:
        lines.append(articles)
        lines.append("")
        lines.append("— ☕ Прочитай за кофе, потом обсудим")

    return "\n".join(lines)


# ── Telegram Send ──────────────────────────────────────────────────

def send_telegram(message, token=None):
    """Send message to all known chats (from bot's known_chats.json)."""
    if not token:
        env_file = BASE / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("TG_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break
    if not token:
        print("  [no TG_BOT_TOKEN in .env]", file=sys.stderr)
        return False

    # Read known chats from bot's registry
    chats_file = BASE / "known_chats.json"
    if not chats_file.exists():
        print(f"  [no {chats_file} — message the bot first]", file=sys.stderr)
        return False

    try:
        chat_ids = json.loads(chats_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [chats read error: {e}]", file=sys.stderr)
        return False

    if not chat_ids:
        print("  [no known chats]", file=sys.stderr)
        return False

    success = False
    for cid in chat_ids:
        try:
            body = json.dumps({
                "chat_id": int(cid), "text": message,
                "parse_mode": "Markdown",
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            success = True
        except Exception as e:
            print(f"  [send to {cid} failed: {e}]", file=sys.stderr)

    return success


# ── Main ────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    do_send = "--send" in args
    do_dry = "--dry" in args

    memory = load_memory()
    week = memory.get("current_week", 0)
    phase_name, topic = find_week(week)

    msg = build_research_message(week, topic or "", phase_name or "")
    print(msg)

    if do_send and do_dry:
        print("\n[dry run — not sent]")

    if do_send and not do_dry:
        ok = send_telegram(msg)
        print(f"\n[Telegram: {'✅' if ok else '❌'}]")


if __name__ == "__main__":
    main()
