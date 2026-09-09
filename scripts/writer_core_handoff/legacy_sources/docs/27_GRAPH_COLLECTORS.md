# 27. Graph Collectors — что собирать для каждого из 12 графов

> Статус: **spec v0.1** (04.09.2026). Назначение: определить, КАКИЕ данные и откуда собирает каждый «скучный парсер», чтобы из артефакта (диссертация PDF) построить 12 графов. Все коллекторы детерминированные (извлечение структуры, чисел, цитат, таблиц, терминов — без LLM). LLM используется ТОЛЬКО внутри извлекающей капсулы для семантических claims.

## 0. Вход: артефакт

```yaml
artifact_id: ART_BLINOVA_2018
source_path: "F:/AnalisysDataSet/pdfs/Автореферат диссертации Блинова Е.В. 2018-09-27-14.pdf"
artifact_type: dissertation_autoreferat
parser_output: canonical_document.json   # результат pymupdf/grobid+docling
```

## 1. Парсер-первичка: PDF → неявный контент (до 12 графов)

| Коллектор | Что извлекает | Откуда |
|---|---|---|
| **C1. Blocks** | страницы, блоки текста, позиции, размер шрифта, жирность | pymupdf `page.get_text("dict")` |
| **C2. Struct** | заголовки (по шрифту/нумерации), абзацы, списки, таблицы, формулы, подписи | blocks + эвристика |
| **C3. Sentences** | разбиение абзацев на предложения | regex (конец {:.;!?…} + заглавная) |
| **C4. Lines** | строки + координаты (для таблиц/формул вне потока) | pymupdf `get_text("words")` |

## 2. Коллекторы по графам

### Граф 1 — document_structure
| Поле | Коллектор | Источник |
|---|---|---|
| Document | C1 | artifact metadata |
| Section (глава/раздел) | C2 | заголовок → уровень (по шрифту/нумерации «1.», «1.1»…) |
| Paragraph | C2+C3 | блок + абзацный отступ |
| Sentence | C3 | предложения |
| InlineNode | C4 | numbers/citations внутри sentence |
| TableBlock / FigureBlock | C2 | таблицы (по координатам/границам) + подписи «Таблица N», «Рисунок N» |
| EquationBlock | C2 | формулы (LaTeX-детект из текста/шрифта) |
| Отношения PARENT_OF/NEXT/PREVIOUS | C2 | порядок блоков |

### Граф 2 — writing_decomposition
*(для Черновиков; для Эталонов не строится — только для author-графа)*
| Поле | Коллектор | Источник |
|---|---|---|
| WritingObjective | — | пользователь |
| SectionIntent | C2 | заголовок → намерение (введение/обзор/метод/результаты/заключение) |

### Граф 3 — discourse
| Поле | Коллектор | Источник |
|---|---|---|
| DiscourseMove | C2+C3 | классификация раздела по контенту (state_of_art/method/result/interpretation/limitation…) — детерминированный рубрикатор по сигнальным словам + позиция |
| SectionIntent | C2 | заголовок |
| ParagraphIntent | C3 | роль абзаца (маркеры: «таким образом», «однако», «следует отметить»…) |
| Transition | C3 | коннекторы на границах предложений |

### Граф 4 — epistemic_argument  (Researcher-owned; Writer строит ТОЛЬКО из extraction капсулы)
| Поле | Коллектор/extractor | Источник |
|---|---|---|
| Claim | **EXTRACTOR capsule (LLM typed)** | после R1 staged extraction |
| Scope | extractor + C3 (scope dimensions: материал, условия, метод) | sentence + контекст |
| Evidence span | C3 + C4 (exact span, locator: страница, строка) | предложение |
| Quantity | C5-number (ниже) | числа в предложении |
| Derivation | extractor (derived_from, operation) | из claims |
| Gap/Conflict | extractor | из claims/status |

### Граф 5 — artifact_symbol  (полностью детерминированно)
| Поле | Коллектор | Источник |
|---|---|---|
| Quantity | **C5-NUMBER** | числа с единицами в тексте: regex `(?P<val>-?\d+[,.]\d*)\s*(?P<unit>[Åμµm°C%КНМПаВЖ...])` + диапазоны |
| Formula | C6-FORMULA | выражения с `=`/индексами/Греческими символами, LaTeX-фрагменты |
| Table | C2 (structure) | таблицы по координатам |
| Figure | C2 | изображения + подписи |
| Citation | C7-CITATION | `[12]`, `(Иванов, 2005)`, список литературы |
| Term | C8-TERM | термин (капит. или в кавычках) + определение |
| Отношения USES/DERIVED/DISPLAYS | C5-C8 | привязка по span |

