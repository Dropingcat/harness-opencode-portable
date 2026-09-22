#!/usr/bin/env python3
"""Живой тест блока «Писатель» на маленьком тексте через AITunnel API.

Прогоняет полный цикл: patch_planner → writer (LLM) → critic (LLM) → 
reviewer (LLM) → editor (LLM) → proofreader (LLM) → consistency → regression.

Использует AITunnel deepseek-v4-flash для всех LLM-вызовов.
"""

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from state_machine import create_state, save_state, add_question, record_answer, add_patch, update_patch_status
from patch_planner import plan_patches, plan_to_sexpr
from meta_select import select_writer, competence_boundaries, load_registry
from contracts import get_contract, contract_to_prompt
from consistency_check import consistency_check
from reverify import compare_verdicts
from regression_suite import regression_gateway
from sexpr import SExpr, format_sexpr, parse

# ── Конфигурация ──

from config_loader import get, load_config
from llm_client import llm_call, call_parallel

MODEL = get("llm.default_model", "deepseek-v4-flash")
cfg = load_config()
COST_INPUT = 19 / 1_000_000
COST_OUTPUT = 38 / 1_000_000
_tokens_spent = {"input": 0, "output": 0}

def _track_tokens(system: str, user: str, out: str):
    _tokens_spent["input"] += (len(system) + len(user)) // 3
    _tokens_spent["output"] += len(out) // 3

def _cost():
    return _tokens_spent["input"] * COST_INPUT + _tokens_spent["output"] * COST_OUTPUT

# ── Тестовый текст ──

TEST_ABSTRACT = """Азотирование стали 38Х2МЮА проводилось при температуре 500-570°C 
в атмосфере аммиака. Твёрдость поверхности после азотирования составила HV 8240-9000.
Размер областей когерентного рассеяния определяли по формуле Шеррера: D = 1λ/(βcosθ).
Плотность дислокаций рассчитывали как ρ = 2·10¹⁶·β² см⁻².
Микродеформация решётки в азотированном слое составила 0.15%.
Глубина азотированного слоя 0.3-0.6 мм."""

TEST_CLAIMS = [
    {"claim_id": 1, "claim_text": "Азотирование 38Х2МЮА при 500-570°C в аммиаке",
     "verdict": "SUPPORTED", "confidence": 0.90, "caveats": [], "problematic": False},
    {"claim_id": 2, "claim_text": "Твёрдость HV 8240-9000",
     "verdict": "CONTRADICTED", "confidence": 0.20,
     "caveats": [{"severity": "critical", "text": "Физически невозможная твёрдость. Лахтин: 900-1000 HV"}],
     "problematic": True, "numeric_comparison": {"status": "mismatch"}},
    {"claim_id": 3, "claim_text": "Формула Шеррера D = 1λ/(βcosθ)",
     "verdict": "AMBIGUOUS", "confidence": 0.65,
     "caveats": [{"severity": "warning", "text": "K=1 вместо стандартного 0.9, не указан тип ширины"}],
     "problematic": True},
    {"claim_id": 4, "claim_text": "ρ = 2·10¹⁶·β² см⁻²",
     "verdict": "AMBIGUOUS", "confidence": 0.50,
     "caveats": [{"severity": "warning", "text": "Универсальная константа без обоснования"}],
     "problematic": True},
    {"claim_id": 5, "claim_text": "Микродеформация 0.15%",
     "verdict": "SUPPORTED", "confidence": 0.80,
     "caveats": [{"severity": "info", "text": "Не указан метод определения"}],
     "problematic": True},
    {"claim_id": 6, "claim_text": "Глубина слоя 0.3-0.6 мм",
     "verdict": "SUPPORTED", "confidence": 0.85, "caveats": [], "problematic": False},
]

AUTHOR_ANSWERS = {
    "q_2_1": "Да, опечатка. Реальная твёрдость 824-900 HV. В таблице лишний ноль.",
    "q_3_1": "Используется FWHM. K=1 — опечатка, правильно K=0.9.",
    "q_4_1": "Константа из справочника Миркина. Калибровка по ПЭМ не проводилась.",
    "q_5_1": "Метод Williamson-Hall, по 6 рефлексам.",
}

# ── LLM-клиент (через llm_client / config) ──

# ── Фазы с LLM ──

