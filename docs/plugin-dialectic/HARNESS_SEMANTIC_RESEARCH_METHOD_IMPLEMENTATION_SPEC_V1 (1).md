# HARNESS SEMANTIC RESEARCH METHOD IMPLEMENTATION SPECIFICATION
## Графы гипотез, вопросы, извлечение единиц информации и многоязычная семантика
Версия: 0.1-design
Статус: DESIGN / IMPLEMENTATION SPEC

---

## 0. Назначение и область применения

Документ задаёт реализуемый метод семантического исследования для Harness. Цель: превратить текст, гипотезы, вопросы, evidence и выводы в типизированный,
проверяемый граф. Метод должен работать поверх Writer, Researcher, Tribunal, Coder и OpenCode Native Plugin. LLM рассматривается как семантический
исполнитель, а не владелец состояния. Код определяет допустимые переходы, admission, версии и provenance. Источник не заменяется пересказом. Ответ
специалиста не становится evidence автоматически. MODEL_PRIOR разрешён как источник гипотезы, но не как доказательство. Подтверждение гипотезы не сводится
к одному confidence-score.

## 1. Базовые принципы

P1. Код управляет состоянием, LLM предлагает семантические действия. P2. История важнее текущей формулировки, поэтому revision не перезаписывается. P3.
SourceSpan, Claim, Hypothesis, Evidence, Question, Answer и Argument различаются типами. P4. Поддержка не равна истинности, а согласие источников не равно
независимости. P5. Любой итоговый тезис должен трассироваться назад до точного source locator. P6. Междисциплинарные ветви независимы до явного join. P7.
Join выполняется по покрытию, зависимостям и конфликтам, не голосованием. P8. OpenCode является host/runtime, а научная семантика остаётся в Harness Core.

## 2. Историческая модель объекта

Гипотеза хранится как цепочка версий HYP-X.r1 → HYP-X.r2 → HYP-X.r3. Каждая revision хранит parent, trigger, evidence, вопросы, assumptions и scope
changes. Перезапись старой версии запрещена. Для SPLIT разрешено ветвление revision graph. Для MERGE создаётся новый HypothesisCase, а не уничтожается
история родителей. Аналогичный принцип применяется к Claim, EvidenceDigest и VerificationPlan. История делает возможным ответ на вопрос: почему
формулировка изменилась.

## 3. Source и SourceSpan

Source описывает документ, dataset, эксперимент, вычисление или иной первичный источник. Минимальные поля: source_id, kind, title, authors, year, version,
DOI/URL, content_hash. SourceSpan указывает точный фрагмент: page/section/lines/char offsets/table/figure. Span должен быть воспроизводимым. Для PDF
предпочтительны page + anchor text + file hash. Для HTML предпочтительны canonical URL + heading path + retrieval time. Для локального текста допустимы
line range + content hash. SourceSpan не содержит интерпретацию научного смысла.

## 4. InformationUnit и PropositionUnit

InformationUnit является общей минимальной единицей извлечённой информации. unit_kind ∈ {OBSERVATION, MEASUREMENT, METHOD, ASSUMPTION, INTERPRETATION,
DEFINITION, LIMITATION, PREDICTION}. PropositionUnit является минимальной проверяемой предикацией. Поля: subject, predicate, object, conditions, modality,
polarity, quantifiers, temporal qualifiers. Одна фраза может породить несколько PropositionUnit. Несколько предложений могут образовать одну
PropositionUnit, если смысл неделим. Atomicity проверяется по наличию одной основной проверяемой предикации. Механическое дробление по предложениям
запрещено.

## 5. Claim

Claim является утверждением, которое система может проверять и использовать дальше. Поля: claim_id, statement, normalized_semantics, scope, modality,
polarity, qualifiers. Claim хранит source/evidence links, revision, admission state и status projection. Claim не обязан быть гипотезой. Наблюдение «пик
расширился» может стать Claim. Объяснение «уширение вызвано микродеформациями» уже требует гипотезного уровня. Writer использует только авторизованные
Claim projections.

## 6. Hypothesis

Hypothesis является проверяемым объяснением, механизмом или предсказанием. Она обязана иметь scope, assumptions, predictions, competing hypotheses и
falsification conditions. Пример: изменение параметра решётки связано преимущественно с составом твёрдого раствора, а не residual stress. Hypothesis не
является просто Claim со статусом confidence. Она запускает VerificationPlan. Каждая новая существенная корректировка создаёт новую revision. Гипотеза
может быть сохранена как OPEN даже при отсутствии подтверждения.

## 7. Question и Answer

Question представляет типизированную информационную потребность. Типы: CLARIFICATION, EVIDENCE, METHOD, CAUSAL, COUNTEREXAMPLE, SCOPE, MEASUREMENT,
PROVENANCE. Дополнительные типы: COMPARISON, DISCRIMINATION, REPLICATION, ASSUMPTION, EXTRAPOLATION, FRESHNESS. Answer всегда связан с конкретным Question.
Answer обязан содержать grounding profile. Answer не получает статус evidence только потому, что его выдал specialist. Question/Answer являются частью
исследовательской истории.

## 8. Grounding profile ответа

Допустимые основания: DISCLOSED_EVIDENCE, DISCLOSED_TARGET, PRIOR_ARGUMENT, PRIOR_TURN. Также: DERIVATION_FROM_VISIBLE, EXPLICIT_ASSUMPTION, MODEL_PRIOR.
MODEL_PRIOR разрешён как гипотеза, query seed или alternative explanation. MODEL_PRIOR запрещён как citation, measurement или independent confirmation.
Если ответ пытается SUPPORT/QUALIFY только на MODEL_PRIOR, создаётся MissingEvidence. Такой ответ может остаться полезным, но не закрывает научную ветку.
Grounding profile сохраняется в Argument/Answer.

## 9. EvidenceUnit и EvidenceDigest

EvidenceUnit описывает, что именно конкретный SourceSpan поддерживает, ограничивает или опровергает. Поля: evidence_id, span_ids, supports, counters,
limits, conditions, method, material/population. Добавляются independence_group, quality_notes и extractor_trace. EvidenceDigest является коротким
source-bounded резюме. Digest обязан отвечать: что источник показывает, что не показывает, при каких условиях и каким методом. Digest не заменяет
SourceSpan. Round-trip validator проверяет, не усилил ли digest причинность или modality.

## 10. Assumption и Derivation

Assumption хранит явное или обнаруженное допущение. Состояния: EXPLICIT, IMPLICIT_DETECTED, SUPPORTED, UNSUPPORTED, CHALLENGED, REJECTED. Derivation хранит
воспроизводимый вывод из входных объектов. Поля: inputs, formula/algorithm, parameters, code_version, output, uncertainty. Вычислительный результат Coder
не становится evidence без Derivation/provenance. Assumption может быть отдельной целью QuestionGraph. Reject одного assumption не обязательно отвергает
всю Hypothesis.

## 11. Основной мультиграф

Исследовательское состояние задаётся ориентированным мультиграфом G=(V,E). V = V_S ∪ V_P ∪ V_C ∪ V_H ∪ V_Q ∪ V_A ∪ V_E ∪ V_R ∪ V_D. V_S: sources/spans;
V_P: propositions; V_C: claims; V_H: hypotheses. V_Q: questions; V_A: answers/arguments; V_E: evidence; V_R: revisions; V_D: derivations. Ребро
e=(u,r,v,m), где r является типом отношения, m хранит scope/policy/provenance. Граф является мультиграфом, поэтому один EvidenceUnit может одновременно
SUPPORTS и LIMITS Claim. Граф процесса исследования не следует путать с KnowledgeGraph истины.

## 12. Отношения графа

Базовые отношения: SUPPORTS, COUNTERS, LIMITS, CONDITIONS, DERIVED_FROM. Зависимости: REQUIRES, SHARES_EVIDENCE, SHARES_ASSUMPTION, INTEGRATES_WITH.
Конфликты: CONFLICTS_WITH, FAILS_TO_DISCRIMINATE. Диалектика: ATTACKS, UNDERCUTS, REPLIES_TO, DEFENDS. Revision/provenance relations должны иметь
направление и version metadata. ATTACKS direction: source/newer argument → target/earlier argument. Нельзя использовать одно универсальное ребро RELATED_TO
для authority path.

## 13. Почему scalar confidence недостаточен

Для гипотезы вводится оценочный вектор A(H)=(S,C,M,P,I,U,R,F). S: достаточность поддержки; C: тяжесть противоречий; M: адекватность метода. P: provenance
quality; I: independence evidence; U: unresolved assumptions. R: replication state; F: scope fit. Компоненты предпочтительно типизированы: RESOLVED,
QUALIFIED, MATERIAL, BLOCKING, UNCHARACTERIZED. Status(H)=Π(A(H), policy), где Π является policy projection. Если C=BLOCKING или M=BLOCKING, SUPPORTED
запрещён независимо от остальных компонентов. Среднее арифметическое компонентов использовать нельзя.

## 14. Evidence independence

Пусть имеется E={e1,...,en} и граф зависимостей G_E=(E,D). Ребро может означать общий dataset, эксперимент, calibration, pipeline или primary source.
Каждому evidence присваивается independence group g(ei). Эффективное число независимых групп N_eff=|{g(ei)}|. Для частичной зависимости можно хранить
матрицу R=[ρ_ij], ρ_ij∈[0,1], ρ_ii=1. Диагностическая оценка: N_eff≈n²/(Σ_iΣ_jρ_ij). Эта формула не является вероятностью истины. Три статьи на одном
dataset могут иметь n=3, но N_eff≈1.

## 15. Матрица покрытия гипотезы

