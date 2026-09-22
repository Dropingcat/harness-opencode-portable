# Researcher: текущая архитектура и циклы прохождения информации

## 0. Назначение документа

Этот документ описывает не целевое ядро, а **текущее состояние researcher-контура** в opencode и то, как сейчас должна/пытается проходить информация через агентов, артефакты и deterministic-скрипты.

Первый документ:

```text
researcher-core-architecture.md
```

описывает будущую архитектуру. Этот файл нужен как карта текущей системы: что уже есть, где разрывы, какие циклы надо сохранить, а какие заменить.

---

## 1. Текущие активные элементы

### 1.1 Primary agents

В профиле opencode найдены два researcher-агента:

```text
C:\Users\Arhys\.config\opencode\agent\researcher.md
C:\Users\Arhys\.config\opencode\agent\research-orchestrator.md
```

`researcher.md` сейчас отключён:

```yaml
disable: true
```

Он является старым агентом типа:

```text
LLM + web search + prose report
```

Основной актуальный агент:

```text
research-orchestrator.md
```

Он уже формулирует правильный принцип:

```text
LLM производит свидетельства. Код принимает решения.
```

Но на текущей Windows-машине он ссылается на отсутствующий серверный runtime.

### 1.2 Subagents

Текущий research-orchestrator ожидает следующих subagents:

```text
claim-parser
source-fetcher
fact-checker
tribunal-judge
synthesizer
```

Их роли:

```text
claim-parser      -> разбить текст на atomic claims
source-fetcher    -> найти источники под claim
fact-checker      -> дать предварительный verdict по claim+sources
tribunal-judge    -> разобрать спорные/критические случаи
synthesizer       -> собрать финальный Markdown-отчёт
```

### 1.3 Skills

Активные research skills уже в основном восстановлены:

```text
conducting-scientific-research
research-workflows
research-lookup
perplexity-search
sources
compare
reproduce
verify
literature-review
citation-management
openalex-database
pubmed-database
biorxiv-database
source-driven-development
doubt-driven-development
scientific-critical-thinking
hypothesis-generation
scientific-brainstorming
scientific-problem-selection
markitdown
```

Вывод:

```text
skills не главный блокер;
главный блокер — отсутствие deterministic runtime/scripts.
```

---

## 2. Текущий задуманный цикл research-orchestrator

Согласно `research-orchestrator.md`, цикл должен быть таким:

```text
input text
  ↓
BRICKS runner
  ↓
claim-parser
  ↓
claims.json
  ↓
source-fetcher per claim
  ↓
sources_<claim_id>.json + sources_index.json
  ↓
fact-checker
  ↓
verdicts_raw.json
  ↓
numeric_comparator.py
  ↓
numeric_result.json
  ↓
merge_numeric.py
  ↓
verdicts_enriched.json
  ↓
evidence_contract.py
  ↓
evidence_out.json
  ↓
post_processor.py
  ↓
verdicts_final.json
  ↓
justification_check.py
  ↓
escalation.py
  ↓
tribunal if needed
  ↓
tribunal_combined.json
  ↓
synthesizer.py + synthesizer agent
  ↓
final_report.md
  ↓
summary.json + audit log
```

Идея правильная: агент не должен вручную вести весь цикл. Его должен вести runner.

Проблема: сам runner и скрипты на Windows сейчас отсутствуют.

---

## 3. Реальное состояние runtime на Windows

Проверено:

```text
C:\Users\Arhys\.config\opencode\shared\code-factory-process.md
```

не найден.

Также не найдены:

```text
C:\Users\Arhys\.config\opencode\scripts\**\*.py
```

То есть отсутствуют локальные аналоги:

```text
run_research.sh
numeric_comparator.py
merge_numeric.py
evidence_contract.py
post_processor.py
justification_check.py
escalation.py
synthesizer.py
judge_brief.py
factory_ctl.py
contract_validator.py
```

Большая часть agent-файлов всё ещё ссылается на Linux-пути:

```text
/home/orangepi/...
/tmp/research-...
```

Следствие:

```text
текущий research-orchestrator концептуально правильный,
но исполняемо сломан на Windows без восстановления/переноса runtime.
```

---

## 4. Текущие циклы прохождения информации

### 4.1 Цикл старого researcher.md

Старый агент работал примерно так:

