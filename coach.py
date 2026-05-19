#!/usr/bin/env python3
"""
Java Coach — персональный AI-тьютор по Java (AQA Interview Survival, 18 недель).

Режимы:
  python3 coach.py --chat              # интерактивный диалог
  python3 coach.py "вопрос"            # разовый ответ
  python3 coach.py --daily             # утренняя мотивация (для cron)
  python3 coach.py --status            # текущий прогресс
  python3 coach.py --push-daily        # --daily + отправить в Telegram
"""

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
MEMORY_FILE = BASE / "memory.json"

# ── Curriculum ──────────────────────────────────────────────────────

CURRICULUM = {
    "title": "AQA Interview Survival (18 недель)",
    "phases": [
        {
            "name": "Фаза 0: Фундамент",
            "weeks": [
                {"num": 1, "topic": "Переменные, типы, операторы, массивы, циклы",
                 "practice": "CodingBat Warmup-1", "check": "CodingBat Warmup-1 без ошибок"},
                {"num": 2, "topic": "String, StringBuilder, методы, return",
                 "practice": "CodingBat String-1", "check": "CodingBat String-1 без ошибок"},
                {"num": 3, "topic": "Классы, объекты, конструкторы, ООП (инкапсуляция)",
                 "practice": "CodingBat", "check": "Написать класс BankAccount"},
                {"num": 4, "topic": "Наследование, полиморфизм, интерфейсы, абстрактные классы",
                 "practice": "CodingBat", "check": "Написать иерархию Employee"},
            ],
        },
        {
            "name": "Фаза 1: Core для собеса",
            "weeks": [
                {"num": 5, "topic": "Исключения, дженерики, Collections (List, Set, Map)",
                 "practice": "LeetCode Easy", "check": "Разобрать 3 задачи на Map/Set"},
                {"num": 6, "topic": "Многопоточность: Thread, Runnable, synchronized, volatile",
                 "practice": "Конспект", "check": "Написать потокобезопасный счётчик"},
                {"num": 7, "topic": "ConcurrentHashMap, Concurrent коллекции, race conditions",
                 "practice": "Конспект", "check": "Разобрать race condition пример"},
                {"num": 8, "topic": "CompletableFuture, Lambda, Streams",
                 "practice": "Mock-сессия 1", "check": "Mock-сессия 45 мин"},
            ],
        },
        {
            "name": "Фаза 2: Инструменты тестирования",
            "weeks": [
                {"num": 9, "topic": "Awaitility, асинхронные тесты без Thread.sleep",
                 "practice": "Практика", "check": "Тест на async код"},
                {"num": 10, "topic": "RestAssured: пагинация, таймауты, параллельные запросы",
                 "practice": "Практика", "check": "Написать тест с пагинацией"},
                {"num": 11, "topic": "JUnit 5 + Mockito для собеса",
                 "practice": "Практика", "check": "Mock-тест с Mockito"},
            ],
        },
        {
            "name": "Фаза 3: Алгоритмы лайт",
            "weeks": [
                {"num": 12, "topic": "Two Sum, Reverse array, Duplicates, Two Pointers",
                 "practice": "LeetCode Easy", "check": "5 задач LeetCode Easy"},
                {"num": 13, "topic": "Стек, очередь, базовая сортировка, Big O",
                 "practice": "LeetCode Easy", "check": "Объяснить Big O 3 алгоритмов"},
            ],
        },
        {
            "name": "Фаза 4: System Design",
            "weeks": [
                {"num": 14, "topic": "Нагрузочное тестирование: k6/Gatling, rate limiting",
                 "practice": "k6 скрипт", "check": "Написать k6 скрипт"},
                {"num": 15, "topic": "CI-стратегия: @StressTest, изолированные стенды",
                 "practice": "CI-конфиг", "check": "Описать стенд на 1000 RPS"},
            ],
        },
        {
            "name": "Фаза 5: Mock-сессии",
            "weeks": [
                {"num": 16, "topic": "Mock-сессия #1 (полный собес 1 час)",
                 "practice": "Собес", "check": "Оценка ≥ 3.0"},
                {"num": 17, "topic": "Разбор ошибок + Mock-сессия #2",
                 "practice": "Собес", "check": "Оценка ≥ 3.0"},
                {"num": 18, "topic": "Финальная Mock-сессия",
                 "practice": "Собес", "check": "Оценка ≥ 3.5"},
            ],
        },
    ],
}


def find_week(num):
    """Find phase and week info by week number."""
    for phase in CURRICULUM["phases"]:
        for w in phase["weeks"]:
            if w["num"] == num:
                return phase["name"], w
    return None, None


# ── Memory ──────────────────────────────────────────────────────────

