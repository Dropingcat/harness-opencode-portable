# Архитектура модульного ассистента задач и заметок

**Статус:** архитектурная спецификация пилота\
**Назначение:** зафиксировать принципы, границы модулей, контракты и
последовательность разработки так, чтобы система оставалась
работоспособной без LLM, расширялась без переписывания ядра и не
зависела от дисциплины модели.

## 1. Клайм проекта

Система является самостоятельным многопользовательским ядром задач и
заметок. Telegram, web, AI, Google Calendar и иные интеграции являются
подключаемыми входными, интеллектуальными или выходными модулями.

Ключевая формула:

> **COMMAND → CORE → EVENT → MODULE**

LLM не является ядром приложения. Она является опциональным
семантическим сопроцессором, работающим через те же разрешённые
операции, что и пользовательский интерфейс.

## 2. Цели

1.  Дать пользователю простой контур «задачи + заметки» с понятным
    Dashboard.
2.  Обеспечить работу системы без AI: UI, cron, hooks и
    детерминированная логика должны быть самодостаточны.
3.  Сделать Telegram первым gateway и пользовательским frontend.
4.  Позволить подключать внешние выходы: Google Calendar,
    Telegram-уведомления и последующие адаптеры.
5.  Подключать AI как отдельный, отключаемый и потенциально платный
    модуль.
6.  Не позволять LLM определять права, инварианты, жизненный цикл данных
    или произвольный порядок исполнения.
7.  Подготовить многопользовательскую и многоприложенческую архитектуру
    без преждевременного построения собственной инфраструктуры
    календарей и уведомлений.
8.  Сохранить полную трассируемость действий для диагностики,
    восстановления и будущего анализа поведения.

## 3. Не-цели пилота

Пилот не должен: - становиться собственной заменой Google Calendar или
Telegram; - строить полноценный двусторонний календарный sync без
необходимости; - физически удалять пользовательские задачи обычными
пользовательскими командами; - давать LLM SQL, shell, административные
операции или произвольный API; - превращать всю бизнес-логику в YAML; -
строить универсальный workflow-engine раньше, чем он действительно
понадобится; - зависеть от доступности LLM для штатной работы.

## 4. Принципы проекта

### P1. Core --- источник истины

Задачи, заметки, состояния, права и история принадлежат Core. Внешние
сервисы получают представление данных или исполняют выходное действие.

### P2. AI --- вход, а не фундамент

Удаление AI-модуля не нарушает CRUD, Dashboard, cron, hooks, архивы,
авторизацию и интеграции.

### P3. Код определяет допустимость

Промпт может объяснять модели локальную задачу, но не является
механизмом безопасности.

> LLM предлагает действие. Код определяет допустимые действия. Core
> выполняет. Audit фиксирует.

### P4. Одна операция --- один Core API

Telegram UI, web, voice, AI и automation не имеют отдельных путей
изменения данных.

### P5. Три типа связей

Между коробками предпочтительно оставить три семантики: - `COMMAND` ---
запрос на изменение; - `QUERY` --- чтение; - `EVENT` --- сообщение о
состоявшемся факте.

Появление четвёртого неформального канала требует архитектурного
обоснования.

### P6. Hardcode invariants, configure policies, declare workflows, register implementations

В коде жёстко остаются безопасность, tenant isolation, транзакции,
аудит, idempotency и schema validation. Политики конфигурируются.
Процедуры skills декларируются. Реализации подключаются через registry.

### P7. Никакого скрытого destructive CRUD

`completed` и `deleted` --- состояния/архивы. Физическое стирание
относится к отдельной административной retention-процедуре.

### P8. Любое нестабильное UI-состояние имеет путь домой

Каждый frontend реализует `HOME`, `BACK`, `CANCEL`, `RECOVER`.

### P9. Минимально необходимый контекст

Модель получает только данные, необходимые текущему шагу. Не «пусть сама
найдёт, что важно».

### P10. Модель не должна догадываться о процедуре

Skill уже выбран, инструкция уже выбрана, инструменты уже ограничены,
контекст уже собран, следующий допустимый переход определён
контроллером.

### P11. Модуль можно отключить

Отказ Google, Telegram notification или AI не должен разрушать Core.

### P12. Наблюдаемость является частью архитектуры

Business events, audit и technical logs различаются и имеют разные
назначения.

