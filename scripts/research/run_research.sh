#!/bin/bash
# run_research.sh — детерминированный BRICKS-runner научной верификации.
#
# ⚠️ LINUX-ONLY (Pi / WSL). НЕ использовать на Windows напрямую.
#    Hardcoded /home/orangepi/*, bash-зависимости, MODEL=ollama-cloud/*.
#    На Windows: python-контур (numeric_comparator.py, synthesizer.py, judge_brief.py)
#    + пути из config/path_resolution_map.json. См. IMPLEMENTATION_TRACKER.md WS-04.
#
# Принцип №0: LLM производит свидетельства. КОД принимает решения.
# Этот скрипт — КОД. Он ведёт цикл, вызывает детерминированные скрипты в
# строгом порядке, валидирует артефакты, трекает бюджет/хопы, парсит ответы
# search-сервера, логирует audit. Агенты opencode — LLM-узлы, вызываемые на
# шагах, где нужно LLM-свидетельство (извлечение клаймов, факт-чекинг,
# трибунал, синтез). Никакой LLM не решает окончательный вердикт — только код.
#
# Usage:
#   bash run_research.sh <input.txt> [--workspace DIR] [--rules rules_balanced.yaml] \
#                        [--opencode-model ollama-cloud/glm-5.2] [--dry-run] \
#                        [--max-cost-rub 20.0] [--max-iterations 3]
#
# Конвейер (BRICKS):
#   1. SPLIT    — claim-parser (opencode agent) → claims.json + валидация схемы
#   2. SEARCH   — source-fetcher (opencode agent) → sources_<id>.json + circularity-гейт + парсер ответов
#   3. VERDICT  — fact-checker (opencode agent) → verdicts_raw.json + factcheck_guard (санитизация)
#   4. NUMERIC  — numeric_comparator → numeric_result.json + merge_numeric → verdicts_enriched.json
#   5. EVIDENCE — evidence_contract (clamp trust, provenance) + post_processor (окончательный вердикт)
#   6. JUSTIFY  — justification_check (без обоснования → OPEN)
#   7. ESCALATE — escalation (stop criteria: max_hops/convergence/alarms)
#   8. TRIBUNAL — если триггер: judge_brief → tribunal-judge (opencode agent) → tribunal_<id>.json
#   9. SYNTHESIZE — synthesizer.py (база) + synthesizer agent (расширение) → final_report.md
#  10. AUDIT    — сводка run/<ts>/_audit.json (input_hash → decision → output → ts)

set -uo pipefail

# === ПУТИ (детерминированные, из окружения harness с fallback на относительные) ===
# Приоритет: env-переменные harness (RESEARCH_SCRIPTS_ROOT / RESEARCH_RULES_PATH /
# OPENCODE_HARNESS_ROOT), иначе относительные пути от текущего скрипта.
SCRIPT_DIR_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="${RESEARCH_SCRIPTS_ROOT:-$SCRIPT_DIR_ABS}"
VERIF="$SCRIPTS/verification"
RULES_DEFAULT="${RESEARCH_RULES_PATH:-$SCRIPTS/rules_balanced.yaml}"
HARNESS_ROOT="${OPENCODE_HARNESS_ROOT:-$(dirname "$SCRIPT_DIR_ABS")}"
SHARED="${RESEARCH_SHARED_METHODOLOGY:-$HARNESS_ROOT/shared/research-orchestration-process.md}"
# BROWSER_VENV: только для Linux (browser-MCP venv); на Windows не используется.
BROWSER_VENV="${BROWSER_VENV:-}"

# === Параметры по умолчанию ===
INPUT=""
WORKSPACE=""
RULES="$RULES_DEFAULT"
MODEL="ollama-cloud/glm-5.2"
DRY_RUN=0
MAX_COST_RUB=20.0
MAX_ITER=3

# === Парсинг аргументов ===
while [ $# -gt 0 ]; do
  case "$1" in
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --rules) RULES="$2"; shift 2 ;;
    --opencode-model) MODEL="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --max-cost-rub) MAX_COST_RUB="$2"; shift 2 ;;
    --max-iterations) MAX_ITER="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0"
      exit 0 ;;
    *) INPUT="$1"; shift ;;
  esac
done

if [ -z "$INPUT" ]; then
  echo "ERROR: нужен <input.txt>" >&2
  exit 2
fi
if [ ! -f "$INPUT" ]; then
  echo "ERROR: файл не найден: $INPUT" >&2
  exit 2
fi
if [ ! -f "$RULES" ]; then
  echo "ERROR: rules.yaml не найден: $RULES" >&2
  exit 2
fi

# === Рабочая папка ===
TS=$(date +%Y%m%d_%H%M%S)
if [ -z "$WORKSPACE" ]; then
  WORKSPACE="/tmp/research-${TS}"
fi
mkdir -p "$WORKSPACE/run/${TS}"
RUN_DIR="$WORKSPACE/run/${TS}"
AUDIT_LOG="$RUN_DIR/_audit.json"

# === Состояние ===
ITERATION=0
BUDGET_SPENT_RUB=0.0
BUDGET_SPENT_TOKENS=0
STOP_REASON=""
EXIT_CODE=0

# === Утилиты ===
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$RUN_DIR/runner.log"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $*" | tee -a "$RUN_DIR/runner.log" >&2; }

# input_hash (sha256) — для воспроизводимости
input_hash() {
  sha256sum "$1" | awk '{print $1}'
}

# audit-запись: block, decision, input, output, ts, duration, errors[]
# Пишет JSON-строку в _audit.json (массив)
audit() {
  local block="$1" decision="$2" inp="$3" out="$4" dur="$5" errs="$6"
  python3 - "$AUDIT_LOG" "$block" "$decision" "$inp" "$out" "$dur" "$errs" <<'PYEOF'
import json, sys, os, datetime
log_path, block, decision, inp, out, dur, errs = sys.argv[1:8]
entry = {
    "schema": "research-runner/v1",  # P1.3: версия схемы для воспроизводимости
    "block": block, "decision": decision,
    "input": inp, "output": out,
    "ts": datetime.datetime.now().isoformat(timespec="seconds"),
    "duration_sec": float(dur) if dur else 0.0,
    "errors": json.loads(errs) if errs else []
}
# Дописываем в массив
log = []
if os.path.exists(log_path):
    try:
        with open(log_path) as f:
            log = json.load(f)
    except Exception:
        log = []
log.append(entry)
with open(log_path, "w") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)
PYEOF
}

