# Sci-Bot: REST API endpoints

Альтернативный (REST) способ работы со Sci-Bot (sci-bot.ru). Основной путь — WebSocket-клиент (`scripts/sci_bot_client.py`), этот референс для диагностики и Obsidian-интеграции.

**Credentials:** логин `CherenkovYaVl`, cookie-based аутентификация.

## 1. Логин

```bash
curl -s --max-time 15 -c /tmp/scibot_cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"username":"ЛОГИН","password":"ПАРОЛЬ"}' \
  "https://sci-bot.ru/api/login"
```

Успешный ответ: `{"ok":true,"username":"..."}`. Cookie `scibot_auth` сохраняется в файл.

## 2. API endpoints

| Endpoint | Описание |
|---|---|
| `GET /api/balance` | Баланс токенов (клиент WebSocket использует для floor-проверки) |
| `GET /api/question-status?handle=ХЭШ` | Статус вопроса + текст вопроса |
| `GET /api/conversations` | Список всех диалогов пользователя |
| `GET /api/my-active` | Активные вопросы (generating/answered) |
| `GET /api/recent-answers` | Последние публичные ответы |

## 3. Извлечение ответа из SPA-страницы

1. Загрузить HTML страницы (с кукой авторизации)
2. Найти подстроку `renderSharedPage("`
3. Извлечь текст между кавычками до `", true/false` (разделитель параметров)
4. Распарсить JSON-escaped строку: `\\n` → `\n`, `\\"` → `"`, `\\t` → `\t`, `\\/` → `/`

```bash
curl -s -b /tmp/scibot_cookies.txt "https://sci-bot.ru/ХЭШ-вопроса" > /tmp/scibot_page.html
python scripts/extract-answer.py /tmp/scibot_page.html --out /tmp/scibot_answer.md
```

**Pitfall:** после разэкранирования убрать лишние бэкслеши: `re.sub(r'\\([^nrt"\\/])', r'\1', raw)`.

## 4. Obsidian-заметка с DOI-ссылками

1. Извлечь все DOI из секции References (формат: `DOI: 10.xxxx/yyyy`)
2. Создать словарь `номер → DOI`
3. Заменить inline `[N]` на `[N](https://doi.org/DOI)` в теле обзора
4. В References заменить `DOI: ...` на markdown-ссылку `[Title](https://doi.org/DOI)`

## 5. Pitfalls

- Cookie `scibot_auth` живёт 30 дней (Max-Age=2592000). После первого логина можно использовать сохранённую cookie без повторного логина.
- URL диалога вида `https://sci-bot.ru/ХЭШ-вопроса`. Хэш используется как `handle` в API.
- В HTML ответа все управляющие символы JSON-escaped.