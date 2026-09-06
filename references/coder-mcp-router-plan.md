# MCP-серверы вызова кодера (архитектура) — план

## Идея (2026-08-21, Ярослав)
Создать MCP-серверы, через которые оркестратор (Hermes) вызывает кодера (opencode) с предзаданными настройками.
**Кластер на каждый случай** + **отдельный MCP для оркестратора**. Один на free-модель, другой на polza, третий появится (antigravity).

## Зачем
- Единая точка вызова кодера с правильной моделью (не вручную выбирать)
- Кластеры под классы задач (маршрутизация — из нашего reflection-gate / инструментального маршрутизатора)
- Переключение free/polza без правки конфига каждый раз

## Схема
```
[Hermes-оркестратор]
   │  вызывает MCP
   ▼
┌───────── MCP-сервер: coder-router ─────────┐
│  маршрут по настройке:                     │
│  coder_free  → opencode --model hy3-free    │
│  coder_polza → opencode --model polza/dsv4  │
│  coder_anti  → opencode --model antigravity (третий, вскоре) │
└────────────────────────────────────────────┘
   │ запускает opencode run (one-shot, не TUI — не виснет)
   ▼
[opencode run ... --model <X>] → артефакты
```

## Кластеры (по классам задач, из reflection-gate)
| Кластер | free | polza | antigravity |
|---|---|---|---|
| Быстрые микрозадачи/поиск-парсинг | hy3-free ✅ | — | — |
| Глубокий кодинг/рефактор | — | deepseek-v4-flash-0731 ✅ | — |
| Топ-модели (Claude Opus/Gemini 3) | — | — | antigravity (вскоре) |
| LLM-свидетельство (судья/верификатор) | hy3-free | deepseek | qwen |

## MCP-сервер: интерфейс
```
tools:
  coder_run(task, model_class="free"|"polza"|"antigravity", workdir, files[]) -> {stdout, artifacts}
  coder_models()  -> список доступных моделей по провайдерам
  coder_status()  -> баланс/лимиты (free rate-limit, polza остаток)
```
Настройки в конфиге MCP (не в промпте): путь к opencode, модели по классам, бюджеты.

## Что уже проверено
- **hy3-free**: стабильный кодер (пишет код, запускает python) ✅
- **x-preview-f-free**: нестабилен (иногда виснет)
- **polza/deepseek-v4-flash-0731**: работает, но 23₽
- **opencode free**: deepseek-free СНЯТ (в конфиге ещё стоит → падает, надо заменить на hy3-free)

## Следующие шаги (когда бюджет/кодер)
1. Заменить дефолт opencode на hy3-free (сейчас битая deepseek-free).
2. Создать MCP `coder-router` (free + polza) с интерфейсом выше.
3. Подключить к Hermes config.yaml (mcp_servers).
4. antigravity — третий, когда будет доступ (изучить noefabris/opencode-antigravity-auth).

## Плагины opencode (из composio), которые усилить кластер
- opencode-mem (память сессий) — полезно
- Context7 (актуальные доки) — полезно
- Composio MCP (GitHub/Linear/Slack) — интеграции
- Envsitter Guard (защита чувствит.) — trust boundary