Гипотеза раскладывается на компоненты H={h1,...,hk}. EvidenceUnits образуют E={e1,...,em}. Строится матрица M размерности m×k.
M_ij∈{SUPPORT,COUNTER,LIMIT,CONDITION,NO_INFO,NON_DISCRIMINATING}. Coverage(hj)=число evidence groups, которые действительно относятся к hj. Количество
публикаций само по себе не является coverage. Readiness учитывает independence и method adequacy. Blocking component блокирует общий статус, если он
required.

## 16. Предсказания и различающие тесты

Для Hypothesis H вводится Pred(H)={p1,...,pq}. Prediction хранит observable, expected_direction, range, conditions и measurement_method. Также хранятся
expected results competing hypotheses. Если P(data|H1)≈P(data|H2), наблюдение плохо различает H1 и H2. В графе это фиксируется FAILS_TO_DISCRIMINATE.
Совместимость данных с H не равна сильной поддержке H. VerificationPlan должен искать discriminating evidence, а не просто ещё совпадения.

## 17. Bayesian-представление без псевдоточности

В численных задачах допустимо P(H|E)∝P(E|H)P(H). Но текстовые evidence нельзя автоматически переводить в likelihood. Поддерживаются режимы QUALITATIVE,
SEMIQUANTITATIVE и NUMERIC. QUALITATIVE использует typed relations и uncertainty states. SEMIQUANTITATIVE может использовать ordinal классы
WEAK/MODERATE/STRONG. NUMERIC разрешён только при явной модели, параметрах, independence assumptions и uncertainty propagation. Никакой «уверенности модели
0.83» как научной вероятности.

## 18. Pipeline извлечения текста

Source → structural segmentation → candidate propositions → normalization. Далее: entity/relation linking → modality extraction → scope extraction. Затем:
evidence-role classification → duplicate/conflict check → admission. Структурная сегментация сохраняет
title/section/paragraph/sentence/list/table/figure/footnote. Chunking для retrieval не считается semantic segmentation. InformationUnit может пересекать
chunk boundaries. Source structure сохраняется как provenance context.

## 19. Atomicity и composition

Atomic proposition имеет одну основную проверяемую предикацию. Фраза «температура увеличивает диффузию и уменьшает твёрдость» должна дать минимум две
units. Фраза «при 540 °C после 24 ч параметр вырос на 0.12 %» остаётся одной unit. ClaimComposer может собирать несколько units только при semantic
compatibility. compat(U)=entity_consistency ∧ scope_consistency ∧ polarity_consistency ∧ temporal_consistency ∧ method_compatibility. Если связь между
units не доказана, Claim получает UNDERCONSTRAINED или RelationNeed. Склейка по близости абзацев запрещена.

## 20. Round-trip semantic validation

Для преобразования T_source→T_normalized извлекаются C_s и C_n. Строится matching φ:C_n→C_s∪{∅}. Если φ(c)=∅, возникает candidate unauthorized claim.
Сравниваются scope, modality, causality, polarity, quantities и conditions. Классы ошибок: scope_shift, modality_shift, causality_upgrade, numeric_drift.
Дополнительно: unauthorized_claim, omission, polarity_flip, condition_loss, entity_swap, temporal_shift. Hard-class errors блокируют admission/release. Это
общий принцип Writer и Researcher, а не отдельная Writer-функция.

## 21. Русский язык: безличность и субъект

Русский научный текст часто использует безличные конструкции: «установлено», «показано», «наблюдается». Нельзя автоматически создавать агента действия.
«Установлено увеличение» означает reported observation, а не causal action автора. Неопределённо-личные конструкции требуют discourse context. Если субъект
неразрешим, agent=UNRESOLVED. Свободный порядок слов запрещает простое positional entity linking. Surface form всегда сохраняется рядом с normalized
semantics.

## 22. Русский язык: вид, modality и отрицание

«увеличивался» и «увеличился» несут разную aspect/temporal информацию. Модальные маркеры: может, возможно, вероятно, по-видимому, не исключено, скорее. Они
должны превращаться в explicit modality fields. «Не исключено отсутствие влияния» нельзя нормализовать как «влияние есть». Нужна явная polarity structure,
а не один boolean negated. Quantifier и modality являются частью Claim identity. Потеря modality считается hard semantic drift.

## 23. Английский язык: passive и hedging

Passive voice часто скрывает агента: “an increase was observed”. Это observation, а не causal attribution. Hedging markers: may, might, could, suggest,
appears to, is consistent with, cannot rule out. “is consistent with” не равно “demonstrates”. “No significant increase was observed” не означает
математически increase=false. Нужно учитывать significance/detection method. Nominalizations должны разворачиваться в predicates без потери qualifiers.

## 24. Перевод и cross-language identity

Перевод является derived representation, а не новым evidence. Canonical SourceSpan остаётся на языке оригинала. Translation хранит source_span_id,
languages, translator/model, version и RTT status. Cross-language Claim matching сравнивает subject, predicate, causality, modality, scope и conditions.
Embeddings используются только как candidate mechanism. “is associated with” и «приводит к» не считаются эквивалентами. Научные термины связываются через
TermConcept, а не простое string equality.

## 25. Термины и false friends

TermConcept хранит concept_id, preferred terms, synonyms, language variants и ambiguity notes. Особенно опасны
deformation/strain/stress/деформация/напряжение. Р18, R18, P18 могут быть transliteration/OCR variants, но требуют contextual confirmation. Аббревиатуры
связываются ALIAS_OF только после admission. Русская морфология обрабатывается на уровне lemma/concept. Surface forms не уничтожаются. Domain profile может
добавлять собственный словарь и правила.

## 26. QuestionGraph

Вопросы образуют отдельный граф G_Q=(Q,E_Q). Рёбра: REFINES, DEPENDS_ON, ANSWERED_BY, GENERATED_FROM, CHALLENGES, DISCRIMINATES, REOPENS, DUPLICATES.
Каждый Question связан с AssessmentNeed или конкретной issue. Дополнительный Q2 допустим только при новой semantic surface. QuestionGraph хранит
происхождение поисковых и диалектических вопросов. Он не должен быть списком промптов без связи с состоянием исследования.

## 27. Новизна дополнительного вопроса

Определим Features(Q)=entities∪relations∪assumptions∪evidence_needs∪methods∪scope_dimensions. Вспомогательная мера J(Q1,Q2)=|F1∩F2|/|F1∪F2|. novelty=1-max
similarity с предыдущими вопросами ветки. Embedding similarity является только одним сигналом. Даже лексически новый вопрос может дублировать тот же
AssessmentNeed. Rule checks сравнивают assumption, target relation, missing evidence и branch state. Низкая novelty переводит вопрос в DUPLICATES или
STOP_NO_PROGRESS.

## 28. Q→A→Q-on-answer

Цикл: Q1→A1→issue extraction→Q2→A2. Продолжение разрешено, если A1 создаёт новый assumption, conflict, evidence need или scope boundary. Также новая
competing hypothesis или method limitation считается новой поверхностью. Если новая поверхность отсутствует, branch прекращается. Question-on-answer не
должен быть ритуальной глубиной «до 4». Глубина является максимумом, а не обязанностью. Branch state определяет необходимость следующего хода.

## 29. Математика no-progress

Пусть I_t является множеством активных issues ветки после шага t. Пусть ΔEvidence, ΔAssumptions, ΔScope описывают изменения. Если I_{t+1}=I_t и все три Δ
равны нулю, прогресс отсутствует. Диагностическая метрика: Δ_t=w1*N_new_issue+w2*N_new_evidence+w3*N_resolved+w4*N_new_test. Если Δ_t=0 несколько итераций,
STOP_NO_PROGRESS. Метрика управляет orchestration, а не научной истинностью. Причина остановки сохраняется как typed event.

## 30. Поисковые вопросы и RAG

Retrieval query должен происходить из AssessmentNeed, а не из общей темы. Need→SearchIntent→QuerySet→SearchMemory. Пример: различить composition effect и
residual stress. QuerySet включает method-targeted, counterevidence, replication и primary-source варианты. Search queries тоже образуют граф
BROADENS/NARROWS/TARGETS_METHOD/TARGETS_COUNTEREVIDENCE. Каждый query хранит provider, timestamp, results, selected/rejected sources и reason codes. Это
предотвращает бесконечный повтор одинакового поиска.

## 31. Source admission

DiscoveryHit не является Source. Pipeline: DiscoveryHit→SourceCandidate→SourceValidation→Source→SourceSpan→EvidenceUnit. Проверяются identity, version,
authorship, date, primary/secondary status, scope и content availability. Review article может быть полезен для discovery, но не автоматически независим от
cited primary studies. Source validation хранит причины rejection. Неверифицированная hallucinated citation остаётся SourceCandidate/UNVERIFIED. Citation
никогда не создаётся только из model prior.

## 32. Evidence dependency graph

Отдельный provenance/dependency graph хранит USES_DATASET, REANALYZES, SHARES_SAMPLE. Также CITES_AS_PRIMARY, SHARES_METHOD_PIPELINE, REPLICATION_OF,
DERIVED_FROM. Этот граф помогает TD-049 evidence independence. Он не является KnowledgeGraph фактов предметной области. Review и primary study могут иметь
сильную зависимость. Два agents, анализирующие один SourceSpan, не создают два независимых confirmations. Model diversity тоже не делает evidence
независимым.

## 33. Competing hypotheses

Для Problem P хранится H(P)={H1,...,Hn}. Competing hypothesis обязана иметь отличающий механизм или набор assumptions. Для каждой пары желательно хранить
overlapping и discriminating predictions. Если evidence совместим с обеими, связь FAILS_TO_DISCRIMINATE обязательна. Не надо выбирать «главную» гипотезу
слишком рано. Новая гипотеза может быть sibling, а не revision старой. Split и revision должны различаться.

