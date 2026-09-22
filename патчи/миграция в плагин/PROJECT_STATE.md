# Project State — 2026-09-14

## 1. Текущий статус

Harness состоит из трёх peer-модулей и общей инфраструктуры:

- Writer;
- Researcher;
- Coder/code-factory;
- Router / Job-Attempt / orchestration / capabilities / capsules / memory / kanban.

Native OpenCode Plugin является **host integration layer**, а не четвёртым authority-модулем.

## 2. Подтверждённый integrated baseline

Каноническая интегрированная поставка 2026-09-13:

- closure HEAD: `badb5e2526307bf3ebfb4279cfba6a40b7932bf0`;
- code ZIP SHA256: `7d24cd04ea8311d3d028ffa6c2cd25fe5f0c2d18aa69764d1fdce61f23869802`.

Сохранённая acceptance:

- Writer: 31 tests + 15 subtests PASS;
- Researcher full: 588/588 PASS;
- Researcher R4: 111/111 PASS;
- Coder: 5/5 PASS;
- cross-module routing: 2/2 PASS;
- compatibility groups: 136/136 PASS;
- runtime compiler hash: `8910fd61122b450212d5bc459cdb52acdc02aa3cf6d87a37c5eaa3778e3cdfef`;
- capability compiler hash: `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`.

## 3. Windows deployment baseline

Развёртывание `C:\Temp\opencode\harness-deploy` подтвердило deterministic acceptance того же release. `.git` отсутствует намеренно в code-only distribution.

На этом deployment старый CLI-based Tribunal provider был недоступен (`missing:opencode`). Это не дефект deterministic Harness и не научный `OPEN`; это runtime-provider gate.

## 4. Native Plugin P1

По актуализированной документации P1 включает:

- package `packages/opencode-harness-plugin`;
- OpenCode-facing tools `harness_status` и `harness_run`;
- NDJSON full-duplex JSON-RPC bridge через stdio;
- protocol `harness-bridge-rpc/1.0`;
- DTO:
  - `HostContext/1.0`;
  - `WorkspaceRef/1.0`;
  - `SemanticExecutionRequest/1.0`;
  - `SemanticExecutionResult/1.0`;
- reverse RPC при незавершённом родительском запросе;
- deterministic `harness_run` boundary;
- `semantic.execute` как следующий, не сертифицированный production path.

**Важно:** exact commit/tree Native Plugin P1 в доступном reconciliation source не установлен. Поэтому P1 отмечается как `HOSTLESS_IMPLEMENTATION_REPORTED`, а не как новый fully verified integrated release.

## 5. Что пока не подтверждено

- live загрузка Native Plugin в настоящий OpenCode Desktop;
- отсутствие двойной регистрации legacy/native plugin;
- фактическая форма SDK calls на установленной OpenCode версии;
- live `harness_status`/`harness_run`;
- HostContext/WorkspaceRef из реального ToolContext;
- cancel propagation;
- child semantic session;
- read-only recursion isolation;
- structured-output portability;
- production Tribunal через plugin;
- Writer/Coder через единый semantic transport.

## 6. Следующая точка перехода

Сначала Native Desktop P2. Только после него разрешено переключать Tribunal provider binding с CLI на plugin transport.
