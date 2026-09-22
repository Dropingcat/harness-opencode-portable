# Архитектура модульного ассистента задач и заметок

**Статус:** расширенная архитектурная спецификация, версия 0.3\
**Назначение:** рабочая опора для реализации. Документ фиксирует не
только что строить, но и зачем, кто владеет состоянием, какие цепочки
являются штатными, что запрещено и где оставлены точки расширения.

## 0. Как пользоваться документом

Перед реализацией нового компонента нужно ответить на четыре вопроса:

1.  К какому слою он относится: Core, Gateway, AI, Output Adapter, Admin
    или Infrastructure?
2.  Через какой контракт он общается с соседями: `COMMAND`, `QUERY` или
    `EVENT`?
3.  Кто является владельцем изменяемого состояния?
4.  Что произойдёт, если компонент отключить или он упадёт?

Если для реализации требуется напрямую менять таблицу соседнего модуля,
обходить общий API или знать внутренности конкретного адаптера,
архитектурная граница, вероятно, нарушена.

## 1. Клайм проекта

Проект --- самостоятельное многопользовательское ядро задач и заметок с
подключаемыми интерфейсами, внешними сервисами и необязательным
интеллектуальным агентом.

Core владеет пользовательскими данными и жизненным циклом. Telegram, web
и voice --- входы. Google Calendar, Telegram-уведомления и последующие
интеграции --- выходы. AI преобразует естественный язык в формальные
команды, но не является источником истины и не получает отдельного
привилегированного пути.

``` text
USER -> GATEWAY -> COMMAND -> CORE -> EVENT -> OUTPUT MODULE
```

С AI:

``` text
USER -> GATEWAY -> AI RUNTIME -> TOOL GATE -> COMMAND -> CORE
```

Ручное управление и AI сходятся в одном command layer.

## 2. Цели

### Пользовательские

Пользователь должен уметь создать задачу/заметку, увидеть Dashboard,
завершить, перенести, исправить, удалить обратимо, восстановить и
подключить удобные внешние выходы. При доступном AI те же операции
выполняются текстом или голосом.

### Инженерные

Новый frontend, LLM, skill, календарь или платёжный provider не должен
требовать переписывания TaskService.

### Эксплуатационные

Для любого изменения должно быть возможно установить actor, source,
command, resource, before/after, AI run при наличии, внешние hooks и
точку ошибки.

## 3. Не-цели

Пилот не строит собственный календарь, универсальную платформу
уведомлений, обязательный AI, авторизацию через prompt, произвольный
workflow-язык, marketplace plugins или микросервисную сетку без
эксплуатационной необходимости.

## 4. Принципы

### Core --- source of truth

Если локальная задача создана, а Google упал, задача существует. Ошибка
Google --- ошибка внешней проекции.

### Код определяет допустимость

Invariant реализуется кодом: tenant isolation, state transitions,
transactions, audit append-only, schema validation, idempotency.

Policy может конфигурироваться: AI entitlement, необходимость
confirmation, включение модуля.

Workflow декларируется skill contract.

Implementation выбирается registry.

``` text
Hardcode invariants.
Configure policies.
Declare workflows.
Register implementations.
```

### Один путь изменения

Не существует `create_from_ai()` и `create_from_telegram()`. Есть
`CreateTask(UserContext, Command)`.

### Атомарность

Core-команда полностью фиксирует локальное изменение либо не меняет
state. Внешний API не является частью локальной DB transaction.

### Идемпотентность

Повтор Telegram update, AI retry или network retry не должен создавать
дубль.

### Обратимость

`completed` и `deleted` --- состояния. Физическое стирание --- отдельная
административная retention-процедура.

### Минимальный контекст AI

Модель получает только данные текущего шага. Она не должна сама искать,
какая информация могла бы пригодиться.

### Детерминированный UI recovery

Любой frontend имеет HOME, BACK, CANCEL, RECOVER.

## 5. Слои

``` text
PRESENTATION / INPUT
Telegram | future Web | Voice
          |
OPTIONAL AI
          |
APPLICATION GATE
Auth | UserContext | Policy | Tool Gate
          |
CORE
Tasks | Notes | Queries | Hooks | Cron | Events
          |
OUTPUT ADAPTERS
Google Calendar | Telegram notify | future
```

Admin plane расположен сбоку и управляет пользователями, entitlement,
credentials, modules, health, versions и diagnostics.

Core не импортирует Telegram SDK или LLM SDK.

## 6. Доменная модель

### Tenant/User

Каждая пользовательская сущность содержит `tenant_id` и `user_id`. Scope
закладывается сразу.

### Task

``` text
id
tenant_id
user_id
user_year_no
title
body
state
deadline_at
created_at
updated_at
completed_at
deleted_at
revision
```

`id` машинный. `user_year_no`, например `2026-00417`, нужен человеку.

### Deadline

`NULL` означает отсутствие срока.

``` text
active + deadline < now  -> overdue
active + deadline >= now -> upcoming
active + NULL            -> no_deadline
```

Overdue не хранится как независимый lifecycle state.

### Lifecycle

``` text
active -> completed
active -> deleted
completed -> active
completed -> deleted
deleted -> restored state
```

Переходы централизованы в Core.

### Optimistic locking

Edit/Move/Complete получает `expected_revision`. Несовпадение даёт
conflict вместо тихого перетирания изменений.

## 7. Dashboard и Query layer

Command изменяет, Query читает.

Dashboard формируется серверными запросами:

``` text
overdue
upcoming
no_deadline
completed
deleted
notes
```

Категоризацию не дублируют Telegram и web. Pagination закладывается
сразу.

## 8. Command contract

Envelope:

``` text
command_id
request_id
actor/source
payload
expected_revision?
idempotency_key?
```

UserContext создаётся authentication layer и не принимается из
недоверенного payload.

Путь команды:

``` text
Authenticate
-> Authorize
-> Validate
-> Transaction
-> Execute
-> Domain Event
-> Audit
-> Outbox
```

## 9. Multi-user isolation

Запрос по одному resource ID запрещён архитектурно.

``` sql
SELECT *
FROM tasks
WHERE tenant_id = ?
  AND user_id = ?
  AND id = ?
```

Лучше repository принимает UserContext и автоматически применяет scope.
LLM не передаёт `user_id` в tool schema.

