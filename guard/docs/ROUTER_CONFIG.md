# Router Configuration: 171 skills по 15 агентам + routing table

> Конфигурация роутера оркестратора. Факты + опции, решение за пользователем (принцип сервера).
> Дата: 2026-08-26. Всего skills: 171 (18 наших + 30 D1 + 123 D1-max из openscience).

## Источники
- Наши 18: autoresearch, clonedeps, codemap, code-review-and-quality, context-engineering, deepwork, doubt-driven-development, incremental-implementation, interview-me, oh-my-opencode-slim, reflect, rivulet-numeric, simplify, source-driven-development, test-driven-development, using-agent-skills, verification-planning, worktrees
- R2 addyosmani 8: doubt-driven-development, source-driven-development, context-engineering, using-agent-skills, code-review-and-quality, test-driven-development, interview-me, incremental-implementation
- openscience 153: physics(23), chemistry(23), data-engineering(10), writing(10), research(17), coding(14+), databases(23), llm-tools(17), visualization(7), quantum(4), document-parsing(2), biology(3+)

---

## Маппинг по агентам (полный, 171 skills)

### code-orchestrator (роутер + фабрика)
**Роутинг/мета:** using-agent-skills, context-engineering, oh-my-opencode-slim, skill-installer, get-available-resources
**Планирование:** verification-planning, planning-and-task-breakdown (R2 ref в shared/orchestration-patterns.md)
**Параллельная работа:** deepwork, worktrees
**Cost/budget:** (модуль 12-cost-optimization как reference)
**Optimization:** pymoo, multi-objective-optimization

### coder-worker
**Реализация:** incremental-implementation, test-driven-development, feature-forge
**Debug:** debugging-and-error-recovery, systematic-debugging
**Языки:** python-pro, modern-python, typescript-pro, matlab, sympy
**Math/numeric:** sympy, statsmodels, statistical-analysis, networkx, scikit-learn
**Data:** exploratory-data-analysis, pandas-pro, polars, dask, geopandas, vaex, zarr-python, hdf5-pde-data-loading, ray-data, hugging-face-datasets, aeon
**API:** api-and-interface-design, api-designer, fastapi-expert, cli-developer
**Audio:** audiocraft

### code-reviewer
**Review:** code-review-and-quality, differential-review, make-no-mistakes, definition-of-done (ref), review, peer-review
**Static analysis:** semgrep-security-scan, shap (interpretability)
**Verification:** verification-before-completion, verify

### code-tester
**Testing:** test-master, property-based-testing, test-driven-development, testing-patterns (ref), testing-handbook
**Evals:** llm-as-judge-evaluation, exploratory-data-analysis, statistical-analysis
**Web:** browser-testing-with-devtools, webapp-testing, playwright
**Visualization:** matplotlib, plotly, seaborn

### code-auditor (security/guard)
**Security:** secure-code-guardian, security-and-hardening, security-reviewer, security-checklist (ref), sharp-edges, insecure-defaults, fullstack-guardian
**Sandbox:** 08-sandboxes (ref)
**Guard:** llamaguard, constitutional-ai, nemo-guardrails
**Audit:** audit-context-building, variant-analysis, semgrep-rule-creator
**Observability:** observability-and-instrumentation, monitoring-expert, scientific-visualization

### experimenter
**Optimization:** autoresearch, pymoo, multi-objective-optimization, shap, idea-refine, brainstorming, scientific-brainstorming, hypothesis-generation, scientific-problem-selection
**RL:** slime, grpo-rl-training
**Benchmarks:** (модуль 09-evals benchmarks/)

### research-orchestrator
**Workflow:** research-workflows, conducting-scientific-research, research-lookup, perplexity-search
**Planning:** scientific-problem-selection, hypothesis-generation, scientific-brainstorming
**Source audit:** sources, compare, reproduce
**Export:** export, market-research-reports, research-grants

### claim-parser
**Extraction:** interview-me, spec-miner, ask-questions-if-underspecified
**Scientific:** scientific-critical-thinking, scientific-problem-selection