## 5. Верхнеуровневая архитектура

``` text
                         USER
                          |
                  Telegram Gateway
                    /           \
             Manual UI        AI Module*
                    \           /
                     Tool/API Gate
                          |
                    +-----v-----+
                    |   CORE    |
                    | tasks     |
                    | notes     |
                    | auth      |
                    | hooks     |
                    | cron      |
                    | audit     |
                    +-----+-----+
                          |
                        EVENTS
             +------------+------------+
             |                         |
      Google Calendar            Telegram Notify
             |                         |
          external                  external

* optional / entitlement-controlled
```

Административная плоскость существует отдельно: пользователи,
entitlement, сервисные credentials, модули, версии, health, audit,
migrations.

## 6. Домен Core

### 6.1 Task

Основные поля: - глобальный технический ID; - `tenant_id`, `user_id`; -
человекочитаемый номер пользователя за год; - title; - body; - deadline
nullable; - lifecycle state; - created/updated/completed/deleted
timestamps; - tags.

Состояния: - `active`; - `completed`; - `deleted`.

`overdue` не хранится как независимое состояние:

``` text
active && deadline < now => overdue
active && deadline >= now => upcoming
active && deadline == null => no_deadline
```

### 6.2 Note

Минимум: - active; - deleted.

Архивацию можно добавить отдельно, не смешивая её с удалением.

### 6.3 Tags

Нормализованные `tags` + relation table. Не строка с запятыми.

## 7. Dashboard

Рабочие выборки: - Просроченные; - Предстоящие; - Без срока; -
Выполненные; - Удалённые; - заметки.

Быстрые операции задачи: - выполнить; - перенести deadline; -
редактировать; - удалить в архив удалённых; - восстановить / reopen по
контексту.

Dashboard является query/read-model, а не отдельным владельцем данных.

## 8. Core command layer

Минимальные команды:

``` text
CreateTask
EditTask
CompleteTask
ReopenTask
MoveDeadline
DeleteTask
RestoreTask

CreateNote
EditNote
DeleteNote
RestoreNote

SetRoute
RemoveRoute
```

Контракт исполнения:

``` text
Command
  -> Authenticate/Authorize
  -> Validate
  -> Transaction
  -> Execute
  -> Domain Event
  -> Audit
  -> Outgoing Hooks
```

Каждая изменяющая команда поддерживает `request_id` и там, где
требуется, `idempotency_key`.

## 9. Многопользовательская изоляция

Все пользовательские данные имеют `tenant_id` и `user_id`.

Недопустимо:

``` sql
SELECT * FROM tasks WHERE id = ?
```

Допустимый принцип:

``` sql
SELECT *
FROM tasks
WHERE tenant_id = ?
  AND user_id = ?
  AND id = ?
```

Лучше инкапсулировать scope в repository/context, чтобы разработчик не
мог случайно «забыть WHERE».

LLM никогда не передаёт `user_id` для пользовательской операции.
Identity добавляет gateway/tool gate из авторизованного контекста.

## 10. Авторизация и сервисные identities

Пользовательский контур:

``` text
request -> authenticate -> user_context -> authorize -> command
```

`user_context` содержит как минимум tenant, user, session, source,
permissions, locale/timezone.

Сервисный контур использует отдельные identities: - core worker; -
Google adapter; - Telegram gateway/worker; - AI runtime; - admin
service; - backup/migration service при необходимости.

Не использовать один всевластный ключ приложения.

Credentials внешних сервисов хранятся через `credential_ref`; секрет не
является обычным полем пользовательской таблицы.

## 11. Модули и capabilities

Технический registry:

``` text
modules
- code
- type
- version
- enabled
- config_ref
```

Типы: - INPUT/GATEWAY; - INPUT_PROCESSOR; - OUTPUT; - INTERNAL/INFRA.

Пользовательское включение модуля отделено от системной доступности.

Рекомендуется связывать skills не с брендами, а с capabilities:

``` text
calendar.publish_event -> google_calendar_adapter
semantic.extract_datetime -> configured_llm_provider
notify.message -> telegram_notify_adapter
```

Это позволяет менять реализацию без изменения skill.

## 12. Telegram Gateway

Telegram --- первый frontend/gateway, но не владелец бизнес-логики.

Два режима: 1. детерминированный кнопочный UI; 2. conversational input
через AI-модуль, если он разрешён.

