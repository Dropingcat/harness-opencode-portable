Новые файлы
1. shared\paper-review-chain-contracts.md — единый источник истины: шаблоны JSON и acceptance для всех звеньев цепочки /review-paper:

Контракт 1 — paper-analyzer → analysis.json: парсинг, ссылки (reference_stats), фигуры, preview ключевых утверждений.
Контракт 2 — technical-reviewer → tech_review.json: 4 измерения (корректность, эксперименты, статистика, fairness) со score [1,5], issues с severity, SOTA-таблица, missing baselines.
Контракт 3 — reference-auditor → reference_audit.json: верификация ссылок (с обязательным равенством verified+mismatch+not_found == total), недостающие цитаты, покрытие related work.
Контракт 4 — paper-comparator → competitor_analysis.json: Tier 1–3 конкуренты, техническое сравнение, SOTA-позиция, missing baselines.
Контракт 5 — merge (делает оркестратор) → merged_scores.json: детерминированные правила — overall = среднее 6 измерений, вердикт по порогам, критический триггер (любой critical → не выше borderline), флаги среды. + шаблон Review_Report_<paper>.md. И анти-контракты (что отклоняется на повторный диспатч).
2. shared\paper-review-orchestration.md — инструкции оркестратору:

Порядок цепочки, диспатч через task с полным контрактом в prompt (субагент не знает своего SKILL.md).
Параллельный fan-out Фазы 2 (3 task одним ходом) + merge в контексте оркестратора.
Стадия «подготовка» с загрузкой venue-профилей и перспектив рецензентов.
Вспомогательные цепочки /pre-screen (без полного цикла) и /rebuttal (без диспатча субагентов).
Анти-паттерны: субагент-внутри-субагента, merge в чужом контексте, субъективный вердикт в обход правил, выдуманные SOTA-числа и т.д.
Обновлено
4 агента (agents\paper-*.md, reference-auditor.md, technical-reviewer.md): добавлена ссылка на контракт цепочки в шапку + секция «Контракт возврата (JSON)» с кратким шаблоном и правилами (численные инварианты, enum-ограничения, «не выдумывай SOTA-числа»).
3 команды (.opencode\commands\review-paper.md, pre-screen.md, rebuttal.md): указан источник истины — shared-файлы оркестрации.
Реестр агентов: перекомпилирован (compile_agents.py — 30 агентов OK, registry.py --validate — OK).
Конвенция выдержана
Принцип №0 harness: LLM даёт свидетельства (JSON-артефакты), оркестратор детерминированно валидирует контракты и сшивает score/вердикт по правилам — никакого «суммарного ощущения».
Артефакты по жёстким именам в рабочей папке ${PAPER_WORKSPACE}; флаги среды понижают confidence вместо блокировки; блоки фиксируются через tech_debt_cli.py auto.