## 10. Event model

Event --- уже произошедший факт:

``` text
TASK_CREATED
TASK_EDITED
TASK_DEADLINE_CHANGED
TASK_COMPLETED
TASK_REOPENED
TASK_DELETED
TASK_RESTORED
```

Envelope содержит event ID, type, resource, tenant/user, time, actor,
source, payload version, correlation/request ID.

TaskService не вызывает Google и Telegram напрямую. Он публикует event.

## 11. Outbox

Локальное изменение и запись события для внешней доставки фиксируются в
одной DB transaction.

``` text
transaction:
  update domain
  insert event
  insert outbox
commit

worker:
  dispatch
  delivered / retry / failed
```

Так падение процесса после commit не теряет необходимость внешней
обработки.

## 12. Hooks

Hook --- контролируемая точка расширения, а не скрытое второе ядро.

Допустимые роли: собрать context, преобразовать данные, вызвать
зарегистрированный контракт, обработать event.

Hook имеет name/version, trigger, timeout, error policy и observability.
Не следует строить неявные цепочки, где порядок hooks тайно определяет
бизнес-результат.

## 13. Cron/Scheduler

Scheduler определяет момент запуска, но не меняет domain напрямую.

``` text
cron -> query -> command/event -> Core/output
```

Cron не выполняет прямой `UPDATE tasks`.

## 14. Telegram Gateway

Gateway идентифицирует пользователя, отображает Dashboard, принимает
buttons/text/voice, управляет UI session, преобразует ручные действия в
Query/Command и при включённом AI направляет свободный ввод в AI
runtime.

Он не владеет lifecycle, permissions, Google sync или DB.

UI state machine имеет стабильные состояния
HOME/DASHBOARD/TASK_VIEW/SETTINGS и transient create/edit/move.
Transient state имеет TTL.

Stale callback заново проверяет session, ownership, resource state и
revision. При invalid state: diagnostic/audit, очистка transient, HOME.

## 15. Google Calendar

Google --- output projection.

Пилот:

``` text
Core Task -> Google Event
```

Mapping хранит task, integration, external event ID, calendar ID, sync
status, timestamps и last error.

На TASK_CREATED создаётся event, на DEADLINE_CHANGED обновляется.
Поведение при completion задаётся module/user policy.

Google failure не откатывает Core. Используются retry и диагностируемый
sync state.

Bidirectional sync не реализуется до явного требования, потому что
требует conflict policy для удалений, переносов, timezone и конкурентных
edits.

## 16. Telegram Notification

Логически отделён от Telegram Gateway. Gateway принимает
пользовательские действия; notification adapter отправляет системно
инициированные сообщения.

Это позволяет позже независимо менять вход и канал уведомлений.

## 17. Module Registry и capabilities

Различаются:

``` text
installed
system_enabled
user_enabled
entitlement_active (если платный)
```

Фактическая доступность вычисляется из этих условий.

Skills и Core предпочитают capability конкретному бренду:

``` text
calendar.publish_event -> google_calendar_adapter
semantic.extract_datetime -> configured_llm_provider
notify.message -> telegram_adapter
```

## 18. Entitlement и будущая оплата

EntitlementService отвечает только на вопрос, имеет ли пользователь
право использовать модуль сейчас.

``` text
user_id
module_id
state
valid_from
valid_until
source
grant_reference
```

Сегодня source=admin. Позже verified payment вызывает тот же
grant/extend. Payment provider не управляет AI runtime напрямую.

Истечение AI entitlement не блокирует доступ к собственным задачам.

## 19. Admin plane

Admin surface:

-   users/sessions/status;
-   user modules;
-   entitlements;
-   service identities;
-   credential status;
-   integrations;
-   jobs/retries/dead-letter;
-   health;
-   app/DB/module versions;
-   migrations;
-   audit/system/AI traces.

Все admin mutations также авторизуются и аудитируются.

## 20. AI: назначение и границы

AI нужен для семантической неоднозначности: распознать intent, разрешить
ссылку «та задача», извлечь относительный deadline, подготовить
формальную команду.

AI не определяет ownership, transaction, entitlement, DB invariants и
service credentials.

## 21. AI Runtime

``` text
INPUT
-> Intent
-> Skill Router
-> Skill Contract
-> Step Controller
-> Context Engine
-> Epistemic Context / Claim Graph Slice
-> Prompt Renderer
-> LLM
-> Proposal Validator
-> Claim/State Update
-> Transition Validator
-> Tool Gate
-> Core
-> Result Validator
-> Observation Ingest
-> Claim Graph Update
-> next step / response
```

Controller, а не модель, управляет циклом.

Run хранит run ID, skill/version, current step, working state, budgets и
status.

Обязательны max steps, max tool calls, timeout, context/cost budget и
retry limit.

## 22. Skills

Skill --- процедурный пакет, а не инструкция-эссе.

Он задаёт trigger, entrypoint, steps, executor (`code|llm|tool`),
context recipe, allowed capabilities, output schema, transitions,
success condition, fallback и version.

Пример:

``` yaml
step: resolve_datetime
executor: llm
context_recipe: datetime.resolve_v1
output_schema: resolved_datetime_v2
transitions:
  FOUND: derive_title
  NONE: derive_title
  AMBIGUOUS: clarify_datetime
```

Новый skill не должен требовать `if skill == ...` в общем Controller.

## 23. Context Engine

Ключевой принцип: нужная информация автоматически кладётся модели под
конкретное действие.

Resolvers узкие:

``` text
resolve_current_time
resolve_user_timezone
resolve_task_candidates
resolve_current_task
resolve_daypart_policy
```

Они возвращают sanitized schema, а не произвольные DB objects.

Conditional context:

``` text
relative date -> current time + timezone
daypart -> daypart policy
"та задача" -> bounded candidates
multiple candidates -> resolution step
```

Если модель просит дополнительный context, она делает декларативный
ContextRequest. Context Gate проверяет, разрешён ли resolver текущему
skill.

Secrets, чужие данные и нерелевантные поля в LLM context не попадают.

## 24. Prompt-light

Prompt собирается:

``` text
BASE_LIGHT
+ SKILL_FRAGMENT
+ STEP_FRAGMENT
+ CONDITIONAL_FRAGMENTS
+ LIVE_CONTEXT
+ OUTPUT_CONTRACT
```

