# Skills Routing Plan: подбор скилов под задачи/клаймы по агентам

> Источник: librarian report (3 репозитория, 68 candidates). Формат: факты + опции, решение за пользователем (принцип сервера: LLM свидетельствует, КОД решает).
> Дата: 2026-08-26

## Контекст

**Существующие агенты (15):** code-orchestrator, coder-worker, code-reviewer, code-tester, code-auditor, experimenter, research-orchestrator, claim-parser, source-fetcher, fact-checker, tribunal-judge, synthesizer, writing-orchestrator, article-writer, researcher.

**Существующие skills (10):** autoresearch, clonedeps, codemap, deepwork, oh-my-opencode-slim, reflect, rivulet-numeric, simplify, verification-planning, worktrees.

**Источники:** Repo1 = zavalishev/awesome-claude-skills (81 skill, markdown+frontmatter), Repo2 = addyosmani/agent-skills (24 SKILL.md, нативная opencode-поддержка), Repo3 = justxor/Aiagentsfullcourse (14 модулей + templates/checklists/anti-patterns).

---

## Маппинг по агентам (рекомендуемые skills для интеграции)

### code-orchestrator (роутер + фабрика)
| Skill | Репо | Назначение | ROI | Заменяет/дополняет |
|--|--|--|--|--|
| `orchestration-patterns` (ref) | R2 | Multi-persona, "personas don't invoke personas" — предотвращает рекурсивную диспетчеризацию | **high** | дополняет — критично для роутера |
| `using-agent-skills` (meta) | R2 | Маппинг входящей задачи на нужный skill-workflow | **high** | дополняет oh-my-opencode-slim |
| `spec-driven-development` | R2 | PRD до кода: objectives/commands/structure | high | дополняет verification-planning |
| `planning-and-task-breakdown` | R2 | Декомпозиция в small verifiable tasks | high | дополняет verification-planning |
| `subagent-driven-development` | R1 | Параллельная работа через субагентов | high | формализует текущий factory-цикл |
| `dispatching-parallel-agents` | R1 | Параллельный запуск | high | формализует |
| `context-engineering` | R2 | Подача нужного контекста в нужный момент | high | закрывает taint loss (threat_tracker) |
| **модуль 12-cost-optimization** | R3 | Бюджеты, роутинг, деградация | high | наш Budget-класс (patch_keys) |
| **модуль 07-multi-agent** | R3 | Роли, супервизор, изоляция контекста, налог на оркестрацию | high | формализует factory |
| `skill-creator`/`writing-skills` | R1 | Создание новых скиллов (meta) | med | для расширения |

### coder-worker
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `incremental-implementation` | R2 | Thin vertical slices: impl→test→verify→commit | high |
| `test-driven-development` | R1/R2 | Red-Green-Refactor | high |
| `debugging-and-error-recovery` | R2 | 5-step triage | high |
| `systematic-debugging` | R1 | 4-фазный поиск причины | high |
| `python-pro`/`modern-python` | R1 | Идиоматичный Python 3.10+ | high (для Python) |
| `feature-forge` | R1 | End-to-end реализация фичи | med |
| `api-and-interface-design` | R2 | Contract-first, Hyrum's Law | med |

### code-reviewer
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `code-review-and-quality` | R2 | Five-axis review, change sizing ~100 lines, severity | high |
| `differential-review` | R1 | Security-focused review diff'ов (не всего файла) | high |
| `make-no-mistakes` | R1 | Максимальная точность перед ответом | high |
| `verification-before-completion` | R1 | Проверка перед "готово" | high |
| `definition-of-done` (ref) | R2 | Standing bar для каждого change | high |
| `second-opinion` | R1 | Альтернативный взгляд | med (дополняет reflect) |
| `the-fool` | R1 | Свежий взгляд, проверка assumptions | med |

