# Java Coach — AI Context

Полная документация для будущих AI-агентов. Всё что нужно чтобы продолжить разработку.

## Репозиторий

```
github.com/overgoer/java-tutor
```

## Архитектура

Сервер: `217.144.185.210` (root, Amsterdam)
Все процессы под pm2. Код на Python 3. DeepSeek API. Telegram Bot API.

## Схема данных (Message Flow)

```
Telegram (пользователь)
   │  sendMessage(message)
   ▼
bot.py (pm2: java-coach)
   │  subprocess.run(["python3", "coach.py", message])
   ▼
coach.py
   │  читает memory.json (прогресс, conversation, stuck_points)
   │  вызывает DeepSeek API (urllib)
   │  сохраняет memory.json (обновляет conversation, stuck_points)
   │  print(response)
   ▼
bot.py
   │  sendMessage(chat_id, response)
   ▼
Telegram (пользователь)
```

Ночной флоу:
```
cron 0 3 * * *
   │  researcher.py --send
   │  ├── extractor.get_chapter_text(week_num)  → horstmann.txt
   │  ├── adapt_book_excerpt()                  → DeepSeek
   │  ├── research_articles()                   → DeepSeek
   │  └── send_telegram()                       → Telegram API
```

## Файлы

### `coach.py` — ядро агента

Точка входа. Принимает вопрос через аргумент или stdin, отвечает.

Режимы:
- `coach.py "вопрос"` — разовый ответ
- `coach.py --chat` — интерактивный цикл
- `coach.py --daily` — утренняя мотивация (для cron)
- `coach.py --push-daily` — daily + отправить в Telegram
- `coach.py --status` — прогресс

Основные функции:
- `process_message(user_msg, memory)` — маршрутизация команд / вопросов
- `build_system_prompt(memory)` — сборка промпта: статус + conversation + stuck_points
- `cmd_quiz(memory)` — мини-собес (приоритет: stuck_points → текущая неделя)
- `cmd_status(memory)` — прогресс
- `cmd_start(memory)` — инициализация недели 1
- `cmd_advance(memory)` — переход к следующей неделе
- `cmd_daily(memory)` — утреннее напоминание

### `bot.py` — Telegram Bot (pm2: java-coach)

Long-polling бот. Читает `TG_BOT_TOKEN` из `.env`.

Особенности:
- Регистрирует chat_id в `known_chats.json` на любое входящее сообщение
- Вызывает `coach.py` через subprocess
- Делит длинные ответы по 4096 символов
- Polling интервал: 10 секунд

### `researcher.py` — Ночной дайджест

Запуск: `cron 0 3 * * *` — генерирует утренний дайджест.

Что делает:
1. Читает memory.json → узнаёт текущую неделю
2. Вызывает `extractor.extract(week_num)` → текст из книги (Хорстманн)
3. DeepSeek адаптирует: суть + код + собеседование + docs
4. DeepSeek ищет 3 статьи: 2 практических + 1 теория/собесы
5. Собирает сообщение, шлёт в Telegram всем known_chats

### `extractor.py` — Извлечение глав из книг

Содержит `CHAPTER_MAP` — привязку недель к главам книг.

Источники:
- `/root/java-tutor/books/horstmann.txt` — Core Java, том 1 (Хорстманн, 11-е изд., рус.)
- `/root/java-tutor/books/bloch.txt` — Effective Java (Блох, рус.)
- metanit.com — HTML fallback

Функции:
- `get_chapter_text(week_num)` — ищет "Глава N." в txt, выкусывает ~3000 символов
- `fetch_web(source, week_num)` — парсит HTML metanit (crude regex)
- `extract(week_num, topic)` — main entry: книга → metanit → None

## Memory Schema (`memory.json`)

```json
{
  "current_week": 0,           // 0 = не начал, 1-18 = неделя
  "started_at": null,          // ISO date
  "last_session": null,        // ISO date
  "sessions": 0,               // всего сессий
  "streak": 0,                 // дней подряд
  "completed_weeks": [],       // номера пройденных недель
  "conversation": [            // последние 10 реплик
    {"user": "...", "coach": "...", "stuck": false}
  ],
  "stuck_points": [            // темы, вызывавшие вопросы
    "что такое final?",
    "разница между == и equals()"
  ],
  "strong_topics": [],
  "notes": []
}
```

