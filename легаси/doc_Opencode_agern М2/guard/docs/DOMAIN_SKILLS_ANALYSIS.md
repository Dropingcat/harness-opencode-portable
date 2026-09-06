# Domain Skills Analysis: сам / заимствовать / гибрид

> Источник: librarian report (4 научных репозитория) + аудит существующей инфраструктуры (numeric_comparator.py, formulas.py, domain_map.py). Формат: факты + опции, решение за пользователем (принцип сервера: LLM свидетельствует, КОД решает).
> Дата: 2026-08-26

## Контекст

**Что искали (6 доменов по запросу пользователя):** математические операции/преобразования, физические, химические, спектральные, работа с большими данными, тексты (стили).

**Предыдущий вывод** ("нет в 3 репо") — верный для software-engineering репо, НО librarian нашёл **4 научных репозитория**:

| Репо | Skills | Лицензия | Совместимость opencode |
|--|--|--|--|
| **synthetic-sciences/openscience** | 311 (по доменам) | Apache-2.0 | SKILL.md + references + scripts |
| **K-Dense-AI/scientific-agent-skills** | 163 | MIT | Agent Skills standard, `npx skills add` |
| **GPTomics/bioSkills** | 561 (archived) | MIT | install-opencode.sh (есть!) |
| **psi-oss/get-physics-done** | framework (не skills) | Apache-2.0 | verification-core reference |

**Существующая инфраструктура (наша, гибридная база):**
- `numeric_comparator.py` — 4-слойный: units registry, dimension analysis, токенизатор формул (FORMULA/GRADE/MILLER/SCIENTIFIC/UNIT_VALUE/RANGE/PERCENT/PLAIN), парное выравнивание
- `formulas.py` — Scherrer, Williamson-Hall, dislocation density, Arrhenius (детект + constants)
- `domain_map.py` — многослойная карта знаний + TMS-веса
- `expert_registry.yaml` — реестр доменных экспертов

---

## Матрица: САМ / ЗАИМСТВОВАТЬ / ГИБРИД (по 6 доменам)

### 1. Математические операции / преобразования (units, dimensional analysis)

| Под-задача | Что есть у нас | Что есть в репо | Решение | Обоснование |
|--|--|--|--|--|
| **Сравнение чисел (claim vs source)** | `numeric_comparator.py` (4-слойный, units registry, dimension matching) | OpenScience `physics/dimensional-analysis` (Buckingham Pi, pint) | **ГИБРИД** | Наш comparator — ядро (уже работает с units); заимствовать pint-based unit-conversion как дополнение для преобразований (eV→J, K→°C) которых нет в нашем units.py |
| **Dimensional analysis** | частично в numeric_comparator (dimension_mismatch → cap 0.3) | OpenScience `physics/dimensional-analysis` (полный) + GPD `verification-core` (~60% physics errors catch) | **ЗАИМСТВОВАТЬ** reference + **ГИБРИД** с нашим | GPD verification-core — методологический референс для расширения нашего dimension check; OpenScience pint — библиотека unit conversion |
| **Формулы (детект+constants)** | `formulas.py` (Scherrer, Williamson-Hall, Arrhenius, dislocation) | OpenScience symbolic-regression, physics-fitting | **САМ** (расширить) | Наш formulas.py заточен под материаловедение (Scherrer для XRD, Williamson-Hall для crystallite size) — уникален. Добавить новые формулы самим (через skill-creator) |

### 2. Физические преобразования (thermo, entropy, energy)

| Под-задача | Что есть у нас | Что есть в репо | Решение | Обоснование |
|--|--|--|--|--|
| **Термодинамика (enthalpy, entropy, activation energy)** | `formulas.py` (Arrhenius) + numeric_comparator (energy units) | OpenScience `physics/statistical-mechanics` (близко, но не thermo-калькулятор) | **САМ** | Готового thermo-skill нет (statistical-mechanics близок, но не калькулятор). Создать skill-creator'ом на базе нашего formulas.py + numeric_comparator (Arrhenius уже есть). |
| **Energy unit conversion** | numeric_comparator (units registry) | OpenScience pint | **ГИБРИД** | Наш registry + pint для расширения (eV↔J↔kcal/mol, K↔°C) |
| **Conservation laws / limiting cases** | — | GPD `verification-core` (limiting cases, symmetry, conservation) | **ЗАИМСТВОВАТЬ** reference | Методология проверки физической корректности — уникальна, нет у нас |