### code-tester
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `test-master` | R1 | Стратегия тестирования | high |
| `property-based-testing` | R1 | Генеративное тестирование свойств | high |
| `test-driven-development` | R1/R2 | Red-Green-Refactor | high |
| `testing-patterns` (ref) | R2 | Test structure, mocking, anti-patterns | high |
| `verification-before-completion` | R1 | Проверка перед "готово" | high |
| **модуль 09-evals + benchmarks/** | R3 | Golden set, LLM-as-judge, регрессии | high |
| `webapp-testing`/`playwright` | R1 | Тестирование веб-приложений | med |

### code-auditor (security/guard)
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `secure-code-guardian` | R1 | Безопасное кодирование "с учётом security" | high |
| `security-and-hardening` | R2 | OWASP Top 10, 3-tier boundary system | high |
| `security-reviewer` | R1 | Security-focused code review | high |
| `security-checklist` (ref) | R2 | Pre-commit, auth, OWASP | high |
| `semgrep-security-scan` | R1 | Статический анализ | high |
| `sharp-edges`/`insecure-defaults` | R1 | Опасные паттерны, настройки по умолчанию | high |
| `fullstack-guardian` | R1 | Full-stack security review | high |
| **модуль 11-security** | R3 | Prompt injection, trusted/untrusted, least privilege | **high** — прямо наш guard-слой |
| **модуль 08-sandboxes** | R3 | Изоляция, права, сеть, лимиты | med-high |
| `audit-context-building`/`variant-analysis` | R1 | Контекст для audit, поиск похожих уязвимостей | med |

### experimenter
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `idea-refine` | R2 | Divergent/convergent thinking | med |
| `brainstorming` | R1 | Обсуждение идей/edge cases | med |

### research-orchestrator
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `orchestration-patterns` (ref) | R2 | Multi-persona, "personas don't invoke personas" | high |
| `prompt-engineer` | R1 | Оптимизация промптов LLM | high |
| `spec-miner` | R1 | Извлечение требований из документации | med |
| **модуль 03-planning** | R3 | ReAct, план-файл, перепланирование | med |

### claim-parser
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `interview-me` | R2 | One-question-at-a-time до 95% confidence | high |
| `ask-questions-if-underspecified` | R1 | Когда задавать уточняющие вопросы | med |
| `spec-miner` | R1 | Извлечение требований | med |

### source-fetcher
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `source-driven-development` | R2 | Grounding в офиц.документации, verify+cite | high |
| `rag-architect` | R1 | Проектирование RAG системы | high |
| **модуль 05-rag** | R3 | Чанкинг, гибридный поиск, реранк, цитирование | high |
| `pdf` | R1 | Работа с PDF | med |

### fact-checker
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `doubt-driven-development` | R2 | CLAIM→EXTRACT→DOUBT→RECONCILE→STOP | high |
| `source-driven-development` | R2 | Verify+cite | high |
| **модуль 09-evals + benchmarks/** | R3 | Golden set, LLM-as-judge, статистика | high |
| `second-opinion` | R1 | Альтернативный взгляд | med |

### tribunal-judge
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `doubt-driven-development` | R2 | CLAIM→DOUBT→RECONCILE adversarial review | high — ядро tribunal |
| **модуль 14-agent-failures + anti-patterns/** | R3 | Таксономия 30 отказов, каталог граблей | high |
| `second-opinion` | R1 | Альтернативный взгляд | med |
| `the-fool` | R1 | Свежий взгляд | med |

### synthesizer
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `documentation-and-adrs` | R2 | ADR, документировать "почему" | med |

### writing-orchestrator
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `orchestration-patterns` (ref) | R2 | Multi-persona | high |
| `doc-coauthoring` | R1 | Совместное написание документации | med |
| `documentation-and-adrs` | R2 | ADR | med |

### article-writer
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `doc-coauthoring` | R1 | Совместное написание | med |
| `documentation-and-adrs` | R2 | ADR, API docs | med |

### researcher
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `rag-architect` | R1 | RAG проектирование | high |
| **модуль 05-rag** | R3 | Чанкинг, поиск, реранк | high |
| `pandas-pro` | R1 | Данные в pandas | med |

### all agents (cross-cutting)
| Skill | Репо | Назначение | ROI |
|--|--|--|--|
| `context-engineering` | R2 | Подача контекста (taint loss) | high |
| **модуль 04-memory** | R3 | Компакция, эпизодический журнал | med |

---

## Роутер оркестратора (какие skills активировать при каких задачах)

### code-orchestrator routing table

| Тип входящей задачи (claim) | Активируемые skills | Целевые агенты |
|--|--|--|
| **Новая фича/модуль** | spec-driven-development + planning-and-task-breakdown + incremental-implementation + test-driven-development | coder-worker, code-tester |
| **Bug fix** | systematic-debugging + debugging-and-error-recovery + differential-review | coder-worker, code-reviewer |
| **Security audit/guard** | secure-code-guardian + security-and-hardening + модуль 11-security + security-checklist | code-auditor |
| **Code review (запрос)** | code-review-and-quality + differential-review + make-no-mistakes + definition-of-done | code-reviewer |
| **Test suite** | test-master + property-based-testing + testing-patterns + модуль 09-evals + verification-before-completion | code-tester |
| **Оптимизация (cost/perf)** | модуль 12-cost-optimization + performance-optimization | code-orchestrator, code-auditor |
| **Рефакторинг/упрощение** | simplify (наш) + code-simplification (если R2) | coder-worker |
| **Мульти-агент задача** | orchestration-patterns + subagent-driven-development + dispatching-parallel-agents + модуль 07-multi-agent | code-orchestrator |
| **Документация** | documentation-and-adrs + doc-coauthoring | article-writer, synthesizer |
| **Production/ship** | shipping-and-launch + модуль 13-production + before-prod checklist | code-orchestrator |

### research-orchestrator routing table

| Тип задачи | Активируемые skills | Целевые агенты |
|--|--|--|
| **Проверка научного текста** | doubt-driven-development + source-driven-development + модуль 09-evals | claim-parser, fact-checker, tribunal-judge |
| **Поиск источников** | rag-architect + модуль 05-rag + source-driven-development + pdf | source-fetcher, researcher |
| **Извлечение клаймов** | interview-me + spec-miner + ask-questions-if-underspecified | claim-parser |
| **Трибунал/вердикт** | doubt-driven-development + модуль 14-agent-failures + anti-patterns + second-opinion | tribunal-judge |
| **Синтез отчёта** | documentation-and-adrs | synthesizer |

---

## Дубликаты — НЕ интегрировать (использовать наши)

| Наш skill | Дубликат | Действие |
|--|--|--|
| `worktrees` | `git-worktrees` (R1) | Оставить наш |
| `simplify` | `code-simplification` (R2) | Оставить наш |
| `verification-planning` | `spec-driven-development`/`planning-and-task-breakdown` (R2) | Дополнить (PRD-формат), не заменить |
| `autoresearch` | `05-rag`/`rag-architect` (R1/R3) | Дополнить (реранк, оценка retrieval) |
| `reflect` | `second-opinion`/`the-fool` (R1) | Дополнить, не заменить |
| `oh-my-opencode-slim` | `using-agent-skills` (R2 meta) | Дополнить routing |

---

## Приоритет интеграции (топ-15 по ROI)

| # | Skill | Целевой агент | ROI | Усилие | Формат |
|--|--|--|--|--|--|
| 1 | `orchestration-patterns` (ref) | все оркестраторы | high | low (copy md) | R2 reference |
| 2 | `doubt-driven-development` | tribunal-judge, fact-checker | high | low (SKILL.md) | R2 native opencode |
| 3 | `source-driven-development` | source-fetcher, fact-checker | high | low | R2 native |
| 4 | `secure-code-guardian` + модуль 11-security | code-auditor | high | med (адаптация R3) | R1 md + R3 module |
| 5 | `context-engineering` | code-orchestrator/all | high | low | R2 native |
| 6 | `using-agent-skills` (meta) | code-orchestrator (роутер) | high | low | R2 native |
| 7 | `code-review-and-quality` + `differential-review` | code-reviewer | high | low | R2/R1 native |
| 8 | `test-driven-development` + `property-based-testing` | code-tester, coder-worker | high | low | R1/R2 native |
| 9 | `interview-me` | claim-parser | high | low | R2 native |
| 10 | модуль `12-cost-optimization` | code-orchestrator | high | med (адаптация R3) | R3 module → skill |
| 11 | `systematic-debugging` + `debugging-and-error-recovery` | coder-worker, code-tester | high | low | R1/R2 |
| 12 | модуль `09-evals` + `benchmarks/` | code-tester, fact-checker | high | med | R3 → skill |
| 13 | `spec-driven-development` + `planning-and-task-breakdown` | code-orchestrator | high | low | R2 native |
| 14 | модуль `14-agent-failures` + `anti-patterns/` | tribunal-judge, code-reviewer | high | med | R3 → skill |
| 15 | `incremental-implementation` | coder-worker | high | low | R2 native |

**Стратегия интеграции:**
1. **Волна 1 (R2 native, low effort):** 8 skills из addyosmani — нативная opencode-поддержка (`docs/opencode-setup.md`), копирование SKILL.md + регистрация. Самый высокий ROI.
2. **Волна 2 (R1 markdown, low effort):** 6 skills из zavalishev — markdown с frontmatter, совместим, но нет opencode-специфики.
3. **Волна 3 (R3 modules → skills, med effort):** 4 модуля justxor — нужно адаптировать конспекты в SKILL.md формат.

---

## Что требует решения пользователя

1. **Волна 1 (R2 addyosmani) — начать интеграцию?** 8 native-opencode skills, low effort, highest ROI. Рекомендую начать с этого.
2. **Формат интеграции R3 modules** — конвертировать в SKILL.md (извлечь process + checklists) или оставить как reference-чтение для агентов?
3. **Роутер в конфиге или в промпте?** — `orchestration-patterns` + `using-agent-skills` как skills (activate по задаче) или вшить в системный промпт code-orchestrator?
4. **Клонировать репозитории локально** (через skill `clonedeps`) для чтения полного содержимого skills перед интеграцией?