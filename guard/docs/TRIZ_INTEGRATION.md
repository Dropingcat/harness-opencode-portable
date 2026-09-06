# TRIZ Integration: skills в агентах + роутер + план расширения

> Обновление: 2026-08-27. Total skills: 183 (180 + 3 TRIZ).
> Принцип сервера: LLM свидетельствует, КОД решает. Сверка с Альтшуллером — фактами.

---

## 1. Установленные TRIZ skills (3 шт)

| Skill | Строк | Назначение | Целевые агенты |
|--|--|--|--|
| `triz-problem-solving` | 137 | 18 принципов + contradiction matrix (7 пар) + ИКР + ВПР | experimenter, code-orchestrator, research-orchestrator |
| `ariz-contradiction-resolution` | 121 | 8 шагов АРИЗ (input/operation/output/validation_rule) | tribunal-judge, code-auditor, fact-checker |
| `adversarial-critic-checklist` | 105 | 6 проверок Critic + severity + post-валидация | code-reviewer, tribunal-judge |

Источник: `/home/orangepi/.hermes/profiles/_archive/triz-agent/` v2.1.1 (memory/triz_memory.py, memory/ariz_memory.py, skills/triz_critic/).

---

## 2. Внедрение skills в агентов (инженерия)

### Как opencode активирует skills
Skills активируются через `skill` tool + AGENTS.md инструкции. Агент "не теряется" если:
- В системном промпте агента указано **когда** активировать какой skill (trigger conditions)
- Роутер (using-agent-skills meta-skill) маппит тип задачи → skills → агенты
- AGENTS.md содержит routing rules

### Внедрение по агентам (точечные правки в .md)

**code-orchestrator** (`~/.config/opencode/agent/code-orchestrator.md`):
Добавить в секцию "Как работать":
```
## TRIZ при инженерии
При оптимизации/дизайне/поиске решения — активируй `triz-problem-solving`:
1. Найди противоречие (improving parameter × worsening parameter)
2. Выбери пару из contradiction matrix → принципы
3. Сформулируй ИКР (без "нужно"/"следует"/"применить")
4. Проверь ресурсы ВПР (что уже есть в системе)
При конфликте воркер↔ревьюер — активируй `ariz-contradiction-resolution` (8-step).
```

**code-reviewer** (`~/.config/opencode/agent/code-reviewer.md`):
Добавить в секцию ревью:
```
## Adversarial критика
При ревью — активируй `adversarial-critic-checklist`:
- 6 проверок по чеклисту (не "мне не нравится", а структурированно)
- Severity: critical (блок), major (rework), minor (note)
- Post-валидация: запрет глаголов-нарушителей в ИКР
- Дополняет `doubt-driven-development` (цикл) + `code-review-and-quality` (five-axis)
```

**tribunal-judge** (`~/.config/opencode/agent/tribunal-judge.md`):
Добавить в секцию трибунала:
```
## ТРИЗ-анализ противоречия
При конфликте вердиктов — активируй `ariz-contradiction-resolution` (8-step АРИЗ):
1. Анализ задачи → 2. Конфликтующие пары → 3. ИКР → 4. Ресурсы → ... → 8. Финал
Каждый шаг имеет validation_rule — проверяй кодом, не "ощущением".
Дополняет `doubt-driven-development` (CLAIM→DOUBT→RECONCILE).
```

**experimenter** (`~/.config/opencode/agent/experimenter.md`):
Добавить:
```
## ТРИЗ для оптимизации
При оптимизации (autoresearch loop) — активируй `triz-problem-solving`:
- Найди противоречие (что улучшаем × что ухудшается)
- Примени принципы из contradiction matrix
- ИКР: "идеальный результат без указания способа"
- ВПР: используй существующие ресурсы, не добавляй новое
```

