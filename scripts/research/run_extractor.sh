#!/bin/bash
# run_extractor.sh — обёртка для запуска ClaimeAI wrapper (Node 1)
# Usage: bash run_extractor.sh <input.txt> <output.json>
set -e

INPUT="$1"
OUTPUT="$2"

if [ -z "$INPUT" ] || [ -z "$OUTPUT" ]; then
  echo "Usage: bash run_extractor.sh <input.txt> <output.json>" >&2
  exit 1
fi

if [ ! -f "$INPUT" ]; then
  echo "ERROR: input file not found: $INPUT" >&2
  exit 1
fi

# ClaimeAI требует PYTHONSAFEPATH=1 и запуск НЕ из директории проекта (NLTK блокирует defusedxml)
# wrapper уже выставляет env внутри, но перестрахуемся
export PYTHONSAFEPATH=1

VENV_PY="/home/orangepi/projects/ClaimeAI/apps/agent/.venv/bin/python3"
WRAPPER="/home/orangepi/projects/claimeai-service/scripts/claimeai_wrapper.py"

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: venv python not found: $VENV_PY" >&2
  exit 1
fi

if [ ! -f "$WRAPPER" ]; then
  echo "ERROR: wrapper not found: $WRAPPER" >&2
  exit 1
fi

# Запуск из /tmp (не из директории проекта — NLTK security)
cd /tmp

echo "▶ Node 1: Extractor (ClaimeAI)"
echo "  input:  $INPUT"
echo "  output: $OUTPUT"
echo "  venv:   $VENV_PY"
echo "  start:  $(date '+%Y-%m-%d %H:%M:%S')"

PYTHONSAFEPATH=1 "$VENV_PY" "$WRAPPER" "$INPUT" "$OUTPUT" "science-auditor pilot"

echo "  end:    $(date '+%Y-%m-%d %H:%M:%S')"

if [ -f "$OUTPUT" ]; then
  echo "✅ claims.json created: $(wc -c < "$OUTPUT") bytes"
else
  echo "❌ claims.json NOT created" >&2
  exit 1
fi