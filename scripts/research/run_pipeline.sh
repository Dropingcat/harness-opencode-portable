#!/bin/bash
# run_pipeline.sh — скелет оркестрации пайплайна верификации диссертации.
# Слой 3 (в): этапы = отдельные вызовы, артефакты на диске, проверка exit-кодов.
#
# Usage:
#   bash run_pipeline.sh <input.txt> [--workspace DIR] [--dry-run] [--profile resercher] [--stub-verify]
#
# Каждый этап: проверяет вход → вызывает команду → проверяет выход.
# Фатально падает, если артефакт не создан.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$SCRIPT_DIR/scripts"
PROFILE="${PROFILE:-resercher}"
HERMES=(hermes --profile "$PROFILE")
WORKSPACE=""
INPUT=""
DRY_RUN=0
RESUME=0
SCI_BOT=0
SCI_BOT_SIM=0
STUB_VERIFY=0
WRITER=0
WRITER_STATE=""
WRITER_ANSWERS=""

while [ $# -gt 0 ]; do
  case "$1" in
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --resume) RESUME=1; shift ;;
    --sci-bot) SCI_BOT=1; shift ;;
    --sci-bot-simulate) SCI_BOT_SIM=1; shift ;;
    --stub-verify) STUB_VERIFY=1; shift ;;
    --writer) WRITER=1; shift ;;
    --writer-state) WRITER_STATE="$2"; shift 2 ;;
    --writer-answers) WRITER_ANSWERS="$2"; shift 2 ;;
    --profile) PROFILE="$2"; HERMES=(hermes --profile "$PROFILE"); shift 2 ;;
    --) shift; break ;;
    -*) echo "Неизвестный флаг: $1" >&2; exit 2 ;;
    *) INPUT="$1"; shift ;;
  esac
done

if [ -z "$INPUT" ]; then
  echo "Usage: bash run_pipeline.sh <input.txt> [--workspace DIR] [--dry-run] [--stub-verify]" >&2
  exit 2
fi

if [ ! -f "$INPUT" ]; then
  echo "ERROR: входной файл не найден: $INPUT" >&2
  exit 1
fi

if [ -z "$WORKSPACE" ]; then
  WORKSPACE="${SCRIPT_DIR}/workspace/$(basename "$INPUT" .txt)-$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "$WORKSPACE"

INPUT_TXT="$WORKSPACE/input.txt"
CLAIMS_JSON="$WORKSPACE/claims.json"
CLAIM_GROUPS_JSON="$WORKSPACE/claim_groups.json"
TOPICS_JSON="$WORKSPACE/topics_tree.json"
PATTERNS_JSON="$WORKSPACE/patterns.json"
CONTEXTS_JSON="$WORKSPACE/compressed_contexts.json"
SOURCES_JSON="$WORKSPACE/sources.json"
SOURCES_SCIBOT_JSON="$WORKSPACE/sources_scibot.json"
VERDICTS_JSON="$WORKSPACE/verdicts.json"
VERDICTS_EVIDENCE="$WORKSPACE/verdicts_with_evidence.json"
NUMERIC_JSON="$WORKSPACE/numeric_result.json"
VERDICTS_WITH_NUMERIC="$WORKSPACE/verdicts_with_numeric.json"
VERDICTS_PROCESSED="$WORKSPACE/verdicts_processed.json"
JUDGE_BRIEFS_JSON="$WORKSPACE/judge_briefs.json"
ESCALATED_JSON="$WORKSPACE/escalated.json"
JUSTIFICATION_JSON="$WORKSPACE/justification_check.json"
ALARMS_JSON="$WORKSPACE/alarms.json"
TRIBUNAL_JSON="$WORKSPACE/tribunal.json"
DOMAIN_MAP_DIR="${DOMAIN_MAP_DIR:-$SCRIPT_DIR/domain_map}"
FINAL_REPORT="$WORKSPACE/final_report.md"
RULES_YAML="/home/orangepi/.hermes/profiles/$PROFILE/rules.yaml"