# Валидация схемы артефакта (блокирующая, не warning)
# Использует verdict_schemas.py если есть; иначе простая проверка структуры
validate_artifact() {
  local file="$1" kind="$2"
  if [ ! -f "$file" ]; then
    err "валидация $kind: файл не найден $file"
    return 1
  fi
  python3 - "$file" "$kind" "$SCRIPTS/verdict_schemas.py" <<'PYEOF'
import json, sys, os
file_path, kind, schemas_path = sys.argv[1:4]
try:
    with open(file_path) as f:
        data = json.load(f)
except Exception as e:
    print(f"VALIDATION FAIL [{kind}]: JSON не читается: {e}", file=sys.stderr)
    sys.exit(2)
# Базовые структурные проверки по kind
errors = []
if kind == "claims":
    if not isinstance(data, dict): errors.append("корень не dict")
    elif "claims" not in data: errors.append("нет ключа 'claims'")
    elif "validated" not in data.get("claims", {}): errors.append("нет claims.validated")
    for i, c in enumerate(data.get("claims", {}).get("validated", [])):
        if "text" not in c: errors.append(f"claim[{i}]: нет text")
        if "index" not in c: errors.append(f"claim[{i}]: нет index")
        if "claim_type" not in c: errors.append(f"claim[{i}]: нет claim_type")
        if c.get("claim_type") not in ("numeric","qualitative","definition","methodological"):
            errors.append(f"claim[{i}]: неверный claim_type '{c.get('claim_type')}'")
elif kind == "sources":
    if not isinstance(data, dict): errors.append("корень не dict")
    for sid, slist in data.items():
        if not isinstance(slist, list): errors.append(f"source[{sid}]: не list")
        for j, s in enumerate(slist):
            if "trust" in s:
                t = s["trust"]
                if not isinstance(t, (int, float)) or t < 0.0 or t > 1.0:
                    errors.append(f"source[{sid}][{j}]: trust={t} вне [0,1]")
            if "excerpt" in s and len(s["excerpt"]) > 2000:
                errors.append(f"source[{sid}][{j}]: excerpt {len(s['excerpt'])} > 2000")
            if "found_via" not in s:
                errors.append(f"source[{sid}][{j}]: нет found_via")
elif kind == "verdicts":
    if not isinstance(data, dict): errors.append("корень не dict")
    for i, v in enumerate(data.get("verdicts", [])):
        if "verdict" not in v: errors.append(f"verdict[{i}]: нет verdict")
        if v.get("verdict") not in ("SUPPORTED","CONTRADICTED","UNSUPPORTED","AMBIGUOUS","OPEN"):
            errors.append(f"verdict[{i}]: неверный verdict '{v.get('verdict')}'")
        if "confidence" in v:
            c = v["confidence"]
            if not isinstance(c, (int, float)) or c < 0.0 or c > 1.0:
                errors.append(f"verdict[{i}]: confidence={c} вне [0,1]")
    # P0.2: Pydantic-валидация через verdict_schemas (БЛОК, не warning).
    # verdict_schemas.VerdictModel имеет Literal enum + confidence ge/le.
    # Раньше это был WARNING (exit 0) — теперь блокируем при нарушении схемы.
    if not errors:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("verdict_schemas", schemas_path)
            vs = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(vs)
            pyd_errors = vs.validate_verdicts(data.get("verdicts", []))
            if pyd_errors:
                errors = [f"pydantic: {e}" for e in pyd_errors[:10]]
        except Exception as e:
            # verdict_schemas недоступен — не блокируем, структурная проверка уже прошла
            pass
if errors:
    print(f"VALIDATION FAIL [{kind}]:", file=sys.stderr)
    for e in errors[:10]:
        print(f"  {e}", file=sys.stderr)
    sys.exit(2)
print(f"VALIDATION OK [{kind}]: {file_path}")
PYEOF
  return $?
}

# Проверка budget: если превышен → STOP
check_budget() {
  python3 - "$BUDGET_SPENT_RUB" "$MAX_COST_RUB" <<'PYEOF'
import sys
spent, mx = float(sys.argv[1]), float(sys.argv[2])
if spent > mx:
    print("BUDGET_EXCEEDED")
    sys.exit(1)
print("OK")
PYEOF
  return $?
}