### source-fetcher
**Sources:** source-driven-development, rag-architect, literature-review, citation-management
**Databases (23):** openalex-database, pubmed-database, chembl-database, pubchem-database, pdb-database, uniprot-database, biorxiv-database, kegg-database, fda-database, drugbank-database, cosmic-database, clinvar-database, zinc-database, hmdb-database, reactome-database, string-database, ensembl-database, geo-database, brenda-database, alphafold-database, uspto-database, fred-economic-data, clinicaltrials-database
**RAG:** faiss, chroma, pinecone, qdrant, langchain, llamaindex, sentence-transformers, molecular-rag
**PDF:** pdf
**Search:** perplexity-search, research-lookup

### fact-checker
**Verification:** doubt-driven-development, verify, reproduce, compare, sources, peer-review, scientific-critical-thinking
**Numeric:** numeric_comparator (наш скрипт), rivulet-numeric, statistical-analysis, statsmodels
**Judge:** llm-as-judge-evaluation, second-opinion
**Sources:** source-driven-development

### tribunal-judge
**Adversarial:** doubt-driven-development, second-opinion, the-fool, review, peer-review
**Failures:** (модуль 14-agent-failures + anti-patterns/)
**Critical:** scientific-critical-thinking

### synthesizer
**Synthesis:** documentation-and-adrs, scientific-writing, ml-paper-writing, literature-review, citation-management
**Export:** export, paper-2-web, venue-templates
**Visualization:** scientific-visualization, scientific-schematics, infographics, plotly, seaborn, matplotlib, molecule-visualization, protein-diagram

### writing-orchestrator
**Process:** orchestration-patterns (ref), doc-coauthoring, documentation-and-adrs
**Writing:** scientific-writing, ml-paper-writing, latex-posters, pptx-posters, scientific-slides, paper-2-web, venue-templates
**Style:** (tone-voice-style — создать в D3)

### article-writer
**Prose:** doc-coauthoring, documentation-and-adrs, scientific-writing
**Visual:** infographics, scientific-schematics, hugging-face-paper-publisher
**Style:** (tone-voice-style — D3)

### researcher
**Research:** conducting-scientific-research, research-workflows, hypothesis-generation, scientific-brainstorming, scientific-problem-selection, scientific-critical-thinking
**Data:** pandas-pro, biopython, bioservices, scanpy, networkx, statsmodels, scikit-learn, pymc, umap-learn
**Physics:** pymatgen, spectral-analysis, wave-propagation, dimensional-analysis, statistical-mechanics, physics-fitting, physics-visualization, symbolic-regression, bayesian-inference, ode-solver, pde-solver, physics-databases, fluid-dynamics, fluidsim, hamiltonian-mechanics, dynamical-systems, conservation-law-discovery, neural-operator, pinn-training, shock-capturing-neural-operators, sindy-identification, astropy, autoregressive-neural-pde-solver
**Chemistry:** rdkit, datamol, deepchem, matchms, pyopenms, smiles-validation, molecule-visualization, admet-prediction, admet-reasoning, binding-affinity, denovo-design, diffdock, drug-design, hypogenic, medchem, molecular-docking, molecular-optimization, molfeat, pocket-detection, pytdc, structure-prediction, torchdrug
**Quantum:** cirq, pennylane, qiskit, qutip
**Audio:** audiocraft, whisper
**LLM tools:** langchain, llamaindex, dspy, instructor, outlines, guidance, long-context, transformers, sentence-transformers
**Document:** markitdown, liteparse

### all agents (cross-cutting)
context-engineering (taint loss), long-context, compact (openscience runtime — НО конфликт, не ставить)

---

## Routing table: тип задачи → skills → агенты

### code-orchestrator routing

