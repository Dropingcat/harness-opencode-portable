#!/usr/bin/env bash
# Runtime environment bootstrap for OpenCode unified module (Linux / Pi server)

HARNESS="${OPENCODE_HARNESS_ROOT:?set OPENCODE_HARNESS_ROOT first}"

export OPENCODE_HARNESS_ROOT="$HARNESS"
export OPENCODE_RUNS_DIR="${OPENCODE_RUNS_DIR:-$HARNESS/.runs}"
export OPENCODE_CONFIG_DIR="$HOME/.config/opencode"
export OPENCODE_BIN="${OPENCODE_BIN:-opencode}"
export DOC_GUARD_ENTRYPOINT="$HARNESS/guard/src/session_guard.py"
export DOC_GUARD_RUNNER="$HARNESS/guard/src/guard_runner.py"
export DOC_GUARD_CONFIG="$HOME/.config/opencode/guard_config.json"
export DOC_GUARD_PROVIDER="${DOC_GUARD_PROVIDER:-cloud}"
export PYTHON="${PYTHON:-python3}"
export HERMES_ROOT="$HARNESS"

# Native Writer Core. Runtime artifacts stay outside the source tree.
export WRITER_CORE_ROOT="$HARNESS/scripts/writer-core"
export WRITER_RUNS_DIR="$HARNESS/.runs/writer-core"
export WRITER_LINGUISTICS_REGISTRY_DIR="$HARNESS/scripts/writer-core/linguistic_assets"

# Preserve an explicitly configured Writer Core interpreter. Otherwise prefer a
# repository-local writer venv and use the general interpreter as an honest
# fallback; capability preflight verifies the required dependencies.
if [ -n "${WRITER_PYTHON:-}" ]; then
  if [[ "$WRITER_PYTHON" == */* ]] && [ ! -x "$WRITER_PYTHON" ]; then
    echo "WARN: configured WRITER_PYTHON is not executable: $WRITER_PYTHON; Writer Core preflight will be degraded" >&2
  fi
elif [ -x "$HARNESS/scripts/writer-core/.venv/bin/python" ]; then
  export WRITER_PYTHON="$HARNESS/scripts/writer-core/.venv/bin/python"
else
  export WRITER_PYTHON="$PYTHON"
  echo "WARN: no dedicated Writer Core venv found; using '$WRITER_PYTHON' and relying on preflight dependency checks" >&2
fi

# OPENCODE_SESSION_DB — real session DB; set if known.
# export OPENCODE_SESSION_DB="/home/orangepi/.local/share/opencode/opencode.db"

# Research contour (claimeai-service) — set only if those scripts exist on this box.
# export RESEARCH_RUNNER_SH="/home/orangepi/projects/claimeai-service/scripts/run_research.sh"
# export RESEARCH_RULES_PATH="/home/orangepi/.hermes/profiles/resercher/rules_balanced.yaml"
# export RESEARCH_SCRIPTS_ROOT="/home/orangepi/projects/claimeai-service/scripts"
# export RESEARCH_NUMERIC_COMPARATOR="$RESEARCH_SCRIPTS_ROOT/numeric_comparator.py"
# export RESEARCH_SYNTHESIZER="$RESEARCH_SCRIPTS_ROOT/synthesizer.py"
# export RESEARCH_JUDGE_BRIEF="$RESEARCH_SCRIPTS_ROOT/judge_brief.py"
# export RESEARCH_VERIFICATION_ROOT="$HARNESS/.runs/verification"

echo "Runtime env applied (current shell). Restart OpenCode from this shell."