## Curriculum (18 недель)

Хранится в `coach.py` (CURRICULUM dict) и дублирован в `researcher.py` / `extractor.py`.

```
Фаза 0: Фундамент        (нед. 1-4)  — синтаксис, String, ООП, наследование
Фаза 1: Core для собеса  (нед. 5-8)  — Collections, многопоточность, Streams
Фаза 2: Инструменты      (нед. 9-11) — Awaitility, RestAssured, JUnit/Mockito
Фаза 3: Алгоритмы лайт   (нед. 12-13) — Two Sum, стек/очередь, Big O
Фаза 4: System Design    (нед. 14-15) — k6, CI-стратегия
Фаза 5: Mock-сессии      (нед. 16-18) — полные собесы
```

## Chapter Mapping (extractor.py)

| Неделя | Книга | Глава |
|--------|-------|-------|
| 1 | Хорстманн | 3 — Основные языковые конструкции |
| 2 | Хорстманн | 3 (String) |
| 3 | Хорстманн | 4 — Объекты и классы |
| 4 | Хорстманн | 5 — Наследование + 6 — Интерфейсы |
| 5 | Хорстманн | 7 — Исключения + 8 — Generics + 9 — Коллекции |
| 6 | Хорстманн | 12 — Параллелизм |
| 7 | Хорстманн | 12 (Concurrent) |
| 8 | Хорстманн | 6 (лямбды) |
| 9+ | metanit / статьи | (не замаплено) |

## Команды пользователя

Через Telegram-бот (`@razesdazbot`):

| Команда | Действие |
|---------|----------|
| любой вопрос по Java | объяснение с кодом |
| `поехали` | начать программу (нед. 1) |
| `дальше` | отметить неделю, перейти к следующей |
| `статус` | текущий прогресс |
| `дай задачу` | задача на текущую тему |
| `опрос` / `зачёт` / `собес` | мини-интервью (по stuck_points) |
| `/new` или `вв <вопрос>` | новый тред + ответ |
| `проверь код` | анализ Java-кода (пока не реализовано) |

## Cron (на сервере)

```
2  9 * * *  coach.py --push-daily     → утренняя мотивация
0  3 * * *  researcher.py --send      → ночной дайджест
```

## PM2 процессы

```
java-coach  → /root/java-tutor/bot.py        (бот)
tg-bizzy    → /root/blog-analysis/agents/bsa/telegram_bot.py  (Bizzy)
```

## Зависимости

Только стандартная библиотека Python 3 (urllib, json, subprocess, re, Path).
DeepSeek API — единственный внешний вызов.
PyMuPDF не нужен — PDF сконвертированы в текст через pdftotext локально и загружены на сервер.

## Книги на сервере

```
/root/java-tutor/books/
├── horstmann.txt    (2.9 MB) — Core Java том 1 (11-е изд., рус.)
└── bloch.txt        (1.6 MB) — Effective Java (3-е изд., рус.)
```

## DeepSeek API

- Модель: `deepseek-chat`
- Ключ: `DEEPSEEK_API_KEY` в `/root/java-tutor/.env`
- DeepSeek v4 Flash используется в coach.py, researcher.py

## Obsidian Vault

```
/root/obsidian-vault/eddytester/
├── Java/                        ← curriculum (перенесено из _Архив)
│   ├── 00_Фундамент/
│   ├── 01_Core_Для_Собеса/
│   ├── 02_Инструменты/
│   ├── 03_Алгоритмы_Лайт/
│   ├── 04_System_Design/
│   ├── 05_Mock_Сессии/
│   ├── README.md
│   ├── Бэклог задач.md
│   ├── Прогресс.md
│   └── Ресерч_собесы_AQA_Java_2026.md
└── _Архив/Java/Archived Java/    ← старая программа (Qwen, не трогать)
```

## Важные паттерны

1. Всегда используй `subprocess.run` для вызова coach.py — не импортируй напрямую
2. Memory.json — единственный источник правды по прогрессу
3. Изменения в curriculum → синхронизируй в coach.py, researcher.py И extractor.py
4. Новый тред для бота = очистка `conversation[]` в memory.json
5. Токен в `.env`, НЕ в memory.json, НЕ в коде
