#!/usr/bin/env python3
"""S-expression контракты для Writer Cell и свиты.

Каждая операция — контракт: вход, выход, критерии приёмки, бюджет, on_fail.
Conservation law: Σ бюджетов ≤ бюджет клетки.

Контракты:
  (contract writer ...)      — генератор патча
  (contract critic ...)      — критик-скептик
  (contract reviewer ...)    — рецензент
  (contract editor ...)      — редактор
  (contract proofreader ...) — корректор
  (contract consistency ...) — двухслойная приёмка
  (contract reverify ...)    — повторная верификация
  (contract regression ...)  — регрессионный гейт
"""

from sexpr import (
    SExpr, format_sexpr, parse,
    make_contract, make_patch, make_change, make_message,
    has_marker, not_pred, and_pred, or_pred,
    in_scope, has_answer, verdict_is,
    sym, kw, dotted, alist, plist,
)

# ── Базовый контракт (наследуется всеми) ──

BASE_CONTRACT = parse("""
(contract base
  (lifecycle (created) (active) (completed) (destroyed))
  (conservation-law (sum-budgets <= cell-budget))
  (on-fail (retry-once) (escalate-to-human))
  (resource-budget (max-tokens 4096) (max-cost-rub 0.1)))
""")

# ── Контракт писателя-генератора ──

WRITER_CONTRACT = parse("""
(contract writer
  (input
    (pattern . "паттерн узла: роль + путь + специфика")
    (vector . "вектор линзы: physical/structural/critical/defensive/logic")
    (claims . "claims группы")
    (answers . "ответы автора на вопросы")
    (facts . "установленные факты из источников"))
  (output
    (patch-diffs . "список изменений (old . new)")
    (justification . "обоснование каждого изменения")
    (used-answers . "какие ответы автора использованы"))
  (criteria
    (hard
      (only-own-claims "править только claims своей группы")
      (numbers-from-answers "числа только из ответов автора")
      (no-content-deletion "не удалять содержательные блоки")
      (justification-required "каждый diff обязан иметь justification"))
    (soft
      (style-consistent "стиль не должен выбиваться из контекста")
      (terminology-consistent "терминология направления (линза)")))
  (on-fail
    (retry-once "одна попытка перегенерации")
    (mark-open-honest "если нет ответа — [требует данных автора]"))
  (resource-budget (max-tokens 4096) (max-cost-rub 0.15)))
""")

# ── Контракт критика-скептика ──

CRITIC_CONTRACT = parse("""
(contract critic
  (input
    (pattern . "паттерн узла")
    (vector . "вектор линзы")
    (diff . "patch_diff от генератора")
    (neighbors . "соседние блоки для кросс-проверки"))
  (output
    (attacks . "список атак: что не так")
    (verdict . "SUPPORTED | AMBIGUOUS | CONTRADICTED")
    (confidence . "0.0-1.0"))
  (criteria
    (hard
      (attacks-nonempty "хотя бы одна атака или явное 'атак нет'")
      (competence-respected "атаки в рамках компетенции"))
    (soft
      (adversarial-stance "скептик обязан атаковать, не подтверждать")))
  (on-fail
    (retry-once)
    (accept-with-warning "если атак нет — принять с пометкой"))
  (resource-budget (max-tokens 2048) (max-cost-rub 0.05)))
""")

# ── Контракт рецензента ──

REVIEWER_CONTRACT = parse("""
(contract reviewer
  (input
    (block . "переписанный блок текста")
    (criteria-list . "список критериев оценки")
    (neighbor-verdicts . "вердикты соседних блоков"))
  (output
    (review
      (verdict . "SUPPORTED | AMBIGUOUS | CONTRADICTED")
      (criteria . "оценка по каждому критерию")
      (conflicts . "конфликты с соседними блоками")))
  (criteria
    (hard
      (verdict-justified "вердикт обоснован критериями")
      (conflict-flagged "конфликты с соседями явно отмечены"))
    (soft
      (global-consistency "связность с документом в целом")))
  (on-fail
    (retry-once)
    (flag-for-human "пометить для ручной проверки"))
  (resource-budget (max-tokens 2048) (max-cost-rub 0.08)))
""")

# ── Контракт редактора ──

EDITOR_CONTRACT = parse("""
(contract editor
  (input
    (diff . "patch_diff")
    (style-rules . "правила академического стиля"))
  (output
    (suggested-text . "предложенный текст")
    (edits . "список правок"))
  (criteria
    (hard
      (meaning-preserved "смысл не изменён")
      (no-new-facts "не добавлено новых утверждений"))
    (soft
      (clarity-improved "ясность улучшена")
      (conciseness "не раздувает текст")))
  (on-fail
    (keep-original "оставить исходный текст генератора"))
  (resource-budget (max-tokens 2048) (max-cost-rub 0.05)))
""")

# ── Контракт корректора ──

PROOFREADER_CONTRACT = parse("""
(contract proofreader
  (input
    (text . "текст после редактора")
    (answers . "ответы автора для сверки чисел"))
  (output
    (corrections . "список исправлений")
    (ok . "#t если ошибок нет"))
  (criteria
    (hard
      (json-valid "структура патча валидна")
      (numbers-consistent "числа согласованы с answers")
      (units-correct "единицы измерения корректны"))
    (soft
      (typos-fixed "опечатки исправлены")))
  (on-fail
    (retry-once)
    (mark-issues "пометить проблемы, не блокировать"))
  (resource-budget (max-tokens 1024) (max-cost-rub 0.03)))
""")

