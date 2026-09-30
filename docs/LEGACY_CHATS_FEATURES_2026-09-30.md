# ФИЧИ ИЗ LEGACY-ЧАТОВ (исследовательский анализ)

**Дата:** 2026-09-30
**Источник:** `F:\1\_STRUCTURED\09_LITERATURE\datasets\для изучения\` (2 чата)
- `chat-export-1790789337710.json` — «Академические шаблоны глав» (22 сообщения)
- `chat-export-1790789351306.json` — «Цикл ReAct агента» (54 сообщения)
**Назначение:** формирование фич для ветки `refactor-v2` (Meta-Cycle harness).

---

## 1. Сводка чатов

### Чат 1 «Академические шаблоны глав»
Библиотека риторических шаблонов **T1-T16** (CARS/Swales, Toulmin D-C-W-B-Q-R, Hyland hedging, Gopen&Swan, Bunton, Bazerman) как *последовательности научных утверждений*, а не заголовков. 5 валидаторов (Rhetoric/Logic/Physics/Epistemic/Genre), онтология физического рассуждения (12 классов, Entity≠Role, типизированные рёбра, запрещённые связи), Gap G1-G6, evidence E0-E4, шкала epistemic-глаголов. Затем — Git-подобный Meta-Cycle: Baseline → ErrorSet → clustering → RootCause → Branch → Merge → Clean Replay → Commit.

### Чат 2 «Цикл ReAct агента»
Модель **Adaptive Adversarial Control Loop**: S_t → Generator → Filter → Diagnosis → Controller → Candidate → StateValidator → S_{t+1}. Атака мутирует **политику** (retrieval/contract/prompt/validator), а не только текст. Три уровня устойчивости Invariant > Policy > Tactic с TTL/гистерезисом. Merge = валидируемая гипотеза (clean replay, ΔM, P(ΔM>0)>τ). Legacy = отрицательная память. Внешняя сила обязана сигнализировать «система умирает».

---

## 2. Маппинг: идея → реализовано/пробел

| Идея | Статус | Пробел |
|---|---|---|
| Шаблоны T1-T16 | Пробел | Нет модуля риторических шаблонов |
| 5 валидаторов | Частично | Нет RhetoricalValidity/GenreValidity |
| Типизированные рёбра | Частично | Semantic type vs физ. размерность не выделены |
| Evidence E0-E4 + глаголы | Частично | Нет лестницы E0-E4 |
| Gap G1-G6 | Частично | Нет типизации gap |
| ErrorSet→clustering→RootCause | Частично | Нет clustering ошибок |
| 3 типа веток + checkpoint | Частично | Нет debug-веток/checkpoint-resume |
| Merge после clean replay | Частично | Нет стат. гейта |
| is_significantly_better | Пробел | TD-REF-11 (заглушка) |
| ReAct-аудитор | Реализовано | Правит текст, не политику |
| Attack→RootCause→Intervention | Частично | Нет StateMutationProposal |
| Invariant>Policy>Tactic | Частично | Нет TTL/гистерезиса |
| Candidate State | Пробел | Нет fork-эксперимента |
| PreGenGuard | Частично | Нет guard до генерации |
| Изоляция ≠ независимость | Частично | Нет матрицы изоляции |
| Внешняя сила | Частично | Нет канала деградации LLM |
| E2E на реальной главе | Пробел | Нет приёмочного прогона |

---

## 3. Предлагаемые фичи

### F1 (P0) — StateMutationProposal + Candidate-State gate
**Зачем:** ошибка не имеет права менять глобальное состояние; нужна цепочка ошибка→гипотеза→кандидат→эксперимент→приём/отказ.
**Куда:** state.py, aar.py, debt_cycle.py.
**Элементы:** StateMutationProposal(root_cause, target_variable, old/new, expected_effect, risk, reversibility, validation_plan, delta_budget); CandidateState = fork(SystemState, Delta); promote/reject/archive.
**Готовность:** AAR даёт proposal → кандидат прогоняется; приём только при I(S')=true и ΔS≤B.

### F2 (P0) — Attribution chain + гистерезис
**Куда:** aar.py, health_monitor.py. Пороги N_failure>N_threshold, P(rootcause)>θ, ΔQ>ε.

### F3 (P0) — Merge как атомарный протокол + стат. гейт + clean replay
**Куда:** merge_protocol.py. MergeDecision(accepted|partial|rejected|rolled_back_to); significance_test; pareto_admissible; clean_replay_required.

### F4 (P1) — AcademicTextGrammar: шаблоны T1-T16 + claim type-system
**Куда:** templates.py + validation_engines (RhetoricalValidity, GenreValidity). ClaimType (D,F,C,E,I,R,X,L,H,Q,G,S,M); AllowedTransitions/ForbiddenTransitions; quasi_gap_detector.

### F5 (P1) — ReAct-аудитор как внешняя сила: наблюдения → мутация политики
**Куда:** react_auditor.py, orchestrator.py. AuditObservation; PolicyMutation(retrieval|contract|prompt|validator); связь с V-1 veto.

### F6 (P1) — Legacy как negative-knowledge с PreGenGuard
**Куда:** legacy.py. NegativeKnowledge; pregen_guard(hypothesis)→similar|contradict|known_failed; garbage_collect; growth_bound.

### F7 (P1) — Корреляционный контроль изоляции
**Куда:** branch.py, orchestrator.py. IsolationMatrix {state, context, memory, cache, tool_state, randomness, model_state, dataset, evaluation}; detect_shared_cache.

### F8 (P2) — Канал деградации и контроля ресурсов
**Куда:** health_monitor.py. DriftChannel(monotonic_degradation, oscillation, resource_growth); лимиты {branch_count, compute_budget, merge_rate, legacy_growth}.

---

## 4. Рекомендации по внедрению
1. **P0-трио**: F1 (candidate gate) → F3 (merge-атомарность+значимость) → F2 (гистерезис).
2. **Внешняя сила сразу**: F5 (ReAct → мутация политики + veto).
3. **Содержательный слой**: F4 (AcademicTextGrammar) — замыкает V3.
4. **Приёмочный гейт**: E2E на реальных абзацах nkr_ch1_dom.yaml.
5. **После стабильности**: F6 (PreGenGuard), F7 (изоляция), F8 (сторож деградации).