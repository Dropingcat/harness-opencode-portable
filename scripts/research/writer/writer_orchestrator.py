#!/usr/bin/env python3
"""Оркестратор блока «Писатель» (N9-N12.5).

Сквозной интеграционный скрипт: загружает writer_state.json, прогоняет полный цикл
писателя (patch_planner → writer cells → suite waves → consistency → reverify → regression),
пишет чекпоинты после каждой фазы.

LLM-вызовы — через llm_client (llm_call / call_parallel), параметры — из
writer_config.yaml (config_loader.get / llm_params).

Запуск:
  python writer_orchestrator.py <discussion_id> [--iteration N] [--dry-run]
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from state_machine import (
    load_state, save_state, advance_phase, start_new_iteration, finalize,
    add_question, record_answer, pending_questions, answered_questions,
    add_patch, update_patch_status, record_verdict_flow, record_regression,
    add_budget, budget_exceeded, iterations_exhausted, add_text_version,
    resume, validate, recover, create_state,
)
from patch_planner import plan_patches, plan_to_sexpr, plan_to_json
from meta_select import select_writer, competence_boundaries, check_competence, load_registry
from contracts import get_contract, contract_to_prompt, check_acceptance_criteria
from consistency_check import consistency_check, consistency_to_sexpr
from reverify import compare_verdicts, reverify_to_sexpr
from regression_suite import regression_gateway, regression_to_sexpr
from sexpr import SExpr, format_sexpr, parse, make_patch, make_change, make_message
from config_loader import get, llm_params
from llm_client import llm_call, call_parallel

WORKSPACE = Path("/media/orangepi/1234-5678/AnalisysDataSet/workspace_pipeline")
DISCUSSIONS = WORKSPACE / "discussions"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _sexpr_to_text(sexpr) -> str:
    if isinstance(sexpr, SExpr):
        return format_sexpr(sexpr)
    return str(sexpr)


# ── Доменные keywords для выбора писателя (R3) ──

_STOPWORDS = {
    "при", "для", "после", "этот", "эта", "это", "что", "как", "так", "все",
    "также", "его", "ее", "её", "них", "приведен", "использова", "данные",
    "данный", "изучен", "проведен", "показан", "составлен", "the", "of",
    "and", "with", "from", "that", "this", "was", "were", "are", "were",
}

_WORD_RE = re.compile(r"[а-яёa-z]{4,}")


def _extract_keywords(texts: list[str]) -> list[str]:
    """Контентные keywords из claim-текстов (латинские/кириллические слова)."""
    out = []
    for text in texts:
        for w in _WORD_RE.findall(str(text).lower()):
            if w in _STOPWORDS:
                continue
            if w not in out:
                out.append(w)
    return out


def _find_node_with_claim(root: dict, gi) -> Optional[dict]:
    if str(gi) in [str(x) for x in root.get("claims", [])]:
        return root
    for child in root.get("children", []):
        found = _find_node_with_claim(child, gi)
        if found is not None:
            return found
    return None


def _build_node_index(root: dict) -> dict[str, dict]:
    index = {}

    def walk(node):
        index[str(node.get("id"))] = node
        for child in node.get("children", []):
            walk(child)

    walk(root)
    return index


def _collect_node_keywords(node: Optional[dict], index: dict) -> list[str]:
    """Keywords узла + предков (наследование ветки, как в pattern_generator)."""
    out = []
    seen = set()
    cur = node
    while cur is not None:
        for k in cur.get("keywords", []):
            if k not in seen:
                seen.add(k)
                out.append(k)
        parent_id = cur.get("parent")
        cur = index.get(str(parent_id)) if parent_id else None
    return out


def _domain_keywords(group_index, claim_texts: list[str],
                     topics_tree: dict = None) -> list[str]:
    """Доменные keywords для селектора писателя: из claim-текстов и узла дерева.

    Порядок: content-слова claim → keywords узла/предков (topics_tree, если дан).
    """
    kws = _extract_keywords(claim_texts)
    root = topics_tree.get("topics_tree", topics_tree) if topics_tree else None
    if root:
        index = _build_node_index(root)
        node = _find_node_with_claim(root, group_index)
        if node is not None:
            for k in _collect_node_keywords(node, index):
                if k not in kws:
                    kws.append(k)
    return kws


# ── Разбор LLM-ответов ──

def _parse_sexpr(text: str) -> Optional[SExpr]:
    try:
        res = parse(text)
        return res if isinstance(res, SExpr) else None
    except Exception:
        return None


def _walk(root):
    if root is None:
        return
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, SExpr):
            yield node
            stack.extend(node.args)


def _node_value(node, default=None):
    if isinstance(node, SExpr) and len(node.args) >= 2 and node.args[0] == ".":
        return node.args[1]
    return default


def _leaf_string(node) -> str:
    v = _node_value(node)
    if v is not None:
        return str(v) if not isinstance(v, SExpr) else format_sexpr(v)
    if isinstance(node, SExpr):
        return format_sexpr(node)
    return str(node)


def _normalize_verdict(v) -> str:
    if not v:
        return "SUPPORTED"
    up = str(v).upper()
    for tok in ("SUPPORTED", "AMBIGUOUS", "CONTRADICTED"):
        if tok in up:
            return tok
    if any(t in up for t in ("ACCEPT", "OK", "PASS", "TRUE", "ВЕРНО")):
        return "SUPPORTED"
    return "AMBIGUOUS"


def _extract_writer_output(text: str) -> tuple[list, str]:
    """Распарсить ответ writer'а: диффы (patch-diffs/patch-diff) + justification."""
    sexpr = _parse_sexpr(text)
    if sexpr is None:
        return [], text.strip()
    diffs = []
    justification = None
    for node in _walk(sexpr):
        if node.head == "patch-diffs":
            for a in node.args:
                if isinstance(a, SExpr) and a.head in ("patch-diff", "patch"):
                    diffs.append(format_sexpr(a))
        elif node.head in ("patch-diff", "patch"):
            diffs.append(format_sexpr(node))
        elif node.head == "justification" and justification is None:
            j = _node_value(node)
            if j is not None:
                justification = str(j)
    return diffs, (justification or text.strip())