# ── writer paths ──────────────────────────────────────────────────────
WRITER_DIR="/home/orangepi/.hermes/profiles/$PROFILE/scripts/writer"
WRITER_DISCUSSIONS="$WORKSPACE/discussions"
WRITER_DISCUSSION_ID="$(basename "$WORKSPACE")"
WRITER_STATE_FILE="$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/writer_state.json"
WRITER_PATCH_PLAN="$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/patch_plan.sexpr"
WRITER_PATCH_DIFFS="$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/patch_diffs.json"

# ── helpers ─────────────────────────────────────────────────────────
step()  { printf '\n▶ [%s] %s\n' "$(date +%H:%M:%S)" "$1"; }
fail()  { echo "✗ FATAL: $1" >&2; echo "  workspace: $WORKSPACE" >&2; exit 1; }
ok()    { echo "✓ $1"; }

require_file() { [ -f "$1" ] || fail "нет входного артефакта: $1"; }
# run_step <desc> <out_file> <cmd...> — выполняет, проверяет выход
run_step() {
  local desc="$1" out="$2"; shift 2
  step "$desc"
  if [ "$RESUME" -eq 1 ] && [ -f "$out" ]; then
    ok "пропущен (--resume): $out уже существует"
    return 0
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] ${*}"
    return 0
  fi
  "$@"; local rc=$?
  [ $rc -ne 0 ] && fail "$desc: команда вернула $rc"
  [ -f "$out" ] || fail "$desc: не создан артефакт $out"
  ok "создан: $out"
}

# ── Этап 0: нормализация .doc → .txt ────────────────────────────────
case "$INPUT" in
  *.doc|*.docx)
    step "Этап 0: конвертация DOC → TXT (LibreOffice)"
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "  [dry-run] libreoffice --headless --convert-to txt:writer_pdf_Export --outdir $WORKSPACE $INPUT"
    else
      libreoffice --headless --convert-to txt:Text --outdir "$WORKSPACE" "$INPUT" >/dev/null 2>&1 \
        || fail "Этап 0: LibreOffice не смог конвертировать $INPUT"
      base="$(basename "$INPUT" | sed 's/\.docx\?$//i')"
      [ -f "$WORKSPACE/$base.txt" ] || fail "Этап 0: txt не создан"
      mv "$WORKSPACE/$base.txt" "$INPUT_TXT"
    fi
    ;;
  *.txt) cp "$INPUT" "$INPUT_TXT" ;;
  *)     fail "неизвестный формат входа: $INPUT (ожидал .txt/.doc/.docx)" ;;
esac
ok "вход: $INPUT_TXT"

# ── Этап 1: извлечение claims (ClaimeAI — детерминированный код) ────
if [ -f "$CLAIMS_JSON" ] && [ "$CLAIMS_JSON" -nt "$INPUT_TXT" ]; then
  step "Этап 1: извлечение claims (run_extractor.sh)"
  ok "пропущен: $CLAIMS_JSON уже создан"
else
  run_step "Этап 1: извлечение claims (run_extractor.sh)" "$CLAIMS_JSON" \
    bash "$SCRIPTS/run_extractor.sh" "$INPUT_TXT" "$CLAIMS_JSON"
fi

# ── Этап 0.5: дерево направлений (topics_tree.py, детерм.) ──────────
run_step "Этап 0.5: дерево направлений (topics_tree.py)" "$TOPICS_JSON" \
  python3 "$SCRIPTS/topics_tree.py" "$INPUT_TXT" "$CLAIM_GROUPS_JSON" "$TOPICS_JSON"

# ── Этап 0.6: паттерны и рождение судей (pattern_generator.py) ──────
run_step "Этап 0.6: паттерны и рождение судей (pattern_generator.py)" "$PATTERNS_JSON" \
  python3 "$SCRIPTS/pattern_generator.py" "$TOPICS_JSON" "$CLAIM_GROUPS_JSON" "$PATTERNS_JSON"

# ── Этап 2: динамический контекст по тезису (context-digestor) ──────
run_step "Этап 2: динамический контекст (context-digestor)" "$CONTEXTS_JSON" \
  "${HERMES[@]}" --skills context-digestor -z \
  "Собери динамический контекст по каждому claim из $INPUT_TXT.
   Claims: $CLAIMS_JSON.
   Для каждого claim собери ВСЕ релевантные фрагменты из документа и сожми их под
   ролевые вектора (physical/structural/critical/defensive/logic) согласно
   /home/orangepi/.hermes/profiles/$PROFILE/context_vectors.yaml.
   Запиши результат в $CONTEXTS_JSON (JSON: {claim_id: {vector: compressed_context}})."

