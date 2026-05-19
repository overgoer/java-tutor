# Java Coach

Персональный AI-тьютор по Java (AQA Interview Survival, 18 недель).

Telegram-бот, который ведёт по программе, напоминает, мотивирует, проверяет код.

## Быстрый старт

```bash
cp .env.example .env
# вставить DEEPSEEK_API_KEY

python3 coach.py --chat              # интерактивный режим
python3 coach.py "что такое final?"  # разовый вопрос
python3 coach.py --status            # текущий прогресс
python3 coach.py --daily             # утренняя мотивация
```

## Установка на сервер

```bash
git clone https://github.com/overgoer/java-tutor.git /root/java-tutor
cd /root/java-tutor
cp .env.example .env
# вставить ключи

# cron: ежедневное напоминание в 9 утра
echo "0 9 * * * cd /root/java-tutor && python3 coach.py --daily | python3 -c 'import sys; sys.path.insert(0,\"/root/blog-analysis/agents/bsa\"); from telegram_bot import push_message; push_message(sys.stdin.read())'" | crontab -
```

## Программа

18 недель, 6 фаз:

| Фаза | Недели | Тема |
|------|--------|------|
| 0 Фундамент | 1-4 | Синтаксис, String, ООП, наследование |
| 1 Core для собеса | 5-8 | Collections, многопоточность, Streams |
| 2 Инструменты | 9-11 | Awaitility, RestAssured, JUnit/Mockito |
| 3 Алгоритмы лайт | 12-13 | Two Sum, стек/очередь, Big O |
| 4 System Design | 14-15 | Нагрузка, CI-стратегия |
| 5 Mock-сессии | 16-18 | Полные собесы |