```text
user question
  ↓
researcher.md
  ↓
tvly / webfetch / docs
  ↓
manual synthesis by LLM
  ↓
structured prose report
```

Плюсы:

```text
быстро;
хорошо пишет;
удобен для человеческого чтения;
может собрать длинный raw_report.md.
```

Минусы:

```text
state живёт в тексте;
нет claim graph;
нет event history;
нет детерминированного stop condition;
нет source admission vs evidence admission;
сложно проверить, почему конкретная фраза попала в отчёт.
```

Архитектурный вывод:

```text
старый researcher не выбрасывать;
использовать как генератор raw_report.md или как prose-facing слой,
но не как источник истины.
```

### 4.2 Цикл текущего research-orchestrator.md

Задуманный цикл:

```text
input text/file
  ↓
orchestrator creates workspace
  ↓
orchestrator launches deterministic runner
  ↓
runner calls subagents and scripts
  ↓
runner validates schemas and stop criteria
  ↓
orchestrator reads final artifacts
  ↓
orchestrator summarizes result to user
```

Плюсы:

```text
правильное разделение LLM/code;
есть artifact names;
есть идея audit;
есть идея budget/max iterations;
есть tribunal escalation;
есть numeric/evidence/postprocessor этапы.
```

Минусы:

```text
runner отсутствует локально;
пути Linux-only;
форматы artifact-ов не закреплены локальными contracts;
нет graph repository;
нет разделения epistemic/provenance graph;
финальный результат всё ещё ориентирован на verdicts/report, а не на claim graph.
```

Архитектурный вывод:

```text
research-orchestrator.md сохранить как оболочку,
но заменить backend runner на новый local research-runtime.
```

---

## 5. Текущая цепочка артефактов и её ограничения

Текущий orchestrator ожидает такие файлы:

```text
input.txt
claims.json
sources_<claim_id>.json
sources_index.json
verdicts_raw.json
numeric_result.json
verdicts_enriched.json
evidence_out.json
verdicts_final.json
judge_briefs.json
tribunal_combined.json
final_report.md
run/<ts>/_audit.json
run/<ts>/summary.json
```

Эта цепочка полезна, но плоская. В ней нет явной модели:

```text
ClaimProposal -> Claim
SourceCandidate -> Source
EvidenceSpan -> EvidenceRelation -> Claim
ValidationEvent -> state reducer
Gap/Conflict as nodes
WriterDecision -> FinalAnswer
```

Главное ограничение:

```text
verdicts_final.json не заменяет graph state.
```

Он может сказать, что claim supported/unsupported, но плохо отвечает:

```text
почему конкретная рекомендация появилась?
какое предположение её блокирует?
какая операция породила claim?
какой source является independent evidence root?
какие 14 claims зависят от одной слабой экстраполяции?
```

---

## 6. Как информация должна проходить в новой модели

Новый цикл должен сохранять prose-слой, но добавить graph-слой.

```text
user question / input document
  ↓
ResearchRequest
  ↓
raw researcher / report generator
  ↓
raw_report.md
  ↓
claim extraction
  ↓
ClaimProposal[] + QuantityProposal[] + EdgeProposal[]
  ↓
GraphTransaction
  ↓
validators
  ↓
accepted Claims / Quantities / Edges
  ↓
Source/Evidence linking
  ↓
GapBuilder + ConflictBuilder + StructuralRiskAnalyzer
  ↓
Snapshot
  ↓
targeted ResearchOperations
  ↓
graph update
  ↓
WriterContext
  ↓
final_answer.md
```

Главное отличие:

```text
raw_report.md не является концом исследования;
он становится одним из входов для claim graph.
```

---

## 7. Цикл клайма

Жизненный цикл claim:

```text
ClaimProposal
  ↓ normalize
  ↓ atomicity check
  ↓ admission
Claim C001@1
  ↓ evidence linked
  ↓ validators
Claim C001@1 status changed
  ↓ new evidence / conflict / retraction / scope change
Claim C001@2 or dirty state
  ↓ snapshot
  ↓ writer context inclusion/exclusion
```

Claim не хранит своих родителей/детей. Связи только через `GraphEdge`.

Ревизии:

```text
C001@1
C001@2
C001@3
```

При существенном изменении смысла создаётся новая semantic identity или edge `supersedes`.

---

## 8. Цикл числа / Quantity

