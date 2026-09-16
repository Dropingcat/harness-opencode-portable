# Harness OpenCode Plugin — Task Tree

Обновлено: 2026-09-14.
Источник архитектуры: `патчи/миграция в плагин/ревью/OPENCODE_NATIVE_PLUGIN_P1_ARCHITECTURE.md`,
`патчи/миграция в плагин/HARNESS_OPENCODE_INTERFACE_CONTROL.md`.

Правило из ревью: **нельзя смешивать hostless, focused subset и full-suite counts**.
`LIVE_CERTIFIED` достижим только через настоящий OpenCode host.

## Легенда

- `[x]` — сделано и подтверждено тестами/evidencе.
- `[ ]` — TODO.
- `(BLOCKED)` — требует внешнего условия (live OpenCode host, credentials).

---

## 1. Hostless Core (не зависит от OpenCode)

```
1.1  DTO-контракты                              [x]  P1: HostContext/WorkspaceRef/SemanticExecutionRequest/Result
1.2  JSON Schema для 4 контрактов                [x]  schemas/*.json
1.3  harness-bridge-rpc/1.0 NDJSON full-duplex   [x]  src/bridge + core/bridge_peer.py
1.4  reverse RPC (parent pending + reverse call) [x]  bridge.reverse_echo_test
1.5  HostAdapter / normalize ToolContext         [x]  src/host/types.ts
1.6  Host feature probes                         [x]  src/host/probe.ts (exact SDK 1.18.16 call-shape)
1.7  Writer/Researcher/Coder regression          [x]  Researcher 590+2; compilers PASS
```

## 2. Plugin surface (P1)

```
2.1  harness_status                             [x]  src/tools/harness_status.ts
2.2  harness_run (детерминированная маршрутизация) [x]  src/tools/harness_run.ts
2.3  Plugin entry (index.ts)                    [x]  tools + forbidden-tool guard + degrade path
2.4  Installer (project/global plugin dir)      [x]  core/install_plugin.py
2.5  Doctor (plugin-aware)                      [x]  core/doctor.py
2.6  host_integration_policy.json (schema 2.0)  [x]  config/host_integration_policy.json
2.7  compatibility/opencode/1.18.16.json        [x]  NOT_LIVE_CERTIFIED semantic
```

## 3. Тесты P1

```
3.1  TS bridge/fake-host tests                 [x]  8/8 PASS (protocol, host types, Python-peer E2E,
                                                        full-duplex reverse, missing-method)
3.2  Python plugin factory tests               [x]  4/4 PASS (dist tools, bridge peer hello/status/run,
                                                        doctor, installer)
3.3  typecheck (tsc --noEmit)                  [x]  PASS
3.4  build (dist/)                             [x]  PASS
```

## 4. Live P2 — настоящий OpenCode host (DONE на движке 1.18.30)

```
4.1  installer -> project plugin dir           [x]  .opencode/plugins/opencode-harness-plugin.ts
4.2  plugin load in real OpenCode 1.18.30      [x]  "harness plugin loaded ... required_features_ok=true"
4.3  harness_status виден и вызван моделью     [x]  live tool_use, вернул core status JSON
4.4  harness_run виден и вызван моделью        [x]  live tool_use, routed через Python core resolve()
4.5  HostContext/WorkspaceRef из реального ToolContext [x]  session/message/agent/directory/worktree
4.6  doctor + HostCapabilitySnapshot           [ ]  (doctor скрипт готов; live snapshot = logs)
4.7  legacy plugin НЕ загружен одновременно    [ ]  (M0/RED-1 rule; legacy жив в global config)
4.8  certification record v1.18.30             [x]  compatibility/opencode/1.18.30.json LIVE
```

Примечание: live-проверка выполнена через OpenCode CLI 1.18.30 native (тот же движок/плагинный механизм,
что и Desktop). Остаток: повторить в Desktop GUI + зафиксировать live HostCapabilitySnapshot и отсутствие legacy.

## 5. Semantic P3 — read-only semantic.execute

```
5.1  generic read-only worker (no harness_* tools, no mutating tools) [x]  tools: {} in child prompt
5.2  child session: create -> prompt -> abort (SDK v1 session API)   [x]  live session.created + prompt
5.3  timeout/cancel; auth failure; recursion isolation; credentials host-local [x] unit-test timeout->abort
5.4  structured output (optional, Core revalidated)                   [x]  structured_output.text
5.5  negative tests: malformed output, host unavailable              [ ]  (partially: BAD_SCHEMA unit)
5.6  semantic gate flag HARNESS_SEMANTIC_ENABLED                     [x]  tool absent unless Core enables
```