def _extract_critic_output(text: str) -> tuple:
    sexpr = _parse_sexpr(text)
    verdict = None
    confidence = None
    attacks = []
    if sexpr is not None:
        for node in _walk(sexpr):
            if node.head == "verdict" and verdict is None:
                verdict = _leaf_string(node)
            elif node.head == "confidence" and confidence is None:
                confidence = _node_value(node)
            elif node.head in ("attack", "attacks"):
                nodes = node.args if node.head == "attacks" else [node]
                for a in nodes:
                    if isinstance(a, SExpr):
                        t = _leaf_string(a)
                        if t and t not in ("attack", "attacks", "атак нет"):
                            attacks.append(t)
    if verdict is None:
        up = text.upper()
        for v in ("SUPPORTED", "AMBIGUOUS", "CONTRADICTED"):
            if v in up:
                verdict = v
                break
    attacks = list(dict.fromkeys(attacks))
    return verdict or "SUPPORTED", attacks, confidence


def _extract_proofreader(text: str) -> tuple:
    sexpr = _parse_sexpr(text)
    ok = True
    corrections = []
    if sexpr is not None:
        for node in _walk(sexpr):
            if node.head == "ok":
                v = None
                if len(node.args) >= 2 and node.args[0] == ".":
                    v = node.args[1]
                elif node.args:
                    v = node.args[0]
                ok = v not in (False, "false", "False", "#f", "no", 0)
            elif node.head == "corrections":
                for a in node.args:
                    if isinstance(a, SExpr):
                        t = _leaf_string(a)
                        if t and t != "corrections":
                            corrections.append(t)
    return ok, corrections


def _extract_editor(text: str) -> tuple:
    sexpr = _parse_sexpr(text)
    suggested = None
    suggestions = []
    if sexpr is not None:
        for node in _walk(sexpr):
            if node.head == "suggested-text" and suggested is None:
                suggested = _node_value(node)
            elif node.head == "suggestions":
                for a in node.args:
                    if isinstance(a, SExpr):
                        t = _leaf_string(a)
                        if t and t != "suggestions":
                            suggestions.append(t)
    return suggested, suggestions


