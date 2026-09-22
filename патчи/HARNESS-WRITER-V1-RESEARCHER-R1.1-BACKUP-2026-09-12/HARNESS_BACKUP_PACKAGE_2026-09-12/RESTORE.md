# Restore

Preferred: unpack `working_tree/`; it includes the complete Git history for this checkpoint.

Alternative:

```bash
git clone harness_writer_v1_researcher_r1_1.bundle restored-harness
cd restored-harness
git checkout backup-writer-v1-researcher-r1.1-2026-09-12
```

Validation:

```bash
python -m unittest tests.test_writer_v1_freeze tests.test_writer_compose_001 tests.test_writer_iterative_e2e_hardening tests.test_writer_e2e_hardening tests.test_writer_semantic_handoff -q
PYTHONPATH=scripts/researcher python -m unittest tests.researcher.test_research_planning tests.researcher.test_research_planning_runtime -q
python scripts/router/compile_capability_runtime.py --check
python scripts/router/compile_runtime.py --check
python -m compileall -q scripts/writer scripts/researcher/researcher_core
git diff --check
```