| Тип задачи (claim) | Активируемые skills | Целевые агенты |
|--|--|--|
| **Новая фича/модуль** | spec-driven-development, planning-and-task-breakdown, incremental-implementation, test-driven-development | coder-worker, code-tester |
| **Bug fix** | systematic-debugging, debugging-and-error-recovery, differential-review | coder-worker, code-reviewer |
| **Security audit/guard** | secure-code-guardian, security-and-hardening, security-checklist, llamaguard, nemo-guardrails | code-auditor |
| **Code review** | code-review-and-quality, differential-review, make-no-mistakes, definition-of-done, peer-review | code-reviewer |
| **Test suite** | test-master, property-based-testing, testing-patterns, llm-as-judge-evaluation, verification-before-completion | code-tester |
| **Optimization (cost/perf)** | pymoo, multi-objective-optimization, autoresearch, shap | experimenter, code-auditor |
| **Рефакторинг** | simplify, code-simplification (skip — dup), incremental-implementation | coder-worker |
| **Мульти-агент** | orchestration-patterns, deepwork, worktrees | code-orchestrator |
| **Документация** | documentation-and-adrs, doc-coauthoring, scientific-writing | article-writer, synthesizer |
| **Production/ship** | shipping-and-launch, before-prod checklist | code-orchestrator |
| **Materials/XRD** | pymatgen, spectral-analysis, physics-fitting, physics-visualization | researcher |
| **Термодинамика** | statistical-mechanics, dimensional-analysis, ode-solver, sympy | researcher |
| **ИК/спектры** | spectral-analysis, matchms, pyopenms, molecule-visualization | researcher |
| **Звук/аккустика** | wave-propagation, spectral-analysis, audiocraft | researcher |
| **Chemistry/molecular** | rdkit, datamol, deepchem, diffdock, molecular-docking | researcher |
| **Big data** | polars, dask, ray-data, vaex, zarr-python, geopandas | coder-worker, researcher |
| **Quantum** | qiskit, pennylane, cirq, qutip | researcher |

### research-orchestrator routing

| Тип задачи | Активируемые skills | Целевые агенты |
|--|--|--|
| **Проверка научного текста** | doubt-driven-development, verify, compare, sources, peer-review, scientific-critical-thinking | claim-parser, fact-checker, tribunal-judge |
| **Поиск источников** | source-driven-development, rag-architect, databases (23), faiss, langchain, perplexity-search | source-fetcher, researcher |
| **Извлечение клаймов** | interview-me, spec-miner, scientific-critical-thinking | claim-parser |
| **Трибунал/вердикт** | doubt-driven-development, second-opinion, the-fool, peer-review, scientific-critical-thinking | tribunal-judge |
| **Синтез отчёта** | scientific-writing, ml-paper-writing, literature-review, citation-management, export | synthesizer |
| **Reproduce/verify** | reproduce, verify, compare, sources | fact-checker, researcher |
| **Гипотезы** | hypothesis-generation, scientific-brainstorming, scientific-problem-selection | research-orchestrator, researcher |
| **Grants/markets** | research-grants, market-research-reports | research-orchestrator |

---

## Конфликты (НЕ активировать)

| Skill | Почему не активировать | Альтернатива |
|--|--|--|
| openscience `other/init` | конфликт с factory init (factory_ctl.py) | наш factory_ctl init |
| `other/plan` | конфликт с planning-and-task-breakdown | R2 planning |
| `other/resume` | конфликт с session resume (наш guard анализ) | — |
| `other/context` | конфликт с context-engineering | R2 context-engineering |
| `other/goal`, `status`, `stop` | openscience runtime, не агентные | — |
| `other/compact`, `checkpoint`, `handoff` | openscience runtime | — |
| `code-simplification` (R2) | полный дубликат нашего simplify | наш simplify |
| `git-worktrees` (R1) | полный дубликат нашего worktrees | наш worktrees |

## Приоритет (наш > заимствован)
При конфликте имени/функции — наш skill приоритет. Заимствованные skills = дополнение, не замена.

## Файл
`/home/orangepi/Документы/doc_guard/docs/ROUTER_CONFIG.md`