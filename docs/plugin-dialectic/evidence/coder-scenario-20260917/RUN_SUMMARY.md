# Coder Scenario Run — 2026-09-17

Статус: `RUN COMPLETE / REWORK (numeric extractor proto) / EVIDENCE FOR TD-068`

## Что прогонялось

Полный Coder-цикл через фабрику:
- `factory_ctl init CODER-SCENARIO-20260917`
- воркер: детерминированная утилита `numeric_validator` (числовой экстрактор claims)
- `artifact-register` (артефакт с hash)
- submit worker → reviewer/tester/auditor

## Результат гейтов

| Гейт | Вердикт | Суть |
|---|---|---|
| Reviewer | RETRY (REWORK) | regex-вырезание переменных ломает валидные значения (a=5.27 А); греческие индексы (2θ), ≈ не обработаны |
| Tester | RETRY (REWORK) | 2/5 тестов: IC50 (OK), без чисел (OK); a=5.27, 2θ/t=25, x=0.5/a≈5.32 (FAIL) |
| Auditor | PASS | процесс корректен; числовой экстрактор — прототип |

## Ключевой вывод (evidence для TD-068)

**Числовая экстракция требует токенизатора, а не цепочки regex.**

Edge-кейсы, которые ломают regex:
1. `IC50 = 8.2 мкМ` — «50» в IC50 ловится как число (нужна граница слова);
2. `параметр a=5.27 А` — «a=5.27» вырезается как переменная, но это валидное значение;
3. `2θ≈44.3°, t=25°C` — греческий θ и связка ≈ не обработаны, t=25 теряется;
4. `x=0.5 даёт a≈5.32 Å` — x= и a≈ вырезаются целиком (оба числа потеряны);
5. единицы А/Å/a смешиваются (юникод).

Это прямое подтверждение TD-068: Writer extractor НЕ извлекает числовые claims.
Решение — токенизатор чисел с контекстом (переменная/индекс/значение+единица), не regex-цепочка.

## Артефакты
- worker_numeric_validator.json, reviewer_numeric_validator.json,
  tester_numeric_validator.json, auditor_numeric_validator.json (в корне).

## Связь с трекером
- TD-068 подтверждён на Coder-уровне (не только Writer extractor): нужен общий
  числовой токенизатор, переиспользуемый Writer/Researcher/Coder.
- Coder-цикл фабрики работает корректно (init→submit→gates→rework).