# Researcher Pipeline Run — 2026-09-17

Статус: `RUN COMPLETE / ARTIFACTS SAVED`
Маршрут: `academic-research` (strict), policy_hash `8910fd…`
Модель: `polza/deepseek/deepseek-v4-flash-0731` (калибровочные данные)

## Ход прогона

1. `harness_run(route=academic-research, task=…)` — маршрут подтверждён:
   2 capsules, 12 skills, 5 tools, guard untrusted (arxiv/openalex/research/extract/searxng).
2. Реальный поиск (детерминированно, напрямую в academic_search_server):
   - `search_xrd_catalyst.json`: arxiv=4, openalex=4.
   - `search_vegard.json`: arxiv=4, openalex=4.
3. Верификация (`verification_artifact.json`):
   - CLM-1 (Вегард/состав) → UNSUPPORTED (MODEL_PRIOR, источник не раскрыт).
   - CLM-2 (n=63) → SUPPORTED (derivation, подтверждён кодом).

## Артефакты (run/researcher_20260917/)

- `search_xrd_catalyst.json`
- `search_vegard.json`
- `verification_artifact.json`

## Наблюдения (для калибровки)

1. **arXiv-шум**: поиск по XRD/твёрдым растворам возвращает нерелевантные результаты
   (lattice QCD, B→Kll) — `all:`-запрос слабо селективен. Для материаловедения:
   приоритет OpenAlex; arXiv-канал калибровать или исключить. (см. verification_artifact.search_noise)
2. **OpenAlex** даёт релевантные кандидаты (ceria MOF, CeO2 nanoparticles) — но для
   CLAIM-1 всё равно требуется первичный XRD-источник с составом x=0.5.
3. **CLM-1 UNSUPPORTED** — корректный fail-closed вердикт: MODEL_PRIOR не есть evidence.
   Это подтверждает калибровку DEV-09 (T-01).

## Покрытие долгов

- TD-009 (runtime core live): маршрут и поиск реально работают — частично закрыт.
- TD-017 (evidence.verify): claims/верификация сформированы — наблюдение.
- TD-038 (traceability): поиск → claims → вердикт прослеживается.

## Лимиты

- Прогон выполнен напрямую (search + verify), не через полный LLM-оркестраторный цикл;
  LLM-шаги (summary/grounding-классификация) — по калибровочным данным, помечены в артефакте.
- `harness_run` без route в live-среде — TD-066 (peer mismatch), сценарий шёл с явным route.