# ── Этап 3: поиск источников (literature-searcher) ──────────────────
run_step "Этап 3: поиск источников (literature-searcher)" "$SOURCES_JSON" \
  "${HERMES[@]}" --skills literature-searcher -z \
  "Для каждого claim из $CLAIMS_JSON найди и провалидируй источники.
   Локальный корпус первым: /media/orangepi/1234-5678/AnalisysDataSet/.
   Используй контекст из $CONTEXTS_JSON. Запиши источники в $SOURCES_JSON (JSON)."

# ── Этап 3.5: sci-bot для групп без источников (опционально, платно) ─
if [ "$SCI_BOT" -eq 1 ] || [ "$SCI_BOT_SIM" -eq 1 ]; then
  ARGS=()
  [ "$SCI_BOT_SIM" -eq 1 ] && ARGS+=(--simulate)
  run_step "Этап 3.5: sci-bot заполнение дыры (sci_bot_integration.py)" "$SOURCES_SCIBOT_JSON" \
    python3 "$SCRIPTS/sci_bot_integration.py" "$SOURCES_JSON" "$TOPICS_JSON" "$PATTERNS_JSON" "$SOURCES_SCIBOT_JSON" "${ARGS[@]}"
else
  step "Этап 3.5: sci-bot (пропущен — нужен --sci-bot или --sci-bot-simulate)"
fi

# Актуальный sources.json для последующих этапов
if [ "$SCI_BOT" -eq 1 ] || [ "$SCI_BOT_SIM" -eq 1 ]; then
  SOURCES_JSON="$SOURCES_SCIBOT_JSON"
fi

# ── Этап 4: проверка фактов (fact-checker / stub_verifier) ──────────
if [ "$STUB_VERIFY" -eq 1 ]; then
  run_step "Этап 4: проверка фактов (stub_verifier.py, без LLM-корпуса)" "$VERDICTS_JSON" \
    python3 "$SCRIPTS/stub_verifier.py" "$CLAIMS_JSON" "$VERDICTS_JSON"
else
  # P0-фикс: retry-цикл + страховка факт-чекера. LLM иногда возвращает не-JSON;
  # guard выявляет сбой, повторяем (до N раз), при исчерпании — LLM_PARSE_FAIL
  # БЕЗ critical caveat (не валидируется как свидетельство).
  step "Этап 4: проверка фактов (fact-checker, retry×$FACTCHECK_MAX_RETRIES)"
  FACTCHECK_MAX_RETRIES="${FACTCHECK_MAX_RETRIES:-3}"
  factcheck_attempt=0
  factcheck_ok=0
  if [ "$RESUME" -eq 1 ] && [ -f "$VERDICTS_JSON" ]; then
    ok "пропущен (--resume): $VERDICTS_JSON уже существует"
    factcheck_ok=1
  elif [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] ${HERMES[*]} --skills fact-checker -z ..."
    echo "  [dry-run] (retry×$FACTCHECK_MAX_RETRIES) python3 $SCRIPTS/factcheck_guard.py $VERDICTS_JSON"
    factcheck_ok=1
  else
    while [ "$factcheck_attempt" -lt "$FACTCHECK_MAX_RETRIES" ]; do
      factcheck_attempt=$((factcheck_attempt + 1))
      echo "  → попытка $factcheck_attempt/$FACTCHECK_MAX_RETRIES"
      "${HERMES[@]}" --skills fact-checker -z \
        "Сравни каждый claim из $CLAIMS_JSON с источниками $SOURCES_JSON и контекстом
         $CONTEXTS_JSON. Сформируй preliminary verdicts с caveats[].
         Запиши в $VERDICTS_JSON (JSON)." \
        || echo "  ⚠ факт-чекер вернул ненулевой код — retry"
      if [ ! -f "$VERDICTS_JSON" ]; then
        echo "  ⚠ $VERDICTS_JSON не создан — retry"
        continue
      fi
      if python3 "$SCRIPTS/factcheck_guard.py" "$VERDICTS_JSON"; then
        factcheck_ok=1
        echo "  ✓ выдача факт-чекера валидна (попытка $factcheck_attempt)"
        break
      fi
      echo "  ⚠ выдача содержит LLM-сбой парсинга — retry"
    done
    if [ "$factcheck_ok" -ne 1 ]; then
      echo "  → retry исчерпан ($FACTCHECK_MAX_RETRIES) — помечаем LLM_PARSE_FAIL"
      python3 "$SCRIPTS/factcheck_guard.py" "$VERDICTS_JSON" --mark-parse-fail --out "$VERDICTS_JSON"
      factcheck_ok=1
    fi
  fi
  [ -f "$VERDICTS_JSON" ] || fail "Этап 4: не создан $VERDICTS_JSON"
  ok "создан: $VERDICTS_JSON"