## 34. Hypothesis lifecycle

Состояния: PROPOSED, UNDER_TEST, PARTIALLY_SUPPORTED, SUPPORTED_WITH_LIMITS, CONTESTED, REVISED, REJECTED, OPEN. Переход PROPOSED→UNDER_TEST требует
VerificationPlan. PARTIALLY_SUPPORTED требует supporting evidence и отсутствие blocking contradiction. SUPPORTED_WITH_LIMITS требует явного scope и
известных ограничений. REVISED создаёт новую revision и сохраняет старую. REJECTED требует reasoned assessment, а не отсутствие новых источников. OPEN
допустим как нормальный итог неполного исследования.

## 35. VerificationPlan

VerificationPlan содержит predictions, falsification_conditions и competing_hypotheses. Также assessment_needs, required_methods, required_evidence_classes
и discriminating_tests. Дополнительно stop_conditions и budget. Plan является исполнимым research contract. Он должен показывать, что наблюдалось бы при
истинности H и что отличило бы альтернативы. Не каждый search result закрывает Need. Plan имеет собственную version/fingerprint.

## 36. VerificationIteration

Каждый цикл хранит iteration_id и input_revision. Сохраняются questions, searches, considered sources, evidence_added, arguments и issues. Фиксируются
assessment_before и assessment_after. Decision ∈ {RETAIN,QUALIFY,REVISE,SPLIT,REJECT,OPEN}. Iteration позволяет анализировать траекторию, а не только
финальный статус. Новая iteration не стирает неудачные поиски. Это важно для повторяемости и SearchMemory.

## 37. Observation vs interpretation

Observation: “peak at 44.5° broadened”. Interpretation: “broadening is caused by microstrain”. Первое может быть measurement/evidence. Второе является
Claim/Hypothesis и требует обоснования. Система должна сохранять переход Observation→Interpretation как отдельную relation/derivation. Нельзя допускать,
чтобы extraction сразу превратил наблюдение в механизм. Это особенно важно в научных текстах с плотными интерпретациями.

## 38. Причинность

Предлагается taxonomy: ASSOCIATION, TEMPORAL_ORDER, MECHANISTIC_PLAUSIBILITY. Далее CAUSAL_CONTRIBUTION, PRIMARY_CAUSE, NECESSARY_CAUSE, SUFFICIENT_CAUSE.
Normalizer не может повышать уровень причинности. “associated with” остаётся ASSOCIATION. “consistent with mechanism” не становится CAUSAL_CONTRIBUTION.
Causality level входит в Claim signature. RTT проверяет causality_upgrade как hard error.

## 39. Quantifiers и scope

Извлекаются all, most, some, few, none, at least, at most, approximately, typically. Русские аналоги: все, большинство, часть, некоторые, не менее, не
более, примерно, как правило. “In this sample” и «в исследованной серии» являются scope qualifiers. Потеря quantifier считается scope shift. Scope хранит
population/material, temperature, time, method, geography/domain при необходимости. Два claims с разным scope могут не противоречить друг другу. Conflict
detector обязан сравнивать scope overlap.

## 40. Числа, единицы и uncertainty

MeasurementUnit хранит value, unit, uncertainty, distribution, method, sample и significant_digits. Нормализованная единица не заменяет исходную. 540 °C
может дополнительно храниться как 813.15 K, но source value остаётся. «около 20 %» получает approximation marker. Типы: EXACT, ROUNDED, APPROXIMATE, RANGE,
UPPER_BOUND, LOWER_BOUND, DETECTION_LIMIT. Numeric RTT проверяет sign, unit, scale, bounds и rounding. 5, 5.0 и 5.00 могут означать разную precision.

## 41. Таблицы, рисунки и формулы

Table evidence хранит table_id, row, column и header path. Число без заголовка параметра/единицы не допускается к admission. Digitized figure point
является derived observation и хранит digitization uncertainty. Figure evidence связывает axis labels, series, caption и image ref. FormulaUnit хранит
surface и normalized symbolic form. Derivation связывает formula, assumptions, inputs, code version и result. При возможности формулы проверяются
symbolic/numeric tools, не только LLM.

## 42. MethodUnit

MethodUnit описывает instrument, parameters, calibration, preprocessing, model и uncertainty. Sample preparation также является частью method context.
METHOD Question должен ссылаться на конкретный MethodUnit или missing method field. Сопоставление evidence из разных methods требует method compatibility.
Method limitation может ограничить Claim без прямого counterevidence. Method adequacy является отдельной осью Assessment. Это предотвращает смешение
«данные есть» и «метод способен различить эффект».

## 43. ClaimReviewCase и facets

Один root Claim может иметь несколько ReviewFacet. Facet содержит proposition projection, discipline/method view, AssessmentNeeds и branch key. Пример: XRD
interpretation, kinetics/causality, measurement/statistics. Каждая ветка имеет собственные Q/A, ARG, evidence и issues. Все сохраняют root_claim_id,
case_id, facet_id и branch_id. Root Claim не размножается без необходимости. Это сохраняет независимость ветвей и общую трассируемость.

## 44. Cross-facet relations

Разрешены REQUIRES, CONDITIONS, CONFLICTS_WITH, SHARES_ASSUMPTION, SHARES_EVIDENCE. Также QUALIFIES и INTEGRATES_WITH. Пример: XRD phase identification
REQUIRES calibration validity. Или XRD result INTEGRATES_WITH kinetics interpretation. Эти отношения являются review-process relations. Они не
автоматически становятся domain KnowledgeGraph truth. Cross-facet conflict создаёт integration issue. Cross-facet synergy должна быть явно прослеживаема.

## 45. Join без голосования

ClaimReviewJoinProjection не считает majority vote. Если required facet имеет BLOCKING, whole case обычно BLOCKED. Если unresolved conflict, статус
CROSS_FACET_CONFLICT. Если coverage неполное, INCOMPLETE_COVERAGE. Если нужна смысловая reconciliation, создаётся integration review branch. Readiness
может быть READY_FOR_REDUCER или QUALIFIED_READY. Никакого среднего confidence по специалистам.

## 46. Coverage matrix facets × needs

Пусть F={f1,...,fn}, Needs={n1,...,nm}. Матрица C_ij∈{0,1} показывает покрытие need nj facet fi. Join требует покрытие всех required needs. Дополнительно
проверяется dependency closure. Если Need B зависит от Need A, B не считается закрытым при BLOCKING A. Coverage и dependency являются разными измерениями.
JoinProjection хранит unresolved facets и integration gaps.

## 47. Response ownership

Defender не является отдельной постоянной персоной. ResponseAssignment выбирает scientific_owner_role, addressed_role и response_function.
response_function∈{EXPLAIN,DEFEND,QUALIFY,CONCEDE,REFER,REQUEST_EVIDENCE}. Поля также включают claim_id, facet_id, question_id, advocate_required и
reason_codes. Provider binding выполняется после semantic ResponseAssignment. При missing evidence отвечает owner/research path, а не «адвокат по
умолчанию». Это сохраняет специализацию и уменьшает ролевой зоопарк.

## 48. Specialist, Advocate, Methodologist

Specialist может EXPLAIN, DEFEND, QUALIFY или CONCEDE. Если specialist CONCEDE_LOCAL_POINT, Advocate обычно не нужен. Advocate активируется только при
material attack на ещё defendable position. Methodologist проверяет assumptions, identifiability, measurement limitations и uncertainty. Evidence Auditor
проверяет source/provenance/support/scope/dependencies. Critic атакует конкретный тезис, Skeptic проверяет достаточность основания и альтернативы. Ни одна
роль не меняет authoritative state напрямую.

## 49. Contradiction detection

Contradiction не является простой антонимией. Сравниваются scope, population/material, conditions, time, method и uncertainty. “effect at 740 C” не
противоречит “no effect at 540 C”. Создаётся ConflictCase с shared_scope и differing_scope. Типы: DIRECT, SCOPE_CONDITIONAL, METHOD_DEPENDENT, TEMPORAL,
MEASUREMENT, APPARENT_ONLY, UNRESOLVED. Conflict resolution создаёт AssessmentNeed. История конфликта сохраняется.

## 50. Deduplication и canonical claim

Два claims могут быть EXACT_DUPLICATE, SEMANTIC_EQUIVALENT, SUBSUMES, OVERLAPS или DISTINCT. Deduplication не удаляет provenance. Эквивалентные
formulations связываются с canonical Claim. Canonical Claim может иметь RU, EN, technical и plain-language renderings. Embeddings используются для
candidate matching. Structured semantics решают финальную equivalence decision. Различие causality/modality/scope запрещает автоматическое объединение.

## 51. Writer integration

Writer получает authorized claims, evidence links, scope, modality, uncertainty и citation requirements. Writer не получает право свободно «улучшать»
фактологию. Draft→realized claim extraction→RTT→repair. AUTHORIZED и QUALIFIED_AUTHORIZED могут использоваться как factual prose. OPEN/BLOCKED упоминаются
только как hypothesis/limitation/discussion. Citation выбирается через ClaimEvidenceLink/HypothesisEvidenceLink, а не proximity. Writer ontology не должна
дублировать Researcher ontology.

## 52. Researcher integration

Researcher владеет extraction, ResearchDOM, Claim/Evidence, Hypothesis, QuestionGraph и Verification. Он создаёт AssessmentNeed/ReviewWorkField для
Tribunal. Researcher не отвечает за литературный стиль финального текста. После Tribunal он принимает typed issues и research challenges. Новый evidence
возвращается в точную branch anchor. Branch resume не должен перезапускать всю тему. Researcher хранит uncertainty как многомерное поле.