Сессия frontend хранит: - current screen; - current resource; -
operation; - draft; - page; - expiry.

Стабильные состояния: `HOME`, `DASHBOARD`, `TASK_VIEW`, `SETTINGS`.\
Transient: create/edit/move deadline и т.п.

Каждый экран имеет детерминированные `HOME`, `BACK`, `CANCEL`.
Ошибка/stale callback/invalid session приводит к audit + очистке
transient state + `HOME`.

Старые Telegram callback должны повторно проверять session, ownership,
resource state и допустимость операции.

## 13. Выходные модули

### 13.1 Google Calendar

Это выход, а не источник доменной истины.

Пилот предпочтительно односторонний:

``` text
Core -> Google Calendar
```

Core публикует события, адаптер реагирует на них. Если Google
недоступен, локальная задача не теряется.

Хранится только mapping/sync metadata: task, provider, external event
ID, target calendar, status, timestamps.

Двусторонний sync откладывается до появления реального требования,
поскольку он немедленно создаёт конфликты удаления, переноса,
конкурентных изменений и ownership.

### 13.2 Telegram notifications

Тонкий выходной адаптер. Core/cron генерирует событие, модуль отправляет
сообщение. Не требуется строить собственную платформу уведомлений.

### 13.3 Будущие выходы

Outlook, Nextcloud, email, webhook и прочее подключаются по
capability/event contract.

## 14. Cron и hooks без AI

Core обязан выполнять детерминированные процедуры:

``` text
cron -> query condition -> hook/command -> event -> output adapter
```

Например приближение deadline может породить событие для
Telegram/Calendar без участия LLM.

Hooks не должны содержать скрытую бизнес-логику. Их роль: - собрать
данные; - вызвать зарегистрированную процедуру; - передать событие; -
выполнить техническое связывание.

## 15. AI как опциональный модуль

AI-модуль доступен только при сочетании: - system module enabled; - user
module enabled; - active entitlement.

Пользователь видит простую функцию «AI assistant: доступен/включён».
Provider keys, model routing и инфраструктурные настройки находятся у
администратора.

`user_entitlements` должны поддерживать: - module; - state; -
valid_from; - valid_until; - granted_by; - reason/source.

Сегодня entitlement может выдавать администратор. Позже payment
module/webhook подтверждает оплату и выдаёт/продлевает то же право.
Платёжная логика поэтому не встраивается в AI runtime.

Окончание AI entitlement не блокирует доступ пользователя к его задачам
и заметкам.

## 16. AI runtime: не «гигантский промпт»

``` text
AI MODULE
├── LLM provider/runtime
├── ReAct Controller
├── Skill Registry
├── Contracts
├── Context Engine
├── Prompt Renderer
├── Memory
├── Tool Registry/Gate
├── Hooks
├── Validators
└── Runtime Audit
```

LLM является семантическим сопроцессором. Циклом управляет controller.

Не:

``` text
while model_wants:
    think()
    tool()
```

А:

``` text
controller.next_step(state)
-> build_context(step)
-> render_prompt(step)
-> call_llm()
-> validate_schema()
-> validate_transition()
-> optional tool gate
-> update state
-> next_step()
```

## 17. Skills

Skill --- исполняемый процедурный пакет, а не эссе для модели.

Он задаёт: - triggers/intents; - entrypoint; - required/optional data; -
steps; - executor каждого шага (`code`, `llm`, `tool`); - context
recipe; - allowed tools/capabilities; - output schema; - transitions; -
success condition; - fallback/error route; - version.

Движок не содержит `if skill == create_task`. Он загружает skill из
registry и исполняет общий контракт.

## 18. Context Engine: «положить информацию под действие»

Это один из центральных принципов AI-модуля.

Каждый шаг имеет `context_recipe`. Контекст подтягивается автоматически
перед действием.

Пример для извлечения относительной даты: - raw input; - current
datetime; - timezone; - date rules; - daypart defaults, только если они
понадобились.

Для разрешения ссылки на задачу: - raw input; - текущий UI context; -
ограниченный список кандидатов; - релевантные task IDs/titles.

Модель не получает весь профиль «на всякий случай».

### Conditional context

Контекст может подключаться декларативно:

``` text
IF relative_datetime
  include current_time, timezone

IF ambiguous_daypart
  include daypart_policy

IF multiple_task_candidates
  include bounded_candidate_list

IF destructive_action
  include confirmation_policy
```

