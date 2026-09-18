#!/usr/bin/env bash
# Coder DOM verify-gate pre-commit hook (CD-004).
# Использование:
#   - pre-commit framework: .pre-commit-config.yaml:
#       - repo: local
#         hooks:
#           - id: coder-dom-verify
#             name: coder-dom in sync
#             entry: bash hooks/coder-dom-verify.sh
#             language: system
#             files: \.py$
# Логика:
#   1. verify_coder_dom.py --root <repo> — если STALE/MISSING -> fail с подсказкой
#   2. stub_detect: не-осознанные заглушки -> fail
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT" || exit 1

PYTHON_BIN="${PYTHON_BIN:-python}"
GLOSSARY_DIR="scripts/glossary"

echo "[coder-dom] verify: coder_dom.yaml in sync with code..."
if ! "$PYTHON_BIN" "$GLOSSARY_DIR/verify_coder_dom.py" --root "$REPO_ROOT"; then
  echo "[coder-dom] FAIL: coder_dom.yaml stale. Run:"
  echo "  python $GLOSSARY_DIR/coder_dom_build.py --root $REPO_ROOT"
  echo "  git add docs/glossary/coder_dom.yaml"
  exit 1
fi

echo "[coder-dom] stub check..."
"$PYTHON_BIN" "$GLOSSARY_DIR/coder_dom_stub_gate.py" --root "$REPO_ROOT"