Base содержит только стабильные правила runtime. Skill объясняет
локальную процедуру. Step говорит, что сделать сейчас. Dynamic fragment
появляется только по условию.

Prompt не является security boundary. Фактические запреты исполняются
кодом.

## 25. Tool Registry/Gate

Модель видит атомарные application tools, но не SQL/shell/arbitrary
HTTP/admin.

Tool descriptor: input/output schema, capability, preconditions, side
effects, idempotency.

Tool Gate:

``` text
inject UserContext
-> entitlement/capability
-> schema
-> policy
-> confirmation if required
-> Core Command
-> result validation
```

Ошибочный prompt не расширяет физический набор tools.

## 26. Policy Engine

Изменяемые условия не размазываются по handlers.

Predicates:

``` text
authenticated
owns_resource
resource_active
ai_entitled
confirmation_present
module_enabled
```

Сложный predicate реализуется кодом и регистрируется. Не создаётся язык
произвольных выражений.

## 27. Memory

Разделяются:

-   working memory одного AI run;
-   session memory UI/draft/current resource;
-   устойчивые user settings;
-   будущий behavioral profile.

Behavioral inference является гипотезой, а не Core fact. Он не получает
права автоматически менять задачи.

## 28. Versioning AI

AI run фиксирует model config, skill, contract, context recipe, prompt
fragments и tool schema versions.

Для диагностики сохраняются наблюдаемые inputs/structured context,
outputs, tool calls, transitions и results. Скрытая цепочка рассуждений
не требуется.

## 29. Audit, Events, Logs

Domain event отвечает «что произошло с сущностью».

Audit отвечает «кто, откуда и каким путём изменил».

Technical log отвечает «почему технически сломалось».

AI trace отвечает «какой путь runtime прошёл».

Audit append-only. Для объёма: hot storage + read-only archive, а не
бесконтрольное удаление.

## 30. Ошибки и retry

Минимальная taxonomy:

``` text
validation
authorization
conflict
external_temporary
external_permanent
internal
```

Retry только для идемпотентных/защищённых операций.

Для нестабильного provider нужен circuit breaker. После исчерпания
retries job уходит в failed/dead-letter и виден админу.

## 31. Concurrency

Optimistic revision защищает пользовательские edits. Повтор event не
должен создавать второй внешний объект.

Workers проектируются под at-least-once delivery: duplicate delivery
допустима, duplicate side effect --- нет.

## 32. Time model

Хранятся однозначные timestamps и user timezone.

Относительное «завтра в 9» разрешается только при явных current
datetime + timezone.

Dayparts имеют configurable policy/default. Prompt не должен скрыто
придумывать, что «вечером» всегда 19:00.

## 33. Service credentials

Сервисы имеют отдельные identities и least privilege.

Credential lifecycle:

``` text
created -> active -> rotating/revoked/expired
```

Секреты не попадают в audit, logs и LLM context. В domain/config tables
хранится `credential_ref`.

## 34. Configuration

Разделить:

-   deployment config;
-   secrets;
-   system module config;
-   user settings;
-   entitlements.

Не складывать всё в бесформенный `settings_json`.

## 35. Migrations

DB меняется только versioned migrations.

Migration имеет ID, start/result audit, processed/changed/skipped/failed
counters. Критичные data migrations сохраняют before/after либо
воспроизводимый отчёт.

App version и DB schema version различаются.

## 36. Backup/restore

Audit не является backup.

Нужны регулярный DB backup, проверяемый restore, сохранение module
configuration и безопасная стратегия восстановления credential
references. Наличие файла backup без теста restore недостаточно.

## 37. Observability/health

Сервисы имеют `alive`, `ready`, `degraded`.

Admin видит DB, queue/outbox, Telegram, Google, LLM, workers,
migrations.

Базовые метрики: command failure rate, queue depth, oldest pending job,
provider failures, AI run failures, tool rejections, latency.

## 38. Безопасная деградация

``` text
AI down -> manual UI works
LLM down -> Core works
Google down -> local task remains
Telegram notify down -> Core state remains
worker down -> durable outbox remains
admin UI down -> user operations remain
payment down -> existing entitlement follows stored policy
```

## 39. Порядок разработки

### Этап 0 --- швы

UserContext, Command/Query/Event envelopes, errors, capability
interfaces, clock/idempotency abstractions.

Критерий: fake command проходит пустой application pipeline.

### Этап 1 --- Core

Schema, migrations, repositories, task/note lifecycle, tags, revision,
events, audit.

Критерий: полный lifecycle тестируется без frontend.

### Этап 2 --- Query/Dashboard

Server-side categories, filters, pagination.

### Этап 3 --- Auth/multi-user

Identity, sessions, scoped repositories. Обязательные cross-user
negative tests.

### Этап 4 --- Telegram без AI

Полный ручной цикл. Это доказывает самодостаточность продукта.

### Этап 5 --- Outbox/hooks/cron

Durable event delivery и scheduler.

### Этап 6 --- Telegram notifications

Первый output adapter.

### Этап 7 --- Google Calendar

Односторонняя projection + mapping + retries.

### Этап 8 --- Admin/modules

Registry, credentials, entitlements, health, diagnostics.

### Этап 9 --- AI Runtime на FakeLLM

Controller, Skills, Context, Prompt, Tool Gate, Validators.

Сначала проверяется машина исполнения, а не вероятностная модель.

### Этап 10 --- CreateTask skill

Полный путь intent -\> context -\> datetime -\> title -\> validate -\>
tool -\> Core -\> verify.

### Этап 11 --- остальные skills

Resolve/Edit/Move/Complete/Reopen/Delete/Restore/Notes.

Acceptance: новый skill не требует изменения Controller.

### Этап 12 --- реальная LLM

Provider adapter, structured outputs, budgets/timeouts/retries.

### Этап 13 --- AI entitlement

Admin выдаёт право на период, user включает доступную функцию.

### Этап 14 --- Payment

Verified payment вызывает EntitlementService. Никакой прямой связи
payment -\> AI internals.

### Этап 15 --- Web

Тот же application API, собственный presentation/navigation.

## 40. Ориентир структуры репозитория