def phase_writing(patch_info: dict, claim_text: str, answer: str, issue: str) -> str:
    system = contract_to_prompt("writer")
    user = f"""Перепиши научный claim, исправив проблему.

Claim: {claim_text}
Проблема: {issue}
Ответ автора: {answer}

Вывод — S-expression (patch-diff ...) с changes и justification.
Исправляй ТОЛЬКО проблемное место, не меняй остальное."""
    out = llm_call(system, user, role="writer")
    _track_tokens(system, user, out)
    return out


def phase_critic(patch_text: str, claim_text: str) -> str:
    system = contract_to_prompt("critic")
    user = f"""Атакуй этот патч как скептик. Найди ошибки, противоречия, выход за границы.

Исходный claim: {claim_text}
Патч: {patch_text}

Вывод — S-expression (critic-result ...) с attacks, verdict, confidence."""
    out = llm_call(system, user, role="critic")
    _track_tokens(system, user, out)
    return out


def phase_reviewer(patched_text: str, original: str) -> str:
    system = contract_to_prompt("reviewer")
    user = f"""Оцени переписанный текст по критериям научной строгости.

Оригинал: {original}
Переписанный: {patched_text}

Вывод — S-expression (reviewer-result ...) с verdict, criteria, conflicts."""
    out = llm_call(system, user, role="reviewer")
    _track_tokens(system, user, out)
    return out


def phase_editor(patched_text: str) -> str:
    system = contract_to_prompt("editor")
    # Извлекаем suggested-text из патча, если это S-expression
    try:
        parsed = parse(patched_text)
        new_text = parsed.get("new") or parsed.get("suggested-text")
        if new_text:
            patched_text = str(new_text) if not isinstance(new_text, str) else new_text
    except Exception:
        pass
    user = f"""(edit-text "{patched_text}")"""
    out = llm_call(system, user, role="editor")
    _track_tokens(system, user, out)
    return out


def phase_proofreader(patched_text: str, answer: str) -> str:
    system = contract_to_prompt("proofreader")
    user = f"""Проверь текст: числа, единицы, опечатки. Сверь числа с ответом автора.

Текст: {patched_text}
Ответ автора (числа оттуда): {answer}

Вывод — S-expression (proofreader-result ...) с corrections, ok."""
    out = llm_call(system, user, role="proofreader")
    _track_tokens(system, user, out)
    return out


# ── Главный тест ──