fi

# ── Этап 4.3: Pydantic-предвалидация вердиктов (WARNING, не блокирует) ─
step "Этап 4.3: предвалидация вердиктов (verdict_schemas.py)"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] python3 $SCRIPTS/verdict_schemas.py $VERDICTS_JSON"
else
  python3 "$SCRIPTS/verdict_schemas.py" "$VERDICTS_JSON"
  ok "предвалидация выполнена (нарушения схемы — только WARNING)"
fi

# ── Этап 4.5: evidence contract (evidence_contract.py, детерм.) ─────
run_step "Этап 4.5: evidence contract (evidence_contract.py)" "$VERDICTS_EVIDENCE" \
  python3 "$SCRIPTS/evidence_contract.py" "$VERDICTS_JSON" "$RULES_YAML" "$VERDICTS_EVIDENCE"

# ── Этап 5: числовой entailment (детерминированный код) ─────────────
if [ "$RESUME" -eq 1 ] && [ -f "$NUMERIC_JSON" ]; then
  step "Этап 5: числовой entailment (numeric_comparator.py)"
  ok "пропущен (--resume): $NUMERIC_JSON уже существует"
elif [ "$DRY_RUN" -eq 1 ]; then
  step "Этап 5: числовой entailment (numeric_comparator.py)"
  echo "  [dry-run] python3 $SCRIPTS/numeric_comparator.py $VERDICTS_JSON $SOURCES_JSON $NUMERIC_JSON"
else
  step "Этап 5: числовой entailment (numeric_comparator.py)"
  python3 "$SCRIPTS/numeric_comparator.py" "$VERDICTS_JSON" "$SOURCES_JSON" "$NUMERIC_JSON" \
    || fail "Этап 5: numeric_comparator завершился с ошибкой"
  [ -f "$NUMERIC_JSON" ] || fail "Этап 5: не создан $NUMERIC_JSON"
  ok "создан: $NUMERIC_JSON"
fi

# ── Этап 5.1: слияние числовых результатов в вердикты (детерм.) ─────
run_step "Этап 5.1: слияние числовых результатов (merge_numeric.py)" "$VERDICTS_WITH_NUMERIC" \
  python3 "$SCRIPTS/merge_numeric.py" "$VERDICTS_EVIDENCE" "$NUMERIC_JSON" "$VERDICTS_WITH_NUMERIC"

# ── Этап 6: пост-обработка (детерминированный код) ─────────────────
run_step "Этап 6: пост-обработка (post_processor.py)" "$VERDICTS_PROCESSED" \
  python3 "$SCRIPTS/post_processor.py" "$VERDICTS_WITH_NUMERIC" "$RULES_YAML" "$VERDICTS_PROCESSED"

# ── Этап 5.5: резак и эскалация (escalation.py) ─────────────────────
run_step "Этап 5.5: резак и эскалация (escalation.py)" "$ESCALATED_JSON" \
  python3 "$SCRIPTS/escalation.py" "$VERDICTS_PROCESSED" "$TOPICS_JSON" "$RULES_YAML" "$ESCALATED_JSON"

# ── Этап 6.5: проверка обоснованности (justification_check.py) ──────
run_step "Этап 6.5: проверка обоснованности (justification_check.py)" "$JUSTIFICATION_JSON" \
  python3 "$SCRIPTS/justification_check.py" "$ESCALATED_JSON" "$RULES_YAML" "$JUSTIFICATION_JSON" \
    --report "$ALARMS_JSON"