## 53. Coder integration

Coder обслуживает numerical analysis, simulations, graph algorithms и extraction tooling. Задача оформляется ComputationNeed/CodeWork contract. Coder
возвращает DerivationArtifact, DataArtifact, TestArtifact и provenance. Artifact не становится evidence до admission. WorkspaceRef является обязательным,
process cwd не является authority. Code hash, inputs, environment, random seed и outputs сохраняются. Это делает вычисление воспроизводимым.

## 54. OpenCode plugin boundary

OpenCode plugin является host adapter и transport. Он не знает внутреннюю научную онтологию глубже generic contracts. Plugin получает HostContext и
вызывает Harness Core через bridge RPC. Core запрашивает SemanticExecutionRequest. Plugin выполняет его через OpenCode SDK/session runtime. Возвращается
SemanticExecutionResult. Claim/Hypothesis/Evidence/Tribunal state остаются в Python Harness Core. Обновление OpenCode должно менять HostAdapter, а не
научные контракты.

## 55. HostContext и WorkspaceRef

HostContext содержит host, host_version, plugin_version, session_id, message_id и agent_id. Также directory, worktree, project_ref и features_fingerprint.
Raw OpenCode SDK objects не проходят RPC. WorkspaceRef содержит directory, worktree, readonly, identity и authorization state. Core повторно валидирует
WorkspaceRef. Plugin является источником host context, но не научной authority. HostContext versioned как отдельный DTO.

## 56. SemanticExecutionRequest/Result

Request содержит execution_id, purpose, role_ref, bounded_input и expected_output_schema. Дополнительно permission_profile, model_policy, timeout и
trace_context. purpose может быть TRIBUNAL_ROLE, WRITER_DRAFT, WRITER_REPAIR, CODE_WORK, CODE_REVIEW. Result содержит runtime_status, host_session_id,
provider_id, model_id и structured_output. Дополнительно raw_output_ref, usage, timing, host_error, features_fingerprint. Runtime status не содержит
epistemic status. FAILED/TIMED_OUT/CANCELLED не превращаются в scientific OPEN.

## 57. Bridge RPC

Bridge должен быть full-duplex, а не request-response subprocess wrapper. Plugin может отправить harness.run и ждать. В это время Core может отправить
reverse semantic.execute. Correlation IDs связывают nested requests. Protocol поддерживает hello, health, run, cancel, semantic.execute, semantic.cancel,
shutdown. NDJSON framing удобен для stdio transport. Protocol major mismatch блокирует работу. Minor compatible versions договариваются о highest common
version.

## 58. Update resilience

Версия OpenCode не равна capability. Поддержка = exact host version + feature probes + packaged E2E + compatibility record. HostAdapter является
единственным слоем, знающим OpenCode-specific shapes. Если OpenCode меняет worktree/session API, меняется adapter/probe fixture. Core DTO и scientific
state не меняются. Unknown host version получает DEGRADED_UNCERTIFIED. Production semantic provider не выбирается молча на uncertified host.

## 59. Provider readiness

Старые implemented/available слишком грубы. Новые измерения: adapter_present, bridge_ready, runtime_ready, authenticated. Также healthy,
semantic_smoke_passed, certified_host. Проекция состояний: MISSING, INSTALLED, DEGRADED, EXECUTION_READY, SEMANTIC_VALIDATED, CERTIFIED. RPB policy
указывает требуемый уровень. Наличие launcher-файла не означает runtime readiness. Fallback требует нового preflight и нового provider binding lineage.

## 60. Language-specific benchmark

Нужен gold corpus отдельно для RU и EN. Аннотации: units, modality, negation, scope, entities, relations, evidence links. Метрики extraction:
Precision=TP/(TP+FP), Recall=TP/(TP+FN). Semantic match классы: exact, compatible, partial, wrong. Отдельно измеряются modality drift, causality upgrade и
numeric drift. Mixed-language corpus нужен обязательно. LanguageProfile хранит modality/causality/negation/quantifier patterns.

## 61. Query quality и discriminating power

Question оценивается по relevance к Need, novelty, answerability и scope precision. Отдельно оценивается discriminating power. Если возможный ответ
одинаков при H1 и H2, discrimination LOW. Если ответы расходятся по предсказаниям, HIGH. Не оптимизировать «интересность вопроса». Search action выбирается
по ожидаемому уменьшению blocking uncertainty. Формально можно использовать max E[ΔU_blocking|a]/Cost(a), но qualitative policy предпочтительнее фиктивных
вероятностей.

## 62. Budget и stop conditions

Budget: max_queries, max_sources, max_semantic_turns, max_external_cost, max_wall_time, max_branch_depth. Budget ограничивает completeness, но не меняет
scientific status автоматически. Stop reasons: STOP_RESOLVED, STOP_NO_PROGRESS, STOP_BUDGET. Также STOP_BLOCKING_DATA_MISSING, STOP_METHOD_LIMIT,
STOP_CONFLICT_REQUIRES_HUMAN, STOP_EXTERNAL_DEPENDENCY. Каждый stop является event. OPEN после budget exhaustion является нормальным исходом. REJECTED не
выводится из простого отсутствия ресурсов.

## 63. Security и prompt injection

Source text всегда считается data, а не instructions. System contract, task и bounded evidence разделяются. Untrusted PDF/HTML не получает authority.
Internal semantic worker имеет minimum permissions. По умолчанию read-only, no harness recursion, no unrestricted shell. Coder получает отдельный
workspace-bound profile. Recursion guard запрещает semantic worker вызывать harness_run. Security checks не должны зависеть только от prompt.

## 64. Failure taxonomy

RUNTIME_FAILED, RUNTIME_TIMED_OUT, RUNTIME_CANCELLED и HOST_UNAVAILABLE различаются. Также AUTH_REQUIRED, OUTPUT_INVALID, SEMANTIC_REJECTED,
EPISTEMIC_OPEN. Они не сворачиваются в один ERROR. PER хранит runtime outcome. Argument/HypothesisAssessment хранит epistemic outcome. Host failure не
должен создавать научное «нет данных». Scientific OPEN не означает transport failure.

## 65. Canonical JSON и fingerprints

Критические объекты получают fingerprint fp(x)=SHA256(canonical_json(x)). Canonical JSON: sorted keys, UTF-8, normalized numbers, explicit schema version.
Transient timestamps не должны менять semantic fingerprint. Fingerprint нужен для TEX, HypothesisRevision, VerificationPlan, EvidenceDigest и policy. ID и
fingerprint различаются. ID сохраняет identity, fingerprint отражает content revision. Migration хранит old→new fingerprint mapping.

## 66. Event log и provenance

События: UNIT_EXTRACTED, CLAIM_PROPOSED, CLAIM_ADMITTED, HYPOTHESIS_CREATED. Также QUESTION_ASKED, ANSWER_RECEIVED, EVIDENCE_ADDED, ASSUMPTION_OPENED.
Дополнительно HYPOTHESIS_REVISED, ASSESSMENT_CHANGED, BRANCH_JOINED. Event log append-only. Derived object знает created_from, created_by, method,
model/code version и policy hash. LLM trace хранит model/provider, contract и bounded-input fingerprint. Это позволяет replay и forensic audit.

## 67. Storage и graph persistence

На первом этапе достаточно canonical JSON + SQLite indexes + append-only events. Отдельная graph DB не обязательна. Нужны indexes by_source, by_claim,
by_hypothesis, by_question, by_branch. Также by_revision, by_independence_group, by_entity, by_method. Graph projections строятся из authoritative
objects/events. Одна огромная mutable JSON-свалка запрещена. Graph DB рассматривается позже при corpus-scale traversal.

## 68. Deterministic checks vs LLM

Код проверяет hashes, IDs, dangling refs, schema versions, units и exact duplicates. Также graph existence, revision parent, numeric formatting и policy
permissions. LLM нужен для semantic decomposition, scope interpretation, relation proposal и question generation. LLM не нужен для SHA256, unit conversion,
ID lookup и простых arithmetic checks. Это снижает стоимость и семантический шум. Принцип: deterministic when possible, semantic when necessary.

## 69. Multi-pass extraction

Pass 1: candidate information units. Pass 2: normalization и entity/relation linking. Pass 3: round-trip semantic audit. Pass 4: adversarial
scope/contradiction check для важных claims. Каждый pass имеет собственный artifact и trace. Нельзя перезаписывать предыдущий pass без lineage. Admission
происходит после hard validators. Для простых текстов некоторые passes можно объединять по policy, но trace сохраняется.

## 70. Evidence slicing и независимость ролей

Evidence-view compiler определяет, какие spans видит роль. Role не может сам расширить view на sibling branch. FRESH_CONTEXT получает минимальный
независимый slice. Запрос дополнительного контекста создаёт typed ResearchNeed. Несколько roles на одном evidence не увеличивают evidence independence.
Role diversity полезна для analysis, но не является replication. Это особенно важно для Tribunal.

## 71. Exact resume и stale context

Resume anchor содержит case_id, branch_id, question_id, issue_id, graph_revision и policy_hash. Новый evidence возвращается в точную точку ветки. Если
graph revision изменился, старый answer может стать stale. Он должен revalidate или получить superseded state. Optimistic concurrency использует
expected_revision. Конфликт revision вызывает reconcile/retry, а не молчаливую перезапись. Idempotency обеспечивается operation_id и input fingerprint.

## 72. Final synthesis contract

