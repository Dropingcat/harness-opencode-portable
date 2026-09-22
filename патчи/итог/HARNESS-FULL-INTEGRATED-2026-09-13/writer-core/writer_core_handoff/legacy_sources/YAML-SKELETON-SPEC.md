# YAML Skeleton & Claim-DB Tree — Implementation Spec (doc-as-code)

> Статус: **spec v1** (2026-09-03). Цель: YAML — единый канонический «код документа» (doc-as-code). БД клаймов — древовидная система. Двусторонний конвейер: вход (просеять) → хранилище (отсортировать) → выход (собрать обратно, оставить лучшее).

---

## 1. Принцип: YAML как канонический код, SQLite как индекс

- **YAML-файлы** — source of truth (читаемо, git-diffable, валидируемо, версионируемо).
- **SQLite** — проекция/индекс для запросов (не источник).
- **Pandoc/MD** — артефакт сборки (build), пересобирается из YAML.

```
YAML (канон) ──validate──▶ pydantic-модель ──load──▶ SQLite (индекс)
    ▲                                                      │
    │                 export/writeback                     ▼
    └──────────────────────◀──────────────  запросы/сборка
```

---

## 2. Документ-скелет (YAML tree)

Жанровый скелет = дерево юнитов. Пример (диссертация ВАК):

```yaml
# dissertation_skeleton.yaml
document:
  id: DOC_SKELETON
  genre: dissertation_vak
  spec_vak: "05.13.18"
  gost: "Р 7.0.11"
  skeleton_version: "1.0"

skeleton:
  - id: SEC_INTRO
    type: section
    title: "Введение"
    role: introduction
    apparatus:                # научный аппарат (ВАК)
      relevance: true
      object_subject: true
      goal_tasks: true
      hypothesis: true
      novelty: true
      positions: true
      approbation: true
    children:
      - id: SEC_INTRO_REL
        type: paragraph
        role: relevance
        required: true
      - id: SEC_INTRO_NOV
        type: paragraph
        role: novelty
        required: true

  - id: SEC_CH1
    type: section
    title: "Глава 1. Обзор литературы"
    role: review
    children:
      - id: SEC_CH1_STATE
        type: paragraph
        role: state_of_art
        required: true
      - id: OBJ_T1
        type: object
        kind: number
        required: true          # число обязано присутствовать

  - id: SEC_CH2
    type: section
    title: "Глава 2. Методология"
    role: methodology
    children:
      - id: SEC_CH2_METHOD
        type: paragraph
        role: method
      - id: OBJ_F1
        type: object
        kind: formula
        required: true

  - id: SEC_CONCL
    type: section
    title: "Заключение"
    role: conclusion
```

Правила скелета:
- `type`: section | paragraph | assertion | object
- `role`: назначение юнита (relevance, state_of_art, method, novelty...)
- `required`: обязателен ли (валидация полноты)
- `children`: вложенность (PARENT_OF/CHILD_OF) — дерево
- `apparatus`: требования научного аппарата (только для dissertation/monograph)

---

## 3. Клайм-БД как древовидная система (YAML)

Каждый документ (свой + эталонный) → YAML-файл клайм-графа:

```yaml
# claims_doc_xxx.yaml
document: DOC_...
source_ref: "F:\AnalisysDataSet\pdfs\mekka2019.pdf"
ingest_meta:
  engine: "claim-extractor-v1"
  date: "2026-09-03"

claims:                        # древовидная система (levels 1-4)
  - id: SEC_1
    level: 1
    type: section
    title: "Глава 1"
    parent: null
    children: [PAR_1, PAR_2]
    relations: []

  - id: PAR_1
    level: 2
    type: paragraph
    text: "..."
    parent: SEC_1
    children: [CLM_1, OBJ_1]
    relations:
      - {type: SUPPORTS, target: SEC_CONCL, weight: 0.8}

  - id: CLM_1
    level: 3
    type: assertion
    text: "ε-фаза повышает износостойкость"
    parent: PAR_1
    children: [OBJ_1]
    relations:
      - {type: DERIVED_FROM, target: CLM_2}
      - {type: CITES, target: EVD_1}
    evidence: [EVD_1]

  - id: OBJ_1
    level: 4
    type: object
    kind: number
    value: "12.5"
    unit: "μm"
    dimension: "length"
    parent: CLM_1
    children: []
    relations: []
    validated: true            # pint-проверка прошла
```