def _extract_reviewer(text: str) -> tuple:
    sexpr = _parse_sexpr(text)
    verdict = None
    confidence = None
    conflicts = []
    if sexpr is not None:
        for node in _walk(sexpr):
            if node.head == "verdict" and verdict is None:
                verdict = _leaf_string(node)
            elif node.head == "confidence" and confidence is None:
                confidence = _node_value(node)
            elif node.head == "conflicts":
                for a in node.args:
                    if isinstance(a, SExpr):
                        t = _leaf_string(a)
                        if t and t != "conflicts":
                            conflicts.append(t)
    return verdict or "SUPPORTED", confidence, conflicts


# ── Промпты фаз ──

def _writer_system() -> str:
    return contract_to_prompt("writer")


def _writer_user(claim_text: str, issue: str, answer: str, gi=None) -> str:
    gi_line = f"Группа: {gi}" if gi is not None else ""
    return f"""Перепиши научный claim, исправив проблему.

{gi_line}
Claim: {claim_text}
Проблема: {issue}
Ответ автора: {answer}

Вывод — S-expression (patch-diff ...) или (patch-diffs (patch-diff ...) ...).
changes: (change (old . "старый текст") (new . "новый текст")).
В конце — (justification . "что исправлено и почему").
Исправляй ТОЛЬКО проблемное место, не меняй остальное."""


def _critic_task(claim_text: str, patch_text: str) -> dict:
    system = contract_to_prompt("critic")
    user = f"""Атакуй этот патч как скептик. Найди ошибки, противоречия, выход за границы.

Исходный claim: {claim_text}
Патч:
{patch_text[:2000]}

Вывод — S-expression (critic-result (verdict . "SUPPORTED|AMBIGUOUS|CONTRADICTED") (confidence . 0.0-1.0) (attacks (attack . "текст") ...)).
Если атак нет — (attacks (attack . "атак нет"))."""
    return {"system": system, "user": user, "role": "critic"}


def _proofreader_task(patch_text: str, answer: str) -> dict:
    system = contract_to_prompt("proofreader")
    user = f"""Проверь текст: числа, единицы, опечатки. Сверь числа с ответом автора.

Текст:
{patch_text[:2000]}
Ответ автора: {answer}

Вывод — S-expression (proofreader-result (ok . #t|#f) (corrections (correction . "текст") ...))."""
    return {"system": system, "user": user, "role": "proofreader"}


def _editor_task(patch_text: str) -> dict:
    system = contract_to_prompt("editor")
    user = f"""Отредактируй текст: улучши стиль, связность, лаконичность. НЕ меняй смысл.

Текст:
{patch_text[:2000]}

Вывод — S-expression (editor-result (suggested-text . "...") (suggestions (suggestion . "текст") ...)).
Если правок нет — (suggestions (suggestion . "правок нет"))."""
    return {"system": system, "user": user, "role": "editor"}


def _reviewer_task(patch_text: str, original: str) -> dict:
    system = contract_to_prompt("reviewer")
    user = f"""Оцени переписанный текст по критериям научной строгости.

Оригинал: {original}
Переписанный:
{patch_text[:2000]}

Вывод — S-expression (reviewer-result (verdict . "SUPPORTED|AMBIGUOUS|CONTRADICTED") (confidence . 0.0-1.0) (criteria (item . "...")) (conflicts (conflict . "..."))).
Если конфликтов нет — (conflicts (conflict . "конфликтов нет"))."""
    return {"system": system, "user": user, "role": "reviewer"}