## 6. Tribunal P4 — plugin transport

```
6.1  plugin provider candidate (priority 120)     [x]  PluginBridgeProviderTransport (TribunalProviderTransport protocol)
6.2  binding selects runtime tool semantic.execute [x]  Q1 E2E: READY binding, runtime_tool=semantic.execute
6.3  Q1 через plugin bridge + Core admission      [x]  execute_question COMPLETED, InquiryTurn materialized
6.4  A1/answer через plugin transport             [x]  execute_answer COMPLETED, ArgumentArtifact QUALIFY, graph REPLIES_TO
6.5  3 variability runs                            [ ]
6.6  Q2 question-on-answer (deterministic)          [x]  admitted issue -> DQC/RPB/TEX -> IQT/PER
6.7  Live Q1/A1/Q2 через Desktop и stdio bridge     [ ]
6.8  A2 + observer: повтор/новизна/исследование     [x]  deterministic, три сценария
6.9  Q3 bounded follow-up (opt-in)                  [x]  DialecticPolicy.allow_bounded_followup; см. docs/plugin-dialectic/Q3_BOUNDED_FOLLOWUP_CONTRACT.md
```

Уточнение evidence (2026-09-15): тест `test_plugin_transport_q1_e2e.py` проверяет
**Q1+A1+Q2** с настоящим Core и фиктивным semantic callback. Он не запускает
Desktop, модель или stdio bridge. Provider authority/preflight в нём — тестовые.
После A1 Core допускает новую проблему, создаёт Q2 для методолога и сохраняет
связи с ответом A1, проблемой, DQC/RPB/TEX и receipt PER. Проверяются material
второго вопроса и сохранение receipt; Q1/A1 admission остаётся частью сценария.
После A2 проверены три исхода по текущему Core: повтор -> STOP_NO_PROGRESS,
новая неблокирующая проблема -> STOP_DEPTH_LIMIT, запрос недостающих
доказательств -> REQUEST_LOCAL_RESEARCH. A2 получает материализованный Q2,
сохраняет parent link, проходит graph admission и создаёт PER.
Это соответствует исходному `RESEARCHER_R4_4_DIALECTIC_OBSERVER_ARCHITECTURE.md`
(§11–12) и `decide_dialectic_control`: новизна необходима, но не отменяет
лимиты. Сравнение содержательного уровня Q3 с Q2 и разрешение Q3 по этому
критерию пока не реализованы; нужны отдельный контракт и тесты observer.
Осталось: реальная регистрация provider и live-цикл через bridge,
затем 3 variability runs. Зелёный callback-тест не закрывает live P4.

## 7. Convergence P5 — Writer/Coder через единый transport

```
7.1  Writer draft/repair через SemanticExecutionRequest/Result
7.2  Coder worker/reviewer через тот же transport
7.3  CLI/legacy launchers остаются explicit fallback (transport=opencode_cli_legacy)
```

## 8. Certification P6+ / legacy retirement

```
8.1  per-version compatibility matrix (clean install/upgrade/rollback)
8.2  retire legacy plugins/tool-skill-contract-router.ts (after 2 certified releases)
8.3  OPENCODE_BIN/OPENCODE_SESSION_DB -> optional legacy only
8.4  health_check -> plugin-aware doctor
```

---

## Критический путь

```
1 (Hostless) -> 2 (P1) -> 3 (tests) -> 4 (live P2) -> 5 (semantic P3)
            -> 6 (Tribunal P4) -> 7 (convergence P5) -> 8 (certification)
```

Сейчас завершены блоки 1–3 (P1, hostless). Следующий обязательный gate — блок 4 (live P2).
До его прохождения `semantic.execute` не считается production-ready.

## Текущий статус по документу PROJECT_STATE

- `native_plugin_p1.status = HOSTLESS_IMPLEMENTATION_REPORTED` — теперь соответствует фактическому коду в репозитории.
- `live_desktop_certified = false` — ждёт P2.
- `exact_commit = NOT_ESTABLISHED` — будет зафиксирован после коммита P1.