``` text
app/
├── core/
│   ├── domain/
│   ├── commands/
│   ├── queries/
│   ├── policies/
│   ├── events/
│   └── repositories/
├── auth/
├── audit/
├── scheduler/
├── modules/
│   ├── registry/
│   ├── telegram_gateway/
│   ├── telegram_notify/
│   └── google_calendar/
├── agent/
│   ├── runtime/
│   ├── skills/
│   ├── contracts/
│   ├── context/
│   ├── prompts/
│   ├── tools/
│   ├── policies/
│   ├── memory/
│   ├── validators/
│   └── claims/
│       ├── models/
│       ├── graph/
│       ├── rules/
│       ├── registry/
│       ├── propagation/
│       └── views/
├── admin/
├── infrastructure/
│   ├── db/
│   ├── queue/
│   ├── secrets/
│   └── logging/
└── tests/
```

Dependency direction: infrastructure реализует interfaces Core, Core не
зависит от infrastructure implementation.

## 41. Что не абстрагировать заранее

Не строить заранее universal broker, собственный policy language, plugin
marketplace, dynamic untrusted code loading, service mesh или ontology
engine.

Модульная архитектура может жить в одном deployable monolith/monorepo.
Микросервис появляется только при реальной причине: isolation,
independent scaling, security boundary или отдельный тяжёлый worker.

## 42. Contract tests

Core: lifecycle, invalid transitions, ownership, conflicts, idempotency,
rollback.

Adapter: duplicate event, timeout, permanent error, revoked credential,
retry exhaustion.

Skill: happy path, ambiguity, missing context, invalid schema, forbidden
context/tool, tool failure, stale revision, budget exceeded.

Context recipe тестируется и на отсутствие лишнего:

``` text
+ timezone
+ relevant candidates
- OAuth token
- unrelated notes
- other user data
```

## 43. Definition of Done новой коробочки

Компонент готов, если:

1.  ответственность определена;
2.  вход/выход формализованы;
3.  владелец state известен;
4.  failure mode описан;
5.  timeout/retry policy определена;
6.  observability существует;
7.  отключение имеет понятное поведение;
8.  нет доступа за границы полномочий;
9.  есть contract tests;
10. Core не получил специальный `if module == X`.

## 44. Красные флаги

Следует остановиться и пересмотреть решение при фразах:

``` text
"просто добавим модели инструкцию"
"здесь быстрее напрямую UPDATE"
"Telegram сам запомнит"
"этот hook всегда должен идти первым, надо просто помнить"
"передадим модели весь профиль, вдруг пригодится"
"для этого skill добавим исключение в Controller"
"пока один пользователь, scope не нужен"
"retry просто ещё раз вызовет функцию"
```

Это типичные точки рождения скрытой связанности.

## 45. Намеренные зазоры

Сменными остаются DB/ORM, Telegram framework, queue, secret storage, LLM
provider, Google client, payment provider и web framework.

Фиксируются не технологии, а contracts, которым они обязаны
соответствовать.

## 46. Итоговая ответственность

``` text
USER
 ↓
GATEWAY
"что пользователь сделал/сказал?"
 ↓
optional AI
"что это значит?"
 ↓
SKILL/RUNTIME
"какой формальный шаг сейчас?"
 ↓
TOOL GATE
"можно ли физически это вызвать?"
 ↓
CORE
"допустимо ли изменение и какова новая истина?"
 ↓
EVENT
"что уже произошло?"
 ↓
OUTPUT ADAPTER
"как отразить факт во внешнем сервисе?"
```

## 47. Финальные правила

1.  Core работает без агента.
2.  AI не получает возможностей вне Tool Gate.
3.  Если решение надёжно принимает код, его не принимает LLM.
4.  Context Engine сам приносит модели необходимые сведения.
5.  Skill выбирает процедуру до исполнения шага.
6.  Tools ограничиваются текущим контрактом.
7.  Prompt объясняет действие, но не обеспечивает безопасность.
8.  Все mutations проходят единый command path.
9.  Все данные scoped по tenant/user.
10. Пользовательское удаление обратимо.
11. Внешний provider не владеет Core state.
12. Command требует, Query читает, Event сообщает факт.
13. Hook не становится вторым Core.
14. Реализации подключаются через registry/capability.
15. Новый skill не требует изменения общего Controller.
16. Контракты и поведение версионируются.
17. Ошибка оставляет диагностический след.
18. Transient UI имеет детерминированное восстановление.
19. Модульность не означает микросервисы.
20. Сложность добавляется только ради конкретной гарантии.

Цель проекта не в максимальном количестве абстракций. Через несколько
месяцев разработчик должен открыть контракт компонента и без
археологических раскопок понять, зачем он существует, что ему разрешено,
чем он владеет и куда ведёт каждая его связь.


## 48. Claim Graph как epistemic control plane агента

Claim Graph вводится не только для research-задач. Он является формализованным
слоем рабочего знания агента на протяжении выполнения skill.

Его задача --- хранить не «мысли модели», а проверяемые утверждения о текущей
ситуации:

```text
что известно
что предполагается
что выведено
что противоречиво
что ещё неизвестно
какое действие чем обосновано
```

Claim Graph не заменяет Core state.

Разделение:

```text
Core state
    "что истинно в домене"

Claim Graph
    "что агент считает известным и на каком основании"

Working memory
    "что нужно конкретному текущему run"

LLM context
    "какой ограниченный slice этих данных нужен текущему шагу"
```

Пример:

```text
Core:
Task T17.deadline_at = 2026-08-30T09:00

Claim Graph:
C1: пользователь говорит "перенеси её на завтра"
C2: "её" вероятно означает T17
C3: tomorrow = 2026-08-29 в timezone пользователя
A1: пользователь хочет сохранить текущее время задачи
R1: выполнить MoveTask(T17, 2026-08-29T09:00)
```

`C2` и `A1` не становятся Core fact только потому, что модель их предложила.

---

## 49. Claim Graph в операционном цикле агента

Расширенный цикл:

```text
INPUT
 ↓
Intent proposal
 ↓
Claim extraction
 ↓
Claim Graph update
 ↓
Skill Router
 ↓
Precondition evaluation
 ↓
Context selection
 ↓
Step execution
 ↓
Observation
 ↓
Claim Graph update
 ↓
Transition evaluation
 ↓
Tool proposal
 ↓
Action justification
 ↓
Tool Gate
 ↓
Core
 ↓
Result observation
 ↓
Claim Graph update
 ↓
next step / response
```