Контекстная policy определяет, что разрешено увидеть. Renderer
определяет, как это представить конкретной модели.

Если модели нужен дополнительный контекст, она возвращает ограниченный
`ContextRequest`; Context Gate проверяет, разрешён ли такой resolver
текущему skill/step.

## 19. Prompt-light и динамические шаблоны

Промпт не является хранилищем системных правил.

Сборка:

``` text
BASE_LIGHT
+ SKILL_FRAGMENT
+ STEP_FRAGMENT
+ CONDITIONAL_FRAGMENTS
+ LIVE_CONTEXT
+ TOOL/OUTPUT CONTRACT
```

Шаблон содержит: - локальную роль; - objective текущего шага; -
предоставленные данные; - разрешённые действия; - локальные
ограничения; - output schema; - допустимые результаты/переходы.

Prompt fragments и recipes версионируются и тестируются.

Правила доступа, ownership и транзакционные инварианты не дублируются в
prompt как средство защиты: они физически исполняются кодом.

## 20. Tool Gate

Модель видит только атомарные инструменты текущего skill/step.

Например: - create/read/list task; - edit title/body; - move deadline; -
complete/reopen/delete/restore; - операции с note; - dashboard query.

Не выдаются SQL, shell, arbitrary HTTP/API и admin actions.

Tool contract описывает input/output, preconditions, side effects,
idempotency и capability.

`user_context` Tool Gate добавляет самостоятельно. Модель не выбирает
чужого пользователя.

Перед исполнением: 1. schema validation; 2. current state validation; 3.
ownership/permissions; 4. policy; 5. confirmation rule, если требуется;
6. Core command.

## 21. Memory

Разделить минимум на: - `working_memory` --- только текущий run; -
`session_memory` --- UI/draft/current resource; - `user_memory` ---
устойчивые настройки, которые разрешено использовать; - будущий
behavioral/profile layer --- отдельно от CRUD.

Долговременный профиль не попадает в каждый prompt автоматически. Его
использование требует явного context recipe/resolver.

## 22. Гибкость без хрупкости

Движок должен быть универсальным, а изменяемые правила вынесены из
центрального control flow.

Нужны registries: - SkillRegistry; - ToolRegistry; - PolicyRegistry; -
ContextResolverRegistry; - HookRegistry; - PromptFragmentRegistry; -
Capability/ModuleRegistry.

Разделение: - **Mechanism**: как гарантированно работает система ---
код; - **Policy**: что разрешено при данных условиях ---
конфигурация/декларативное правило; - **Workflow**: последовательность
шагов --- skill contract; - **Implementation**: конкретный
provider/adapter --- registry/plugin.

Не следует делать конфигурируемыми tenant isolation, audit append-only,
transaction boundaries и базовую authorization model.

## 23. Events, audit и logs

### Domain event log

Факты предметной области: TASK_CREATED, TASK_EDITED, DEADLINE_CHANGED,
TASK_COMPLETED, TASK_REOPENED, TASK_DELETED, TASK_RESTORED и аналоги
notes/routes.

Полезен для истории, интеграций и будущей аналитики поведения.

### Audit log

Фиксирует все значимые изменения и административные действия: actor,
source, resource, before/after/diff, request/run ID, versions,
result/error.

Audit append-only. Для объёма: hot storage + недельные/месячные
read-only archives, а не слепое удаление.

Особенно подробно аудитируются migrations: какая запись, какое поле,
before/after, причина и итоговая статистика.

### Technical log

Ошибки, latency, service, stack/context, health. Не смешивать с
бизнес-историей.

### AI runtime trace

Дополнительно: - RUN_STARTED; - SKILL_SELECTED; - STEP_STARTED; -
CONTEXT_BUILT; - LLM_RETURNED; - OUTPUT_VALIDATED; - TOOL_REQUESTED; -
TOOL_EXECUTED; - STEP_COMPLETED; - RUN_COMPLETED/FAILED.

Это позволяет локализовать ошибку до
resolver/prompt/model/validator/tool, а не списывать всё на «LLM что-то
придумала».

## 24. Versioning

Раздельно версионировать: - application; - DB schema; - skill; -
contract; - prompt fragment/base; - tool schema; - model
configuration; - module/adapter.