def load_memory():
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "current_week": 0,
        "started_at": None,
        "last_session": None,
        "sessions": 0,
        "streak": 0,
        "completed_weeks": [],
        "mistakes": [],
        "strong_topics": [],
        "notes": [],
    }


def save_memory(mem):
    MEMORY_FILE.write_text(json.dumps(mem, indent=2, ensure_ascii=False))


# ── DeepSeek ────────────────────────────────────────────────────────

def load_deepseek_key():
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("DEEPSEEK_API_KEY", "")


def call_deepseek(system, user, temp=0.7, max_tokens=2048):
    key = load_deepseek_key()
    if not key:
        return "ERROR: No DeepSeek API key. Create .env with DEEPSEEK_API_KEY=..."

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


# ── System Prompt ───────────────────────────────────────────────────

def build_system_prompt(memory):
    week_num = memory.get("current_week", 0)
    streak = memory.get("streak", 0)
    mistakes = memory.get("mistakes", [])

    lines = []
    lines.append("Ты — Java Coach, персональный AI-тьютор по Java.")
    lines.append("")
    lines.append("## Твой стиль")
    lines.append("- Эксперт по Java Core, Collections, Multithreading, Testing")
    lines.append("- Знаешь как люди отлынивают — мягко возвращаешь к учёбе")
    lines.append("- Хвалишь за усилие, а не только за результат")
    lines.append("- Шутишь, будь живым, не будь роботом")
    lines.append("- Отвечаешь на русском, термины — английскими")
    lines.append("- Объясняешь сложное простыми словами")
    lines.append("")
    lines.append("## Принципы")
    lines.append("- 2 часа в день, макс 3. Воскресенье — выходной")
    lines.append("- Практика каждый день: CodingBat / LeetCode")
    lines.append("- Если не идёт — предложи другой подход")
    lines.append("- После объяснения дай мини-задачу")
    lines.append("- Ошибки разбирай, не стыди")
    lines.append("")

    if week_num == 0:
        lines.append("Эдди ещё не начал. Предложи стартовать.")
        lines.append("Спроси: 'Готов начать с Недели 1?'")
    else:
        phase_name, week_info = find_week(week_num)
        if phase_name:
            lines.append(f"## Текущий прогресс")
            lines.append(f"Неделя {week_num} · {phase_name}")
            lines.append(f"Тема: {week_info['topic']}")
            lines.append(f"Практика: {week_info['practice']}")
            lines.append(f"Цель: {week_info['check']}")
            lines.append(f"Streak: {streak} дней")
        completed = memory.get("completed_weeks", [])
        if completed:
            lines.append(f"Пройдено недель: {len(completed)}")

    if mistakes:
        lines.append("")
        lines.append("Слабые места (возвращайся к ним):")
        for m in mistakes[-5:]:
            lines.append(f"- {m['topic']}: {m['detail']}")

    lines.append("")
    lines.append("## Режимы")
    lines.append("- Вопрос по Java → объясни с примерами кода")
    lines.append("- 'дай задачу' → задача на текущую тему")
    lines.append("- 'проверь код' → проанализируй, найди ошибки")
    lines.append("- 'зачёт', 'собес' → проведи мини-собес")
    lines.append("- 'давай дальше' → отметь неделю, переходи к следующей")
    lines.append("- 'статус' → покажи прогресс")
    lines.append("")
    lines.append("## Формат ответа")
    lines.append("Коротко и по делу. Закончи вопросом или действием.")
    return "\n".join(lines)


# ── Commands ────────────────────────────────────────────────────────

def cmd_status(memory):
    week = memory.get("current_week", 0)
    streak = memory.get("streak", 0)
    completed = memory.get("completed_weeks", [])
    sessions = memory.get("sessions", 0)

    if week == 0:
        return (
            "📚 *Java Coach*\n\n"
            "Программа 18 недель для AQA Interview Survival.\n"
            "Ещё не начал. Напиши «поехали» — и стартуем!"
        )

    phase_name, week_info = find_week(week)
    lines = [f"📚 *Java Coach* — активная неделя #{week}"]
    if phase_name:
        lines.append(f"📖 {phase_name}")
        lines.append(f"🎯 {week_info['topic']}")
        lines.append(f"⚡ {week_info['practice']}")
    lines.append(f"🔥 Streak: {streak} дней · Сессий: {sessions}")
    if completed:
        lines.append(f"✅ Пройдено недель: {len(completed)}")
    if memory.get("mistakes"):
        lines.append(f"📝 Слабых мест: {len(memory['mistakes'])}")
    return "\n".join(lines)


def cmd_start(memory):
    memory["current_week"] = 1
    memory["started_at"] = datetime.now().isoformat()
    memory["streak"] = 1
    memory["sessions"] = memory.get("sessions", 0) + 1
    memory["last_session"] = datetime.now().isoformat()
    save_memory(memory)
    return (
        "🚀 *Поехали! Неделя 1*\n\n"
        "📖 Типы, переменные, операторы, массивы, циклы\n\n"
        "Формат:\n"
        "— «расскажи про типы» — теория\n"
        "— «дай задачу» — практика\n"
        "— «как учить» — план действий\n\n"
        "С чего начнём?"
    )