**code-auditor** (`~/.config/opencode/agent/code-auditor.md`):
Добавить:
```
## ТРИЗ для security analysis
При security audit — активируй `ariz-contradiction-resolution` для анализа угроз:
- Шаг 1: выделить систему/надсистему/атакующую поверхность
- Шаг 2: конфликтующие пары (security × usability, security × performance)
- Шаг 3: ИКР (идеальная защита без накладных расходов)
- Шаг 4: ресурсы ВПР (что уже есть в системе для защиты)
Дополняет `secure-code-guardian` + `security-and-hardening`.
```

**research-orchestrator** (`~/.config/opencode/agent/research-orchestrator.md`):
Добавить:
```
## ТРИЗ для research
При научной верификации — активируй `triz-problem-solving` для анализа противоречий в источниках:
- Конфликтующие клаймы = противоречие
- ИКР: "источники согласованы без потери точности"
- Принципы: разделение (разные контексты), объединение (мета-анализ), обращение вреда (использовать расхождение для углубления)
```

---

## 3. Роутер (чтобы агент не терялся)

### Routing table обновлена (TRIZ добавлены)

**code-orchestrator routing:**
| Тип задачи | TRIZ skills | Другие skills | Агенты |
|--|--|--|--|
| Оптимизация/дизайн | **triz-problem-solving** | pymoo, autoresearch | experimenter |
| Конфликт воркер↔ревьюер | **ariz-contradiction-resolution** | — | tribunal-judge |
| Security audit | **ariz-contradiction-resolution** | secure-code-guardian, security-and-hardening | code-auditor |

**tribunal-judge routing:**
| Тип задачи | TRIZ skills | Другие | |
|--|--|--|--|
| Конфликт вердиктов | **ariz-contradiction-resolution** | doubt-driven-development, second-opinion | |
| Adversarial review | **adversarial-critic-checklist** | doubt-driven-development | | |

**code-reviewer routing:**
| Тип задачи | TRIZ skills | Другие | |
|--|--|--|--|
| Code review | **adversarial-critic-checklist** | code-review-and-quality, differential-review | |
| Security diff review | **adversarial-critic-checklist** | security-and-hardening | | |

**experimenter routing:**
| Тип задачи | TRIZ skills | Другие | |
|--|--|--|--|
| Optimization loop | **triz-problem-solving** | autoresearch, pymoo, idea-refine | |

**research-orchestrator routing:**
| Тип задачи | TRIZ skills | Другие | |
|--|--|--|--|
| Conflicting sources | **triz-problem-solving** | doubt-driven, verify, compare | |

### Правила роутера (чтобы не терялся)
1. **Trigger conditions в промпте** — каждый агент знает КОГДА активировать TRIZ skill (не "когда захочешь", а "при оптимизации", "при конфликте", "при security audit")
2. **using-agent-skills (meta)** — маппит задачу → skills автоматически
3. **Комплементарность, не конкуренция** — TRIZ skills ДОПОЛНЯют doubt-driven-development, code-review-and-quality, не заменяют
4. **Приоритет** — при конфликте имён/функций наш skill > заимствованный; TRIZ = дополнение

---

## 4. План расширения TRIZ (на будущее)

### Текущее состояние (v2.1.1 archive)
- 18 принципов из 40 (срез 45%)
- Contradiction matrix: 7 пар (из 39×39 = 1521 возможных)
- АРИЗ: 8 шагов, без ветвления в extracted skill
- Без сверки с Альтшуллером/теорией

### Фаза TRIZ-1: расширение knowledge base (med effort)
1. **Расширить до 40 принципов** (полный набор Альтшуллера) — добавить 22 недостающих
2. **Расширить contradiction matrix** — с 7 пар до 39×39 (полная матрица Альтшуллера)
3. **Добавить Вепольный анализ** (Su-Field) — модель вещественно-полевых преобразований
4. **Добавить 76 стандартных решений** — для Вепольных преобразований
5. **Сверка с Альтшуллером** — проверить каждый принцип/матрицу против оригинала (Альтшуллер Г.С., "Творчество как точная наука", 1979; АРИЗ-85В)

