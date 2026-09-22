# WRITER ITERATIVE CHAPTER E2E 001

## Цель
Проверить Writer как итерационный контур заполнения главы: грубый каркас → связный черновик → добавление данных → style/discussion pass → намеренная семантическая ошибка → selective repair → semantic evidence curation → release.

## Тестовый объект
Мини-раздел диссертации по фазовым превращениям при азотировании. Содержательное ядро построено по предоставленным пользователем работам Рахадилова и Demchenko; Meka и Schacherl использованы как структурные/style references и сравнительные источники там, где это явно разрешено.

## Итерации

| Версия | Что изменялось | Evidence | Trace | RTT | Release |
|---|---|---:|---:|---:|---:|
| V0 | грубый каркас | FAIL | PASS | FAIL | FAIL |
| V1 | первый фактологический абзац | FAIL | FAIL | PASS | FAIL |
| V2 | числа + внешнее сопоставление | FAIL | FAIL | PASS | FAIL |
| V3 | discussion/style pass | FAIL | FAIL | PASS | FAIL |
| V4 | намеренный causality upgrade | FAIL | FAIL | FAIL | FAIL |
| V5b | semantic repair causality | FAIL | FAIL | PASS | FAIL |
| V6 | новый C-007 + semantic curation | PASS | PASS | PASS | PASS |

## Что поймано по ходу

### 1. Ложный numeric parsing
`Р6М5` разбирался как `6 М`, а `Fe4N` как `4 N`. Это делало нормальные текстовые claims `AMBIGUOUS`. Исправлено boundary-aware regex; добавлены regression tests.

### 2. Release проверял будущие claims
При естественном заполнении DOM в нем уже могут находиться запланированные claims, еще не реализованные в текущем тексте. Старый release считал их omissions/evidence failures. Теперь при наличии явных `[C-*]` release scoped к реально реализованным claims. Исторический unmarked path сохранен как fallback.

### 3. RTT повторно угадывал соответствие claim ↔ sentence
Хотя текст уже содержал `[C-*]`, RTT запускал эвристический rematch и выдавал ложные NUMERIC_DRIFT/NEGATION_FLIP на соседних предложениях. Теперь marker-bound path сравнивает contract с предложением, которое явно содержит его claim marker. Намеренный V4 `однозначно вызвано` корректно дал `CAUSALITY_UPGRADE`; после V5b semantic RTT PASS.

### 4. Read-only verification игнорировал курацию
`verify_claims` защищал curated verdict только при `--apply`; read-only release снова видел `OPEN`. Теперь read-only возвращает effective merged verdict, но DOM не мутирует.

### 5. Style pass рождает новые claims
В V3 связующее предложение про предел обнаружения XRD было полезным, но стало orphan claim. Traceability его поймала. В V6 оно заведено как отдельный derived C-007, связано с S-RAK-87 и после semantic review стало release-eligible. Это желательное поведение, но DraftArtifact пока не имеет первого класса `proposed_new_claims`; новый claim обнаруживается поздно, на trace.

### 6. Researcher остается главным blocker
Детерминированный Researcher хорошо проверяет числа/формулы, но не умеет textual entailment. Поэтому C-001/C-002/C-004 оставались OPEN, пока не была смоделирована semantic curation. Writer pipeline после курации проходит полностью. Это подтверждает, что следующий крупный долг действительно в Researcher, а не в Writer release chain.

### 7. Language hard-filter слишком жесткий для style references
Для русского target автоматический style selection выбрал только русский Rakhadilov fragment. Probe без language hard-filter поставил Meka первым по style+graph score, затем Rakhadilov и Schacherl. Следовательно, нужен tiered режим: same-language для surface/lexical style, cross-language разрешать как `structure_only` (graph motifs, argument structure, paragraph shape, citation architecture).

### 8. Evidence selection пока section-level, а не claim-level
Глобальный query выбирает неплохой набор источников, но порядок может быть нерелевантным конкретному claim. Для зрелого DraftRequest evidence references надо формировать per-claim, а потом объединять в section bundle.

### 9. Source update selective invalidation работает
После семантического обновления S-RAK-87 invalidation затронул только C-004 и C-007 и только PAR-1. Количественный абзац DP-002 не попал в repair. State policy перевел оба claim из SUPPORTED в PENDING_REVALIDATION.

## Что работает уже убедительно
- DraftRequest/DraftArtifact граница;
- запрет web discovery у Writer;
- DOM patch и ChangeLedger;
- claim/source markers;
- RTT после explicit claim binding;
- causality-upgrade detection;
- source→claim→paragraph dependency graph;
- selective invalidation/repair;
- aggregate release после evidence curation.

## Что я бы сделал следующим
1. `StyleReferenceTier`: same-language surface style + cross-language `structure_only`.
2. `ProposedClaim/1.0` в DraftArtifact, чтобы новые synthesis claims не ждали trace stage.
3. `ClaimEvidenceBundle`: evidence selection отдельно для каждого claim.
4. Развести `verification_state=OPEN` и `epistemic_uncertainty`: сейчас trace местами трактует отсутствие semantic verifier как языковую неопределенность claim.
5. Release scope в будущем брать из DraftArtifact/DOM realization map, а inline `[C-*]` оставить проверяемым rendered representation, не единственным authority.
6. После этого contracts Writer можно замораживать v1 и переходить к semantic Researcher.

## Regression
После hardening: 107/107 unittest PASS, compileall PASS, git diff --check PASS.