# ── Этап 6.7: брифы судей (judge_brief.py, детерм.) ─────────────────
# C3: брифы строятся по ролям узла из patterns.json (expert_registry.yaml),
# а не по хардкод-списку; topics_tree.json — маппинг claim → узел.
run_step "Этап 6.7: брифы судей (judge_brief.py)" "$JUDGE_BRIEFS_JSON" \
  python3 "$SCRIPTS/judge_brief.py" "$VERDICTS_EVIDENCE" "$JUDGE_BRIEFS_JSON" \
    "$PATTERNS_JSON" "$TOPICS_JSON"

# ── Этап 7: трибунал (tribunal-judge) ───────────────────────────────
# Гарантия tribunal.json: если LLM-трибунал не дал результат — детерминированный
# fallback из judge_briefs.json (tribunal.json создаётся всегда).
if [ "$RESUME" -eq 1 ] && [ -f "$TRIBUNAL_JSON" ]; then
  step "Этап 7: трибунал (tribunal-judge)"
  ok "пропущен (--resume): $TRIBUNAL_JSON уже существует"
elif [ "$DRY_RUN" -eq 1 ]; then
  step "Этап 7: трибунал (tribunal-judge)"
  echo "  [dry-run] ${HERMES[*]} --skills tribunal-judge -z ..."
  echo "  [dry-run] (fallback) python3 - $JUDGE_BRIEFS_JSON $TRIBUNAL_JSON"
else
  step "Этап 7: трибунал (tribunal-judge)"
  "${HERMES[@]}" --skills tribunal-judge -z \
    "Проведи трибунал по claims из $JUSTIFICATION_JSON (с учётом $NUMERIC_JSON).
     Судьи выбираются по узлу направления: паттерны узлов в $PATTERNS_JSON
     (роль = focus_phrase, question, path). Для каждой группы найди её узел в
     topics_tree.json ($TOPICS_JSON) и назначь судей из паттерна узла
     (>=2 профильных + скептик + адвокат).
     Каждому судье передай паттерн узла в контексте.
     БРИФЫ СУДЕЙ (асимметрия информации): брифы в $JUDGE_BRIEFS_JSON
     ({total_claims, briefs: {claim_id: {claim_text, briefs: [{judge_id, vector,
     sources, include_verdict, context}]}}}). КАЖДОМУ судье передай ТОЛЬКО СВОЙ
     бриф (по judge_id: физик/методолог/скептик/адвокат/агрегатор) — не общий
     багаж источников. Скептик получает include_verdict=false (видит источники
     сырыми, без предвзятости), остальные — свой subset + include_verdict.
     ДИАЛЕКТИКА: каждый судья атакует чужие вердикты (other_verdicts) и
     отвечает на атаки; противоречие = аргумент-вызов (новый хоп).
     КАЛИБРОВКА: сверить вердикт с соседней веткой (neighboring_verdicts).
     КАЖДЫЙ вердикт и финальный verdict ОБЯЗАН содержать justification
     (2-4 предложения с фактами/источниками) — иначе будет OPEN.
     Для параллельных судей используй delegate_task(tasks=[...], role='leaf').
     Запиши вердикты трибунала в $TRIBUNAL_JSON (JSON).
     Формат: {groups: [{original_index, claim_id, verdict, justification,
     questions_for_author: [...]}]}."
  if [ $? -ne 0 ] || [ ! -f "$TRIBUNAL_JSON" ]; then
    echo "  → LLM-трибунал не дал $TRIBUNAL_JSON — детерминированный fallback"
    python3 - "$JUDGE_BRIEFS_JSON" "$TRIBUNAL_JSON" <<'PYEOF'
import json
import sys

briefs_path, out_path = sys.argv[1], sys.argv[2]
with open(briefs_path, "r", encoding="utf-8") as f:
    data = json.load(f)
briefs = data.get("briefs", {}) or {}
groups = []
for claim_id, brief in briefs.items():
    groups.append({
        "original_index": claim_id,
        "claim_id": claim_id,
        "claim_text": brief.get("claim_text", ""),
        "tribunal_verdict": "OPEN",
        "confidence": 0.5,
        "justification": "LLM-трибунал не выполнился — детерминированный fallback из judge_briefs.json",
        "questions_for_author": [],
    })