FinalSynthesis содержит authorized_claims, qualified_claims, open_hypotheses и rejected_hypotheses. Дополнительно blocking_uncertainties, evidence_map,
citation_map, scope и limitations. Writer получает именно этот контракт. Synthesis не является «средним мнением». Она фиксирует agreement, conflicts,
conditionality и missing discriminating evidence. Каждая factual sentence должна быть трассируема до authorized source/evidence path. Round-trip validator
проверяет финальный draft перед release.

## 73. E2E: базовый положительный сценарий

Одна статья, один measurement Claim, явная таблица, нет конфликтов. Ожидается Source→SourceSpan→MeasurementUnit→EvidenceUnit→Claim. Scope и units
сохраняются. Claim получает qualified authorization согласно policy. Writer генерирует предложение с citation link. RTT не обнаруживает drift. Replay
воспроизводит тот же graph projection.

## 74. E2E: зависимые источники

Три статьи используют один dataset. Ожидается три Source, но один independence group. Evidence count не повышает independent support до трёх. Assessment
показывает dependency note. Если одна статья является review, lineage указывает primary work. Writer не формулирует «подтверждено тремя независимыми
исследованиями». Тест проверяет TD-049 behavior.

## 75. E2E: modality и language

RU source: «результаты могут свидетельствовать о влиянии». Extractor proposal «влияние доказано» должен быть rejected. EN source: “is consistent with” не
становится “demonstrates”. RU «не исключено отсутствие эффекта» не превращается в positive effect. EN “no significant increase was observed” не
превращается в strict absence. Cross-language canonical matching сохраняет causality/modality differences. Тесты должны иметь gold annotations.

## 76. E2E: competing hypotheses

H1 и H2 обе совместимы с E1. E1 получает FAILS_TO_DISCRIMINATE. QuestionGenerator создаёт DISCRIMINATION need. SearchPlan ищет метод/measurement,
различающий predictions. Если новый E2 различает H1/H2, assessment обновляется. Если нет, обе hypotheses остаются OPEN/CONTESTED. Система не выбирает H1
из-за большего числа перефразирующих sources.

## 77. E2E: Tribunal grounding

Specialist отвечает убедительно, но без source-backed grounding. Grounding=MODEL_PRIOR. Ответ сохраняется как hypothesis/query seed. Создаётся
MissingEvidence/ResearchChallenge. DEFENDS не создаётся. Если specialist CONCEDE_LOCAL_POINT, Advocate не запускается автоматически. Если evidence-backed
defense допустим, ARG admission происходит до observer.

## 78. E2E: multidisciplinary fork/join

Root Claim получает facets XRD, kinetics и statistics. Каждая ветка независимо проходит Q/A и evidence. XRD=SUPPORTED, kinetics=QUALIFIED,
statistics=BLOCKING. Whole Join=BLOCKED. Позже new measurement закрывает statistics need. Join пересчитывается без изменения истории других branches.
Synergy relation может показать, что XRD result закрыл prerequisite kinetics.

## 79. E2E: OpenCode update

Обновляется OpenCode host version. HostAdapter compatibility probe выявляет изменение API. Plugin provider становится DEGRADED_UNCERTIFIED. Hostless
Writer/Researcher/Coder/R4 tests остаются зелёными. Core scientific schemas не меняются. Исправляется только HostAdapter/compatibility fixture. После
semantic smoke host получает CERTIFIED. Это главный acceptance сценарий maintainability.

## 80. Реализационная декомпозиция пакетов

Предлагаемый Python package: research_semantics/. Модули: contracts.py, information_units.py, normalization.py, language_profiles.py. Также claim_graph.py,
hypothesis.py, questions.py, evidence.py, independence.py. Дополнительно rtt.py, reducers.py, projections.py, migrations.py. OpenCode-specific code
остаётся в packages/opencode-plugin/src/host/. Bridge DTO schemas публикуются отдельно. Не помещать domain ontology внутрь plugin.

## 81. Интерфейсы

InformationExtractor предлагает units. Normalizer создаёт normalized semantics. LanguageProfile задаёт language-specific rules. ClaimComposer собирает
compatible units. HypothesisPlanner создаёт VerificationPlan. QuestionGenerator создаёт typed Question. EvidenceLinker связывает evidence с
Claim/Hypothesis. IndependenceAnalyzer строит dependency groups. SemanticRoundTripValidator ищет semantic drift. AssessmentReducer создаёт authoritative
projection.

## 82. Порядок реализации

P0: SourceSpan, InformationUnit, PropositionUnit, ClaimLink, RTT. P1: QuestionGraph, EvidenceDigest, EvidenceLink. P2: HypothesisRevision и
VerificationPlan. P3: Evidence independence/dependency. P4: ClaimReviewCase и fork/join. P5: iterative verification + branch resume. P6: Writer/Coder
shared integration. Каждый этап проходит virtual E2E до расширения.

## 83. Почему именно такой порядок

Без стабильной InformationUnit гипотезы строятся на неустойчивом тексте. Без RTT семантика расползается между extraction и Writer. Без QuestionGraph
итерации превращаются в свободный разговор агентов. Без independence несколько публикаций создают ложную уверенность. Fork/join имеет смысл после
стабилизации единиц и AssessmentNeeds. Plugin transport внедряется независимо от научной онтологии. Это минимизирует одновременное изменение границ.

## 84. Acceptance metrics

Hard metrics: schema validity, dangling refs=0, unauthorized claims=0, numeric drift=0. Для authorized factual claims provenance coverage=100%. Hard RTT
errors должны быть 0 на release path. Soft metrics: question novelty, retrieval efficiency, evidence independence coverage. Также branch depth, semantic
rejection rate, source verification rate. Runtime calibration измеряет false citation, scope drift и grounding errors. RU/EN метрики ведутся отдельно.

## 85. Ключевые математические инварианты

1) Status(H)=Π(A(H),policy), а не mean(A). 2) N_eff≤N_sources при evidence dependence. 3) FAILS_TO_DISCRIMINATE не увеличивает discriminating support. 4)
Required blocking facet ⇒ Join не READY. 5) fp(x)=SHA256(canonical_json(x)) для versioned semantic artifacts. 6) compat(U) является обязательным условием
composition Claim. 7) Q2 требует новой semantic surface или explicit reopen reason. 8) Runtime failure и epistemic OPEN принадлежат разным пространствам
состояний.

## 86. Итоговая схема

Source→SourceSpan→InformationUnit→PropositionUnit→Claim. Claim→Hypothesis/CompetingHypotheses→VerificationPlan.
VerificationPlan→AssessmentNeed→QuestionGraph→Search/Evidence/Derivation. Далее Tribunal Q→A→Q→ArgumentGraph→HypothesisAssessment.
Assessment→Retain/Qualify/Revise/Split/Reject/Open. ClaimReviewCase объединяет дисциплинарные branches через dependency-aware Join. Authorized Claim
Projection передаётся Writer. Writer проходит round-trip semantic validation и создаёт final artifact. Вся цепочка сохраняет provenance, revisions и policy
fingerprints.

## 87. Финальный принцип

Система обязана различать: что написано, что измерено, что интерпретировано и что предположено. Отдельно: что выведено, что оспорено, что проверено и что
осталось неизвестным. Если эти уровни смешиваются, граф превращается в формализованную галлюцинацию. Цель метода не заменить научный метод одной LLM. Цель
метода: сделать LLM участником исследовательского процесса с контролируемой памятью, provenance и проверками. Модели и OpenCode могут обновляться
независимо. Научная семантика и история решения остаются устойчивыми.

# Приложение A. Минимальные JSON-контракты

## A.1 InformationUnit/1.0

```json
{
  "schema": "information-unit/1.0",
  "unit_id": "IU-...",
  "unit_kind": "OBSERVATION",
  "source_span_ids": ["SPAN-..."],
  "language": "ru",
  "surface_text": "...",
  "normalized_semantics": {},
  "scope": {},
  "modality": "OBSERVED",
  "polarity": "POSITIVE",
  "entities": [],
  "relations": [],
  "provenance": {},
  "revision": 1,
  "fingerprint": "sha256:..."
}
```

## A.2 HypothesisRevision/1.0

```json
{
  "schema": "hypothesis-revision/1.0",
  "hypothesis_id": "HYP-...",
  "revision_id": "HYP-....r2",
  "parent_revision_id": "HYP-....r1",
  "statement": "...",
  "scope": {},
  "assumptions": [],
  "predictions": [],
  "competing_hypotheses": [],
  "falsification_conditions": [],
  "trigger_refs": [],
  "fingerprint": "sha256:..."
}
```

## A.3 Question/1.0

```json
{
  "schema": "research-question/1.0",
  "question_id": "Q-...",
  "question_type": "DISCRIMINATION",
  "assessment_need_id": "NEED-...",
  "branch_id": "BR-...",
  "text": "...",
  "target_refs": [],
  "generated_from": [],
  "semantic_surface": {},
  "status": "OPEN"
}
```

## A.4 EvidenceDigest/1.0

```json
{
  "schema": "evidence-digest/1.0",
  "evidence_id": "EVD-...",
  "span_ids": ["SPAN-..."],
  "direct_support": [],
  "does_not_support": [],
  "conditions": [],
  "method": {},
  "limitations": [],
  "independence_group": "IG-...",
  "fingerprint": "sha256:..."
}
```

## A.5 SemanticExecutionRequest/1.0

```json
{
  "schema": "semantic-execution-request/1.0",
  "execution_id": "EXEC-...",
  "purpose": "TRIBUNAL_ROLE",
  "role_ref": "xrd_specialist",
  "bounded_input": {},
  "expected_output_schema": {},
  "permission_profile": "semantic-worker-readonly",
  "model_policy": {},
  "timeout_ms": 180000,
  "trace_context": {}
}
```

# Приложение B. Обязательные свойства тестового корпуса

