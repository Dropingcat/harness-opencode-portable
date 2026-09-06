# Claim Routing Architecture

Следующий слой после router core: задача сначала раскладывается на claims/proposals, и только потом claims маршрутизируются по buckets/execution cells.

## 1. Поток

```text
task_text
-> split_claims
-> classify claim kinds
-> assign buckets
-> route plan per claim
-> grouped execution plan
-> execution cells
-> audit/integration
```

## 2. Claim-first principle

Минимальная единица orchestration — не whole task и не whole file, а claim/proposal.

Claim может быть:

- requirement
- code_change
- interface
- test
- factual
- evidence
- citation
- config
- security
- performance
- docs
- unresolved_question

## 3. Deterministic first split

Первый splitter не использует LLM. Он:

- режет по буллетам / numbered items / sentence boundaries;
- выделяет imperative statements;
- классифицирует claim kind по regex/policy;
- присваивает bucket по `claim_bucket_rules.json`.

## 4. Claim contract

```json
{
  "claim_id": "CLM_...",
  "text": "Add tests for router core",
  "kind": "test",
  "bucket": "code",
  "priority": "normal",
  "dependencies": [],
  "reason_codes": ["CLAIM_PARSED", "BUCKET_ASSIGNED"]
}
```

## 5. Grouped execution plan

После split claims группируются по bucket:

- `code` claims → code execution cell
- `research` claims → research pipeline
- `integration` claims → config/plugin/MCP cell
- `security` claims → strict guarded cell
- `writing` claims → writer/export cell

## 6. Why this matters

Это позволяет:

- rework не всю задачу, а только failed claims;
- привязывать audit к claim level;
- связывать claims с graph, skills, tools и runtime;
- не смешивать code/research/config/security в одном giant prompt.

## 7. Artifacts

- `config/claim_kinds.json`
- `config/claim_bucket_rules.json`
- `scripts/router/split_claims.py`
- `scripts/router/build_task_plan.py`

## 8. Integration with existing router

`resolve_route.py` остаётся coarse router for task class.

`split_claims.py` добавляет второй слой:

- task-level route
- claim-level routing
- grouped execution plan

`build_task_plan.py` собирает это в один deterministic artifact:

```text
task -> split claims -> per-claim route plan -> grouped execution plan
```

Именно это сближает harness с researcher-core claim pipeline.