AI run и migration audit сохраняют фактические версии, использованные
при исполнении.

Активный run не должен внезапно менять workflow из-за обновления skill
посередине процедуры.

## 25. Администрирование

Минимальная admin surface: - users/status/sessions; - modules; - user
module enablement; - entitlements and validity periods; - service
identities; - provider credentials status; - integrations; -
queues/jobs; - health; - application/DB/module versions; - migrations; -
audit/system/AI traces.

Админский UI может быть утилитарным. Его задача --- диагностика и
управление, а не презентация.

## 26. Обработка ошибок и деградация

Требуемая деградация:

  -----------------------------------------------------------------------
  Отказ                               Поведение
  ----------------------------------- -----------------------------------
  LLM/API недоступны                  ручной Telegram UI и Core работают

  AI entitlement истёк                AI отключён, данные пользователя
                                      доступны

  Google недоступен                   задача сохраняется, внешний выход
                                      фиксирует ошибку

  Telegram notification не отправлен  Core state не откатывается

  stale UI callback                   действие отклоняется, audit,
                                      возврат в стабильный UI

  invalid LLM output                  tool не вызывается

  повтор запроса                      idempotency предотвращает дубль

  ошибка migration                    фиксируется до уровня записи/поля;
                                      миграция имеет контролируемый
                                      статус
  -----------------------------------------------------------------------

## 27. Основные зазоры и места будущего решения

1.  **Одно- или двусторонний Calendar sync.** Пилот: однонаправленный.
    Двусторонний потребует conflict policy.
2.  **Очередь/доставка событий.** На пилоте допустима простая durable
    outbox/job queue; интерфейс должен позволять заменить реализацию.
3.  **Policy DSL.** Не создавать сложный язык заранее. Начать с
    ограниченной схемы условий и зарегистрированных predicates.
4.  **Skill DSL.** Аналогично: декларативные transitions и references,
    но сложные вычисления остаются кодовыми handlers.
5.  **Payment verification.** Пока entitlement выдаётся admin; payment
    module позже вызывает тот же EntitlementService.
6.  **Web frontend.** Подключается к тому же Query/Command API; не
    переносит Telegram-specific navigation в Core.
7.  **Behavioral/Human OS.** Event history пригодна как сырьё, но
    inference/profile слой не должен загрязнять CRUD и автоматически
    управлять задачами.
8.  **Модельный fallback/routing.** Должен быть реализацией semantic
    capabilities, а не условием внутри каждого skill.
9.  **Retention/legal erasure.** Отдельный административный процесс; не
    путать с пользовательским Deleted.
10. **Voice/STT.** Входной адаптер перед AI/skill router; Core не знает,
    был ввод голосовым или текстовым.

## 28. Последовательность разработки

### Этап 0. Контракты и инварианты

До UI: 1. зафиксировать domain entities и lifecycle; 2.
UserContext/tenant boundary; 3. Command/Query/Event envelopes; 4. error
model; 5. idempotency; 6. audit/event contracts; 7. module/capability
registry interfaces.

**Зачем:** это швы системы. Если их менять после появления Telegram,
Google и AI, верёвочки действительно начнут путаться.

### Этап 1. Самодостаточный Core

Реализовать DB migrations, repositories, Task/Note services, state
transitions, tags, Dashboard queries, domain events и audit.

**Критерий:** полный жизненный цикл задачи проходит тестами без
Telegram, Google и LLM.

### Этап 2. Auth и multi-user

Sessions/identity, authorization middleware, tenant-scoped repositories,
service identities.

**Критерий:** cross-user access невозможен через API и покрыт
отрицательными тестами.

### Этап 3. Telegram Gateway без AI

Dashboard, create/edit/complete/delete/restore, FSM навигации, drafts,
HOME/BACK/CANCEL/RECOVER.

**Критерий:** пользователь полноценно работает только кнопками/формами.

### Этап 4. Cron/hooks и event delivery

Простой scheduler, hook registry, durable event/outbox/job mechanism.

**Критерий:** Core выполняет временные процедуры и доставляет события
без агента.

### Этап 5. Выходные адаптеры

Google Calendar и Telegram notifications.

**Критерий:** отказ внешнего API не нарушает локальный transaction;
ошибка видима и повторяема.

### Этап 6. Module/admin plane