Корпус должен содержать русский и английский научный текст. Должны присутствовать modality hedges и отрицание. Должны присутствовать numbers, ranges, units
и uncertainty. Должны присутствовать dependent sources. Должны присутствовать competing hypotheses. Должны присутствовать таблицы и figure captions. Должны
присутствовать OCR errors. Должны присутствовать ложные cross-language equivalents. Должны присутствовать causal vs associative formulations. Должны
присутствовать cases, где ответ модели основан только на MODEL_PRIOR.

# Приложение C. Release checklist

Проверить schema versions. Проверить canonical JSON. Проверить fingerprints. Проверить dangling refs. Проверить RTT hard classes. Проверить evidence
independence groups. Проверить ClaimReviewJoin blocking rules. Проверить QuestionGraph novelty. Проверить OpenCode plugin host adapter отдельно от Core.
Проверить Writer/Researcher/Coder hostless regression. Проверить production semantic trace. Проверить rollback/migration. Проверить tracker и tech debt.
Да, при таком уточнении я бы не проектировал это как один «большой модуль», а как **модульный контур с явными портами, реестром и маршрутизатором исполнения**. То есть `semantic_field` должен быть не монолитом, а набором взаимозаменяемых капсул, которые можно подключать к разным точкам пайплайна: к Writer, Researcher, Coder, dialogue-loop, benchmark-runner и т. д.

Ниже — предлагаемая архитектура.

---

# 1. Ключевое разделение: модуль ≠ роутер ≠ артефакт

Чтобы система не превратилась в неконтролируемую сеть вызовов, нужно жёстко разделить три сущности.

## 1.1. Модуль

Модуль — это вычислительная капсула с конкретным входом и выходом.

Примеры модулей:

```text
source.normalizer
segmentation.base_units
segmentation.clause
observations.tfidf
observations.sbert
observations.symbolic
geometry.direct_sum
windows.fixed
windows.adaptive
basis.identity
basis.nmf
calibration.pseudo
analytics.rank_spectrum
analytics.kinematics
analytics.recurrence
derived.transitions
derived.claim_candidates
derived.temporal_graph
validation.invariants
projection.writer
projection.researcher
projection.coder
projection.dialogue
```

Каждый модуль обязан иметь:

```python
module_id: str
version: str
input_contract: ContractRef
output_contract: ContractRef
required_capabilities: set[str]
optional_capabilities: set[str]
side_effects: SideEffectPolicy
```

---

## 1.2. Роутер / планировщик

Роутер не выполняет математику сам. Он только:

1. принимает запрос;
2. выбирает профиль;
3. разрешает конфигурацию;
4. строит план исполнения;
5. проверяет зависимости между модулями;
6. вызывает модули;
7. собирает артефакт;
8. возвращает ссылку на результат.

То есть роутер — это диспетчер, а не аналитик.

---

## 1.3. Артефакт

Артефакт — иммутабельный результат исполнения.

Другие модули не должны менять артефакт. Они могут:

- читать его;
- ссылаться на него;
- сравнивать с другим артефактом;
- строить новый артефакт на его основе.

Это принципиально для интеграции с Writer/Researcher/CodeFactory, потому что анализ не должен мутировать авторитетные состояния.

---

# 2. Общая схема модульного контура

Я бы предложил такую структуру:

```text
External pipeline steps
        │
        ▼
SemanticFieldRouter
        │
        ├── ProfileResolver
        ├── ConfigResolver
        ├── CapabilityRegistry
        ├── PlanBuilder
        ├── DependencyValidator
        ├── CacheStore
        ├── ArtifactStore
        └── ModuleExecutor
                │
                ├── SourceModule
                ├── SegmentationModule
                ├── ObservationModule
                ├── GeometryModule
                ├── BasisModule
                ├── WindowModule
                ├── AnalyticsModule
                ├── DerivedModule
                ├── ValidationModule
                └── ProjectionModule
```

Снаружи это выглядит как несколько высокоуровневых вызовов:

```python
semantic_field.analyze(request)
semantic_field.validate_draft(request)
semantic_field.project_research_question(request)
semantic_field.extract_requirements(request)
semantic_field.update_dialogue(session_ref, turn)
semantic_field.compare(artifact_a, artifact_b)
```

Но внутри каждый вызов проходит через один и тот же модульный механизм.

---

# 3. Контракт запроса к роутеру

Чтобы модуль можно было вставлять в разные места пайплайна, нужен единый формат запроса.

Минимально:

```python
class SemanticFieldRequest(BaseModel):
    request_id: UUID
    source_ref: SourceRef | None = None
    source_text: str | None = None
    context_ref: ContextRef | None = None
    profile: ProfileKind
    stage_hint: StageHint | None = None
    requested_outputs: set[OutputKind]
    budget: RunBudget
    constraints: ConstraintSet
    contract_ref: ContractRef | None = None
```

Где `stage_hint` задаёт место в пайплайне:

```python
class StageHint(str, Enum):
    PRE_DRAFT = "pre_draft"
    POST_DRAFT = "post_draft"
    PRE_RESEARCH_CYCLE = "pre_research_cycle"
    RESEARCH_GAP_DETECTION = "research_gap_detection"
    FEATURE_REQUEST_ANALYSIS = "feature_request_analysis"
    DIALOGUE_TURN = "dialogue_turn"
    BENCHMARK_COMPARISON = "benchmark_comparison"
```

Это позволяет роутеру выбирать разные проекции и наборы модулей, не меняя сам формат запроса.

---

# 4. Контракт ответа

Ответ должен быть одинаково удобен и для человека, и для пайплайна.

```python
class SemanticFieldResult(BaseModel):
    request_id: UUID
    status: RunStatus
    artifact_ref: ArtifactRef
    manifest_ref: ManifestRef
    validation_ref: ValidationRef
    capabilities: dict[str, CapabilityStatus]
    projections: dict[ProfileKind, ProjectionRef]
    warnings: list[str]
    errors: list[ErrorReport]
```

Если вызов происходит внутри Writer:

```python
result.projections[ProfileKind.WRITER]
```

Если внутри Researcher:

```python
result.projections[ProfileKind.RESEARCHER]
```

Если внутри Coder:

```python
result.projections[ProfileKind.CODER]
```

То есть роутер может возвращать один артефакт и несколько проекций, а внешний блок берёт только нужную ему проекцию.

---

# 5. Реестр модулей

Для подключения в разные места пайплайна нужен реестр модулей.

```python
class ModuleRegistry:
    def register(self, module: ModuleDescriptor) -> None: ...
    def resolve(self, module_id: str) -> ModuleDescriptor: ...
    def find_by_capability(self, capability: str) -> list[ModuleDescriptor]: ...
    def probe(self, module_id: str) -> CapabilityReport: ...
```

Каждый модуль регистрируется как декларация:

```python
ModuleDescriptor(
    module_id="observations.tfidf",
    version="1.0.0",
    family="observation",
    input_contract="normalized_source+unit_lattice",
    output_contract="observation_view.tfidf",
    required_capabilities={"text"},
    optional_capabilities=set(),
    deterministic=True,
    cache_level=CacheLevel.L2,
)
```

Это даёт несколько преимуществ:

1. Роутер может проверять, какие модули доступны.
2. Можно строить деградационные профили.
3. Можно заменять реализацию модуля без изменения внешнего пайплайна.
4. Можно тестировать контракты независимо от исполнения.

---

# 6. Планировщик исполнения

Роутер должен строить явный план, а не вызывать модули «по ходу».

```python
class ExecutionPlan(BaseModel):
    plan_id: UUID
    request_ref: RequestRef
    profile: ProfileKind
    stages: list[PlannedStage]
    required_modules: list[str]
    optional_modules: list[str]
    cache_keys: dict[str, str]
    budget: RunBudget
```

Пример плана для Writer:

```text
source.normalize
segmentation.base_units
observations.tfidf
observations.symbolic
geometry.direct_sum
windows.fixed
basis.identity
calibration.pseudo
analytics.rank_spectrum
analytics.kinematics
analytics.recurrence
derived.transitions
derived.claim_candidates
validation.invariants
projection.writer
```

Для Researcher:

```text
source.normalize
segmentation.base_units
observations.tfidf
observations.sbert_if_available
geometry.direct_sum
windows.fixed
basis.nmf_if_available
calibration.pseudo
analytics.rank_spectrum
analytics.recurrence
derived.contradiction_hotspots
validation.invariants
projection.researcher
```

Для dialogue:

```text
source.incremental_normalize
segmentation.incremental_units
observations.cache_only_or_recompute
geometry.patch_state
windows.causal_fixed
analytics.rank_spectrum_incremental
analytics.recurrence_incremental
derived.turn_events
projection.dialogue
```

Важно: план должен быть объектом, который можно сохранять, логировать и проверять. Иначе невозможно будет понять, почему два вызова в разных местах пайплайна дали разные результаты.

---

# 7. Порты и адаптеры

Чтобы модуль можно было цеплять в разные места, нужно использовать паттерн «порты и адаптеры».

## 7.1. Входные порты

Входные порты определяют, откуда модуль получает данные:

```python
class SourcePort(Protocol):
    def load_source(self, source_ref: SourceRef) -> SourceInput: ...

class ContextPort(Protocol):
    def load_context(self, context_ref: ContextRef) -> PipelineContext: ...

class ArtifactPort(Protocol):
    def load_artifact(self, artifact_ref: ArtifactRef) -> SemanticFieldArtifact: ...
```

## 7.2. Выходные порты

Выходные порты определяют, куда модуль отдаёт результат:

```python
class ArtifactSink(Protocol):
    def persist(self, artifact: SemanticFieldArtifact) -> ArtifactRef: ...

class ProjectionSink(Protocol):
    def persist_projection(self, projection: RoleProjection) -> ProjectionRef: ...

class ValidationSink(Protocol):
    def persist_report(self, report: ValidationReport) -> ValidationRef: ...
```

## 7.3. Адаптеры пайплайна

Для каждого внешнего пайплайна делается свой адаптер:

```python
class WriterAdapter:
    def analyze_draft(self, draft: DraftRequest) -> WriterProjection: ...

class ResearcherAdapter:
    def analyze_question(self, question: str) -> ResearchProjection: ...

class CoderAdapter:
    def analyze_feature_request(self, request: FeatureRequest) -> CoderProjection: ...

class DialogueAdapter:
    def append_turn(self, session_ref: SessionRef, turn: Turn) -> DialogueUpdate: ...
```

Внутри эти адаптеры не содержат аналитику. Они только преобразуют внешние объекты в `SemanticFieldRequest` и обратно.

---

# 8. Как это подключать к Writer

Для Writer я бы сделал отдельную точку входа:

```python
class WriterSemanticFieldPort:
    def validate_and_project(
        self,
        draft_request: DraftRequest,
        draft: SourceInput,
    ) -> WriterSemanticFieldResult:
        request = SemanticFieldRequest(
            source_text=draft.raw_text,
            profile=ProfileKind.WRITER,
            stage_hint=StageHint.POST_DRAFT,
            requested_outputs={
                OutputKind.FIELD,
                OutputKind.CLAIM_PROPOSALS,
                OutputKind.VALIDATION,
                OutputKind.WRITER_PROJECTION,
            },
            budget=default_writer_budget(),
            constraints=draft_request.constraints,
        )
        result = router.run(request)
        projection = result.get_projection(ProfileKind.WRITER)
        return WriterSemanticFieldResult(
            status=result.status,
            artifact_ref=result.artifact_ref,
            writer_view=projection,
            validation=result.validation_ref,
        )
```

Writer получает:

```python
WriterView
claim_binding_hints
modality_risk_spans
semantic_rtt
repair_spans
```

но не получает права менять `Claim` или `Evidence` напрямую.

Критическое правило:

```text
Writer может использовать проекцию как диагностический сигнал,
но не как автоматический источник истины.
```

---

# 9. Как это подключать к Researcher

Для Researcher точка входа должна быть другой по смыслу.

```python
class ResearcherSemanticFieldPort:
    def project_question(
        self,
        question: str,
        context_ref: ContextRef,
    ) -> ResearchSemanticFieldResult:
        request = SemanticFieldRequest(
            source_text=question,
            context_ref=context_ref,
            profile=ProfileKind.RESEARCHER,
            stage_hint=StageHint.RESEARCH_GAP_DETECTION,
            requested_outputs={
                OutputKind.FIELD,
                OutputKind.QUESTION_FACETS,
                OutputKind.CONTRADICTION_HOTSPOTS,
                OutputKind.RESEARCHER_PROJECTION,
            },
            budget=default_research_budget(),
        )
        result = router.run(request)
        projection = result.get_projection(ProfileKind.RESEARCHER)
        return ResearchSemanticFieldResult(
            status=result.status,
            artifact_ref=result.artifact_ref,
            question_facets=projection.question_facets,
            contradiction_hotspots=projection.contradiction_hotspots,
            evidence_gap_alignment=projection.evidence_gap_alignment,
        )
```

Researcher использует это не для утверждения истинности, а для:

- выделения фасет вопроса;
- поиска противоречий;
- оценки пробелов;
- ранжирования следующих действий.

Особенно важно: `semantic_field` здесь должен выдавать `proposal`, а не `assertion`.

---

# 10. Как это подключать к Coder

Для Coder нужен отдельный порт, потому что там важна трассировка требований.

```python
class CoderSemanticFieldPort:
    def analyze_feature_request(
        self,
        feature_request: str,
        repo_context_ref: RepoContextRef,
    ) -> CoderSemanticFieldResult:
        request = SemanticFieldRequest(
            source_text=feature_request,
            context_ref=repo_context_ref,
            profile=ProfileKind.CODER,
            stage_hint=StageHint.FEATURE_REQUEST_ANALYSIS,
            requested_outputs={
                OutputKind.FIELD,
                OutputKind.REQUIREMENT_UNITS,
                OutputKind.CONSTRAINT_UNITS,
                OutputKind.ACCEPTANCE_CANDIDATES,
                OutputKind.CODER_PROJECTION,
            },
            budget=default_coder_budget(),
        )
        result = router.run(request)
        projection = result.get_projection(ProfileKind.CODER)
        return CoderSemanticFieldResult(
            status=result.status,
            artifact_ref=result.artifact_ref,
            requirement_units=projection.requirement_units,
            constraint_units=projection.constraint_units,
            acceptance_candidates=projection.acceptance_criteria_candidates,
            conflicts=projection.requirement_conflicts,
        )
```

Coder получает кандидатов, но сам решает, какие из них становятся задачами, тестами или acceptance criteria.

---

# 11. Как это подключать к live dialogue

Для диалога нужен не просто `analyze`, а инкрементальный контур.

```python
class DialogueSemanticFieldPort:
    def start_session(self, session_id: str) -> SessionRef: ...

    def append_turn(
        self,
        session_ref: SessionRef,
        turn: DialogueTurn,
    ) -> DialogueUpdate: ...

    def current_summary(
        self,
        session_ref: SessionRef,
    ) -> DialogueSemanticFieldView: ...
```

Внутри `append_turn` должен вызывать не полный пайплайн, а инкрементальный план:

```text
source.incremental_normalize
segmentation.incremental_units
observations.affected_only
geometry.patch_state
windows.causal_append_only
analytics.rank_spectrum_incremental
analytics.recurrence_incremental
derived.turn_events
projection.dialogue
```

Ключевые инварианты:

1. Старые окна не получают информацию из новых реплик.
2. Новые события привязываются только к новым или затронутым юнитам.
3. Возвращается патч, а не весь артефакт.
4. Патч содержит `provenance` до конкретных реплик.

---

# 12. Варианты реализации роутера

Есть три основных варианта. Они не эквивалентны по риску.

---

## Вариант A. Статический граф пайплайна

План исполнения задаётся профилем почти жёстко.

```python
PROFILE_PLANS = {
    ProfileKind.WRITER: WRITER_PLAN,
    ProfileKind.RESEARCHER: RESEARCHER_PLAN,
    ProfileKind.CODER: CODER_PLAN,
    ProfileKind.DIALOGUE: DIALOGUE_PLAN,
}
```

Плюсы:

- высокая воспроизводимость;
- лёгкая отладка;
- понятные тесты;
- минимум «магии».

Минусы:

- меньше гибкости;
- сложнее адаптироваться к бюджету.

Рекомендация: это лучший вариант для v1.

---

## Вариант B. Динамический планировщик

Роутер сам решает, какие модули запускать, по бюджету и доступности.

Плюсы:

- гибкость;
- можно отключать дорогие модули;
- удобно для исследовательских режимов.

Минусы:

- выше риск невоспроизводимости;
- сложнее тестировать;
- труднее объяснять, почему результат именно такой.

Рекомендация: допустим только после того, как статический граф стабилен.

---

## Вариант C. Событийная шина

Модули публикуют события, другие модули подписываются.

Плюсы:

- удобно для распределённых систем;
- хорошо для мониторинга;
- можно подключать внешние обработчики.

Минусы:

- сложно гарантировать порядок;
- трудно отлаживать;
- легко получить скрытые зависимости.

Рекомендация: использовать только как наблюдаемый слой, не как основной механизм исполнения.

---

# 13. Рекомендуемая модель

Для вашей задачи я бы выбрал:

```text
Статический граф + реестр модулей + явные точки расширения
```

То есть:

1. Основной пайплайн детерминирован.
2. Модули регистрируются через реестр.
3. Роутер выбирает план по профилю.
4. Опциональные модули могут выпадать, но только с явным статусом.
5. Внешние пайплайны подключаются через адаптеры портов.
6. Все результаты сохраняются как иммутабельные артефакты.

Это даёт баланс между гибкостью и воспроизводимостью.

---

# 14. Минимальный интерфейс роутера

```python
class SemanticFieldRouter:
    def __init__(
        self,
        registry: ModuleRegistry,
        config_loader: ConfigLoader,
        store: ArtifactStore,
        cache: CacheStore,
    ) -> None:
        ...

    def preflight(self, request: SemanticFieldRequest) -> PreflightReport:
        ...

    def plan(self, request: SemanticFieldRequest) -> ExecutionPlan:
        ...

    def run(self, request: SemanticFieldRequest) -> SemanticFieldResult:
        plan = self.plan(request)
        pre = self.preflight(request)
        if not pre.ok:
            raise PreflightError(pre.errors)

        execution = self._execute_plan(plan)
        artifact_ref = self._persist_artifact(execution)
        projections = self._build_projections(execution, request.profile)

        return SemanticFieldResult(
            request_id=request.request_id,
            status=execution.status,
            artifact_ref=artifact_ref,
            manifest_ref=execution.manifest_ref,
            validation_ref=execution.validation_ref,
            capabilities=pre.capabilities,
            projections=projections,
            warnings=execution.warnings,
            errors=execution.errors,
        )
```

---

# 15. Контракт отдельного модуля

Каждый модуль должен реализовывать один и тот же протокол.

```python
class SemanticFieldModule(Protocol):
    module_id: str
    version: str

    def preflight(self, context: ModuleContext) -> CapabilityReport: ...

    def applicable(self, context: ModuleContext) -> bool: ...

    def execute(self, context: ModuleContext) -> ModuleOutput: ...
```