Таким образом каждый существенный переход можно связать не с произвольным
текстом reasoning, а с конкретным набором claims.

---

## 50. Типы операционных claims

Для обычного ассистента полезно расширить базовые типы.

```text
FACT
OBSERVATION
USER_INTENT
REFERENCE
ASSUMPTION
DERIVED
CONSTRAINT
PRECONDITION
HYPOTHESIS
DECISION
RECOMMENDATION
ACTION_JUSTIFICATION
RESULT
GAP
CONFLICT
```

### FACT

Подтверждённый факт из Core или доверенного resolver.

Пример:

```text
Task T17 существует.
Task T17 принадлежит текущему UserContext.
```

Такие claims создаются кодом, а не LLM.

### OBSERVATION

Наблюдение текущего шага:

```text
tool вернул conflict
resolver вернул 3 candidate tasks
calendar provider недоступен
```

### USER_INTENT

Интерпретация намерения пользователя.

```text
"перенеси её на завтра"
→ intent = MOVE_TASK
```

Это proposal, пока runtime не принял его по правилам skill.

### REFERENCE

Разрешение местоимений и ссылок:

```text
"её" → Task T17
```

REFERENCE должен содержать candidates и основание выбора.

### CONSTRAINT

Ограничение:

```text
не менять title
не отправлять notification
deadline должен быть после now
```

### PRECONDITION

Условие допустимости шага:

```text
task exists
task active
ownership valid
revision current
```

### HYPOTHESIS

Одна из возможных интерпретаций.

Например:

```text
H1: "завтра" означает 09:00
H2: сохранить текущее время задачи
```

### DECISION

Принятое runtime решение.

Оно должно иметь justification path.

### ACTION_JUSTIFICATION

Формальная связь между состоянием и tool proposal.

```text
C12 + C17 + P03 → AJ04 → MoveTask
```

---

## 51. Источники операционных claims

Claim обязательно хранит provenance.

Типы provenance:

```text
USER_INPUT
CORE_QUERY
CONTEXT_RESOLVER
TOOL_RESULT
SYSTEM_CLOCK
POLICY
SKILL_CONTRACT
LLM_PROPOSAL
DERIVATION
EXTERNAL_SOURCE
```

Пример:

```yaml
id: C17
class: FACT
predicate: task_state
value: active

provenance:
  type: CORE_QUERY
  resource_id: T17
  revision: 12

trust: authoritative
```

В противоположность:

```yaml
id: C18
class: REFERENCE
predicate: refers_to
value: T17

provenance:
  type: LLM_PROPOSAL

trust: inferred
```

Код всегда может отличить доменный факт от семантической гипотезы.

---

## 52. Trust class вместо одного confidence

Для операционного агента полезно иметь дискретный класс происхождения:

```text
AUTHORITATIVE
OBSERVED
DERIVED
INFERRED
SPECULATIVE
```

Пример порядка:

```text
Core fact             → AUTHORITATIVE
Tool result           → OBSERVED
Code derivation       → DERIVED
LLM reference resolve → INFERRED
Guess                 → SPECULATIVE
```

Действия могут требовать минимальный trust.

Пример:

```yaml
MoveTask:
  target_task:
    minimum_trust: INFERRED
    ambiguity: forbidden

DeleteTask:
  target_task:
    minimum_trust: AUTHORITATIVE
    confirmation: required
```

---

## 53. Claim Graph не дублирует Core

Запрещено хранить Claim Graph как альтернативную БД задач.

Плохая схема:

```text
Task title меняется в Core
и отдельно "обновляется" в Claim Graph как самостоятельная истина.
```

Правильная:

```text
Core = владелец факта

Claim Graph node =
reference + observed revision + provenance
```

Если Core revision изменился, claim становится stale.

---

## 54. Freshness и stale claims

Операционные claims должны иметь validity.

```yaml
validity:
  based_on_revision: 12
  valid_until: null
  stale: false
```

После:

```text
TASK_EDITED revision 13
```

claims, основанные на revision 12:

```text
dirty/stale
```

Перед action runtime обязан обновить критичные claims.

---

## 55. Run-scoped graph

Для большинства операций граф должен быть scoped по `run_id`.

```text
project graph
session graph
run graph
```

Минимально:

```yaml
claim:
  tenant_id: ...
  user_id: ...
  run_id: ...
```

Run завершается, и большая часть временных claims архивируется вместе с trace.

В Core они не мигрируют.

---

## 56. Persistent claims

Некоторые claims могут переживать run:

```text
user preference
stable mapping
project fact
resolved external identity
```

Но promotion из run graph в persistent memory требует отдельного policy.

LLM не должна сама решать:

```text
"это стоит запомнить навсегда"
```

---

## 57. Claim Proposal Contract

LLM выдаёт только proposal:

```yaml
claim_proposal:
  class: REFERENCE

  subject:
    type: utterance_span
    value: "её"

  predicate: refers_to

  candidates:
    - T17
    - T21

  preferred: T17

  evidence:
    - current_task_context
    - recency

  confidence: 0.81
```

Runtime затем проверяет proposal.

---

## 58. Claim Admission Gate

До попадания в рабочий граф:

```text
Schema
→ provenance exists
→ referenced objects exist
→ scope valid
→ allowed claim class for current step
→ candidate set bounded
→ no forbidden mutation
→ commit
```

Например Skill step `resolve_reference` может создавать:

```text
REFERENCE
HYPOTHESIS
GAP
```

но не:

```text
DECISION
ACTION_JUSTIFICATION
```

Это ограничивается step contract.

---

## 59. Step Contract и допустимые claims

Skill step расширяется:

```yaml
step: resolve_task_reference

executor: llm

allowed_claim_output:
  - REFERENCE
  - HYPOTHESIS
  - GAP

required_input_claims:
  - USER_INTENT

success_condition:
  claim:
    class: REFERENCE
    ambiguity: false

transitions:
  RESOLVED: derive_command
  AMBIGUOUS: clarify
  NONE: not_found
```

Controller не анализирует текст модели.

Он смотрит на валидированное состояние claims.

---

## 60. Transition как функция графа

Вместо:

```python
if llm_output == "FOUND":
```

лучше:

```python
transition = transition_engine.evaluate(
    step_contract,
    graph_view,
)
```

Пример декларации:

```yaml
transition:
  name: RESOLVED

  require:
    claim:
      class: REFERENCE
      status: SUPPORTED

  forbid:
    claim:
      class: CONFLICT
      unresolved: true
```

---

## 61. Preconditions как claims

Перед tool proposal runtime материализует preconditions.

Например:

```text
P1 task exists
P2 task belongs to current user
P3 task state = active
P4 expected revision = current revision
```

P1-P4 строятся кодом из Core/query/policy.

LLM не решает ownership.

Это прямо продолжает существующий принцип архитектуры, где ownership,
transactions и invariants находятся вне AI.

---

## 62. Action Justification Graph

Любой изменяющий tool call должен иметь justification node.

Пример:

```text
C1 USER_INTENT: move task
C2 REFERENCE: "её" = T17
C3 FACT: T17 active
C4 FACT: user owns T17
C5 DERIVED: tomorrow = date X
C6 ASSUMPTION: preserve current clock time
        ↓
AJ1 ACTION_JUSTIFICATION
        ↓
MoveTask
```

Tool Gate получает не только arguments:

```yaml
tool: task.move

arguments:
  task_id: T17
  deadline_at: ...

justification_id: AJ1
```

---

## 63. Action Gate

Перед Tool Gate полезно иметь deterministic Action Gate:

```python
def evaluate_action(action, graph, policy):

    path = graph.justification_path(action.justification_id)

    require(path.intent)
    require(path.target_reference)
    require(path.preconditions)

    forbid(path.unresolved_conflict)
    forbid(path.blocked_claim)

    if action.destructive:
        require(path.confirmation)

    if path.has_speculative_critical_claim:
        return CLARIFY

    return ALLOW
```

Tool Gate после этого по-прежнему проверяет capability, schema, entitlement,
ownership и confirmation.

То есть:

```text
Action Gate
"достаточно ли знания для действия?"

Tool Gate
"разрешено ли физически выполнить действие?"
```

Это две разные границы.

---

## 64. Ambiguity Budget

Не всякая неопределённость требует вопроса пользователю.

Можно формализовать допустимость.

Пример:

```yaml
ambiguity_policy:

  read_only:
    max_candidates: 3
    auto_select_threshold: 0.75

  reversible_write:
    max_candidates: 1
    auto_select_threshold: 0.90

  destructive:
    max_candidates: 1
    require_confirmation: true
```

Таким образом вопрос пользователю появляется не из ощущения LLM:

```text
"кажется, лучше уточнить"
```

а из policy.

---

## 65. Hypothesis Set для неоднозначности

Если несколько interpretations:

```yaml
hypothesis_set:
  id: HS17

  dimension: target_task

  candidates:
    - claim_id: H1
      target: T17

    - claim_id: H2
      target: T21

  resolution_status: unresolved
```

Skill может:

```text
дособрать context
проверить recency
проверить current_task
или запросить clarification
```

---

## 66. Resolver before LLM

Перед semantic resolver используется детерминированный candidate builder:

```text
"эта задача"
 ↓
current task from UI session

"последняя"
 ↓
query ordered by updated_at

"#2026-00417"
 ↓
direct identifier resolution
```

Только когда код не разрешил ссылку однозначно:

```text
bounded candidates → LLM
```

Это снижает свободу модели и расход контекста.

---

## 67. Operation Planning Graph

Для сложных skills можно хранить не только claims, но и plan nodes:

```text
GOAL
OPERATION
PRECONDITION
DEPENDENCY
```

Пример:

```text
Goal: перенести задачу и календарное событие

O1 MoveTask in Core
   ↓ emits event
O2 Calendar projection

```

Но важно:

Google projection не становится обязательным условием успешности Core operation,
поскольку существующая архитектура определяет внешний календарь как projection.

---

## 68. Plan не равен execution authority

LLM может предложить:

```text
O1 query task
O2 move task
O3 notify user
```

Controller преобразует это в candidate plan.

Затем код проверяет:

```text
операции существуют
skill разрешает capability
dependency order допустим
side effects известны
budget не превышен
```

Только после этого plan становится executable.

---

## 69. Dynamic Operation Registry

Чтобы избежать:

```python
if operation == "move_task":
```

используется registry:

```python
operation_registry.register(
    OperationDescriptor(
        id="task.move",
        capability="task.write",
        preconditions=[...],
        side_effect="reversible_write",
        executor=MoveTaskOperation,
    )
)
```

Skill ссылается на `operation_id`.

Controller ничего не знает о внутренностях MoveTask.

---

## 70. Operation Descriptor

```yaml
id: task.move

input_schema: task_move_v2
output_schema: task_v3

capability: task.write

risk_class: reversible_write

preconditions:
  - authenticated
  - owns_resource
  - resource_active
  - revision_current

required_claims:
  - USER_INTENT
  - REFERENCE

effects:
  - changes_core_state
  - emits_domain_event

idempotent:
  strategy: command_id
```

---

## 71. Operation Policy

Одинаковая операция может иметь разные policies.

Пример:

```text
manual UI
AI request
scheduler
admin
```

Но сама Core command остаётся одна.

Policy определяет только входные требования:

```yaml
task.move:

  ai:
    require_reference_resolution: true
    require_action_justification: true

  manual_ui:
    require_reference_resolution: false
```

---

## 72. Observation Ingest

После tool/Core вызова результат превращается в observation claims.

Например:

```yaml
class: OBSERVATION
predicate: command_result
value: conflict

provenance:
  type: TOOL_RESULT
```

Далее rule engine может создать:

```text
C_REVISION_STALE
```

и transition:

```text
refresh_context
```

Модель не обязана сама понимать техническую ошибку из произвольного текста.

---

## 73. Error-to-Claim Mapping

Ошибки нормализуются кодом:

```text
validation
authorization
conflict
external_temporary
external_permanent
internal
```

в соответствующие observations.

Пример:

```text
ConflictError
→ OBSERVATION(resource_revision_changed)
→ invalidate stale claims
→ resolver refresh
→ retry policy
```

---

## 74. Result Validator

После операции проверяется не только schema ответа.

Нужно сопоставить:

```text
expected effect
observed effect
```

Пример:

```text
expected:
Task T17 deadline = X

observed:
Task T17 revision 13 deadline = X
```