Module registry, user_modules, credentials references, entitlement
service, admin UI/API, health/version/migrations.

**Критерий:** модуль можно включить/отключить системно и для конкретного
пользователя без изменения кода Core.

### Этап 7. AI runtime skeleton

Controller, registries, contracts, context engine, prompt renderer, tool
gate, validators, runtime trace. Сначала FakeLLM.

**Критерий:** scripted/fake model проходит workflows детерминированно;
запрещённый tool невозможно вызвать физически.

### Этап 8. Первые skills

Начать с: 1. `create_task`; 2. `resolve/list task`; 3. `move_deadline`;
4. `complete/reopen`; 5. note creation/edit.

Каждый skill имеет fixtures и failure cases.

### Этап 9. Реальная LLM

Provider adapter + semantic capabilities. Prompt-light fragments и
context recipes. Ограниченные budgets/retries/timeouts.

**Критерий:** смена provider не требует изменения Core или domain skill.

### Этап 10. AI entitlement

AI подключается как пользовательский модуль. Admin выдаёт право на
период.

### Этап 11. Payment module

Payment verification не выдаёт права напрямую в UI, а вызывает
EntitlementService. Это позволяет менять платёжного провайдера
независимо.

### Этап 12. Web и дальнейшие модули

Только после стабилизации Core contracts. Web использует тот же API, но
собственную presentation/navigation state machine.

## 29. Тестовая стратегия

Для Core: - state transitions; - ownership; - transaction rollback; -
idempotency; - concurrent updates; - migrations; - restore/reopen
semantics.

Для каждого skill: - happy path; - missing context; - ambiguous input; -
invalid LLM schema; - tool failure; - forbidden action; - stale state; -
repeated command; - context resolver failure.

Инвариантные тесты: - AI не обращается к чужому resource; - invalid
model output не достигает Core; - model-selected user identity
невозможен; - повтор command ID не создаёт дубль; - disabled module не
получает события/commands; - отменённый draft не меняет domain state; -
внешний adapter не способен изменить Core в обход разрешённого command
path.

Отдельно тестируется состав контекста: нужные fragments присутствуют,
лишние чувствительные данные отсутствуют.

## 30. Что было упущено и добавлено в спецификацию

### Concurrency / optimistic locking

Task должен иметь version/revision. Edit принимает expected version. Это
предотвращает тихое перетирание изменений Telegram, AI и будущего web.

### Time semantics

Хранить timezone пользователя отдельно; timestamps --- в однозначном
формате. Относительные даты разрешаются с явным
`current_time + timezone`. Иначе «завтра» быстро превращается в
философскую категорию.

### Resource limits

AI run должен иметь пределы шагов, tool calls, context size, времени и
стоимости. Бесконечный ReAct loop не является функцией продукта.

### Circuit breakers

Повторно падающий внешний adapter или LLM provider не должен создавать
шторм retries.

### Backpressure

Очередь должна иметь пределы и retry/dead-letter policy, пусть сначала
простые.

### Data minimization

Context Engine является также privacy boundary: AI получает только
необходимые поля. Секреты интеграций в LLM context не попадают никогда.

### Reproducibility

AI trace хранит не скрытые рассуждения модели, а наблюдаемые входные
contracts/context references, outputs, tool calls, versions и
результаты. Этого достаточно для инженерной диагностики.

### Feature flags

Экспериментальные modules/skills можно включать ограниченной группе без
ветвления Core.

## 31. Итоговая архитектурная граница

``` text
                    PRESENTATION / INPUT
                 Telegram | Web | Voice
                           |
                    optional AI
                           |
                     COMMAND/QUERY
                           |
        =========================================
                         CORE
        identity | policy | domain | transactions
        hooks | cron | events | audit | registries
        =========================================
                           |
                         EVENT
                           |
              EXTERNAL OUTPUT ADAPTERS
          Calendar | Telegram | future modules
```

Главный критерий качества архитектуры:

> **Новая коробочка должна подключаться через известный контракт. Для её
> появления не должны переписываться соседние коробочки.**

А для AI:

> **Если код уже знает, что должно произойти дальше, модель не принимает
> это решение.**

Это оставляет LLM там, где она действительно сильна: неоднозначный
человеческий ввод, семантика, классификация, извлечение и ограниченное
планирование. Всё, что можно выразить детерминированным правилом,
остаётся детерминированным.
