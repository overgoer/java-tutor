#!/usr/bin/env python3
"""
Extractor — достаёт главы из книг (PDF→text) и сайтов (HTML) для Java Coach.

Источники:
  /root/java-tutor/books/horstmann.txt   — Core Java, том 1 (Хорстманн)
  /root/java-tutor/books/bloch.txt       — Effective Java (Блох)
  metanit.com + javarush.com             — парсинг HTML
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
BOOKS_DIR = BASE / "books"

# ── Mapping: week → source + chapter ──────────────────────────────

CHAPTER_MAP = {
    1:  {"file": "horstmann", "search": "Глава 3. Основные языковые конструкции Java"},
    2:  {"file": "horstmann", "search": "Глава 3. Основные языковые конструкции Java",
         "focus": "String,StringBuilder"},
    3:  {"file": "horstmann", "search": "Глава 4. Объекты и классы"},
    4:  {"file": "horstmann", "search": "Глава 5. Наследование",
         "extra": "Глава 6. Интерфейсы, лямбда-выражения"},
    5:  {"file": "horstmann", "search": "Глава 7. Исключения, утверждения и протоколирование",
         "extra": "Глава 8. Обобщенное программирование,Глава 9. Коллекции"},
    6:  {"file": "horstmann", "search": "Глава 12. Параллелизм"},
    7:  {"file": "horstmann", "search": "Глава 12. Параллелизм",
         "focus": "Concurrent"},
    8:  {"file": "horstmann", "search": "Глава 6. Интерфейсы, лямбда-выражения и внутренние классы",
         "focus": "лямбда"},
    # Weeks 9+ haven't mapped chapters yet, will fall back to web
}

WEB_MAP = {
    "metanit": {
        "1":  "https://metanit.com/java/tutorial/2.1.php",   # variables
        "2":  "https://metanit.com/java/tutorial/7.3.php",   # String
        "3":  "https://metanit.com/java/tutorial/3.1.php",   # classes
        "4":  "https://metanit.com/java/tutorial/3.2.php",   # inheritance
        "11": "https://metanit.com/java/tutorial/9.1.php",   # JUnit
    },
}


def get_chapter_text(week_num):
    """Extract chapter text from book for the given week."""
    info = CHAPTER_MAP.get(week_num)
    if not info:
        return None

    source_file = BOOKS_DIR / f"{info['file']}.txt"
    if not source_file.exists():
        return None

    text = source_file.read_text(encoding="utf-8")
    search = info["search"]

    # Find chapter start
    idx = text.find(search)
    if idx == -1:
        # Try shorter match
        short = search.split(" —")[0].split(". ")[0]
        idx = text.find(short)
        if idx == -1:
            return None

    # Find next chapter (next "Глава X." or end)
    rest = text[idx:]
    next_chapter = re.search(r"\nГлава \d+\.", rest[2000:])
    end = (idx + 2000 + next_chapter.start()) if next_chapter else idx + 3000

    # Extract raw text
    raw = text[idx:end].strip()

    # Optional focus: trim to relevant section
    focus = info.get("focus", "")
    if focus:
        fi = raw.find(focus)
        if fi > 0:
            # Take 500 chars before focus + 1500 chars after
            start = max(0, fi - 500)
            raw = raw[start:fi + 2000]

    return raw[:3000]


def fetch_web(source, week_num):
    """Fetch article from metanit or javarush."""
    week_str = str(week_num)
    urls = WEB_MAP.get(source, {})
    url = urls.get(week_str)
    if not url:
        return None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        # Crude text extraction: strip tags
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        # Find main content
        for marker in ["article", "content", "main", "text"]:
            idx = text.lower().find(marker)
            if idx > 0:
                text = text[idx:idx + 4000]
                break
        return text[:3000]
    except Exception as e:
        return None


def extract(week_num, topic):
    """Main: get text from best source for this week."""
    # Try book first
    book_text = get_chapter_text(week_num)
    if book_text:
        return {"source": "horstmann", "text": book_text}

    # Fallback to metanit
    web_text = fetch_web("metanit", week_num)
    if web_text:
        return {"source": "metanit", "text": web_text}

    return None


if __name__ == "__main__":
    # Test: extract week 1
    for w in [1, 2, 3, 4, 5, 6, 7, 8]:
        res = extract(w, "")
        if res:
            print(f"\n=== Week {w} ({res['source']}) ===")
            print(res['text'][:300])
            print("...")
        else:
            print(f"\n=== Week {w} → no source ===")