# ── Контракт consistency-check ──

CONSISTENCY_CONTRACT = parse("""
(contract consistency
  (input
    (patches . "все патчи ячейки")
    (schema . "JSON-схема контракта"))
  (output
    (schema-ok . "#t/#f")
    (skeptic-ok . "#t/#f")
    (issues . "список проблем"))
  (criteria
    (hard
      (schema-valid "все патчи проходят JSON-схему")
      (justification-present "каждый патч имеет justification")
      (no-content-loss "размер патча в разумных границах"))
    (soft
      (no-new-contradictions "не порождает новых противоречий")))
  (on-fail
    (reject-patch "отклонить патч")
    (return-to-generator "вернуть на доработку"))
  (resource-budget (max-tokens 2048) (max-cost-rub 0.05)))
""")

# ── Контракт re-verify ──

REVERIFY_CONTRACT = parse("""
(contract reverify
  (input
    (slice . "срез изменённых групп")
    (original-verdicts . "вердикты до правки"))
  (output
    (status-flow . "old -> new для каждой группы")
    (new-caveats . "новые замечания")
    (regression-flag . "#t если появились новые проблемы"))
  (criteria
    (hard
      (t0-deterministic "детерминированные этапы пройдены")
      (no-new-critical "нет новых critical caveats"))
    (soft
      (verdict-improved "вердикт поднялся или остался SUPPORTED")))
  (on-fail
    (revert-patch "откатить патч")
    (flag-regression "пометить как регрессию"))
  (resource-budget (max-tokens 4096) (max-cost-rub 0.10)))
""")

# ── Контракт regression gateway ──

REGRESSION_CONTRACT = parse("""
(contract regression
  (input
    (slice . "срез изменённых групп")
    (golden . "эталонные вердикты"))
  (output
    (ks-p-value . "p-value KS-теста стабильности")
    (semantic-agreement . "0.0-1.0 согласие свиты")
    (conformal-set . "(accept) | (accept reject) | (defer)"))
  (criteria
    (hard
      (ks-stable "распределение вердиктов стабильно")
      (conformal-gate "conformal-набор определяет судьбу"))
    (soft
      (no-regressions "0 новых регрессий")))
  (on-fail
    (revert "откат при {accept reject}")
    (open-honest "честная абстенция при {defer}"))
  (resource-budget (max-tokens 2048) (max-cost-rub 0.05)))
""")

# ── Реестр контрактов ──

CONTRACTS = {
    "base": BASE_CONTRACT,
    "writer": WRITER_CONTRACT,
    "critic": CRITIC_CONTRACT,
    "reviewer": REVIEWER_CONTRACT,
    "editor": EDITOR_CONTRACT,
    "proofreader": PROOFREADER_CONTRACT,
    "consistency": CONSISTENCY_CONTRACT,
    "reverify": REVERIFY_CONTRACT,
    "regression": REGRESSION_CONTRACT,
}


def get_contract(name: str) -> SExpr:
    if name not in CONTRACTS:
        raise KeyError(f"unknown contract: {name}")
    return CONTRACTS[name]


def validate_against_contract(data: SExpr, contract_name: str) -> tuple[bool, list[str]]:
    contract = get_contract(contract_name)
    issues = []

    criteria = contract.get("criteria")
    if criteria:
        hard = criteria.get("hard")
        if hard:
            for criterion in hard.args:
                if isinstance(criterion, SExpr):
                    issues.append(f"hard criterion not checked: {criterion.head}")

    return len(issues) == 0, issues


def check_acceptance_criteria(result: SExpr, contract_name: str) -> tuple[bool, list[str]]:
    contract = get_contract(contract_name)
    criteria = contract.get("criteria")
    if not criteria:
        return True, []

    hard = criteria.get("hard")
    soft = criteria.get("soft")
    issues = []

    if hard:
        for criterion in hard.args:
            if isinstance(criterion, SExpr):
                cname = criterion.head
                if cname not in result:
                    issues.append(f"MISSING: {cname}")

    warn_count = 0
    if soft:
        for criterion in soft.args:
            if isinstance(criterion, SExpr):
                cname = criterion.head
                if cname not in result:
                    warn_count += 1

    if warn_count >= 2:
        issues.append(f"2+ soft criteria missing ({warn_count})")

    return len(issues) == 0, issues


def contract_to_prompt(contract_name: str) -> str:
    contract = get_contract(contract_name)
    output_schema = contract.get("output")
    criteria = contract.get("criteria")
    hard = criteria.get("hard") if criteria else None

    schema_str = format_sexpr(output_schema) if output_schema else "(any)"
    hard_str = " ".join(
        a.head if isinstance(a, SExpr) else str(a)
        for a in (hard.args if hard else [])
    )

    return f"""(do
 (role {contract_name})
 (output-format {schema_str})
 (hard-criteria {hard_str})
 (no-reasoning #t)
 (no-markdown #t)
 (language s-expression))"""


if __name__ == "__main__":
    for name, contract in CONTRACTS.items():
        ok, issues = validate_against_contract(contract, name)
        status = "OK" if ok else f"ISSUES: {issues}"
        print(f"  {name:15s} {status}")

    prompt = contract_to_prompt("writer")
    assert "HARD-критерии" in prompt
    assert "S-expression" in prompt
    print("\n  contract_to_prompt: OK")
    print(f"\n  {len(CONTRACTS)} contracts total")