out = {
    "status": "deterministic_fallback",
    "note": "LLM-трибунал не дал результат; tribunal.json сгенерирован кодом из judge_briefs.json",
    "total_groups": len(groups),
    "groups": groups,
}
Path = __import__("pathlib").Path
Path(out_path).parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"✅ Детерминированный tribunal.json: {len(groups)} групп → {out_path}")
PYEOF
  fi
  [ -f "$TRIBUNAL_JSON" ] || fail "Этап 7: не создан $TRIBUNAL_JSON"
  ok "создан: $TRIBUNAL_JSON"
fi

# ── Этапы 9-12.5: блок «Писатель» (writer_orchestrator.py) ───────────
if [ "$WRITER" -eq 1 ]; then
  mkdir -p "$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID"

  # N9: patch-planner (детерм.) — строит план патчей из verdicts + tribunal
  run_step "Этап 9: планировщик патчей (patch_planner.py)" "$WRITER_PATCH_PLAN" \
    python3 "$WRITER_DIR/patch_planner.py" "$VERDICTS_PROCESSED" "$TRIBUNAL_JSON" \
    "$WRITER_PATCH_PLAN"

  # N10: writer-rewriter (LLM) — генерирует патчи через Hermes subagent
  run_step "Этап 10: генерация патчей (writer-rewriter)" "$WRITER_PATCH_DIFFS" \
    "${HERMES[@]}" --skills writer-rewriter -z \
    "Ты — писатель-генератор научного текста. Прочитай
     /home/orangepi/.hermes/profiles/$PROFILE/skills/writer-rewriter/SKILL.md и следуй ему.
     Для каждого патча из $WRITER_PATCH_PLAN сгенерируй patch_diff с justification.
     Используй verdicts из $VERDICTS_PROCESSED, вопросы автору из $TRIBUNAL_JSON,
     ответы автора из $WRITER_STATE_FILE (questions[].answer).
     Для проверки терминов используй MCP-тулз literature_search.
     Запиши результат в $WRITER_PATCH_DIFFS (JSON)."

  # N10.5: critic + proofreader (LLM, Wave A, параллельно)
  step "Этап 10.5: критика + корректура (writer-critic + writer-proofreader)"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] hermes --skills writer-critic,writer-proofreader -z ..."
  else
    "${HERMES[@]}" --skills writer-critic,writer-proofreader -z \
    "Ты выполняешь волну A свиты писателя. Прочитай оба SKILL.md:
     /home/orangepi/.hermes/profiles/$PROFILE/skills/writer-critic/SKILL.md
     /home/orangepi/.hermes/profiles/$PROFILE/skills/writer-proofreader/SKILL.md
     Для каждого патча из $WRITER_PATCH_DIFFS:
     - critic: атакуй патч, найди уязвимости (adversarial)
     - proofreader: сверь числа с ответами автора, проверь единицы
     Используй delegate_task(tasks=[{goal: critic...}, {goal: proofreader...}], role='leaf')
     для параллельного запуска. Запиши результаты в $WRITER_PATCH_DIFFS." \
    || fail "Этап 10.5: критика/корректура завершилась с ошибкой"
    ok "критика + корректура завершены"
  fi

  # N10.7: editor + reviewer (LLM, Wave B, параллельно)
  step "Этап 10.7: редактура + рецензия (writer-editor + writer-reviewer)"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] hermes --skills writer-editor,writer-reviewer -z ..."
  else
    "${HERMES[@]}" --skills writer-editor,writer-reviewer -z \
    "Ты выполняешь волну B свиты писателя. Прочитай оба SKILL.md:
     /home/orangepi/.hermes/profiles/$PROFILE/skills/writer-editor/SKILL.md
     /home/orangepi/.hermes/profiles/$PROFILE/skills/writer-reviewer/SKILL.md
     Для каждого патча из $WRITER_PATCH_DIFFS (после волны A):
     - editor: улучши стиль, связность, лаконичность (НЕ меняй смысл)
     - reviewer: оцени по критериям научной строгости, проверь связность с соседними блоками
     Используй delegate_task(tasks=[...], role='leaf') для параллельного запуска.
     Запиши результаты в $WRITER_PATCH_DIFFS." \
    || fail "Этап 10.7: редактура/рецензия завершилась с ошибкой"
    ok "редактура + рецензия завершены"
  fi

  # N11: consistency-check (детерм.) — двухслойная приёмка
  run_step "Этап 11: проверка согласованности (consistency_check.py)" \
    "$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/consistency_report.json" \
    python3 "$WRITER_DIR/consistency_check.py" "$WRITER_PATCH_DIFFS" \
    "$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/consistency_report.json"

  # N12: re-verify (детерм.) — сравнение вердиктов до/после
  run_step "Этап 12: повторная верификация (reverify.py)" \
    "$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/reverify_result.json" \
    python3 "$WRITER_DIR/reverify.py" "$VERDICTS_PROCESSED" \
    "$WRITER_PATCH_DIFFS" "$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/reverify_result.json"

  # N12.5: regression gateway (детерм.) — KS + conformal
  run_step "Этап 12.5: регрессионный гейт (regression_suite.py)" \
    "$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/regression_result.json" \
    python3 "$WRITER_DIR/regression_suite.py" \
    "$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/reverify_result.json" \
    "$WRITER_DISCUSSIONS/$WRITER_DISCUSSION_ID/regression_result.json"

  step "Блок «Писатель» завершён"
  echo "  Патчи:     $WRITER_PATCH_DIFFS"
  echo "  Состояние: $WRITER_STATE_FILE"
