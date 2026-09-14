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

## 4. Live P2 — настоящий OpenCode host (BLOCKED: нужен live OpenCode)

```
4.1  installer -> project plugin dir           [ ]
4.2  restart OpenCode; tools visible           [ ]  harness_status / harness_run
4.3  doctor + HostCapabilitySnapshot           [ ]
4.4  live probe: session.create/prompt/abort   [ ]
4.5  legacy plugin НЕ загружен одновременно    [ ]  (M0/RED-1 rule)
4.6  certification record v1.18.16 -> LIVE     [ ]
```

## 5. Semantic P3 — read-only semantic.execute (после 4)

```
5.1  generic read-only worker (no harness_* tools, no mutating tools)
5.2  child session: create -> prompt -> abort (SDK v1 session API)
5.3  timeout/cancel; auth failure; recursion isolation; credentials host-local
5.4  structured output (optional, Core revalidated)
5.5  negative tests: malformed output, host unavailable
```

## 6. Tribunal P4 — plugin transport (после 5)

```
6.1  plugin provider candidate (priority 120)
6.2  fresh preflight -> new RPB lineage (no silent CLI fallback)
6.3  Q1/A1/Q2/A2 + grounding + graph admission через plugin bridge
6.4  conditional Advocate (DEFENSE/ADC)
6.5  3 variability runs
```

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