Число проходит отдельно от claim.

```text
number found in text/report/evidence
  ↓
QuantityProposal
  ↓
unit normalization
  ↓
semantic assignment
  ↓
provenance check
  ↓
Quantity
  ↓
NumericValidator
  ↓
status: verified / missing_provenance / unit_mismatch / derived / contradicted
```

Важно:

```text
число всегда контролируется;
но не всегда становится отдельным claim.
```

Пример из отчёта про малину:

```text
"гуматы повышают эффективность удобрений на 15–30%"
```

Разложение:

```text
C201: гуматы повышают эффективность удобрений
Q201: 15–30%, semantic=fertilizer_efficiency_increase
```

Если у Q201 нет evidence provenance, повторный поиск должен идти по Q201, а не по всему разделу про гуматы.

---

## 9. Цикл источника и evidence

### 9.1 Source lifecycle

```text
SearchQuery
  ↓
SourceCandidate
  ↓
metadata resolution
  ↓
dedup / identity / lineage
  ↓
SourceAdmission
  ↓
Source
```

Source admission отвечает:

```text
можно ли считать этот документ допустимым источником?
```

Проверки:

```text
identity
author/date
source type
primary/secondary
duplicate
retraction/correction
scope
accessibility
```

### 9.2 Evidence lifecycle

```text
Source
  ↓ fetch/open
SourceContent
  ↓ extract span
EvidenceCandidate
  ↓ evidence admission
Evidence
  ↓ relation proposal
EvidenceRelation / GraphEdge
  ↓ validators
supports / partially_supports / contradicts / background
```

Evidence admission отвечает:

```text
годится ли конкретный span как evidence для конкретного claim?
```

---

## 10. Цикл gap/conflict и targeted research

После каждого изменения графа validators могут создать gaps/conflicts.

```text
Graph updated
  ↓
GapBuilder
  ↓
Gap nodes
  ↓
ConflictBuilder
  ↓
Conflict nodes
  ↓
StructuralRiskAnalyzer
  ↓
priority score / downstream impact
  ↓
ResearchQueue
  ↓
targeted ResearchOperation
```

Пример:

```text
A17 unsupported assumption
  ↓ blocks
14 claims
  ↓ blocks
6 recommendations
```

Planner должен создать не общий запрос:

```text
найти ещё источники про малину
```

а targeted задачу:

```text
Resolve A17.
Need: primary/source evidence for assumption.
Expected downstream impact: 14 claims, 6 recommendations.
```

---

## 11. Цикл writer-а

Writer запускается после стабилизации графа.

```text
GraphSnapshot
  ↓
ValidationReport
  ↓
WriterContextBuilder
  ↓
writer_context.json
  ↓
Writer
  ↓
WriterDecision[]
  ↓
final_answer.md
```

Writer получает ограничения:

```text
allowed_claims
qualified_claims
forbidden_claims
blocked_recommendations
citation_map
```

Writer не имеет права:

```text
искать источники;
создавать evidence;
повышать claim status;
придумывать числа;
выбирать citation по памяти.
```

---

## 12. Current researcher report как входной слой

Текущий подробный Markdown-отчёт остаётся ценным.

Его роль:

```text
человек читает raw_report.md;
машина извлекает из raw_report.md ClaimProposal/QuantityProposal;
validator показывает, где prose сильный, а где слабый.
```

Не надо ужимать prose. Надо добавить второе представление.

---

## 13. Пример цикла на отчёте про малину

### 13.1 Бедная почва

В prose:

```text
Бедная почва требует в 1,5-2 раза больше питания.
Азот 60-100 кг/га, 1,5× от обычной нормы 40-80 кг/га.
```

В графе:

```text
C001: базовая норма азота 40-80 кг N/га
  ← supported_by E001 from S2

A001: бедная почва требует 1.5-2× питания
  ← unsupported / needs evidence

D001: derive 60-100 кг/га from C001 and A001
  ← computation maybe valid, justification weak

C002: на бедной почве азот 60-100 кг/га
  ← derived_from D001

R001: использовать 60-100 кг N/га
  ← justified_by C002
```

Диагноз:

```text
R001 conditional / needs_research,
потому что зависит от A001.
```

### 13.2 Гнилая древесина

В prose:

```text
Малина растёт на опушках/вырубках, значит гнилая древесина является частью её эволюционной ниши и улучшает питание, подавляет болезни, сокращает полив.
```