else
  step "Этапы 9-12.5: блок «Писатель» (пропущен — нужен --writer)"
fi

# ── Этап 8.5: многослойная карта (domain_map.py, TMS-веса) ──────────
run_step "Этап 8.5: многослойная карта (domain_map.py)" "$DOMAIN_MAP_DIR/overlay.json" \
  python3 "$SCRIPTS/domain_map.py" "$JUSTIFICATION_JSON" "$TOPICS_JSON" "$DOMAIN_MAP_DIR"

# ── Этап 8: синтез отчёта (synthesizer-agent) ───────────────────────
step "Этап 8: синтез отчёта (synthesizer-agent)"
if [ "$RESUME" -eq 1 ] && [ -s "$FINAL_REPORT" ]; then
  ok "пропущен (--resume): $FINAL_REPORT уже существует"
elif [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] ${HERMES[*]} --skills synthesizer-agent -z ..."
  echo "  [dry-run] (fallback) python3 $SCRIPTS/synthesizer.py $VERDICTS_PROCESSED $FINAL_REPORT"
else
  "${HERMES[@]}" --skills synthesizer-agent -z \
    "Собери финальный отчёт-рецензию. Входы:
     claims: $CLAIMS_JSON, контексты: $CONTEXTS_JSON,
     sources: $SOURCES_JSON, verdicts: $JUSTIFICATION_JSON,
     numeric: $NUMERIC_JSON, tribunal: $TRIBUNAL_JSON, alarms: $ALARMS_JSON,
     карта: $DOMAIN_MAP_DIR/overlay.json (веса = credibility, nogood = конфликты слоёв).
     Отчёт: сводка + детали + противоречия + ВОПРОСЫ автору + ПРОБЛЕМНЫЕ ТЕЗИСЫ
     + ОТКРЫТЫЕ ВОПРОСЫ (OPEN-вердикты и алармы из $ALARMS_JSON) + ССЫЛКА НА КАРТУ.
     Запиши в $FINAL_REPORT (Markdown)."
  if [ $? -ne 0 ] || [ ! -s "$FINAL_REPORT" ]; then
    echo "  → LLM-синтез не дал отчёт ($FINAL_REPORT пуст/не создан) — fallback: synthesizer.py"
    # P1-фикс: синтезатор читает tribunal.json (источник истины финальных вердиктов)
    python3 "$SCRIPTS/synthesizer.py" "$VERDICTS_PROCESSED" "$TRIBUNAL_JSON" "$FINAL_REPORT" \
      || fail "Этап 8: fallback synthesizer.py вернул ошибку"
  fi
  [ -s "$FINAL_REPORT" ] || fail "Этап 8: не создан $FINAL_REPORT"
  ok "создан: $FINAL_REPORT"
fi

step "Пайплайн завершён"
echo "  Workspace: $WORKSPACE"
echo "  Отчёт:     $FINAL_REPORT"
ls -la "$WORKSPACE" 2>/dev/null
exit 0