class WriterOrchestrator:
    def __init__(self, discussion_id: str, dry_run: bool = False):
        self.discussion_id = discussion_id
        self.disc_dir = DISCUSSIONS / discussion_id
        self.state_path = self.disc_dir / "writer_state.json"
        self.dry_run = dry_run
        self.state = None
        self.registry = load_registry()

    def load_or_create(self) -> dict:
        if self.state_path.exists():
            self.state = load_state(str(self.state_path))
            info = resume(self.state)
            print(f"Загружено обсуждение: {info['discussion_id']}")
            print(f"  Фаза: {info['phase']}, итерация: {info['iteration']}")
            print(f"  Вопросов без ответа: {len(info['pending_questions'])}")
            print(f"  Патчей: {info['patches_count']} ({info['patches_by_status']})")
            print(f"  Бюджет: {info['budget_spent_rub']}₽ / {info['budget_max_rub']}₽")
        else:
            print(f"Новое обсуждение: {self.discussion_id}")
            self.state = create_state(
                self.discussion_id, "", "",
                max_iterations=get("state.max_iterations", 3),
                max_cost_rub=get("budget.max_cost_rub", 20.0),
            )
            self._save()
        return self.state

    def _save(self):
        if not self.dry_run:
            save_state(self.state, str(self.state_path))

    def _advance(self):
        if self.dry_run:
            current = self.state["cycle"]["phase"]
            if current in ("DONE", "FINAL"):
                return
            from state_machine import TRANSITIONS
            next_phase = TRANSITIONS.get(current)
            if next_phase:
                self.state["cycle"]["phase"] = next_phase
                self.state["checkpoints"].append({"phase": next_phase, "at": _now()})
        else:
            advance_phase(self.state, str(self.state_path))

    def run_cycle(self, verdicts_path: str = None, answers: dict = None) -> dict:
        phase = self.state["cycle"]["phase"]
        iteration = self.state["cycle"]["iteration"]

        print("\n" + "=" * 60)
        print(f"Цикл писателя: итерация {iteration}, фаза {phase}")
        print(f"{'='*60}")

        if phase == "AWAITING_ANSWERS":
            return self._phase_awaiting_answers(answers)

        if phase == "PLANNING":
            return self._phase_planning(verdicts_path)

        if phase == "WRITING":
            return self._phase_writing()

        if phase == "WAVE_A":
            return self._phase_wave_a()

        if phase == "REVISING":
            return self._phase_revising()

        if phase == "WAVE_B":
            return self._phase_wave_b()

        if phase == "CONSISTENCY":
            return self._phase_consistency()

        if phase == "REVERIFY":
            return self._phase_reverify()

        if phase == "REGRESSION":
            return self._phase_regression()

        if phase == "DONE":
            return self._phase_done()

        return {"status": "unknown_phase", "phase": phase}

    def _phase_awaiting_answers(self, answers: dict = None) -> dict:
        print("Фаза AWAITING_ANSWERS: проверка вопросов...")
        pending = pending_questions(self.state)

        if answers:
            for qid, answer in answers.items():
                if record_answer(self.state, qid, answer):
                    print(f"  Ответ на {qid}: {answer[:80]}...")
            self._save()

        pending = pending_questions(self.state)
        if pending:
            print(f"  Ожидание ответов на {len(pending)} вопросов:")
            for q in pending:
                print(f"    {q['id']}: [{q['role']}] {q['text'][:100]}")
            return {"status": "awaiting_answers", "pending": len(pending)}

        print("  Все вопросы отвечены → PLANNING")
        self._advance()
        return {"status": "advanced", "next": "PLANNING"}

    def _phase_planning(self, verdicts_path: str = None) -> dict:
        print("Фаза PLANNING: построение плана патчей...")

        if not verdicts_path:
            verdicts_path = str(WORKSPACE / "verdicts_processed.json")

        vp = Path(verdicts_path)
        if not vp.exists():
            print(f"  verdicts_processed.json не найден: {verdicts_path}")
            return {"status": "error", "reason": "no verdicts"}

        with open(vp) as f:
            verdicts = json.load(f)

        tribunal = _load_json(WORKSPACE / "tribunal.json")
        answers = {qid: q["answer"] for qid, q in self.state.get("questions", {}).items() if q.get("answer")}

        plan = plan_patches(verdicts, tribunal, answers)
        print(f"  Групп: {plan['total_groups']}, проблемных: {plan['problematic_groups']}")
        print(f"  Патчей: {plan['patch_count']}, ячеек: {plan['cell_count']}")
        print(f"  Вопросов без ответа: {plan['unanswered_questions']}")

        plan_sexpr = plan_to_sexpr(plan)
        plan_path = self.disc_dir / "patch_plan.sexpr"
        if not self.dry_run:
            plan_path.write_text(plan_sexpr, encoding="utf-8")
            _save_json(self.disc_dir / "patch_plan.json", plan_to_json(plan))

        for patch in plan["patches"]:
            gi = patch["group"].args[0]
            issues = [a for a in patch.args if isinstance(a, SExpr) and a.head == "issues"]
            issue_list = issues[0].args if issues else ["method_gap"]

            claim_texts = []
            claims_sexpr = patch.get("claims")
            if isinstance(claims_sexpr, SExpr):
                for a in claims_sexpr.args:
                    if isinstance(a, SExpr) and a.head == "claim" and a.args:
                        claim_texts.append(_sexpr_to_text(a.args[-1]))

            answers_map = {}
            answers_sexpr = patch.get("answers")
            if isinstance(answers_sexpr, SExpr):
                for a in answers_sexpr.args:
                    if isinstance(a, SExpr) and len(a.args) >= 2 and a.args[0] == ".":
                        answers_map[str(a.head)] = a.args[1]

            add_patch(self.state, f"p_{gi}", gi, issue_list)
            update_patch_status(self.state, f"p_{gi}", "created",
                claim_texts=claim_texts, answers=answers_map)

        self._save()
        self._advance()
        return {"status": "advanced", "next": "WRITING", "patches": plan["patch_count"]}

    def _phase_writing(self) -> dict:
        print("Фаза WRITING: генерация патчей (LLM)...")
        patches = self.state.get("patches", {})

        topics_tree = _load_json(WORKSPACE / "topics_tree.json")
        if not isinstance(topics_tree, dict) or "topics_tree" not in topics_tree:
            topics_tree = {}

        written = 0
        for pid, pinfo in patches.items():
            if pinfo.get("status") != "created":
                continue
            gi = pinfo["group_index"]
            print(f"  Патч {pid} (группа {gi}): выбор писателя...")

            issues = pinfo.get("issue_types", ["method_gap"])
            claim_texts = pinfo.get("claim_texts", [])
            keywords = _domain_keywords(gi, claim_texts, topics_tree)
            if not keywords:
                keywords = issues
            print(f"    Доменные keywords: {keywords[:10]}{'...' if len(keywords) > 10 else ''}")

            selection = select_writer(keywords, self.registry)
            writer_id = selection["writer"]["id"]
            print(f"    Выбран: {writer_id} (метод: {selection['method']})")

            boundaries = competence_boundaries(writer_id, self.registry)
            in_comp = check_competence(keywords, boundaries)

            claim_text = " ".join(pinfo.get("claim_texts", [])) or f"группа {gi}"
            answer = "; ".join(f"{k}={v}" for k, v in pinfo.get("answers", {}).items()) or "нет ответов автора"
            issue = issues[0] if issues else "method_gap"

            out = llm_call(_writer_system(), _writer_user(claim_text, issue, answer, gi), role="writer")
            print(f"    LLM: {out[:120]}...")

            patch_diffs, justification = _extract_writer_output(out)
            patch_sexpr = None
            if patch_diffs:
                parsed = _parse_sexpr(patch_diffs[0])
                patch_sexpr = format_sexpr(parsed) if parsed else None

            update_patch_status(self.state, pid, "written",
                writer=writer_id,
                in_competence=in_comp,
                written_at=_now(),
                patch_text=out,
                patch_diffs=patch_diffs,
                patch_sexpr=patch_sexpr,
                justification=justification,
            )
            written += 1

        self._save()
        self._advance()
        return {"status": "advanced", "next": "WAVE_A", "patches_written": written}

    def _phase_wave_a(self) -> dict:
        print("Фаза WAVE_A: критик + корректор (LLM, параллельно)...")
        patches = self.state.get("patches", {})

        done = 0
        for pid, pinfo in patches.items():
            if pinfo.get("status") != "written":
                continue
            gi = pinfo["group_index"]
            claim_text = " ".join(pinfo.get("claim_texts", [])) or f"группа {gi}"
            patch_text = pinfo.get("patch_text", "")
            answer = "; ".join(f"{k}={v}" for k, v in pinfo.get("answers", {}).items()) or "нет ответов автора"
            print(f"  Патч {pid}: критика + корректура...")

            tasks = [
                _critic_task(claim_text, patch_text),
                _proofreader_task(patch_text, answer),
            ]
            results = call_parallel(tasks)
            critic_text, proof_text = results

            verdict, attacks, conf = _extract_critic_output(critic_text)
            proof_ok, corrections = _extract_proofreader(proof_text)
            print(f"    critic: {_normalize_verdict(verdict)} (conf={conf}), атак={len(attacks)}; proof_ok={proof_ok}")

            update_patch_status(self.state, pid, "wave_a_done",
                wave_A={
                    "critic_verdict": _normalize_verdict(verdict),
                    "critic_attacks": attacks,
                    "critic_confidence": conf,
                    "proof_ok": proof_ok,
                    "proof_corrections": corrections,
                    "checked_at": _now(),
                    "raw": {"critic": critic_text[:400], "proofreader": proof_text[:400]},
                },
            )
            done += 1

        self._save()
        self._advance()
        return {"status": "advanced", "next": "REVISING", "critiqued": done}

    def _phase_revising(self) -> dict:
        print("Фаза REVISING: доработка после критики (LLM)...")
        patches = self.state.get("patches", {})

        revised = 0
        for pid, pinfo in patches.items():
            if pinfo.get("status") != "wave_a_done":
                continue
            wave_a = pinfo.get("wave_A") or {}
            attacks = wave_a.get("critic_attacks") or []
            if not attacks:
                continue
            gi = pinfo["group_index"]
            claim_text = " ".join(pinfo.get("claim_texts", [])) or f"группа {gi}"
            prev_patch = pinfo.get("patch_text", "")
            answer = "; ".join(f"{k}={v}" for k, v in pinfo.get("answers", {}).items()) or "нет ответов автора"
            issue = (pinfo.get("issue_types") or ["method_gap"])[0]
            print(f"  Патч {pid}: учёт атак критика...")

            attacks_brief = "\n".join("- " + a for a in attacks[:5])
            user = _writer_user(claim_text, issue, answer, gi)
            user = user + f"""

Замечания критика к предыдущей версии:
{attacks_brief}

Предыдущая версия:
{prev_patch[:1500]}

Исправь замечания критика. Вывод — (patch-diff ...) с changes и justification."""
            out = llm_call(_writer_system(), user, role="writer")

            patch_diffs, justification = _extract_writer_output(out)
            patch_sexpr = None
            if patch_diffs:
                parsed = _parse_sexpr(patch_diffs[0])
                patch_sexpr = format_sexpr(parsed) if parsed else None

            update_patch_status(self.state, pid, "revised",
                revised_at=_now(),
                patch_text=out,
                patch_diffs=patch_diffs,
                patch_sexpr=patch_sexpr,
                justification=justification,
                revision_fixed=len(patch_diffs) > 0,
            )
            revised += 1

        self._save()
        self._advance()
        return {"status": "advanced", "next": "WAVE_B", "revised": revised}

    def _phase_wave_b(self) -> dict:
        print("Фаза WAVE_B: редактор + рецензент (LLM, параллельно)...")
        patches = self.state.get("patches", {})

        done = 0
        for pid, pinfo in patches.items():
            if pinfo.get("status") not in ("wave_a_done", "revised"):
                continue
            gi = pinfo["group_index"]
            patch_text = pinfo.get("patch_text", "")
            original = " ".join(pinfo.get("claim_texts", [])) or f"группа {gi}"
            print(f"  Патч {pid}: редактирование + рецензия...")

            tasks = [
                _editor_task(patch_text),
                _reviewer_task(patch_text, original),
            ]
            results = call_parallel(tasks)
            editor_text, reviewer_text = results

            suggested, suggestions = _extract_editor(editor_text)
            verdict, conf, conflicts = _extract_reviewer(reviewer_text)
            print(f"    editor_suggestions={len(suggestions)}; reviewer: {_normalize_verdict(verdict)}")

            update_patch_status(self.state, pid, "wave_b_done",
                wave_B={
                    "editor_suggestions": suggestions,
                    "editor_suggested_text": suggested,
                    "reviewer_verdict": _normalize_verdict(verdict),
                    "reviewer_confidence": conf,
                    "reviewer_conflicts": conflicts,
                    "checked_at": _now(),
                    "raw": {"editor": editor_text[:400], "reviewer": reviewer_text[:400]},
                },
            )
            done += 1

        self._save()
        self._advance()
        return {"status": "advanced", "next": "CONSISTENCY", "checked": done}

    def _phase_consistency(self) -> dict:
        print("Фаза CONSISTENCY: двухслойная приёмка...")
        patches = self.state.get("patches", {})

        all_ok = True
        for pid, pinfo in patches.items():
            if pinfo.get("status") != "wave_b_done":
                continue
            print(f"  Патч {pid}: проверка...")

            answers = {
                qid: q["answer"]
                for qid, q in self.state.get("questions", {}).items()
                if q.get("answer")
            }
            answers.update(pinfo.get("answers", {}))

            patch_sexpr = None
            if isinstance(pinfo.get("patch_sexpr"), str):
                try:
                    parsed = parse(pinfo["patch_sexpr"])
                    patch_sexpr = parsed if isinstance(parsed, SExpr) else None
                except Exception:
                    patch_sexpr = None
            if not isinstance(patch_sexpr, SExpr):
                patch_sexpr = SExpr("patch", pid, SExpr("group", pinfo["group_index"]))

            result = consistency_check(patch_sexpr, answers=answers)

            update_patch_status(self.state, pid,
                "accepted" if result["ok"] else "rejected",
                consistency={
                    "schema_ok": result["hard_pass"],
                    "skeptic_ok": result["soft_pass"],
                    "issues": result["hard_issues"] + result["soft_warnings"],
                },
            )

            if not result["ok"]:
                all_ok = False
                print(f"    ПРОБЛЕМЫ: {result['hard_issues']}")

        self._save()
        self._advance()
        return {"status": "advanced", "next": "REVERIFY", "all_ok": all_ok}

    def _phase_reverify(self) -> dict:
        print("Фаза REVERIFY: повторная верификация...")
        patches = self.state.get("patches", {})

        original = {}
        new = {}
        for pid, pinfo in patches.items():
            gi = pinfo["group_index"]
            flow = self.state.get("verdicts_flow", {}).get(str(gi), [])
            if flow:
                original[gi] = flow[0]["verdict"]
                new[gi] = "SUPPORTED" if pinfo.get("status") == "accepted" else flow[-1]["verdict"]

        result = compare_verdicts(original, new)
        print(f"  Регрессий: {result['regression_count']}")
        print(f"  Улучшений: {result['improvement_count']}")
        print(f"  Без изменений: {result['unchanged_count']}")

        for gi, flow in result["status_flow"].items():
            record_verdict_flow(self.state, int(gi), flow["new"])

        self._save()
        self._advance()
        return {"status": "advanced", "next": "REGRESSION", **result}

    def _phase_regression(self) -> dict:
        print("Фаза REGRESSION: гейт сходимости...")
        patches = self.state.get("patches", {})

        before = {}
        after = {}
        for pid, pinfo in patches.items():
            gi = pinfo["group_index"]
            flow = self.state.get("verdicts_flow", {}).get(str(gi), [])
            if len(flow) >= 2:
                before[gi] = flow[0]["verdict"]
                after[gi] = flow[-1]["verdict"]

        suite_verdicts = self._build_suite_verdicts(patches)
        if not suite_verdicts:
            print("  Предупреждение: свита не дала вердиктов, fallback по статусам патчей")
            for pid, pinfo in patches.items():
                suite_verdicts.append({
                    "verdict": "SUPPORTED" if pinfo.get("status") == "accepted" else "AMBIGUOUS",
                    "confidence": 0.5,
                })

        result = regression_gateway(before, after, suite_verdicts)
        print(f"  Гейт: {result['gate']}")
        print(f"  KS-стабильность: {result['ks_stable']} (d={result['ks_d_statistic']})")
        print(f"  Semantic agreement: {result['semantic_agreement']}")
        print(f"  Conformal: {result['conformal_set']}")

        record_regression(
            self.state,
            result["ks_d_statistic"],
            result["semantic_agreement"],
            result["conformal_set"],
            result["regress_count"],
            result["improve_count"],
            result["residual_count"],
        )

        gate = result["gate"]
        if gate == "accept":
            print("  → ПРИНЯТО")
            self._advance()
            return {"status": "advanced", "next": "DONE", "gate": "accept"}
        elif gate == "revert":
            print("  → ОТКАТ")
            return {"status": "revert", "gate": "revert"}
        else:
            print("  → open_honest")
            return {"status": "open_honest", "gate": "open_honest"}

    def _build_suite_verdicts(self, patches: dict) -> list:
        """Собрать вердикты свиты для регрессионного гейта из реальных результатов."""
        suite = []
        for pid, pinfo in patches.items():
            wb = pinfo.get("wave_B") or {}
            wa = pinfo.get("wave_A") or {}
            if wb.get("reviewer_verdict"):
                try:
                    conf = float(wb.get("reviewer_confidence", 0.5) or 0.5)
                except (TypeError, ValueError):
                    conf = 0.5
                suite.append({
                    "verdict": _normalize_verdict(wb["reviewer_verdict"]),
                    "confidence": conf,
                })
            elif wa.get("critic_verdict"):
                try:
                    conf = float(wa.get("critic_confidence", 0.5) or 0.5)
                except (TypeError, ValueError):
                    conf = 0.5
                suite.append({
                    "verdict": _normalize_verdict(wa["critic_verdict"]),
                    "confidence": conf,
                })
        return suite

    def _phase_done(self) -> dict:
        print("Фаза DONE: проверка критериев остановки...")

        if iterations_exhausted(self.state):
            print("  Итерации исчерпаны → FINAL")
            finalize(self.state, str(self.state_path), "iterations_exhausted")
            return {"status": "final", "reason": "iterations_exhausted"}

        if budget_exceeded(self.state):
            print("  Бюджет исчерпан → FINAL")
            finalize(self.state, str(self.state_path), "budget_exceeded")
            return {"status": "final", "reason": "budget_exceeded"}

        patches = self.state.get("patches", {})
        accepted = sum(1 for p in patches.values() if p.get("status") == "accepted")
        total = len(patches)
        print(f"  Патчей принято: {accepted}/{total}")

        if accepted == total:
            print("  Все патчи приняты → FINAL")
            finalize(self.state, str(self.state_path), "all_accepted")
            return {"status": "final", "reason": "all_accepted"}

        print("  → Новая итерация")
        start_new_iteration(self.state, str(self.state_path))
        return {"status": "new_iteration", "iteration": self.state["cycle"]["iteration"]}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Оркестратор блока «Писатель»")
    ap.add_argument("discussion_id", help="ID обсуждения")
    ap.add_argument("--verdicts", help="Путь к verdicts_processed.json")
    ap.add_argument("--answers", help="Путь к author_answers.json")
    ap.add_argument("--iteration", type=int, default=0, help="Начать с итерации N")
    ap.add_argument("--dry-run", action="store_true", help="Без записи на диск")
    ap.add_argument("--auto", action="store_true", help="Автоматический прогон всех фаз")
    args = ap.parse_args()

    orch = WriterOrchestrator(args.discussion_id, dry_run=args.dry_run)
    state = orch.load_or_create()

    if args.iteration > 0:
        state["cycle"]["iteration"] = args.iteration

    answers = {}
    if args.answers:
        answers = _load_json(Path(args.answers))

    if args.auto:
        for _ in range(12):
            result = orch.run_cycle(args.verdicts, answers)
            print(f"  → {result.get('status')} {result.get('next', '')}")
            if result.get("status") in ("final", "awaiting_answers", "error"):
                break
    else:
        result = orch.run_cycle(args.verdicts, answers)
        print("\nРезультат: " + json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