### 3. Химические (formulas, reactions, stoichiometry)

| Под-задача | Что есть у нас | Что есть в репо | Решение | Обоснование |
|--|--|--|--|--|
| **Molecular chemistry (RDKit, docking, ADMET)** | — | OpenScience `chemistry/` (23 skills: rdkit, datamol, deepchem, docking) + bioSkills `chemoinformatics` (20) | **ЗАИМСТВОВАТЬ** | Готовые, качественные, Apache/MIT. Прямо копировать SKILL.md. |
| **Stoichiometry (reaction balancing)** | — | K-Dense `cobrapy` (только metabolic FBA, не general) | **САМ** | General stoichiometry calculator отсутствует. Создать skill-creator'ом (парсинг хим. уравнений, балансировка). |
| **Reaction enumeration / retrosynthesis** | — | bioSkills `chemoinformatics` (AiZynthFinder, REINVENT 4) | **ЗАИМСТВОВАТЬ** | Готовые, для drug design. |

### 4. Спектральные (IR/UV/XRD/mass spec)

| Под-задача | Что есть у нас | Что есть в репо | Решение | Обоснование |
|--|--|--|--|--|
| **XRD interpretation** | `formulas.py` (Scherrer, Williamson-Hall — прямо для XRD!) | OpenScience `physics/spectral-analysis` (general) | **САМ** (расширить) | Наш formulas.py уже заточен под XRD (Scherrer crystallite size, Williamson-Hall strain). Уникально. Расширить: peak indexing, phase identification. |
| **Mass spectrometry (LC-MS/MS)** | — | OpenScience `chemistry/matchms`, `pyopenms` + bioSkills metabolomics | **ЗАИМСТВОВАТЬ** | Готовые, качественные. |
| **IR/UV spectroscopy interpretation** | — | **ОТСУТСТВУЕТ** (нет ни в одном репо) | **САМ** | Полный гэп. Создать skill-creator'ом (functional group identification из IR peaks, UV transitions, Beer-Lambert). |

### 5. Работа с большими данными (pandas, numpy, scipy, chunking)

| Под-задача | Что есть у нас | Что есть в репо | Решение | Обоснование |
|--|--|--|--|--|
| **Out-of-core processing (dask, polars, ray)** | — | OpenScience `data-engineering/` (10: dask, polars, ray-data, vaex, zarr) | **ЗАИМСТВОВАТЬ** | Готовые, Apache-2.0. Прямо копировать. |
| **Pandas (data manipulation)** | — | R1 `pandas-pro` (один skill) | **ЗАИМСТВОВАТЬ** | Простой, совместимый. |
| **Numpy/Scipy (numeric)** | numeric_comparator (своё) | — (нет dedicated skill, встроены в другие) | **САМ** | Создать skill-creator'ом на базе нашего numeric_comparator (dimension, units) + numpy/scipy transforms. |
| **Statistical analysis** | `rivulet-numeric` (наш skill, numeric regression) | OpenScience `bayesian-inference` | **ГИБРИД** | Наш rivulet-numeric + bayesian-inference reference. |

### 6. Тексты (стили, tone, voice, writing-style transformation)

| Под-задача | Что есть у нас | Что есть в репо | Решение | Обоснование |
|--|--|--|--|--|
| **Научный writing** | `article-writer` (наш агент) + `writing-orchestrator` | OpenScience `writing/scientific-writing`, `ml-paper-writing`, `literature-review`, `citation-management` | **ЗАИМСТВОВАТЬ** + **ГИБРИД** | Заимствовать научный стиль (latex, citation), гибрид с нашим article-writer (который для public-facing prose). |
| **Tone/voice transformation** | — | **ОТСУТСТВУЕТ** (нет ни в одном репо) | **САМ** | Полный гэп. Создать skill-creator'ом (formal↔informal, academic↔popular, technical↔plain, tone shifting). |
| **Summarization** | `synthesizer` (наш агент) | — (нет dedicated skill) | **САМ** (расширить) | Наш synthesizer уже делает синтез вердиктов; расширить до общего summarization skill. |