### Граф 6 — citation_provenance
| Поле | Коллектор | Источник |
|---|---|---|
| SentenceSpan | C3 | предложение |
| CitationMarker → Source | C7 | скобки `[..]` / `(Автор, год)` → список литературы |
| ClaimRef ← SentenceSpan | extractor | назначение claims на span |
| Evidence ← SourceVersion | C3+C7+C5 | span + ссылка + числа |

### Граф 7 — policy_constraint
| Поле | Коллектор | Источник |
|---|---|---|
| GenrePolicy | C2 (жанр по артефакту) | метаданные (автореферат/диссертация/статья) |
| DomainPolicy | C1 (домен из title/spec) | 05.16.01 → metallurgy |
| StylePolicy | C9-STYLE | статистика (см. граф 12) |

### Граф 8 — revision_dependency  (runtime; не из PDF)
| Поле | Коллектор | Истчник |
|---|---|---|
| DEPENDS_ON/INVALIDATES | runtime | регистр измене-> нет из артефакта |

### Граф 9 — executиon (runtime; не из PDF)
(каждый коллектор зелогпризует Run/Command/CapsuleRun; см docs/25)

### Граф 10 — vocabulary (НОВЫЙ)
| Поле | Колектор | Истчник |
|---|---|
| Term | C8-TERM | кандидат: капит/кавычки/деф, + домеенный жаргон |
| Symbol | C6-FORMULA | символ + изначение из текста |
| Abbreviation | C10-ABBR | Скобки: «(АБВ)» → асокр. после полного «абв (АБВ)» |

### Граф 11 — novelty_contribon (НОВЫЙ, из авторефератов! )
| Поле | Колектор | Истчник |
|---|---|---|
| NoveltyClaim | C11-NOV | секц«нвона» «вперв», «развито» → клайм-кандидат |
| PriorArtCoerage | C12-PRIOR | секциальный: «известен», «анный», «в известных» |
| Contbution | C2 (зглавки введение обзор) | «следует отметить» ...|

### Граф 12 - style_profile (НОВЫЙ, read-only)
| Поле | Колектор | Истчник |
|---|---|
| avg_sentence_len | C13-STYL | C3 |
| passie_ratio | C13-STYL | песоч/пп «-ся/-но» + «был» част.; замерно |
| hedg_ratio | C13 | «мжно» «п-вимо» «к кжется» «соответсвенно» |
| term_dsenity | C8 | уник. темин/1000 сл |
| readabultity | C13 | Flesch-кокейд (RU-кодиф.) |

---

## 3. Капсула извлечения целостно (скловчакий пареср: PDF → 12 графов)

```text
PDF
 → [C1-C4 структурные паресры]  → canonical_document (блоки, абзацы, предложения, таблицы, фомулы, цитаты)
 → [C5-C13 деерминированные эксткторы]  → quantities, формулы, цитаты, термины, стиль, новизна
 → [EXTRACTOR cappsule (LLM typed, по researcher-контракту)]  → Claims (proposition, scope, status, evidence_refs, quantities, gaps)
 → [graph_builder]  → 12 графов (SQLite: entities + edges + events)
```

---

## 4. Приоритет коллекторов (первые версии)

| # | Коллектор | Граф | Сложность |
|---|---|---|---|
| 1 | C1-C3 (blocks/sections/sentences) | 1,3 | низкая |
| 2 | **C5-NUMBER** | 5 | низкая |
| 3 | **C7-CITATION** | 5,6 | низкая |
| 4 | C2 (tables) | 1,5 | средняя |
| 5 | **C11-NOV (авторефераты)** | 11 | низкая |
| 6 | C13-STYLE | 12 | низкая |
| 7 | C8-TERM | 10 | средняя |
| 8 | extractor capsule (llm) | 4 | **средняя/высокая** (после калибровки) |

> Правило: сначала «скучные» детерминированные коллекторы (C1-C7, C11, C13) — они дают артефакты без LLM и дешёвы. Капсула-извлекатель (claims) подключается ПОСЛЕ того, как структура и объекты уже надёжно извлечены.