def cmd_advance(memory):
    week = memory.get("current_week", 0)
    if week == 0:
        return "Ты ещё не начал. Напиши «поехали»."

    if week >= 18:
        return "🎉 Вся программа пройдена! Можно повторять слабые места."

    completed = memory.setdefault("completed_weeks", [])
    if week not in completed:
        completed.append(week)

    memory["current_week"] = week + 1
    memory["last_session"] = datetime.now().isoformat()
    save_memory(memory)

    phase_name, week_info = find_week(week + 1)
    return (
        f"✅ *Неделя {week} пройдена!*\n\n"
        f"➡️ *Неделя {week + 1}*"
        + (f" ({phase_name})" if phase_name else "")
        + f"\n🎯 {week_info['topic'] if week_info else ''}\n\n"
        "Готов продолжать?"
    )


def cmd_daily(memory):
    week = memory.get("current_week", 0)
    streak = memory.get("streak", 0)

    if week == 0:
        return (
            "☀️ *Java Coach: доброе утро!*\n\n"
            "18 недель до AQA собеса. Программа ждёт.\n"
            "Напиши «поехали» и начинаем."
        )

    _, week_info = find_week(week)
    topic = week_info["topic"] if week_info else ""

    if streak > 0:
        return (
            f"☀️ *Java Coach: доброе утро!*\n"
            f"🔥 Streak: {streak} дней\n\n"
            f"📖 Неделя {week}: {topic}\n"
            f"⚡ Практика: {week_info['practice'] if week_info else ''}\n\n"
            "2 часа — и ты на шаг ближе к цели. Напиши «готов»!"
        )
    return (
        f"☀️ *Java Coach: доброе утро!*\n\n"
        f"📖 Неделя {week}: {topic}\n\n"
        "Давай сегодня позанимаемся? Напиши «готов»."
    )


# ── Main Logic ──────────────────────────────────────────────────────

def process_message(user_msg, memory):
    msg_lower = user_msg.strip().lower()

    # Command shortcuts
    if msg_lower in ("статус", "status", "прогресс"):
        return cmd_status(memory)

    if msg_lower in ("поехали", "старт", "го", "start", "давай начнём", "давай начнем"):
        return cmd_start(memory)

    if msg_lower in ("дальше", "давай дальше", "готов к следующей",
                     "неделя пройдена", "я всё", "вперёд", "вперед"):
        return cmd_advance(memory)

    # Track session
    memory["sessions"] = memory.get("sessions", 0) + 1
    memory["last_session"] = datetime.now().isoformat()
    if datetime.now().weekday() < 6:  # not Sunday
        memory["streak"] = memory.get("streak", 0) + 1
    save_memory(memory)

    system = build_system_prompt(memory)
    return call_deepseek(system, user_msg)


# ── Telegram Push ───────────────────────────────────────────────────

def push_to_telegram(text):
    """Write to telegram outgoing queue (reuses blog-analysis infrastructure)."""
    bsa_dir = BASE.parent / "blog-analysis" / "agents" / "bsa"
    outgoing = bsa_dir / "outgoing"
    if not outgoing.exists():
        outgoing = Path("/root/blog-analysis/agents/bsa/outgoing")
    if not outgoing.exists():
        return False

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
    (outgoing / f"java_coach_{ts}.json").write_text(json.dumps({
        "text": text,
        "created_at": datetime.now().isoformat(),
        "retries": 0,
        "failed": False,
    }, ensure_ascii=False))
    return True


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    memory = load_memory()

    if "--daily" in args:
        msg = cmd_daily(memory)
        print(msg)
        return

    if "--push-daily" in args:
        msg = cmd_daily(memory)
        push_to_telegram(msg)
        print(msg)
        return

    if "--status" in args:
        print(cmd_status(memory))
        return

    if "--chat" in args:
        print("🤖 Java Coach. Commands: статус, дальше, exit")
        print()
        while True:
            try:
                user = input("> ").strip()
                if user.lower() in ("exit", "quit", "выход"):
                    break
                if not user:
                    continue
                response = process_message(user, memory)
                print(f"\n{response}\n")
            except (KeyboardInterrupt, EOFError):
                break
        return

    # Single message from arg or stdin
    if args:
        msg = " ".join(args)
        print(process_message(msg, memory))
        return

    if not sys.stdin.isatty():
        msg = sys.stdin.read().strip()
        if msg:
            print(process_message(msg, memory))
            return

    print(cmd_status(memory))


if __name__ == "__main__":
    main()
