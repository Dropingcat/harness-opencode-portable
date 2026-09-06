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

# OPENCODE_SESSION_DB — real session DB; set if known.
# export OPENCODE_SESSION_DB="/home/orangepi/.local/share/opencode/opencode.db"

# Research contour (claimeai-service) — set only if those scripts exist on this box.
# export RESEARCH_RUNNER_SH="/home/orangepi/projects/claimeai-service/scripts/run_research.sh"
# export RESEARCH_RULES_PATH="/home/orangepi/.hermes/profiles/resercher/rules_balanced.yaml"
# export RESEARCH_SCRIPTS_ROOT="/home/orangepi/projects/claimeai-service/scripts"
# export RESEARCH_NUMERIC_COMPARATOR="$RESEARCH_SCRIPTS_ROOT/numeric_comparator.py"
# export RESEARCH_SYNTHESIZER="$RESEARCH_SCRIPTS_ROOT/synthesizer.py"
# export RESEARCH_JUDGE_BRIEF="$RESEARCH_SCRIPTS_ROOT/judge_brief.py"

echo "Runtime env applied (current shell). Restart OpenCode from this shell."