# Trust-boundary guard для сессий opencode

Детектор prompt injection, который сканирует SQLite-сессии opencode (`opencode.db`) перед resume/analyze и блокирует оркестратор от выполнения инструкций, спрятанных во внешнем контенте (webfetch, subagent output, browser). Двухслойный: P0 — детерминированный сигнатурный слой (stdlib, без зависимостей), P2 — семантический классификатор (cloud gemma-26b / fallback / local) как tie-breaker для того, что P0 пропустил.

---

## Состояние проекта

Guard создан через фабрику кода с итеративным adversarial testing. Это **частичная защита**, не полное решение. Бypass-rate измерен на 18 синтетических техниках обхода:

| Слой | Bypass-rate | Замечание |
|------|-------------|-----------|
| Baseline (без guard) | 72% | 13/18 техник проходят |
| Post-P0 (сигнатуры) | 50% | 9/18 проходят; 7 закрыты |
| Post-P2 cloud (gemma-4-26b) | ~10% | 9/10 accuracy на attack set |
| Post-P2 local (qwen2.5:0.5b) | 50% | 0.5b слишком слаб для синонимов/indirect |

Из 17 идентифицированных угроз: **7 закрыты** (P0+P2), **3 частично** mitigированы, **7 непреодолимы** текущим подходом (требуют P1-b taint tracker / bigger model / behavioral layer). Подробности — [THREAT_MODEL.md](THREAT_MODEL.md).

Guard готов для single-user dev environment. Для multi-user/production semantic-слой остаётся открытым (semantic paraphrase, realism 1.0).

---

## Быстрый старт

Три команды для первичной проверки. Подразумевается, что `guard_config.json` уже создан из example (см. [INSTALL.md](INSTALL.md)).

```bash
# 1. Показать провайдеров, модели, цены из конфига (без сканирования)
python3 src/semantic_layer.py --list-models
```
```
cloud: model=google/gemma-4-26b-a4b-it
    base_url=https://polza.ai/api/v1/chat/completions
    api_key=set max_tokens=20 cost_per_call=0.001 руб
local: model=qwen2.5:0.5b
    base_url=http://127.0.0.1:11434/api/generate
    api_key=null max_tokens=50 cost_per_call=null руб
fallback: model=sao10k/l3-lunaris-8b
    base_url=https://polza.ai/api/v1/chat/completions
    api_key=set max_tokens=20 cost_per_call=null руб
budget: max=5.0 warn=4.0 alarm=4.8
```

```bash
# 2. Прогнать синтетическую атаку (должна дать FAIL — инъекция поймана)
python3 src/semantic_layer.py tests/synth.db --json
```
Ожидаемый exit code: `1` (FAIL), `verdict: FAIL`, `stats.p0_high >= 1`.

```bash
# 3. Просканировать реальную БД opencode
python3 src/semantic_layer.py ~/.local/share/opencode/opencode.db --json --limit 50
```
Вывод: `verdict`, `budget`, `alarm` (если сработал), `findings` с provenance/url/excerpt.

Exit codes: `0` = PASS, `1` = FAIL (найдена инъекция), `2` = ERROR (БД/конфиг). Полная схема — [API.md](API.md).

---

## Архитектура

Guard работает как pipeline: каждый part из таблицы `part` проходит provenance-классификацию, затем P0, затем (при no-match) P2.

```
                     opencode.db, table `part`
                              │
                              ▼
              ┌─────────────────────────────────┐
              │  Provenance classification      │
              │  (text=trusted | tool=…)        │
              └────────────┬────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
     trusted           untrusted           internal
     (text part)   (webfetch, task,     (bash, read,
      → skip         browser, research)    edit, glob)
                           │                  │
                           ▼                  ▼
              ┌─────────────────────┐  ┌──────────────────┐
              │  P0 signatures      │  │  P0 signatures   │
              │  STRONG_EN/WEAK_RU  │  │  STRONG_EN only  │
              │  NFKC + zerowidth   │  │  (WEAK_RU skip)  │
              │  + casefold         │  │                  │
              └─────────┬───────────┘  └────────┬─────────┘
                        │                       │
                  high? │─── yes ──► FAIL       │ high? ── yes ──► FAIL
                        │ no-match/low          │ no-match/low
                        ▼                       ▼
              ┌─────────────────────┐         PASS
              │  P2 classifier      │      (internal не
              │  (untrusted only)   │       идёт в P2
              │  cloud gemma-26b    │       by design)
              │  → fallback lunaris │
              │  → local qwen 0.5b  │
              │  → ALARM            │
              └─────────┬───────────┘
                        │
              YES ──► FAIL  (semantic injection)
              NO  ──► PASS
              None/timeout ──► FAIL (fail-closed)
```

Полное описание слоёв, ClassifierChain, budget control, trust boundary — [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Документация

| Файл | Назначение |
|------|------------|
| [INSTALL.md](INSTALL.md) | Установка, требования, настройка ключей, troubleshooting |
| [ARCHITECTURE.md](ARCHITECTURE.md) | P0/P2 слои, ClassifierChain, бюджет, data flow, trust boundary |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Kill chain, 17 угроз, 7 insurmountable, defense-in-depth, acceptable level |
| [ADVERSARIAL.md](ADVERSARIAL.md) | Методология bubble-test, 18 техник, regression gate, как добавить технику |
| [API.md](API.md) | CLI reference, JSON schema, exit codes, guard_config.json schema, ALARM schema |

---

## Структура репозитория

```
doc_guard/
├── docs/                      # эта документация
├── src/
│   ├── session_guard.py       # P0: детерминированный сигнатурный слой
│   ├── semantic_layer.py      # P2: гибрид P0 + cloud/local классификатор
│   └── adversarial_build.py   # генератор синтетических attack DB
├── configs/
│   ├── guard_config.json.example  # шаблон конфига (ключи REDACTED)
│   └── .gitignore                 # guard_config.json, *.db, __pycache__
├── tests/
│   ├── test_session_guard.py  # формальные тесты P0 (7 кейсов)
│   └── *.db                   # 18 синтетических БД (t1-t14 + benign)
└── threat-model/
    ├── threat_tracker.json    # 17 угроз: closed/partial/insurmountable
    └── adversarial_report.json# результаты bubble-test
```

---

## Честная оценка

Guard не претендует на полную защиту. Каждое утверждение фальсифицируемо: adversarial DB в `tests/` можно прогнать и проверить bypass-rate локально. Главные ограничения:

- **Semantic paraphrase** (realism 1.0) — перефразированные инструкции вне списка сигнатур. P0 не понимает intent, qwen 0.5b промахивается на синонимах ("forget prior", "act as"). Cloud gemma-26b ловит 9/10, но требует API-ключ и бюджет.
- **Taint loss** (realism 0.9) — webfetch → bash(write) → read теряет provenance untrusted → internal. internal пропускает WEAK_RU и не идёт в P2. Нужен P1-b content-hashing taint tracker.
- **Internal channel blind spot** — P2 вызывается только для untrusted по контракту. bash/read output со слабой RU-инъекцией остаётся PASS.
- **Self-pollution DoS** (realism 1.0) — атакующий plant'ит сигнатуры guard в README → false-positive flood → operator disable guard.

Следующие шаги для закрытия 5/7 insurmountable: prompt engineering (low cost), P1-b taint tracker (medium). Полный план — в [THREAT_MODEL.md](THREAT_MODEL.md), секция "Acceptable security level".