Связи:
- **PARENT_OF / CHILD_OF** — вложенность (дерево)
- **SUPPORTS / CONTRADICTS / DERIVED_FROM / CITES** — аргументация и провенанс
- **weight** — опциональная сила связи (для сравнения графов)

---

## 4. Валидация YAML (doc-as-code gates)

pydantic-модели на каждый тип юнита:

```python
class UnitBase(BaseModel):
    id: str
    level: int  # 1-4
    type: Literal["section", "paragraph", "assertion", "object"]
    parent: str | None
    children: list[str] = []
    relations: list[Relation] = []

class ObjectUnit(UnitBase):
    type: Literal["object"]
    kind: Literal["number", "formula", "citation", "term", "table", "figure"]
    value: str | None
    unit: str | None
    validated: bool = False

class ClaimTree(BaseModel):
    document: str
    claims: list[UnitBase]  # валидируется: иерархия, ссылки, циклы
```

**Валидаторы YAML** (детерминированные):
1. **TreeValidator** — нет циклов, каждый parent существует, уровни согласованы
2. **LinkValidator** — relations указывают на существующие id
3. **ObjectValidator** — число+unit через pint; формула через LaTeX-парсер; цитата через ГОСТ-чек
4. **SkeletonCompleteness** — все required юниты скелета присутствуют
5. **EligibilityGate** — claims не из forbidden-списка

Сбой валидатора → BLOCK (fail-closed), сборка не идёт.

---

## 5. Двусторонний конвейер (the Sieve)

### 5.1 Вход: ПРОСЕЯТЬ (input sieve)

```
raw text/PDF → chunk → claim-candidates → ADMISSION (SourceAdmission,
EvidenceAdmission, Atomicity, Numeric, Scope) → только прошедшие в БД
```

- **Admission** — первое сито: только валидные, атомарные, с провенансом.
- **Ranking** — второе сито: ранжирование (сила evidence, конфликты, релевантность скелету).
- **Dedup** — третье: stable_key, слияние дублей.

### 5.2 Хранилище: ОТСОРТИРОВАТЬ (hold)

```
claim DB (YAML) — отсортированная коллекция: admitted, ranked, dedup,
противорочащие (ConflictBuilder) помечены, слабые (StructuralRisk) отмечены.
```

### 5.3 Выход: СОБРАТЬ ОБРАТНО (reverse assembly)

```
skeleton + writer_context (allowed/qualified/forbidden) + ranking
→ SELECT лучших claims для каждого required-слота
→ сборка дерева → юниты (DRAFT) → writer → валидаторы → self-check
→ рецензент → APPROVED → экспорт MD → Pandoc → ГОСТ DOCX/PDF
```

**«Оставить только лучшее»** = на каждом слоте выбирается claim с максимальным рейтингом среди eligible (не «первый попавшийся»), слабые/конфликтующие исключаются или помечаются.

---

## 6. Схема файлов (doc-as-code layout)

```
writer-core/
  docs/
    skeletons/
      dissertation_vak.yaml
      longread.yaml
      monograph.yaml
      scientific_report.yaml
  claims/                  # канонический клайм-граф каждого документа
    my_dissertation.yaml
    ref_mekka2019.yaml
    ref_ivanov2020.yaml
  db/                      # SQLite-проекция (генерируется, не редактируется)
    index.db
  artifacts/
    build/                 # MD → DOCX/PDF (артефакт сборки)
  src/writer_core/
    yaml_models.py         # pydantic-модели YAML
    yaml_validate.py       # TreeValidator/LinkValidator/ObjectValidator...
    tree_io.py             # YAML ↔ Python ↔ SQLite
    sieve.py               # вход/выход конвейер
    export.py              # юниты → MD → Pandoc
```

---

## 7. Git-интеграция (doc-as-code workflow)

- YAML-скелеты и клайм-файлы — в git (diffable, reviewable).
- Коммит = изменение юнитов/структуры; PR = ревью структуры.
- CI gate: `yaml_validate.py` на каждый PR (как линтер/тест).
- Снэпшоты = теги; релиз документа = merge в main.

---

## 8. Открытые вопросы (для следующей итерации)

1. **Канон: YAML или SQLite?** — рекомендую YAML (канон) + SQLite (индекс), но надо зафиксировать синхронизацию (двунаправленную, с конфликтами).
2. **Формат relations** — расширить (weight, polarity, confidence)?
3. **Скелеты** — статичные (вручную) или обучаемые из корпуса (M3)?
4. **Ranking-функция** — что именно учитывает (сила evidence, релевантность, novelty)?