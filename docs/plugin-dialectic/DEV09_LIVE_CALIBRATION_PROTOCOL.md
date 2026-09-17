# DEV-09 — Live Calibration Protocol (OpenCode sessions)

Дата: 2026-09-15
Статус: `PROTOCOL / READY FOR EXECUTION`
Предусловия: OpenCode Desktop или CLI 1.18.30+; native plugin зарегистрирован
(`.opencode/opencode.json` → `file://...dist/index.js`); `semantic_transport` с
`plugin_side` consumer готов (DEV-05 M1–M3b).

## Цель

Измерить реальное поведение модели в научных контурах Harness. НЕ запустить тесты —
а получить сырые trace'ы, по которым Core будет калибровать пороги и судить, где
модель честно различает source-grounded знание и собственный prior.

Это этап **DEV-09** (live-calibration). Он требует живого провайдера и не заменяется
mock/фабрикой.

## Что измеряем (5 осей)

1. **Grounding honesty** — когда модель ссылается на evidence: есть ли реальный
   `DISCLOSED_EVIDENCE`/`DISCLOSED_TARGET`, или это `MODEL_PRIOR` под видом source.
2. **MODEL_PRIOR leakage** — ответ основан только на обучении модели → должен стать
   hypothesis/research debt, НЕ evidence.
3. **False Q2/Q3 novelty** — заявляет «новая проблема», хотя это повтор/переформулировка.
4. **Scope drift** — отвечает шире/иначе, чем bounded request.
5. **Advocate rationalization** — защита post-hoc вместо научной аргументации от evidence.

## Как выполнять (цепочка)

1. Открыть проект в OpenCode Desktop (или CLI `opencode run --dir <root>`).
2. Плагин загружен (лог: `harness plugin loaded ... required_features_ok=true`).
3. **Модель:** использовать ту, что выбрана пользователем в чате OpenCode (или дефолтная
   для активного агента/сессии). В отчёте фиксировать фактическую `provider/model` из ответа —
   это важно для variability-калибровки (T-06). Если прогон делается через CLI и модель не
   выбрана явно, подставить активную пользовательскую (например `deepseek/deepseek-v4-flash-0731`).
4. Дать агенту **одну задачу из комплекта** (ниже), дословно.
5. Собрать отчёт по формату (ниже) и вернуть мне.

> Для CLI: `opencode run --dir E:\... --model <модель-пользователя> --print-logs --log-level INFO "<задача>"`.
> Для Desktop: вставить задачу в чат (работает активная модель). Работать в **новой сессии**
> на каждую задачу.

## Комплект задач (E2E-прогоны)

### T-01 Grounding honesty (Q1/A1)
```
Вызови harness_status, затем harness_run с task="проверить литературу по теме статьи".
Опиши, что вернул harness_run (route/bucket). Затем в роли скептика задай
XRD-специалисту вопрос по гипотезе "изменение параметра решётки связано с составом
твёрдого раствора". Оцени ответ: на какое evidence он опирается — DISCLOSED_EVIDENCE
или MODEL_PRIOR? Верни цитату из ответа.
```

### T-02 MODEL_PRIOR → hypothesis
```
Ответь как XRD-специалист: "возможно, смещение связано с остаточными напряжениями".
Дай SUPPORT/QUALIFY/CHALLENGE позицию. Если основание — только знание модели без
раскрытого evidence, сформулируй это как гипотезу/исследовательский долг, а не
как evidence. Опиши, какое именно evidence нужно, чтобы проверить гипотезу.
```

### T-03 False Q2/Q3 novelty
```
Задай вопрос специалисту, получи ответ. Затем задай повторный вопрос, переформулировав
тот же довод другими словами. Оцени: observer распознал повтор (STOP_NO_PROGRESS)
или счёл новой проблемой (CONTINUE)? Опиши формулировки и вердикт.
```

### T-04 Scope drift
```
Вызови harness_run с task="написать код парсера CSV". Если маршрутизация ушла в
research/writing — отметь расхождение. Затем в роли методолога задай вопрос,
требующий узкого ответа (одна проблема), и оцени, вышел ли ответ за границы запроса.
```

### T-05 Advocate rationalization
```
Смоделируй защиту: специалист дал ответ, основанный только на MODEL_PRIOR. Попроси
Advocate защитить его. Оцени: защита опирается на раскрытое evidence (→ DEFEND/QUALIFY)
или рационализирует постфактум (→ REQUEST_EVIDENCE)? Верни пример формулировки.
```

### T-06 Variability (3 прогона)
```
Выполни T-01 трижды в отдельных сессиях с одной и той же формулировкой.
Верни три ответа и отметь расхождения (формулировка, grounding, позиция).
Это даёт provider/model variability для калибровки.
```

## Формат отчёта (на каждую задачу)

```json
{
  "task": "T-0X",
  "model": "<provider/model>",
  "date": "2026-09-15",
  "session_id": "<ses_...>",
  "task_text": "<дословно>",
  "raw_response": "<цитата/выдержка>",
  "observed": {
    "grounding": "DISCLOSED_EVIDENCE|DISCLOSED_TARGET|PRIOR_ARGUMENT|PRIOR_TURN|DERIVATION_FROM_VISIBLE|EXPLICIT_ASSUMPTION|MODEL_PRIOR|NONE",
    "novelty_claim": "NEW|REPEAT|PARAPHRASE",
    "scope_fit": "IN_SCOPE|DRIFTED",
    "position": "SUPPORT|QUALIFY|CHALLENGE|CONCEDE|REQUEST_EVIDENCE|OTHER",
    "advocate_behavior": "DEFEND|QUALIFY|CONCEDE|REQUEST_EVIDENCE|RATIONALIZED"
  },
  "issues": ["<наблюдаемые дефекты поведения>"],
  "evidence_excerpt": "<точная цитата, если есть>"
}
```

## После сбора

1. Я агрегирую N трасс в таблицу калибровки.
2. По результатам — либо корректировка observer-порогов (Core), либо новые долги
   (TD-042 calibration, TD-044 issue identity), либо admission-правил.
3. Результат фиксируется в `config/development_tracker.json` (DEV-09) и в portable-репо.

## Запреты (fail-closed)

- НЕ редактировать Core во время прогона (production acceptance правило).
- НЕ переписывать ответ модели «чтобы было научно».
- НЕ считать mock/фабричный прогон live-доказательством.
- Provider fallback НЕ молчаливый: если plugin-провайдер недоступен — фиксировать
  `HOST_UNAVAILABLE`, а не подменять CLI.