В графе:

```text
C101: малина встречается на опушках/вырубках
  ← direct S1

C102: гниющая древесина является частью эволюционной ниши малины
  ← generalizes_from C101

C103: гнилая древесина улучшает питание малины
  ← extrapolates_from C102

C104: гнилая древесина подавляет Botrytis
  ← extrapolates_from C102

C105: гнилая древесина подавляет Phytophthora
  ← extrapolates_from C102

C106: полив можно сократить в 2-3 раза
  ← extrapolates_from C102
```

Диагноз:

```text
large downstream fan-out from weak transition C101 -> C102.
```

### 13.3 Гуматы

В prose:

```text
Гуматы повышают эффективность удобрений на 15-30%, стимулируют корневую систему и повышают стрессоустойчивость.
```

В графе:

```text
C201: гуматы повышают эффективность удобрений
Q201: 15-30%, semantic=fertilizer_efficiency_increase
C203: гуматы стимулируют развитие корней
C204: гуматы повышают стрессоустойчивость
```

Диагноз возможен раздельно:

```text
C201 supported
Q201 missing_numeric_provenance
C203 supported
C204 partially_supported
```

---

## 14. Где текущая архитектура переходит в новую

### Сохраняем

```text
подробный raw_report.md;
agent-based claim-parser/source-fetcher/fact-checker/synthesizer;
идею deterministic runner;
идею numeric/evidence/postprocessor;
идею tribunal для спорных случаев;
skills ecosystem.
```

### Заменяем / добавляем

```text
flat verdict pipeline -> graph repository;
LLM-created final claims -> ClaimProposal admission;
single trust score -> source/evidence/relation separation;
report as state -> snapshot/event repository;
generic confidence -> typed edge metadata;
manual next search -> Gap/Conflict/StructuralRisk-driven ResearchQueue.
```

---

## 15. Как подключать серверные скрипты из Z:\server

`Z:\server` рассматривается как донор legacy/runtime blocks.

Если там появятся:

```text
numeric_comparator.py
merge_numeric.py
evidence_contract.py
post_processor.py
justification_check.py
escalation.py
synthesizer.py
run_research.sh
```

их нельзя делать источником архитектуры.

Правильно:

```text
new research core
  ↓ stable interface
HermesLegacyAdapter
  ↓ subprocess/file contract
legacy script from Z:\server
```

Каждый legacy adapter обязан:

```text
1. явно описывать input schema;
2. явно описывать output schema;
3. нормализовать пути Windows/Linux;
4. не протаскивать hidden state;
5. писать ValidationEvent / OperationEvent;
6. не менять graph state напрямую.
```

---

## 16. Минимальный R0-R3 с учётом текущей архитектуры

### R0

```text
ids.py
enums.py
contracts.py
events.py
transactions.py
repository.py
serialization.py
```

### R1

```text
Question
ClaimProposal
Claim
Quantity
Source
Evidence
Scope
Derivation
GraphEdge
EdgeProposal
Gap
Conflict
Assumption
Recommendation
```

### R2

```text
GraphRepository
ExecutionRepository
GraphTransaction
ValidationEvent log
Snapshot
revision model
dependency traversal
dirty propagation
```

### R3

```text
SourceAdmissionValidator
EvidenceAdmissionValidator
AtomicityValidator
NumericValidator
ScopeValidator
EdgeValidator
GraphCycleValidator
GapBuilder
ConflictBuilder
StructuralRiskAnalyzer
```

---

## 17. Главная диагностика текущего состояния

```text
Агенты есть.
Skills есть.
Промптовая архитектура частично правильная.
Runtime отсутствует.
Graph state отсутствует.
История происхождения ответа отсутствует.
Linux-ссылки остались.
```

Поэтому ближайшая задача:

```text
не подключать сразу интернет и академические источники,
а построить сухое ядро R0-R3 и проверить его на synthetic fixture + malina raw_report.
```

---

## 18. Следующий документ

После этого файла нужен третий, более технический:

```text
researcher-r0-specification.md
```

Он должен описать:

```text
точные enums;
формат IDs;
минимальные dataclasses/pydantic models;
JSON serialization;
GraphTransaction API;
Repository interface;
первый dry-run fixture;
ожидаемый snapshot.
```
