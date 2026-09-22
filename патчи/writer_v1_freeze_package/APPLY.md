# Apply WRITER-V1-FREEZE-001

Prerequisite: repository already contains the accepted Writer changes through `WRITER-ITERATIVE-CHAPTER-E2E-001` / `WRITER-COMPOSE-001`.

Preferred:

```bash
git am patch/WRITER-V1-FREEZE-001.patch
```

Then run:

```bash
python -m unittest discover -s tests -p 'test*.py' -q
python scripts/router/compile_capability_runtime.py --check
python scripts/router/compile_runtime.py --check
python -m compileall -q scripts/writer scripts/researcher/verify_claims.py
git diff --check
```

Expected test result for this snapshot: `117/117 PASS`.
Expected capability policy hash: `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`.
Expected base runtime policy hash: `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`.

This patch freezes Writer v1 public contracts for Researcher integration. Do not reintroduce direct web/provider access into prose Writer agents.
