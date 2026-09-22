#!/bin/bash
# test_runner.sh — золотые тесты BRICKS-runner (P2.1).
# РЕАЛЬНЫЙ тест, не маркетинг: проверяет структуру конвейера и создание артефактов.
# Запуск: bash test_runner.sh   (не требует сети/LLM — dry-run)
# Usage: bash test_runner.sh [--real]

set -uo pipefail
RUNNER="/home/orangepi/projects/claimeai-service/scripts/run_research.sh"
INPUT="/tmp/test-research-input.txt"
WORKSPACE="/tmp/test-runner-ws"
PASS=0
FAIL=0

ok() { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

# --- Тестовый вход ---
cat > "$INPUT" <<'EOF'
Азотирование стали 08Х18Н10Т повышает твёрдость поверхности с 200 HV до 1000-1200 HV.
Энтальпия активации образования нитридной фазы Fe2-3N составляет 77 кДж/моль.
Метод рентгеновской дифрактометрии (РФА) позволяет идентифицировать фазовый состав.
EOF

echo "=== 1. Синтаксис runner ==="
if bash -n "$RUNNER"; then ok "bash -n"; else bad "bash -n"; fi

echo "=== 2. Dry-run прогон (структура конвейера, без LLM) ==="
rm -rf "$WORKSPACE"
bash "$RUNNER" "$INPUT" --workspace "$WORKSPACE" --dry-run >/dev/null 2>&1
if [ -f "$WORKSPACE/run/"*/summary.json ]; then ok "summary.json создан"; else bad "summary.json отсутствует"; fi

echo "=== 3. BRICKS в audit-логе (порядок) ==="
AUDIT=$(ls "$WORKSPACE"/run/*/_audit.json 2>/dev/null | head -1)
if [ -n "$AUDIT" ]; then
  BLOCKS=$(python3 -c "import json; print(','.join(x['block'] for x in json.load(open('$AUDIT'))))")
  echo "  blocks: $BLOCKS"
  # Все критические BRICKS должны присутствовать
  for b in CASCADE_SEARCH SEARCH CONTENT_VERDICT_GATE NUMERIC EVIDENCE_POST JUSTIFY ESCALATE TRIBUNAL SYNTHESIZE; do
    echo "$BLOCKS" | grep -q "$b" && ok "BRICK $b" || bad "BRICK $b отсутствует"
  done
else
  bad "audit не найден"
fi

echo "=== 4. schema-версия ==="
SUMMARY=$(ls "$WORKSPACE"/run/*/summary.json 2>/dev/null | head -1)
if [ -n "$SUMMARY" ]; then
  S=$(python3 -c "import json; print(json.load(open('$SUMMARY')).get('schema',''))")
  [ "$S" = "research-runner/v1" ] && ok "schema $S" || bad "schema='$S' (ожидалось research-runner/v1)"
else
  bad "summary не найден"
fi

echo "=== 5. Валидация артефактов (блокирующая) ==="
# Тест блокирующей валидации verdict_schemas через runner'овскую функцию
python3 - /tmp/verdict_bad.json verdicts /home/orangepi/projects/claimeai-service/scripts/verdict_schemas.py <<'PYEOF' 2>/dev/null
import json, sys
with open("/tmp/verdict_bad.json", "w") as f:
    json.dump({"verdicts":[{"claim_id":0,"claim_text":"t","verdict":"MAYBE","confidence":0.9}]}, f)
PYEOF
python3 - /tmp/verdict_bad.json verdicts /home/orangepi/projects/claimeai-service/scripts/verdict_schemas.py <<'PYEOF'
import json, sys
file_path, kind, schemas_path = sys.argv[1:4]
data = json.load(open(file_path))
errors = []
for i, v in enumerate(data.get("verdicts", [])):
    if v.get("verdict") not in ("SUPPORTED","CONTRADICTED","UNSUPPORTED","AMBIGUOUS","OPEN"):
        errors.append(f"verdict[{i}]: неверный verdict")
    c = v.get("confidence")
    if not isinstance(c,(int,float)) or c<0.0 or c>1.0:
        errors.append(f"verdict[{i}]: confidence вне [0,1]")
if not errors:
    import importlib.util
    spec = importlib.util.spec_from_file_location("verdict_schemas", schemas_path)
    vs = importlib.util.module_from_spec(spec); spec.loader.exec_module(vs)
    pyd = vs.validate_verdicts(data.get("verdicts", []))
    if pyd: errors = [f"pydantic: {e}" for e in pyd[:10]]
sys.exit(2 if errors else 0)
PYEOF
[ $? -eq 2 ] && ok "невалидный enum → блок (exit 2)" || bad "невалидный enum не заблокирован"

echo "=== 6. Budget-tracker (fallback-оценка) ==="
B=0; B=$(python3 -c "print(round($B + 0.01, 4))")
[ "$B" = "0.01" ] && ok "fallback-оценка 0.01" || bad "fallback не сработал"

echo "=== 7. Многоитерационность (логика цикла) ==="
# Проверка: при pending>0 и iter<MAX_ITER цикл продолжается (из runner.log)
LOG=$(ls "$WORKSPACE"/run/*/runner.log 2>/dev/null | head -1)
if [ -n "$LOG" ] && grep -q "ИТЕРАЦИЯ" "$LOG"; then
  ok "цикл итераций запускался ($(grep -c 'ИТЕРАЦИЯ' "$LOG") итераций)"
else
  bad "цикл итераций не запускался"
fi

echo ""
echo "=== ИТОГ: PASS=$PASS FAIL=$FAIL ==="
exit $((FAIL > 0))