# === Запуск opencode-агента синхронно, возврат вывода ===
# $1 = agent name, $2 = prompt
run_agent() {
  local agent="$1"
  local prompt="$2"
  if [ "$DRY_RUN" = "1" ]; then
    log "DRY-RUN: пропуск агента $agent"
    echo '{"status":"dry_run"}'
    return 0
  fi
  local out
  out=$(timeout 600 opencode run --agent "$agent" "$prompt" --model "$MODEL" 2>&1) || {
    err "агент $agent упал (exit $?)"
    echo "$out" >> "$RUN_DIR/${agent}_stderr.log"
    return 1
  }
  # Budget tracking: парсим cost из вывода (opencode иногда пишет cost в stderr/meta)
  # Формат может быть: "cost: 0.05$" или "tokens: 1234" или JSON meta
  local cost_rub
  cost_rub=$(echo "$out" | grep -oiE 'cost[^0-9]*[0-9]+\.[0-9]+' | head -1 | grep -oE '[0-9]+\.[0-9]+' || echo "0")
  if [ "$cost_rub" != "0" ]; then
    # Конвертируем USD→RUB грубо (≈90) если похоже на доллары, иначе рубли
    BUDGET_SPENT_RUB=$(python3 -c "print(round($BUDGET_SPENT_RUB + $cost_rub, 4))")
    log "  $agent: потрачено ~${cost_rub} (cumulative: $BUDGET_SPENT_RUB руб)"
  else
    # FALLBACK (P0.4): если opencode не отдаёт cost — оцениваем по числу LLM-вызовов.
    # 1 вызов агента = 1 LLM-инференс ≈ 0.01₽ (грубая оценка для glm-5.2 на 1-2KB промпта).
    # Это детерминированный счётчик, а не промпт — runner сам накручивает расход.
    PER_CALL_ESTIMATE_RUB="${PER_CALL_ESTIMATE_RUB:-0.01}"
    BUDGET_SPENT_RUB=$(python3 -c "print(round($BUDGET_SPENT_RUB + $PER_CALL_ESTIMATE_RUB, 4))")
    BUDGET_SPENT_TOKENS=$((BUDGET_SPENT_TOKENS + 1000))  # ~1K токенов на вызов агента
    log "  $agent: cost не найден — оценка ~${PER_CALL_ESTIMATE_RUB}₽/вызов (cumulative: $BUDGET_SPENT_RUB руб)"
  fi
  # Пишем budget.json (детерминированно, для воспроизводимости)
  python3 - "$WORKSPACE/budget.json" "$BUDGET_SPENT_RUB" "$MAX_COST_RUB" "$BUDGET_SPENT_TOKENS" <<'PYEOF'
import json, os, sys
path, spent, mx, tokens = sys.argv[1:5]
data = {
    "spent_rub": float(spent), "max_rub": float(mx),
    "spent_tokens": int(tokens),
    "exceeded": float(spent) > float(mx),
    "per_call_estimate_rub": os.environ.get("PER_CALL_ESTIMATE_RUB", "0.01"),
}
with open(path, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PYEOF
  echo "$out"
}

# Извлечение JSON из ответа агента (stdout opencode run содержит шум + JSON).
# Ищет первый ```json блок ИЛИ первую { ... } последовательность.
# $1 = сырой вывод, $2 = путь куда писать
extract_json_to_file() {
  local raw="$1" dest="$2"
  python3 - "$dest" <<PYEOF
import json, re, sys
dest = sys.argv[1]
raw = """$(printf '%s' "$raw" | sed 's/"/\\"/g' | sed 's/\\$/\\\\$/g')"""
# Попытка 1: json-блок в markdown
m = re.search(r'\`\`\`json\s*(\{.*?\})\s*\`\`\`', raw, re.DOTALL)
if not m:
    # Попытка 2: первая { ... } (жадная до последней }) 
    m = re.search(r'(\{.*\})', raw, re.DOTALL)
if m:
    try:
        obj = json.loads(m.group(1))
        with open(dest, "w") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print("OK")
        sys.exit(0)
    except Exception as e:
        print(f"PARSE_FAIL: {e}", file=sys.stderr)
sys.exit(1)
PYEOF
  return $?
}

# === BRICK 1: SPLIT — извлечение клаймов ===
brick_split() {
  log "BRICK 1: SPLIT — извлечение клаймов"
  local t0=$(date +%s)
  local prompt="Прочитай shared-методологию: $SHARED (секция Контракты данных → Claim). Извлеки атомарные клаймы из файла: $INPUT. Верни JSON по контракту Claim в СВОЁМ ответе (stdout), НЕ пиши файл — runner сам сохранит. Формат: {status, claims:{validated:[{text, original_sentence, index, claim_type, importance}], discarded:[{text, reason}]}, statistics}."
  local out
  out=$(run_agent "claim-parser" "$prompt") || return 1
  
  # Runner сам пишет claims.json из ответа агента (агент не имеет write-прав)
  if ! extract_json_to_file "$out" "$WORKSPACE/claims.json"; then
    err "claims.json: JSON не извлечён из ответа claim-parser"
    echo "$out" >> "$RUN_DIR/claim-parser_raw.log"
    audit "SPLIT" "FAIL" "$INPUT" "parse_fail" $(($(date +%s)-t0)) '["JSON not extracted"]'
    return 1
  fi
  
  validate_artifact "$WORKSPACE/claims.json" "claims" || return 1
  
  local n_claims
  n_claims=$(python3 -c "import json; d=json.load(open('$WORKSPACE/claims.json')); print(len(d.get('claims',{}).get('validated',[])))")
  log "  клаймов извлечено: $n_claims"
  audit "SPLIT" "OK" "$INPUT" "$WORKSPACE/claims.json" $(($(date +%s)-t0)) "[]"
  echo "$n_claims"
}

# === BRICK 2.0: CASCADE_SEARCH — детерминированный поиск (L10, P0.3) ===
# cascade.py (local_corpus → openalex → arxiv → web_ddg) строит RU/EN-запросы
#   через глоссарий КОДОМ (0 LLM). Это ПЕРВЫЙ источник. LLM source-fetcher —
#   только веб-дополнение для того, что cascade не покрыл.
# Принцип №0: поиск контролируется кодом, LLM — только чтение/дополнение.
brick_cascade_search() {
  log "BRICK 2.0: CASCADE_SEARCH — детерминированный поиск (0 LLM)"
  local t0=$(date +%s)
  local cascade_py="$VERIF/cascade.py"
  local total_cascade=0
  
  # Для каждого клайма — детерминированный каскад
  python3 - "$WORKSPACE" "$cascade_py" <<'PYEOF'
import json, os, sys, subprocess
ws, cascade_py = sys.argv[1:3]
with open(os.path.join(ws, "claims.json")) as f:
    claims = json.load(f)["claims"]["validated"]
for c in claims:
    cid = str(c.get("index"))
    claim_text = c.get("text", "")
    out_file = os.path.join(ws, f"sources_cascade_{cid}.json")
    # Детерминированный каскад: local_corpus → openalex → arxiv → web_ddg
    # (scibot — платный, не включаем по умолчанию)
    try:
        r = subprocess.run(
            [sys.executable, cascade_py, claim_text,
             "--layers", "local_corpus,openalex,arxiv,web_ddg",
             "--limit", "4", "--json"],
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(f"  claim {cid}: cascade rc={r.returncode}")
            continue
        res = json.loads(r.stdout)
        sources = res.get("sources", [])
        # Нормализуем: обрезаем огромный excerpt до 2000 (cascade отдаёт весь текст)
        for s in sources:
            if s.get("excerpt") and len(s["excerpt"]) > 2000:
                s["excerpt"] = s["excerpt"][:2000]
            if s.get("text") and len(s["text"]) > 2000:
                s["text"] = s["text"][:2000]
        # Пишем в sources_cascade_<cid>.json
        with open(out_file, "w") as f:
            json.dump({"task_id": f"rt_{cid}", "claim_ids": [int(cid)],
                       "sources": sources, "rejected_sources": [],
                       "queries_used": res.get("verification_meta", {}).get("queries_used", []),
                       "found_via": "cascade_deterministic"}, f, ensure_ascii=False, indent=2)
        print(f"  claim {cid}: cascade дал {len(sources)} источников")
    except Exception as e:
        print(f"  claim {cid}: cascade ERR {e}")
PYEOF
  
  audit "CASCADE_SEARCH" "OK" "claims" "sources_cascade_*.json" $(($(date +%s)-t0)) "[]"
  log "  cascade_search: готов"
}

# === BRICK 2: SEARCH — поиск источников + circularity-гейт ===
brick_search() {
  log "BRICK 2: SEARCH — поиск источников (per claim)"
  local t0=$(date +%s)
  local total_sources=0
  local total_rejected=0
  
  # BRICK 2.0: сначала детерминированный каскад (0 LLM)
  brick_cascade_search
  
  # Читаем claims, для каждого — ResearchTask
  local claim_ids
  claim_ids=$(python3 -c "
import json
d=json.load(open('$WORKSPACE/claims.json'))
for c in d.get('claims',{}).get('validated',[]):
    print(c['index'])
")
  
  for cid in $claim_ids; do
    local claim_text
    claim_text=$(python3 -c "
import json
d=json.load(open('$WORKSPACE/claims.json'))
for c in d.get('claims',{}).get('validated',[]):
    if c['index']==$cid: print(c['text']); break
")
    
    log "  claim $cid: поиск..."
    # LLM source-fetcher — ТОЛЬКО веб-дополнение (browser-MCP), cascade уже дал
    # local_corpus/openalex/arxiv. Промпт явно говорит: не дублируй cascade.
    local prompt="Прочитай $SHARED (секция Source/Evidence + Инструменты + Порядок источников). ResearchTask: claim_id=$cid, claim_text=\"$claim_text\", question=\"найди ВЕБ-источники (browser_search/webfetch), которых нет в $WORKSPACE/sources_cascade_$cid.json (детерминированный каскад уже дал local_corpus/openalex/arxiv)\", preferred_source_classes=[primary,textbook,review], max_cost_rub=0.5. НЕ дублируй cascade — ищи ТОЛЬКО веб (DDG/Reddit/прямые URL). Пиши результат в $WORKSPACE/sources_$cid.json (используй write). Каждый source: source_id, title, url, doi, type, trust∈[0,1], excerpt≤2000, found_via."
    local out
    out=$(run_agent "source-fetcher" "$prompt") || continue
    
    if [ ! -f "$WORKSPACE/sources_$cid.json" ]; then
      err "  sources_$cid.json не создан"
      continue
    fi
    
    # Парсер ответов search-сервера — детерминированный (КЛЮЧЕВОЕ: не промпт!)
    # Проверяем blocked/http_status/пустой excerpt/relevance
    python3 - "$WORKSPACE/sources_$cid.json" <<'PYEOF'
import json, sys
file = sys.argv[1]
with open(file) as f:
    data = json.load(f)
rejected = data.setdefault("rejected_sources", [])
kept = []
for s in data.get("sources", []):
    drop_reason = None
    # 1. anti-bot блок
    if s.get("blocked") is True or s.get("http_status", 200) >= 400:
        drop_reason = f"blocked/http_{s.get('http_status','?')}"
    # 2. пустой excerpt
    elif not s.get("excerpt") or len(s["excerpt"].strip()) < 20:
        drop_reason = "empty_excerpt"
    # 3. trust вне [0,1] — clamp (баг из audit)
    elif "trust" in s:
        t = s["trust"]
        if not isinstance(t, (int, float)):
            drop_reason = "trust_not_number"
        else:
            s["trust"] = max(0.0, min(1.0, t))  # clamp
    if drop_reason:
        rejected.append({"title": s.get("title","?"), "reason": drop_reason, "url": s.get("url","")})
    else:
        kept.append(s)
data["sources"] = kept
with open(file, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"  sources_{data.get('task_id','?')}: kept={len(kept)} rejected={len(rejected)}")
PYEOF
    
    # CIRCULARITY-ГЕЙТ (детерминированный, не промпт!) — A5
    # Для каждого source: если excerpt — пересказ документа → понижение trust
    # claim_text передаётся из цикла (cid) — починка слепого circularity
    python3 - "$WORKSPACE/sources_$cid.json" "$INPUT" "$VERIF/circularity.py" "$claim_text" <<'PYEOF'
import json, sys, subprocess, os
src_file, doc_file, circ_py, claim_text = sys.argv[1:5]
with open(src_file) as f:
    data = json.load(f)
for s in data.get("sources", []):
    try:
        r = subprocess.run([sys.executable, circ_py, "--json", "--document", doc_file,
                           s.get("excerpt","")[:500], claim_text[:500]],
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            circ = json.loads(r.stdout)
            if circ.get("origin") == "document_derived":
                s["circularity"] = "document_derived"
                s["trust"] = min(s.get("trust", 0.5), 0.3)  # понижаем trust пересказа
    except Exception:
        pass  # circularity не критична при сбое
with open(src_file, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PYEOF
    
    validate_artifact "$WORKSPACE/sources_$cid.json" "sources" || continue
    local n_src
    n_src=$(python3 -c "import json; d=json.load(open('$WORKSPACE/sources_$cid.json')); print(len(d.get('sources',[])))")
    total_sources=$((total_sources + n_src))
    log "  claim $cid: источников $n_src"
    
    # Budget check
    check_budget || { STOP_REASON="BUDGET_EXCEEDED"; break; }
  done
  
  # MERGE: объединяем cascade (детерминированный) + LLM (веб) источники в sources_<cid>.json
  # Дедуп по url/doi. cascade ПЕРВЫМ (детерминированный, высокий trust).
  python3 - "$WORKSPACE" <<'PYEOF'
import json, os, sys, glob
ws = sys.argv[1]
for cid_file in glob.glob(os.path.join(ws, "sources_*.json")):
    # пропускаем cascade-файлы и index
    base = os.path.basename(cid_file)
    if "cascade" in base or base == "sources_index.json":
        continue
    cid = base.replace("sources_", "").replace(".json", "")
    llm_file = cid_file
    cascade_file = os.path.join(ws, f"sources_cascade_{cid}.json")
    if not os.path.exists(cascade_file):
        continue
    try:
        with open(llm_file) as f:
            llm_data = json.load(f)
        with open(cascade_file) as f:
            cascade_data = json.load(f)
    except Exception:
        continue
    llm_sources = llm_data.get("sources", [])
    cascade_sources = cascade_data.get("sources", [])
    # Дедуп по url/doi (cascade приоритетнее)
    seen = set()
    merged = []
    for s in cascade_sources + llm_sources:
        key = s.get("url") or s.get("doi") or s.get("title", "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged.append(s)
    llm_data["sources"] = merged
    llm_data["cascade_merged"] = True
    llm_data["n_cascade"] = len(cascade_sources)
    llm_data["n_llm"] = len(llm_sources)
    with open(llm_file, "w") as f:
        json.dump(llm_data, f, ensure_ascii=False, indent=2)
    print(f"  merge {cid}: cascade={len(cascade_sources)} + llm={len(llm_sources)} -> {len(merged)} (дедуп)")
PYEOF
  
  audit "SEARCH" "OK" "$WORKSPACE/claims.json" "sources_*.json" $(($(date +%s)-t0)) "[]"
  log "  всего источников: $total_sources"
  echo "$total_sources"
}

# === BRICK 3: VERDICT — факт-чекинг + factcheck_guard (санитизация) ===
brick_verdict() {
  log "BRICK 3: VERDICT — факт-чекинг"
  local t0=$(date +%s)
  local prompt="Прочитай $SHARED (секция Verdict + Принцип №0 + Анти-сикофантия). Для каждого клайма из $WORKSPACE/claims.json и его источников $WORKSPACE/sources_*.json: сравни клайм с источниками, сформируй предварительный вердикт (SUPPORTED/CONTRADICTED/UNSUPPORTED/AMBIGUOUS) с confidence, reason, justification (ОБЯЗАТЕЛЬНО, 2-4 предложения со ссылкой на источник), caveats. НЕ вызывай numeric_comparator.py — это работа runner'а (BRICK 4). Верни JSON в СВОЁМ ответе (stdout), НЕ пиши файл — runner сам сохранит. Формат: {verdicts:[{claim_id, claim_text, verdict, confidence, reason, justification, sources_used, caveats, numeric_comparison:{claim_value, source_value, status}}]}."
  local out
  out=$(run_agent "fact-checker" "$prompt") || return 1
  
  # Runner сам пишет verdicts_raw.json из ответа агента (агент не имеет write-прав)
  if ! extract_json_to_file "$out" "$WORKSPACE/verdicts_raw.json"; then
    err "verdicts_raw.json: JSON не извлечён из ответа fact-checker"
    echo "$out" >> "$RUN_DIR/fact-checker_raw.log"
    audit "VERDICT" "FAIL" "claims" "parse_fail" $(($(date +%s)-t0)) '["JSON not extracted"]'
    return 1
  fi
  
  # FACTCHECK_GUARD — санитизация LLM-сбоев парсинга (A7)
  log "  factcheck_guard: санитизация..."
  python3 "$SCRIPTS/factcheck_guard.py" "$WORKSPACE/verdicts_raw.json" --mark-parse-fail --out "$WORKSPACE/verdicts_raw.json" 2>>"$RUN_DIR/guard.log" || {
    err "factcheck_guard упал"
  }
  
  validate_artifact "$WORKSPACE/verdicts_raw.json" "verdicts" || return 1
  audit "VERDICT" "OK" "claims+sources" "$WORKSPACE/verdicts_raw.json" $(($(date +%s)-t0)) "[]"
}

# === BRICK 3.5: CONTENT_VERDICT_GATE — детерминированный entailment (анти-сикофантия, L8) ===
# content_verdict.py (--no-llm) детерминированно оценивает каждый источник:
#   supports / refutes / neutral / irrelevant (предикаты кодом, 0 LLM-вызовов).
# Гейт: если LLM-факт-чекер сказал SUPPORTED, но content_verdict для ВСЕХ
#   источников дал refutes/irrelevant → LLM-вердикт «слил» claim с похожим
#   источником. Понижаем confidence (cap 0.5) + caveat deterministic_entailment_mismatch.
# Принцип №0: код решает entailment, LLM — только свидетельство.
brick_content_verdict_gate() {
  log "BRICK 3.5: CONTENT_VERDICT_GATE — детерминированный entailment"
  local t0=$(date +%s)
  local cv_py="$VERIF/content_verdict.py"
  local n_gated=0
  
  # Для каждого клайма из claims.json
  python3 - "$WORKSPACE" "$cv_py" "$INPUT" "$RUN_DIR" <<'PYEOF'
import json, os, sys, subprocess, glob
ws, cv_py, doc_file, run_dir = sys.argv[1:5]

# Загружаем claims
with open(os.path.join(ws, "claims.json")) as f:
    claims_data = json.load(f)
claims = claims_data.get("claims", {}).get("validated", [])

# Загружаем LLM-вердикты (verdicts_raw.json)
with open(os.path.join(ws, "verdicts_raw.json")) as f:
    verdicts_data = json.load(f)
verdicts = verdicts_data.get("verdicts", []) if isinstance(verdicts_data, dict) else verdicts_data

# Индекс вердиктов по claim_id
verdict_by_id = {}
for v in verdicts:
    cid = v.get("claim_id", v.get("index"))
    if cid is not None:
        verdict_by_id[str(cid)] = v

gated = 0
for c in claims:
    cid = str(c.get("index"))
    claim_text = c.get("text", "")
    src_file = os.path.join(ws, f"sources_{cid}.json")
    if not os.path.exists(src_file):
        continue
    v = verdict_by_id.get(cid)
    if v is None:
        continue
    # Вызываем content_verdict.py --no-llm (детерминированно, 0 LLM)
    try:
        r = subprocess.run(
            [sys.executable, cv_py, claim_text, "--sources", src_file,
             "--document", doc_file, "--no-llm", "--json"],
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            continue
        cv = json.loads(r.stdout)
    except Exception:
        continue
    
    # Предикаты по источникам
    preds = [p.get("predicate") for p in cv.get("per_source", [])]
    n_supports = sum(1 for p in preds if p == "supports")
    n_refutes = sum(1 for p in preds if p == "refutes")
    n_irrelevant = sum(1 for p in preds if p == "irrelevant")
    n_neutral = sum(1 for p in preds if p == "neutral")
    n_total = len(preds)
    
    # ГЕЙТ: LLM=SUPPORTED, но детерминированный entailment противоречит.
    # Понижаем ТОЛЬКО при явном опровержении (refutes) ИЛИ когда ВСЕ источники
    #   нерелевантны/пересказ (irrelevant — circularity). neutral (источник есть,
    #   но не сопоставлен, напр. RU-claim vs EN-источник) НЕ триггерит — это
    #   «недостаточно данных», а не опровержение. Иначе gate ложно понижает
    #   правильные SUPPORTED из-за языкового барьера.
    llm_verdict = v.get("verdict", "")
    det_contradicts = (n_refutes > 0) or (n_supports == 0 and n_total > 0 and n_irrelevant == n_total)
    if llm_verdict == "SUPPORTED" and det_contradicts:
        # LLM «слил» claim с похожим источником — понижаем
        v["confidence"] = min(v.get("confidence", 0.5), 0.5)
        v["verdict"] = "AMBIGUOUS"  # код решает: без детерм. опоры не SUPPORTED
        v.setdefault("caveats", []).append({
            "severity": "critical",
            "text": f"deterministic_entailment_mismatch: LLM=SUPPORTED, но content_verdict дал supports={n_supports}, refutes={n_refutes}, irrelevant={n_irrelevant}, neutral={n_neutral}"
        })
        v["content_verdict_gate"] = {
            "llm_verdict": llm_verdict, "det_verdict": cv.get("verdict"),
            "supports": n_supports, "refutes": n_refutes,
            "irrelevant": n_irrelevant, "neutral": n_neutral,
            "action": "downgraded_to_ambiguous"
        }
        gated += 1
    else:
        v["content_verdict_gate"] = {
            "llm_verdict": llm_verdict, "det_verdict": cv.get("verdict"),
            "supports": n_supports, "refutes": n_refutes,
            "irrelevant": n_irrelevant, "neutral": n_neutral,
            "action": "ok"
        }

# Сохраняем обогащённые вердикты
with open(os.path.join(ws, "verdicts_raw.json"), "w") as f:
    json.dump(verdicts_data, f, ensure_ascii=False, indent=2)
print(f"  content_verdict_gate: gated={gated} (LLM=SUPPORTED без детерм. опоры)")
PYEOF
  
  audit "CONTENT_VERDICT_GATE" "OK" "verdicts_raw" "verdicts_raw+gates" $(($(date +%s)-t0)) "[]"
  log "  content_verdict_gate: готов"
}

# === BRICK 4: NUMERIC — детерминированный числовой слой + MERGE (починка A1!) ===
brick_numeric() {
  log "BRICK 4: NUMERIC — детерминированный числовой entailment + MERGE"
  local t0=$(date +%s)
  
  # Собираем все sources в один индекс для numeric_comparator
  python3 - "$WORKSPACE" <<'PYEOF'
import json, os, glob, sys
ws = sys.argv[1]
idx = {}
for f in glob.glob(os.path.join(ws, "sources_*.json")):
    try:
        with open(f) as fh:
            d = json.load(fh)
        for s in d.get("sources", []):
            sid = s.get("source_id") or s.get("title","")[:40].lower().replace(" ","_")
            idx[sid] = s
    except Exception:
        pass
with open(os.path.join(ws, "sources_index.json"), "w") as out:
    json.dump(idx, out, ensure_ascii=False, indent=2)
print(f"sources_index: {len(idx)} записей")
PYEOF
  
  # numeric_comparator (детерминированно сравнивает числа)
  if python3 "$SCRIPTS/numeric_comparator.py" "$WORKSPACE/verdicts_raw.json" "$WORKSPACE/sources_index.json" "$WORKSPACE/numeric_result.json" 2>>"$RUN_DIR/numeric.log"; then
    log "  numeric_comparator: OK"
  else
    log "  numeric_comparator: пропущен (нет чисел или ошибка)"
  fi
  
  # MERGE_NUMERIC — КЛЮЧЕВАЯ ПОЧИНКА (A1): вливает numeric в verdicts
  # Без этого numeric_rules в post_processor — мёртвый код!
  if [ -f "$WORKSPACE/numeric_result.json" ]; then
    python3 "$SCRIPTS/merge_numeric.py" "$WORKSPACE/verdicts_raw.json" "$WORKSPACE/numeric_result.json" "$WORKSPACE/verdicts_enriched.json" 2>>"$RUN_DIR/merge.log" || {
      err "merge_numeric упал — копируем raw в enriched"
      cp "$WORKSPACE/verdicts_raw.json" "$WORKSPACE/verdicts_enriched.json"
    }
    log "  merge_numeric: OK (numeric_signal влит в verdicts)"
  else
    cp "$WORKSPACE/verdicts_raw.json" "$WORKSPACE/verdicts_enriched.json"
  fi
  
  audit "NUMERIC" "OK" "verdicts_raw" "$WORKSPACE/verdicts_enriched.json" $(($(date +%s)-t0)) "[]"
}

# === BRICK 5: EVIDENCE + POST — evidence_contract (clamp trust) + post_processor (окончательный вердикт) ===
brick_evidence_post() {
  log "BRICK 5: EVIDENCE + POST — provenance + окончательный вердикт"
  local t0=$(date +%s)
  
  # evidence_contract (добавляет evidence[] в каждый verdict, provenance)
  # trust clamp — встроен в скрипт? Проверим и подстрахуем.
  python3 "$SCRIPTS/evidence_contract.py" "$WORKSPACE/verdicts_enriched.json" "$RULES" "$WORKSPACE/evidence_out.json" 2>>"$RUN_DIR/evidence.log" || {
    err "evidence_contract упал"
    cp "$WORKSPACE/verdicts_enriched.json" "$WORKSPACE/verdicts_final.json"
    audit "EVIDENCE" "FAIL" "enriched" "copy_raw" $(($(date +%s)-t0)) '["evidence_contract failed"]'
    return 0
  }
  
  # Дополнительный clamp trust в evidence (страховка от бага A4: trust:5.0)
  python3 - "$WORKSPACE/evidence_out.json" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
# evidence_out.json может быть dict {verdicts:[...]} ИЛИ list [...] — обработать оба
verdicts = data.get("verdicts", []) if isinstance(data, dict) else data
if isinstance(verdicts, list):
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        for e in v.get("evidence", []):
            t = e.get("trust", 0.5)
            if isinstance(t, (int, float)):
                e["trust"] = max(0.0, min(1.0, t))
            else:
                e["trust"] = 0.5
with open(sys.argv[1], "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PYEOF
  
  # POST_PROCESSOR — ОКОНЧАТЕЛЬНЫЙ ВЕРДИКТ (Принцип №0: код решает)
  # Читает verdicts_enriched (с numeric + evidence), применяет rules.yaml,
  # ставит final_verdict, caveats, problematic, tribunal_trigger
  python3 "$SCRIPTS/post_processor.py" "$WORKSPACE/verdicts_enriched.json" "$RULES" "$WORKSPACE/verdicts_final.json" 2>>"$RUN_DIR/post.log" || {
    err "post_processor упал"
    cp "$WORKSPACE/verdicts_enriched.json" "$WORKSPACE/verdicts_final.json"
  }
  
  if [ -f "$WORKSPACE/verdicts_final.json" ]; then
    log "  post_processor: окончательный вердикт готов"
    # Статистика
    python3 - "$WORKSPACE/verdicts_final.json" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
v = data.get("verdicts", []) if isinstance(data, dict) else data
if not isinstance(v, list):
    v = []
from collections import Counter
c = Counter(x.get("verdict","?") for x in v if isinstance(x, dict))
print(f"  вердикты: {dict(c)} (всего {len(v)})")
PYEOF
  fi
  
  audit "EVIDENCE_POST" "OK" "enriched" "$WORKSPACE/verdicts_final.json" $(($(date +%s)-t0)) "[]"
}

# === BRICK 6: JUSTIFY — justification_check (без обоснования → OPEN) (починка A2!) ===
brick_justify() {
  log "BRICK 6: JUSTIFY — гейт обоснованности (без justification → OPEN)"
  local t0=$(date +%s)
  
  # justification_check — отдельный скрипт (НЕ внутри post_processor, как врал оркестратор!)
  python3 "$SCRIPTS/justification_check.py" "$WORKSPACE/verdicts_final.json" "$RULES" "$WORKSPACE/verdicts_final.json" --report "$RUN_DIR/alarms.json" 2>>"$RUN_DIR/justify.log" || {
    err "justification_check упал"
  }
  
  if [ -f "$RUN_DIR/alarms.json" ]; then
    local n_alarms
    n_alarms=$(python3 -c "import json; print(len(json.load(open('$RUN_DIR/alarms.json'))))" 2>/dev/null || echo "?")
    log "  alarms (вердикты без обоснования → OPEN): $n_alarms"
  fi
  
  audit "JUSTIFY" "OK" "verdicts_final" "verdicts_final+alarms" $(($(date +%s)-t0)) "[]"
}

# === BRICK 7: ESCALATE — stop criteria кодом (починка A6!) ===
brick_escalate() {
  log "BRICK 7: ESCALATE — stop criteria (max_hops/convergence/alarms)"
  local t0=$(date +%s)
  
  # topics_tree — нужен escalation.py. Строим stub если нет.
  if [ ! -f "$WORKSPACE/topics_tree.json" ]; then
    python3 - "$WORKSPACE" <<'PYEOF'
import json, sys, os
ws = sys.argv[1]
# stub topics_tree из claims
try:
    with open(os.path.join(ws, "claims.json")) as f:
        claims = json.load(f)
    tree = {"topics": [{"id": "root", "label": "all", "claim_ids": [c["index"] for c in claims.get("claims",{}).get("validated",[])]}]}
except Exception:
    tree = {"topics": []}
with open(os.path.join(ws, "topics_tree.json"), "w") as f:
    json.dump(tree, f, ensure_ascii=False, indent=2)
PYEOF
  fi
  
  # escalation.py — детерминированный stop criteria
  python3 "$SCRIPTS/escalation.py" "$WORKSPACE/verdicts_final.json" "$WORKSPACE/topics_tree.json" "$RULES" "$WORKSPACE/escalation_out.json" 2>>"$RUN_DIR/escalation.log" || {
    err "escalation упал (некритично — продолжаем)"
  }
  
  # Проверяем escalation status
  if [ -f "$WORKSPACE/escalation_out.json" ]; then
    local status
    status=$(python3 -c "
import json
d=json.load(open('$WORKSPACE/escalation_out.json'))
print(d.get('status','?'))
" 2>/dev/null || echo "?")
    log "  escalation status: $status"
    if [ "$status" = "OPEN" ] || [ "$status" = "escale" ]; then
      log "  → escalation_cutoff: stop criteria сработал"
    fi
  fi
  
  audit "ESCALATE" "OK" "verdicts_final" "escalation_out.json" $(($(date +%s)-t0)) "[]"
}

# === BRICK 8: TRIBUNAL — диалектика судей (если триггер) ===
brick_tribunal() {
  log "BRICK 8: TRIBUNAL — диалектика (если триггер)"
  local t0=$(date +%s)
  
  # judge_brief — асимметрия информации (детерминированно разбивает источники по ролям)
  python3 "$SCRIPTS/judge_brief.py" "$WORKSPACE/verdicts_final.json" "$WORKSPACE/judge_briefs.json" 2>>"$RUN_DIR/brief.log" || {
    err "judge_brief упал"
    audit "TRIBUNAL" "SKIP" "verdicts_final" "no_briefs" $(($(date +%s)-t0)) '["judge_brief failed"]'
    return 0
  }
  
  # Определяем какие claims требуют трибунала (по post_processor флагам)
  local tribunal_claims
  tribunal_claims=$(python3 -c "
import json
d=json.load(open('$WORKSPACE/verdicts_final.json'))
for v in d.get('verdicts', []):
    if v.get('verdict') in ('AMBIGUOUS','CONTRADICTED') or any(c.get('severity')=='critical' for c in v.get('caveats',[])):
        print(v.get('claim_id', v.get('index','?')))
")
  if [ -z "$tribunal_claims" ]; then
    log "  трибунал не требуется (нет спорных клаймов)"
    audit "TRIBUNAL" "SKIP" "verdicts_final" "no_trigger" $(($(date +%s)-t0)) "[]"
    return 0
  fi
  
  log "  спорные клаймы для трибунала: $tribunal_claims"
  local prompt="Прочитай $SHARED (секция TribunalReport + Триггер трибунала). Брифы судей: $WORKSPACE/judge_briefs.json. Вердикты: $WORKSPACE/verdicts_final.json. Для каждого спорного клайма ($tribunal_claims): проведи диалектику 5 судей (физик/методолог/скептик/адвокат/агрегатор), атаки, агрегация. Верни JSON в СВОЁМ ответе (stdout), НЕ пиши файл — runner сам сохранит. Формат: {reports: [{claim_id, judges[], aggregate_verdict, final_confidence, consensus_type, escalation_seed}]}."
  local out
  out=$(run_agent "tribunal-judge" "$prompt") || {
    err "tribunal-judge упал"
    audit "TRIBUNAL" "FAIL" "briefs" "agent_fail" $(($(date +%s)-t0)) '["agent failed"]'
    return 0
  }
  # Runner сам пишет tribunal_combined.json (агент не имеет write-прав)
  if ! extract_json_to_file "$out" "$WORKSPACE/tribunal_combined.json"; then
    err "tribunal_combined.json: JSON не извлечён"
    echo "$out" >> "$RUN_DIR/tribunal-judge_raw.log"
  fi
  
  audit "TRIBUNAL" "OK" "briefs" "$WORKSPACE/tribunal_combined.json" $(($(date +%s)-t0)) "[]"
}

# === BRICK 9: SYNTHESIZE — финальный отчёт ===
brick_synthesize() {
  log "BRICK 9: SYNTHESIZE — финальный отчёт"
  local t0=$(date +%s)
  
  # Сначала детерминированный synthesizer.py (база)
  local tribunal_arg=""
  if [ -f "$WORKSPACE/tribunal_combined.json" ]; then
    tribunal_arg="$WORKSPACE/tribunal_combined.json"
  fi
  python3 "$SCRIPTS/synthesizer.py" "$WORKSPACE/verdicts_final.json" $tribunal_arg "$WORKSPACE/final_report_base.md" 2>>"$RUN_DIR/synth.log" || {
    err "synthesizer.py упал"
  }
  
  # Затем agent-synthesizer (расширение: вопросы автору, проблемные тезисы)
  local prompt="Прочитай $SHARED (секция Поток данных + Шкала вердиктов). Базовый отчёт: $WORKSPACE/final_report_base.md (если есть). Вердикты: $WORKSPACE/verdicts_final.json. Трибунал: $WORKSPACE/tribunal_combined.json (если есть). Сформируй расширенный final_report.md: сводка, детали по клаймам (цветовая кодировка 🟢🔴🟡🟠⚪), проблемные тезисы, вопросы автору (привязаны к claim_id), рекомендации. Пиши в $WORKSPACE/final_report.md (используй write)."
  run_agent "synthesizer" "$prompt" || {
    err "synthesizer agent упал — используем base"
    if [ -f "$WORKSPACE/final_report_base.md" ]; then
      cp "$WORKSPACE/final_report_base.md" "$WORKSPACE/final_report.md"
    fi
  }
  
  if [ -f "$WORKSPACE/final_report.md" ]; then
    log "  final_report.md готов"
  fi
  
  audit "SYNTHESIZE" "OK" "verdicts_final" "$WORKSPACE/final_report.md" $(($(date +%s)-t0)) "[]"
}

# === BRICK 10: AUDIT — сводка ===
brick_audit() {
  log "BRICK 10: AUDIT — сводка"
  local ih
  ih=$(input_hash "$INPUT")
  
  # Сводка run
  python3 - "$WORKSPACE" "$RUN_DIR" "$ih" "$INPUT" "$BUDGET_SPENT_RUB" "$MAX_COST_RUB" <<'PYEOF'
import json, os, sys, datetime
ws, run_dir, ih, inp, spent, mx = sys.argv[1:7]
audit_file = os.path.join(run_dir, "_audit.json")
steps = []
if os.path.exists(audit_file):
    with open(audit_file) as f:
        steps = json.load(f)
summary = {
    "schema": "research-runner/v1",  # P1.3: версия схемы
    "input": inp,
    "input_hash": ih,
    "workspace": ws,
    "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    "budget": {"spent_rub": float(spent), "max_rub": float(mx), "exceeded": float(spent)>float(mx)},
    "steps": steps,
    "artifacts": {
        "claims": os.path.exists(os.path.join(ws, "claims.json")),
        "verdicts_final": os.path.exists(os.path.join(ws, "verdicts_final.json")),
        "final_report": os.path.exists(os.path.join(ws, "final_report.md")),
        "tribunal": os.path.exists(os.path.join(ws, "tribunal_combined.json")),
        "evidence": os.path.exists(os.path.join(ws, "evidence_out.json")),
        "numeric": os.path.exists(os.path.join(ws, "numeric_result.json"))
    }
}
with open(os.path.join(run_dir, "summary.json"), "w") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(json.dumps(summary, ensure_ascii=False, indent=2))
PYEOF
  log "AUDIT записан: $RUN_DIR/summary.json"
}

# === ГЛАВНЫЙ КОНВЕЙЕР ===
log "=== RUN_RESEARCH START ==="
log "input: $INPUT"
log "workspace: $WORKSPACE"
log "rules: $RULES"
log "model: $MODEL"
log "input_hash: $(input_hash "$INPUT")"
log "max_cost_rub: $MAX_COST_RUB, max_iterations: $MAX_ITER"
[ "$DRY_RUN" = "1" ] && log "DRY-RUN: агенты не вызываются, скрипты без данных"

# BRICK 1
n_claims=$(brick_split) || { err "SPLIT failed"; EXIT_CODE=1; }
log "=== клаймов: $n_claims ==="

# BRICK 2-7 в цикле итераций (P1.1 — многоитерационность)
# Пока не достигли MAX_ITER, повторяем SEARCH→VERDICT→... для OPEN/AMBIGUOUS клаймов.
# Уточнённый запрос добавляет "counter-evidence"/альтернативные термины.
ITERATION=0
while [ "$ITERATION" -lt "$MAX_ITER" ] && [ -z "$STOP_REASON" ]; do
  ITERATION=$((ITERATION + 1))
  log "=== ИТЕРАЦИЯ $ITERATION/$MAX_ITER ==="
  
  # BRICK 2
  if [ -z "$STOP_REASON" ]; then
    brick_search || { err "SEARCH failed"; EXIT_CODE=1; }
  fi
  
  # BRICK 3
  if [ -z "$STOP_REASON" ]; then
    brick_verdict || { err "VERDICT failed"; EXIT_CODE=1; }
  fi
  
  # BRICK 3.5 — content_verdict gate (детерминированный entailment, анти-сикофантия)
  if [ -z "$STOP_REASON" ]; then
    brick_content_verdict_gate
  fi
  
  # BRICK 4 — numeric + MERGE (починка A1)
  if [ -z "$STOP_REASON" ]; then
    brick_numeric
  fi
  
  # BRICK 5 — evidence + post (окончательный вердикт)
  if [ -z "$STOP_REASON" ]; then
    brick_evidence_post
  fi
  
  # BRICK 6 — justification gate (починка A2)
  if [ -z "$STOP_REASON" ]; then
    brick_justify
  fi
  
  # BRICK 7 — escalation / stop criteria (починка A6)
  if [ -z "$STOP_REASON" ]; then
    brick_escalate
  fi
  
  # Проверка сходимости: есть ли ещё OPEN/AMBIGUOUS клаймы, требующие новой итерации?
  pending=$(python3 -c "
import json, sys
try:
    d = json.load(open('$WORKSPACE/verdicts_final.json'))
except Exception:
    print(0); sys.exit(0)
n = sum(1 for v in d.get('verdicts', []) if v.get('verdict') in ('OPEN','AMBIGUOUS'))
print(n)
" 2>/dev/null || echo 0)
  
  if [ "$pending" -eq 0 ] || [ "$ITERATION" -ge "$MAX_ITER" ]; then
    log "  сходимость: pending=$pending, iter=$ITERATION/$MAX_ITER → выход из цикла"
    break
  fi
  log "  осталось спорных клаймов: $pending → повтор SEARCH с уточнёнными запросами"
  # В следующих итерациях cascade+source-fetcher сами добавят альтернативные источники
  # (промпт source-fetcher получает claim_text, накапливается history)
  echo "  $pending" > "$WORKSPACE/iteration_${ITERATION}_pending.txt"
done

# BRICK 8 — tribunal (если триггер)
if [ -z "$STOP_REASON" ]; then
  brick_tribunal
fi

# BRICK 9 — synthesize
brick_synthesize

# BRICK 10 — audit summary
brick_audit

log "=== RUN_RESEARCH END (exit=$EXIT_CODE) ==="
if [ -n "$STOP_REASON" ]; then
  log "STOP_REASON: $STOP_REASON"
fi
log "Результаты: $WORKSPACE"
log "Audit: $RUN_DIR/summary.json"

exit $EXIT_CODE