def main():
    print("=" * 70)
    print("ЖИВОЙ ТЕСТ БЛОКА «ПИСАТЕЛЬ» через AITunnel")
    print(f"Модель: {MODEL}")
    print("=" * 70)

    # 1. Patch-planner
    print("\n── Фаза PLANNING ──")
    plan = plan_patches(TEST_CLAIMS)
    print(f"  Групп: {plan['total_groups']}, проблемных: {plan['problematic_groups']}")
    print(f"  Патчей: {plan['patch_count']}")

    for patch in plan["patches"]:
        gi = patch["group"].args[0]
        issues = [a for a in patch.args if isinstance(a, SExpr) and a.head == "issues"]
        issue_list = issues[0].args if issues else ["method_gap"]
        print(f"  p_{gi}: {issue_list}")

    # 2. Writer (LLM) — для каждого проблемного claim
    print("\n── Фаза WRITING (LLM) ──")
    patches_output = {}

    problem_claims = {
        2: ("Твёрдость HV 8240-9000", "CONTRADICTED: числовой mismatch", AUTHOR_ANSWERS["q_2_1"]),
        3: ("Формула Шеррера D = 1λ/(βcosθ)", "AMBIGUOUS: K=1 вместо 0.9, не указан тип ширины", AUTHOR_ANSWERS["q_3_1"]),
        4: ("ρ = 2·10¹⁶·β² см⁻²", "AMBIGUOUS: универсальная константа без обоснования", AUTHOR_ANSWERS["q_4_1"]),
        5: ("Микродеформация 0.15%", "SUPPORTED но не указан метод определения", AUTHOR_ANSWERS["q_5_1"]),
    }

    for gi, (claim, issue, answer) in problem_claims.items():
        print(f"\n  Патч p_{gi}: {claim[:60]}...")
        result = phase_writing({"group_index": gi}, claim, answer, issue)
        patches_output[gi] = result
        print(f"    Ответ: {result[:200]}...")

    # 3. Critic (LLM)
    print("\n── Фаза WAVE_A: CRITIC (LLM) ──")
    critic_results = {}
    for gi, patch_text in patches_output.items():
        claim = problem_claims[gi][0]
        print(f"\n  Критика p_{gi}...")
        result = phase_critic(patch_text, claim)
        critic_results[gi] = result
        print(f"    {result[:200]}...")

    # 4. Reviewer (LLM)
    print("\n── Фаза WAVE_B: REVIEWER (LLM) ──")
    for gi, patch_text in patches_output.items():
        claim = problem_claims[gi][0]
        print(f"\n  Рецензия p_{gi}...")
        result = phase_reviewer(patch_text, claim)
        print(f"    {result[:200]}...")

    # 5. Editor (LLM)
    print("\n── Фаза WAVE_B: EDITOR (LLM) ──")
    for gi, patch_text in patches_output.items():
        print(f"\n  Редактура p_{gi}...")
        result = phase_editor(patch_text)
        print(f"    {result[:200]}...")

    # 6. Proofreader (LLM)
    print("\n── Фаза WAVE_B: PROOFREADER (LLM) ──")
    for gi, patch_text in patches_output.items():
        answer = problem_claims[gi][2]
        print(f"\n  Корректура p_{gi}...")
        result = phase_proofreader(patch_text, answer)
        print(f"    {result[:200]}...")

    # 7. Consistency check (детерм.)
    print("\n── Фаза CONSISTENCY (детерм.) ──")
    for gi, patch_text in patches_output.items():
        try:
            parsed = parse(patch_text) if isinstance(patch_text, str) else patch_text
            result = consistency_check(parsed, answers={f"q_{gi}_1": problem_claims[gi][2]})
            print(f"  p_{gi}: ok={result['ok']}, hard={result['hard_pass']}, action={result['action']}")
        except Exception as e:
            print(f"  p_{gi}: parse error: {e}")

    # 8. Regression gateway
    print("\n── Фаза REGRESSION ──")
    before = {2: "CONTRADICTED", 3: "AMBIGUOUS", 4: "AMBIGUOUS", 5: "SUPPORTED"}
    after = {2: "SUPPORTED", 3: "SUPPORTED", 4: "SUPPORTED", 5: "SUPPORTED"}
    suite = [
        {"verdict": "SUPPORTED", "confidence": 0.85},
        {"verdict": "SUPPORTED", "confidence": 0.80},
        {"verdict": "SUPPORTED", "confidence": 0.90},
    ]
    result = regression_gateway(before, after, suite)
    print(f"  Гейт: {result['gate']}")
    print(f"  KS: stable={result['ks_stable']}, d={result['ks_d_statistic']}")
    print(f"  Semantic agreement: {result['semantic_agreement']}")
    print(f"  Conformal: {result['conformal_set']}")
    print(f"  Регрессий: {result['regress_count']}, улучшений: {result['improve_count']}")

    # 9. Итоги
    print("\n" + "=" * 70)
    print("ИТОГИ ТЕСТА")
    print("=" * 70)
    print(f"  Патчей сгенерировано: {len(patches_output)}")
    print(f"  Regression gate: {result['gate']}")
    print(f"  KS-стабильность: {'✓' if result['ks_stable'] else '✗'}")
    print(f"  Conformal: {result['conformal_set']}")
    print(f"  Регрессий: {result['regress_count']}")

    # Показываем лучший патч
    print("\n── ЛУЧШИЙ ПАТЧ (p_2, твёрдость) ──")
    print(patches_output.get(2, "нет")[:500])

    print("\n── ЛУЧШИЙ ПАТЧ (p_3, Шеррер) ──")
    print(patches_output.get(3, "нет")[:500])

    print(f"\n── СТОИМОСТЬ ──")
    print(f"  Input:  {_tokens_spent['input']:5d} tok ~ {_tokens_spent['input'] * COST_INPUT:.4f} ₽")
    print(f"  Output: {_tokens_spent['output']:5d} tok ~ {_tokens_spent['output'] * COST_OUTPUT:.4f} ₽")
    print(f"  Всего:  ~{_cost():.2f} ₽")

    print("\n✓ Тест завершён")


if __name__ == "__main__":
    main()