---

## Сводная матрица решений

| Домен | САМ | ЗАИМСТВОВАТЬ | ГИБРИД |
|--|--|--|--|
| **Math/units** | formulas.py (расширить) | GPD verification-core (ref), OpenScience pint | numeric_comparator + pint |
| **Physics** | thermo skill (на базе formulas.py) | GPD limiting-cases (ref), OpenScience stat-mech | energy units (наш + pint) |
| **Chemistry** | stoichiometry (general, новый) | OpenScience chemistry/ (23), bioSkills chemoinformatics (20), K-Dense cobrapy | — |
| **Spectroscopy** | XRD (расширить formulas.py), IR/UV (новый) | OpenScience matchms, pyopenms (mass spec) | — |
| **Big data** | numpy/scipy skill (на базе numeric_comparator) | OpenScience data-engineering (10), R1 pandas-pro | rivulet-numeric + bayesian |
| **Text styles** | tone/voice (новый), summarization (расширить) | OpenScience scientific-writing, ml-paper-writing | article-writer + scientific-writing |

**Итого:** САМ = 6 skills (создать/расширить), ЗАИМСТВОВАТЬ = ~35 skills (копировать), ГИБРИД = 4 (наш+заимств).

---

## План интеграции (3 волны для domain skills)

### Волна D1 — ЗАИМСТВОВАТЬ (low effort, high ROI)
Клонировать `synthetic-sciences/openscience`, извлечь:
- `chemistry/` (23 skills: rdkit, datamol, deepchem, docking, smiles-validation) → `~/.config/opencode/skills/`
- `data-engineering/` (10: dask, polars, ray-data, vaex, zarr, geopandas) → `~/.config/opencode/skills/`
- `physics/dimensional-analysis` + `physics/spectral-analysis` → `~/.config/opencode/skills/`
- `writing/scientific-writing`, `writing/ml-paper-writing`, `writing/citation-management` → `~/.config/opencode/skills/`
- Доп: R1 `pandas-pro` (уже есть в клоне) → `~/.config/opencode/skills/`
- Доп: K-Dense `cobrapy` (stoichiometry) → `~/.config/opencode/skills/`

### Волна D2 — ГИБРИД (med effort)
- **units-conversion skill**: наш `numeric_comparator.py` units registry + OpenScience pint → единый skill с CLI `convert <value> <from> <to>` + dimension check
- **physics-verification skill**: наш dimension check + GPD verification-core (limiting cases, conservation laws) → skill для fact-checker
- **scientific-writing-hybrid**: наш article-writer + OpenScience scientific-writing → универсальный (public + academic)

### Волна D3 — САМ (high effort, создать через skill-creator)
Новые skills на базе нашей инфраструктуры:
1. **thermodynamics** — на базе `formulas.py` (Arrhenius) + numeric_comparator (energy units): enthalpy, entropy, activation energy, Gibbs free energy
2. **xrd-interpretation** — расширение `formulas.py` (Scherrer, Williamson-Hall): peak indexing, phase ID, crystallite size, strain
3. **ir-uv-spectroscopy** — новый: functional group ID из IR peaks, UV transitions, Beer-Lambert
4. **stoichiometry** — новый: хим. уравнения, балансировка, molar ratios
5. **numpy-scipy-transforms** — на базе numeric_comparator: matrix ops, FFT, integration, interpolation
6. **tone-voice-style** — новый: formal↔informal, academic↔popular, technical↔plain

---

## Что требует решения пользователя

1. **Волна D1 (заимствовать ~35 skills из openscience)** — начать? Low effort (копирование), high ROI (chemistry + big-data + writing сразу).
2. **Волна D2 (гибриды)** — делать после D1? Нужно интегрировать pint + наш numeric_comparator.
3. **Волна D3 (создать 6 своих)** — приоритет? Какой из 6 первым (thermo / xrd / ir-uv / stoichiometry / numpy-scipy / tone-voice)?
4. **Клонировать openscience** (через clonedeps skill) для чтения полного содержимого перед D1?

## Файл
`/home/orangepi/Документы/doc_guard/docs/DOMAIN_SKILLS_ANALYSIS.md`