Создаётся RESULT claim.

Если expected != observed:

```text
CONFLICT
```

и skill не объявляется завершённым.

---

## 75. Success Condition как graph query

Skill success condition:

```yaml
success:
  require:
    - claim:
        class: RESULT
        predicate: task_deadline
        equals: requested_deadline

  forbid:
    - unresolved_conflict
```

Таким образом успех определяется состоянием, а не фразой модели
`"готово"`.

---

## 76. Claim-based Context Engine

Context recipe может обращаться к claim graph:

```yaml
context_recipe:
  include:
    - active_goal
    - unresolved_hypotheses
    - current_reference
    - blocking_gaps
    - last_tool_observation

  exclude:
    - resolved_intermediate_claims
    - stale_claims
```

LLM получает не всю историю run, а релевантный рабочий срез.

---

## 77. Context Rerank

При необходимости:

```text
score =
  task_relevance
  × unresolved_weight
  × dependency_proximity
  × action_impact
  × freshness
```

Это лучше обычного similarity-only retrieval.

Близкий по embedding claim может быть бесполезен, а precondition непосредственного
следующего действия критичен.

---

## 78. Graph-driven Step Selection

Для сложного skill Step Controller может выбирать следующий шаг по состоянию:

```text
если missing reference
    → resolve_reference

если unresolved datetime
    → resolve_datetime

если critical assumption
    → clarify

если all preconditions ready
    → propose_action

если action completed
    → verify_result
```

Условия находятся в contract/rules.

LLM не выбирает произвольный следующий node workflow.

---

## 79. Operation Budget

В run state:

```yaml
budget:
  llm_calls: 8
  tool_calls: 6
  core_mutations: 2
  clarifications: 2
```

Каждая операция имеет cost.

Planner не может бесконечно создавать новые hypotheses и tools.

---

## 80. Replan

Replan запускается событием:

```text
precondition_failed
tool_conflict
new_user_input
critical_claim_invalidated
budget_pressure
```

Replan не означает «попросить LLM подумать заново обо всём».

Он получает:

```text
current goal
failed operation
blocking claims
allowed operations
remaining budget
```

---

## 81. New User Input во время run

Новое сообщение пользователя создаёт событие:

```text
USER_INPUT_RECEIVED
```

и новые USER_INTENT/CONSTRAINT proposals.

Затем код определяет:

```text
continue current goal
modify current goal
cancel goal
start new goal
```

Это полезнее попытки LLM смешать старую и новую инструкции в одном prompt.

---

## 82. Goal Node

У run должен быть явный Goal:

```yaml
id: G01

type: GOAL

intent: MOVE_TASK

status: active

success_condition: ...
cancel_condition: ...
```

Claims и operations связываются с goal.

Так runtime понимает, зачем вообще исполняется конкретный шаг.

---

## 83. Multiple Goals

Если запрос:

```text
"перенеси задачу на завтра и напомни мне вечером"
```

декомпозиция:

```text
G1 move task
G2 create reminder
```

Dependency:

```text
G2 may_depend_on G1
```

Но каждое изменение проходит свой operation contract.

---

## 84. Goal Graph и Claim Graph

Физически они могут храниться рядом, но логически различаются:

```text
Claim Graph
    состояние знания

Goal/Operation Graph
    состояние исполнения
```

Связи:

```text
claim justifies operation
operation produces observation
observation updates claim
```

Это образует управляемый цикл.

---

## 85. Двухграфовая модель

Практически разумная схема:

```text
EPISTEMIC GRAPH
Source / Observation / Claim / Assumption / Conflict

EXECUTION GRAPH
Goal / Step / Operation / Result

BRIDGE EDGES
justifies
requires
produces
invalidates
```

Это лучше одного универсального графа из сорока типов узлов.

---

## 86. Минимальная реализация Operation Graph

```python
@dataclass
class Goal:
    id: str
    status: str
    intent: str


@dataclass
class Operation:
    id: str
    descriptor_id: str
    status: str
    justification_id: str | None


@dataclass
class OperationResult:
    operation_id: str
    status: str
    observation_ids: list[str]
```

---

## 87. Controller Interface

```python
class StepController:

    async def next(self, run_id):

        state = run_repository.get(run_id)

        graph = claim_graph.view(run_id)

        step = transition_engine.select(
            skill=state.skill,
            current_step=state.current_step,
            graph=graph,
        )

        return await executor.execute(step)
```

Controller не рассуждает о предметной семантике.

---

## 88. Executor Registry

```text
code
llm
tool
query
```

можно расширить:

```text
graph
```

Например:

```yaml
step: verify_preconditions
executor: graph
operation: evaluate_preconditions
```

Для такого шага LLM вообще не вызывается.

---

## 89. Code-first step

Skill должен предпочитать:

```text
code/query/graph
```

если задача решается детерминированно.

LLM используется, когда остаётся semantic ambiguity.

Это делает принцип «если решение надёжно принимает код, его не принимает LLM»
не только декларацией, но свойством workflow engine.

---

## 90. Example: "перенеси ту задачу на завтра"

Полный цикл:

```text
1. Input:
   "перенеси ту задачу на завтра"

2. LLM:
   USER_INTENT = MOVE_TASK

3. Resolver:
   current/recent task candidates = [T17, T21]

4. LLM:
   REFERENCE proposal:
   "ту задачу" → T17
   confidence 0.84

5. Reference policy:
   reversible write threshold = 0.90
   → ambiguity unresolved

6. Runtime:
   clarification required

7. User:
   "про отчёт"

8. Deterministic candidate filter:
   T17.title contains "отчёт"
   unique match

9. Claim:
   REFERENCE "ту задачу" → T17
   status SUPPORTED

10. Context resolver:
    timezone
    current datetime
    T17 current deadline

11. Date resolver:
    tomorrow = 2026-08-29

12. Claim:
    derived date = 2026-08-29

13. Assumption:
    preserve existing task clock time

14. Policy:
    assumption acceptable for reversible move
    or clarification depending configured rule

15. Preconditions from Core:
    exists
    ownership
    active
    revision current

16. Action justification:
    AJ17

17. Action Gate:
    ALLOW

18. Tool Gate:
    capability/schema/policy

19. Core:
    MoveTask

20. Result:
    Task revision incremented

21. Result Validator:
    observed deadline matches requested

22. Goal:
    completed
```