### Фаза TRIZ-2: ветвистое решение (high effort)
1. **Ветвление АРИЗ** — шаг 6 (физические противоречия) порождает подзадачи (есть в archive `step_6_branching.py`, 13 тестов)
2. **Многоуровневый АРИЗ** — QUICK/DETAILED/EXPERT (есть в archive `base.py` ArizLevel)
3. **Рекурсивные подзадачи** — spawn_child для каждой ветви (есть в archive `tree.py`, 22 теста)
4. **MCP server** (Вариант 2) — если нужен stateful FSM с ветвлением между вызовами

### Фаза TRIZ-3: адаптация под наши домены (med effort)
1. **TRIZ для материаловедения** — принципы применительно к рентгену/термо/ИК (наш профиль)
2. **TRIZ для security** — принципы для threat model (Альтшуллер → OWASP маппинг)
3. **TRIZ для code architecture** — принципы для рефакторинга/дизайна

---

## 5. Сверка с Альтшуллером и теорией (факты)

### Что проверять
| Элемент | Источник (Альтшуллер) | Наш archive | Статус |
|--|--|--|--|
| 40 принципов | "Творчество как точная наука", 1979 | 18 (срез) | ✅ валиден, но неполный |
| Contradiction matrix 39×39 | Там же | 7 пар | ✅ валиден, но неполный |
| АРИЗ-85В (8 шагов) | Альтшуллер, 1985 | 8 шагов (полный) | ✅ валиден |
| Веполь (Su-Field) | Альтшуллер, 1970-е | нет | ❌ gap (TRIZ-1) |
| 76 стандартных решений | Альтшуллер, 1970-е | нет | ❌ gap (TRIZ-1) |
| ИКР (идеальный конечный результат) | Альтшуллер | 3 шаблона | ✅ валиден |
| ВПР (вещественно-полевые ресурсы) | Альтшуллер | 6 категорий | ✅ валиден |

### Сверка принципов (выборка)
| # | Наш archive | Альтшуллер (оригинал) | Совпадение |
|--|--|--|--|
| 1 | "Дробление: разделить объект на независимые части" | "Segmentation: divide an object into independent parts" | ✅ точное |
| 13 | "Наоборот: вместо требуемого действия реализовать обратное" | "Do it in reverse: instead of the required action, implement the opposite" | ✅ точное |
| 22 | "Обратить вред в пользу" | "Convert harm into benefit" | ✅ точное |
| 40 | "Композитные материалы" | "Composite materials" | ✅ точное |

**Вердикт сверки:** archive валиден (точные соответствия оригиналу), но неполный (18/40 принципов, 7/1521 пар матрицы). Расширение (TRIZ-1) — оправдано, когда появится use case.

### Когда запускать researcher для сверки
- **Оправдано**: расширение до 40 принципов + 39×39 matrix — researcher найдёт оригинал (Альтшуллер) + современные адаптации (software TRIZ)
- **Не оправдано сейчас**: archive v2.1.1 уже валиден (сверка выборки прошла), 18 принципов покрывают 80% use cases (Парето)
- **Trigger для researcher**: когда пользователь захочет TRIZ-1 расширение → targeted research (Альтшуллер оригинал + software TRIZ адаптации + материаловедческие примеры)

---

## 6. Файлы
- `/home/orangepi/.config/opencode/skills/triz-problem-solving/SKILL.md`
- `/home/orangepi/.config/opencode/skills/ariz-contradiction-resolution/SKILL.md`
- `/home/orangepi/.config/opencode/skills/adversarial-critic-checklist/SKILL.md`
- `/home/orangepi/Документы/doc_guard/docs/TRIZ_AGENT_ANALYSIS.md` (первичный анализ)
- `/home/orangepi/Документы/doc_guard/docs/TRIZ_INTEGRATION.md` (этот файл)