Где:

```python
class ModuleContext(BaseModel):
    request: SemanticFieldRequest
    config: SemanticFieldConfig
    upstream: UpstreamData
    cache: CacheHandle
    budget: RunBudget
```

И:

```python
class ModuleOutput(BaseModel):
    module_id: str
    status: ComponentStatus
    data: dict
    warnings: list[str]
    cache_key: str | None = None
    provenance: ProvenanceReport
```

Это позволяет роутеру обрабатывать все модули одинаково.

---

# 16. Правила взаимодействия между модулями

Чтобы система не расплылась, нужно ввести несколько жёстких правил.

## Правило 1: модули не пишут в чужие авторитетные состояния

Запрещено:

```text
semantic_field -> mutate Writer DOM
semantic_field -> mutate Research DOM
semantic_field -> mutate CodeFactory authority state
semantic_field -> admit Claim truth
semantic_field -> admit Evidence verdict
```

Разрешено только:

```text
semantic_field -> propose
semantic_field -> validate
semantic_field -> project
semantic_field -> compare
```

---

## Правило 2: модули общаются только через контракты

Запрещено передавать внутренние объекты напрямую.

Разрешено:

```text
NormalizedSource
UnitLattice
ObservationView
StateBlock
WindowFrame
ModeBasis
SemanticFieldArtifact
ValidationReport
RoleProjection
```

---

## Правило 3: каждый модуль обязан быть идемпотентным

Если вход, конфиг и версии модулей одинаковы, повторный вызов должен давать одинаковый результат.

Это особенно важно, если один и тот же модуль вызывается на разных шагах пайплайна.

---

## Правило 4: роутер не имеет права молча менять план

Если план изменился из-за деградации, это должно быть записано в манифест.

Например:

```json
{
  "planned_modules": ["observations.sbert", "observations.tfidf"],
  "executed_modules": ["observations.tfidf"],
  "skipped_modules": {
    "observations.sbert": "UNAVAILABLE"
  }
}
```

---

## Правило 5: проекции строятся только после валидации

Нельзя отдавать Writer/Researcher проекцию, если базовые инварианты артефакта не проверены.

Минимальный порядок:

```text
field -> validation -> projection
```

Если валидация падает по обязательному пункту, проекция не должна выглядеть как достоверный результат.

---

# 17. Пример маршрутизации по шагам пайплайна

Ниже — схема, как один и тот же модульный контур может использоваться в разных местах.

---

## Шаг 1: до написания текста

Вызов:

```python
router.run(
    SemanticFieldRequest(
        source_ref=plan_ref,
        profile=ProfileKind.WRITER,
        stage_hint=StageHint.PRE_DRAFT,
        requested_outputs={OutputKind.WRITER_PROJECTION},
    )
)
```

Цель:

- понять фазовую структуру будущего абзаца;
- проверить, какие авторизованные claims должны быть покрыты;
- подготовить ожидания для последующего контроля.

---

## Шаг 2: после генерации абзаца

Вызов:

```python
router.run(
    SemanticFieldRequest(
        source_text=draft_text,
        profile=ProfileKind.WRITER,
        stage_hint=StageHint.POST_DRAFT,
        requested_outputs={
            OutputKind.FIELD,
            OutputKind.CLAIM_PROPOSALS,
            OutputKind.VALIDATION,
            OutputKind.WRITER_PROJECTION,
        },
    )
)
```

Цель:

- проверить покрытие;
- найти модальностные риски;
- предложить ремонтные спаны.

---

## Шаг 3: исследовательский цикл

Вызов:

```python
router.run(
    SemanticFieldRequest(
        source_text=research_question,
        context_ref=research_context_ref,
        profile=ProfileKind.RESEARCHER,
        stage_hint=StageHint.RESEARCH_GAP_DETECTION,
        requested_outputs={OutputKind.RESEARCHER_PROJECTION},
    )
)
```

Цель:

- получить фасеты вопроса;
- найти противоречия;
- связать с пробелами в доказательствах.

---

## Шаг 4: код-пайплайн

Вызов:

```python
router.run(
    SemanticFieldRequest(
        source_text=feature_request,
        context_ref=repo_context_ref,
        profile=ProfileKind.CODER,
        stage_hint=StageHint.FEATURE_REQUEST_ANALYSIS,
        requested_outputs={OutputKind.CODER_PROJECTION},
    )
)
```

Цель:

- выделить требования;
- найти ограничения;
- предложить acceptance-критерии.

---

## Шаг 5: диалог

Вызов:

```python
dialogue_port.append_turn(session_ref, turn)
```

Цель:

- получить текущий `n_peak`;
- отследить переход;
- обнаружить рецидив;
- показать причинно привязанный источник события.

---

# 18. Контроль ошибок в модульной сети

Когда модулей много, ошибки становятся опаснее, чем в монолите. Нужна явная таксономия.

## 18.1. Типы ошибок

```python
class ModuleError(Exception): ...
class ContractError(ModuleError): ...
class CapabilityError(ModuleError): ...
class RequiredModuleError(ModuleError): ...
class OptionalModuleError(ModuleError): ...
class DependencyOrderError(ModuleError): ...
class CacheCorruptionError(ModuleError): ...
class ArtifactReferenceError(ModuleError): ...
```

## 18.2. Правила агрегации

```text
если обязательный модуль FAILED:
    весь запуск FAILED

если обязательные модули прошли, но опциональный деградировал:
    запуск DEGRADED

если модуль не применим к входным данным:
    статус NOT_APPLICABLE

если модуль отсутствует, но не обязателен:
    статус UNAVAILABLE
```

## 18.3. Запрет тихой деградации

Нельзя, чтобы отсутствие SBERT приводило к молчаливой замене результата.

Всегда должно быть видно:

```json
{
  "observations.sbert": "UNAVAILABLE",
  "observations.tfidf": "PASS"
}
```

---

# 19. Валидация модульной архитектуры минимум тремя способами

Для такой архитектуры я бы обязательно использовал три класса проверки.

---

## 19.1. Контрактная валидация

Проверяется:

- каждый модуль имеет корректный входной и выходной контракт;
- роутер не запускает модуль, если входной контракт не совпадает;
- версии контрактов совместимы;
- неизвестные поля отвергаются.

Методы:

- `pydantic` strict models;
- JSON Schema;
- schema round-trip tests.

---

## 19.2. Инвариантная валидация

Проверяется:

- `offset_map` корректен;
- окна нормированы;
- метрика PSD;
- причинный режим не смотрит в будущее;
- ранговый спектр нормирован;
- каждый вывод имеет источник.

Это особенно важно, потому что модульная сеть может быть формально рабочей, но математически испорченной.

---

## 19.3. Поведенческая валидация

Проверяется на фикстурах:

- парафраз;
- перестановка;
- усиление модальности;
- усиление причинности;
- удаление квалификатора.

Ожидаемая матрица:

| Мутация | Ожидаемая реакция |
|---|---|
| парафраз | близкая тематическая геометрия |
| перестановка | различимая траектория |
| модальность | изменение символического слоя |
| причинность | падение `RTT causality` |
| удаление квалификатора | изменение эпистемического статуса |

Если модульная сеть не проходит эти тесты, она не готова к подключению к Writer/Researcher.

---

# 20. Риски, которых нужно избегать

## 20.1. Роутер становится «умным агентом»

Если роутер начинает сам принимать содержательные решения, он превращается из инфраструктурного модуля в скрытый авторитетный источник. Это опасно.

Роутер должен быть глупым в хорошем смысле: детерминированным, логгируемым, проверяемым.

---

## 20.2. Модули начинают мутировать контекст

Если Writer передаёт в модуль свой внутренний объект, а модуль его меняет, возникает скрытая запись состояния. Это недопустимо.

Все изменения должны происходить только через явные команды внешних блоков, не через анализ.

---

## 20.3. Разные шаги пайплайна используют разные версии контрактов

Если один шаг использует `semantic-field-run-request-1.0`, а другой уже `1.1` без явной миграции, результаты станут несопоставимыми.

Нужен явный `schema_version` и политика совместимости.

---

## 20.4. Модуль вызывается слишком часто без кэша

Если каждый шаг пайплайна будет вызывать полный анализ заново, система станет медленной и будет создавать дубли артефактов.

Нужен кэш по:

```text
source_hash
config_hash
module_versions
basis_hash
profile
requested_outputs
```

---

## 20.5. Проекции путают с истиной

`WriterProjection`, `ResearchProjection`, `CoderProjection` — это интерпретационные слои. Они не должны восприниматься как окончательные утверждения.

В интерфейсах стоит явно помечать:

```python
proposal_only: bool = True
authority_mutation_allowed: bool = False
```

---

# 21. Итоговая рекомендация

Я бы делал это не как «один модуль-роутер», а как:

```text
semantic_field = module registry
               + execution router
               + deterministic pipeline plans
               + immutable artifacts
               + role adapters
               + validation layer
               + cache/provenance layer
```

Для внешнего пайплайна это должно выглядеть как набор портов:

```python
WriterSemanticFieldPort
ResearcherSemanticFieldPort
CoderSemanticFieldPort
DialogueSemanticFieldPort
BenchmarkSemanticFieldPort
```

А внутри все они должны использовать один и тот же механизм:

```python
request -> plan -> modules -> validation -> artifact -> projection
```

Если сформулировать коротко:

```text
Нужен не «универсальный модуль»,
а дисциплинированная модульная сеть
с жёсткими контрактами, явными статусами,
иммутабельными артефактами и роутером,
который только выбирает и исполняет план,
но не принимает содержательных решений за другие подсистемы.
```