На каждом этапе понятно, что решил код, а что предложила модель.

---

## 91. Example: destructive operation

Запрос:

```text
"удали её"
```

Даже если REFERENCE имеет высокий confidence:

```text
destructive policy
→ explicit target resolution
→ confirmation claim required
```

Graph:

```text
USER_INTENT
REFERENCE
PRECONDITIONS
CONFIRMATION
       ↓
ACTION_JUSTIFICATION
       ↓
DELETE
```

Без `CONFIRMATION` justification path неполон.

LLM не может обойти это формулировкой
`"пользователь явно хотел удалить"`.

---

## 92. Agent Invariants

Добавляются инварианты:

```text
21. LLM создаёт ClaimProposal, но не authoritative fact.

22. Core/query/tool observations имеют более высокий provenance trust,
    чем LLM interpretation.

23. Изменяющая операция имеет ActionJustification.

24. ActionJustification имеет путь к USER_INTENT или системному trigger.

25. Critical preconditions создаются кодом.

26. Unresolved critical ambiguity блокирует mutation.

27. Stale claim не используется для mutation.

28. Tool result обновляет graph через Observation Ingest.

29. Skill success определяется проверяемым state/result,
    а не декларацией LLM.

30. Claim invalidation распространяется на зависимые decisions/actions.

31. Run graph scoped по tenant/user/run.

32. Promotion claims в persistent memory проходит отдельный policy.

33. Planner предлагает operations, registry определяет доступные реализации.

34. Action Gate проверяет достаточность знания,
    Tool Gate проверяет физическое право вызова.

35. Claim Graph не является вторым Core.
```

---

## 93. Дополнение структуры репозитория

Рекомендуемое расширение:

```text
agent/
├── runtime/
│   ├── controller.py
│   ├── transition_engine.py
│   └── run_state.py
│
├── claims/
│   ├── models/
│   │   ├── claim.py
│   │   ├── provenance.py
│   │   ├── edge.py
│   │   └── scope.py
│   ├── graph/
│   ├── registry/
│   ├── rules/
│   ├── propagation/
│   └── views/
│
├── operations/
│   ├── models.py
│   ├── registry.py
│   ├── planner.py
│   ├── action_gate.py
│   └── result_validator.py
│
├── context/
├── skills/
├── tools/
├── validators/
└── memory/
```

---

## 94. Новые contract tests

Добавить:

```text
claim:
    LLM proposal cannot become authoritative directly
    invalid provenance rejected
    stale revision invalidates dependent reference
    critical ambiguity blocks mutation

operation:
    missing justification blocks action
    blocked claim blocks dependent action
    confirmation required for destructive action
    result mismatch prevents skill success

transition:
    graph state selects deterministic next step
    LLM cannot jump to undeclared step

propagation:
    changed fact marks dependent claims dirty
    invalidated reference invalidates pending operation
```

---

## 95. Минимальный этап интеграции в существующий агент

Не нужно сразу реализовывать весь research Claim Graph.

Для операционного агента достаточно начать с:

```text
1. ClaimProposal / Claim separation.

2. Provenance:
   USER_INPUT
   CORE_QUERY
   TOOL_RESULT
   LLM_PROPOSAL
   DERIVATION.

3. Типы:
   USER_INTENT
   REFERENCE
   FACT
   ASSUMPTION
   PRECONDITION
   OBSERVATION
   RESULT.

4. Typed edges:
   supports
   derived_from
   requires
   justifies
   invalidates
   produces.

5. Claim Admission Gate.

6. ActionJustification.

7. Action Gate перед Tool Gate.

8. Observation ingest после каждого tool/Core result.

9. Dirty/stale propagation.

10. Success condition как query по состоянию.
```

Этого уже достаточно, чтобы превратить текущий Skill Runtime из
«LLM идёт по декларативной процедуре» в
«код ведёт процедуру по формализованному состоянию знания».

---

## 96. Порядок разработки дополнения

### Этап A --- модели

Реализовать:

```text
Claim
ClaimProposal
Provenance
ClaimEdge
ClaimStatus
TrustClass
```

Без LLM.

### Этап B --- Run Claim Registry

```text
create
commit proposal
link
invalidate
mark stale
query
```

### Этап C --- Runtime integration

После каждого:

```text
input
resolver
tool result
core result
```

создавать claims/observations.

### Этап D --- Skill transitions

Перевести один skill с строковых outcomes на graph predicates.

Лучший кандидат --- `MoveTask`, поскольку там есть:

```text
intent
reference
datetime
preconditions
mutation
result verification
```

### Этап E --- ActionJustification / Gate

Mutation не выполняется без justification path.

### Этап F --- propagation

Изменение observation/reference делает зависимые decisions dirty.

### Этап G --- остальные skills

После проверки механизма переносить:

```text
Edit
Complete
Delete
Restore
Notes
```

### Этап H --- research extension

Только после стабилизации операционного графа расширять типы:

```text
SOURCE
EVIDENCE
SYNTHESIS
EXTRAPOLATION
CONFLICT
GAP
RECOMMENDATION
```

Так базовая архитектура проверяется на коротких, воспроизводимых операциях,
а не сразу на огромных исследовательских циклах.

---

## 97. Итоговая операционная схема агента

```text
USER
 ↓
GATEWAY
 ↓
AI RUNTIME
 ↓
CLAIM PROPOSALS
 ↓
CLAIM ADMISSION GATE
 ↓
RUN CLAIM GRAPH
 ↓
SKILL / TRANSITION ENGINE
 ↓
ACTION PROPOSAL
 ↓
ACTION JUSTIFICATION
 ↓
ACTION GATE
 ↓
TOOL GATE
 ↓
CORE
 ↓
OBSERVATION
 ↓
RESULT VALIDATOR
 ↓
CLAIM GRAPH UPDATE
 ↓
GOAL / NEXT STEP
```

Ключевой сдвиг:

```text
раньше:
модель → output → validator → действие

после дополнения:
модель → proposal
код → state
код → transition
модель/код → proposal действия
код → justification
код → gate
Core → факт
код → проверка результата
```

Так LLM остаётся сильным семантическим компонентом, но перестаёт быть
неявным владельцем логики исполнения.


