# Portable Delta — карта переноса v1 → v1.1

Дата: 2026-09-18. Источник: function_index.json (workspace vs portable).

## Сводка
| Контур | Модули base | Модули target | Функции base | Функции target | Модулей нет в target | Функций нет в target |
|---|---|---|---|---|---|---|
| capsules | 8 | 0 | 25 | 0 | 8 | 25 |
| code-factory | 6 | 6 | 47 | 47 | 0 | 0 |
| glossary | 3 | 3 | 6 | 6 | 0 | 0 |
| guard | 4 | 4 | 13 | 13 | 0 | 0 |
| jobs | 1 | 1 | 12 | 12 | 0 | 0 |
| kanban | 1 | 0 | 0 | 0 | 1 | 0 |
| mcp | 11 | 11 | 5 | 5 | 0 | 0 |
| memory | 3 | 0 | 7 | 0 | 3 | 7 |
| orchestration | 5 | 5 | 16 | 16 | 0 | 0 |
| plugin | 3 | 3 | 2 | 2 | 0 | 0 |
| remote_acceptance | 3 | 0 | 5 | 0 | 3 | 5 |
| research | 6 | 0 | 19 | 0 | 6 | 19 |
| researcher | 67 | 64 | 220 | 218 | 3 | 2 |
| router | 12 | 12 | 31 | 31 | 0 | 0 |
| scripts | 8 | 8 | 32 | 31 | 0 | 3 |
| writer | 10 | 0 | 28 | 0 | 10 | 28 |
| writer-core | 40 | 40 | 161 | 161 | 0 | 0 |
| writer_core_handoff | 6 | 0 | 1 | 0 | 6 | 1 |

## Модули, отсутствующие в portable (перенести в v1.1)

### Capsules
- `scripts/capsules/corpus_fts.py`
- `scripts/capsules/document_inspect.py`
- `scripts/capsules/plot_render.py`
- `scripts/capsules/report_compose.py`
- `scripts/capsules/science_compute.py`
- `scripts/capsules/scientific_image_inspect.py`
- `scripts/capsules/search_gateway.py`
- `scripts/capsules/source_resolve.py`

### Kanban
- `references/global-kanban/global_kanban.py`

### Memory
- `scripts/memory/collect_l2.py`
- `scripts/memory/memory_bridge.py`
- `scripts/memory/promote_l2_to_l3.py`

### Remote Acceptance
- `scripts/remote_acceptance/collect_environment.py`
- `scripts/remote_acceptance/opencode_json_worker.py`
- `scripts/remote_acceptance/run_remote_acceptance.py`

### Research
- `scripts/research/formulas.py`
- `scripts/research/judge_brief.py`
- `scripts/research/numeric_comparator.py`
- `scripts/research/synthesizer.py`
- `scripts/research/uncertainty.py`
- `scripts/research/units.py`

### Researcher
- `scripts/researcher/demo_r4_2_evidence_slicing.py`
- `scripts/researcher/demo_research_planning.py`
- `scripts/researcher/verify_claims.py`

### Writer
- `scripts/writer/citation_trace.py`
- `scripts/writer/draft_loop.py`
- `scripts/writer/extractor/__init__.py`
- `scripts/writer/extractor/c5_number.py`
- `scripts/writer/extractor/claim_qa.py`
- `scripts/writer/extractor/context_analyzer.py`
- `scripts/writer/extractor/extraction_engine.py`
- `scripts/writer/extractor/graph_builder.py`
- `scripts/writer/sources/__init__.py`
- `scripts/writer/sources/source_catalog.py`

### Writer Core Handoff
- `scripts/writer_core_handoff/src_skeleton/writer_core_ir/__init__.py`
- `scripts/writer_core_handoff/src_skeleton/writer_core_ir/adaptive_control.py`
- `scripts/writer_core_handoff/src_skeleton/writer_core_ir/linguistics.py`
- `scripts/writer_core_handoff/src_skeleton/writer_core_ir/models.py`
- `scripts/writer_core_handoff/src_skeleton/writer_core_ir/operations.py`
- `scripts/writer_core_handoff/src_skeleton/writer_core_ir/rtt.py`

## Функции, отсутствующие в portable (по контурам)

### Capsules
- `cache_key` — модуль `scripts/capsules/search_gateway.py`
- `crossref` — модуль `scripts/capsules/source_resolve.py`
- `dbopen` — модуль `scripts/capsules/corpus_fts.py`
- `doi_of` — модуль `scripts/capsules/source_resolve.py`
- `equivalent` — модуль `scripts/capsules/science_compute.py`
- `expression` — модуль `scripts/capsules/science_compute.py`
- `index` — модуль `scripts/capsules/corpus_fts.py`
- `inspect_csv` — модуль `scripts/capsules/document_inspect.py`
- `inspect_docx` — модуль `scripts/capsules/document_inspect.py`
- `inspect_pdf` — модуль `scripts/capsules/document_inspect.py`
- `inspect_text` — модуль `scripts/capsules/document_inspect.py`
- `inspect_tiff` — модуль `scripts/capsules/document_inspect.py`
- `inspect_xlsx` — модуль `scripts/capsules/document_inspect.py`
- `iter_segments` — модуль `scripts/capsules/corpus_fts.py`
- `main` — модуль `scripts/capsules/corpus_fts.py`
- `molar_mass` — модуль `scripts/capsules/science_compute.py`
- `norm_query` — модуль `scripts/capsules/search_gateway.py`
- `normalize` — модуль `scripts/capsules/search_gateway.py`
- `openalex` — модуль `scripts/capsules/source_resolve.py`
- `parse_vars` — модуль `scripts/capsules/science_compute.py`
- `search` — модуль `scripts/capsules/corpus_fts.py`
- `sha256_file` — модуль `scripts/capsules/document_inspect.py`
- `solve` — модуль `scripts/capsules/science_compute.py`
- `uncertainty` — модуль `scripts/capsules/science_compute.py`
- `unpaywall` — модуль `scripts/capsules/source_resolve.py`

### Memory
- `cmd_add` — модуль `scripts/memory/memory_bridge.py`
- `cmd_add_file` — модуль `scripts/memory/memory_bridge.py`
- `cmd_search` — модуль `scripts/memory/memory_bridge.py`
- `cmd_stats` — модуль `scripts/memory/memory_bridge.py`
- `collect_l2` — модуль `scripts/memory/collect_l2.py`
- `main` — модуль `scripts/memory/collect_l2.py`
- `promote` — модуль `scripts/memory/promote_l2_to_l3.py`

### Remote Acceptance
- `main` — модуль `scripts/remote_acceptance/collect_environment.py`
- `run` — модуль `scripts/remote_acceptance/collect_environment.py`
- `run_bounded_chain` — модуль `scripts/remote_acceptance/run_remote_acceptance.py`
- `run_prior_only_case` — модуль `scripts/remote_acceptance/run_remote_acceptance.py`
- `sha256` — модуль `scripts/remote_acceptance/collect_environment.py`

### Research
- `build_all_briefs` — модуль `scripts/research/judge_brief.py`
- `build_judge_briefs` — модуль `scripts/research/judge_brief.py`
- `build_report` — модуль `scripts/research/synthesizer.py`
- `compare_claim_sources` — модуль `scripts/research/numeric_comparator.py`
- `compare_qualifiers` — модуль `scripts/research/numeric_comparator.py`
- `compare_ranges` — модуль `scripts/research/numeric_comparator.py`
- `compare_single` — модуль `scripts/research/numeric_comparator.py`
- `compare_value_to_range` — модуль `scripts/research/numeric_comparator.py`
- `compute_stats` — модуль `scripts/research/synthesizer.py`
- `extract_numbers` — модуль `scripts/research/numeric_comparator.py`
- `extract_qualifier` — модуль `scripts/research/numeric_comparator.py`
- `generate_recommendations` — модуль `scripts/research/synthesizer.py`
- `get_source_text` — модуль `scripts/research/numeric_comparator.py`
- `load_sources` — модуль `scripts/research/numeric_comparator.py`
- `load_stats` — модуль `scripts/research/synthesizer.py`
- `load_tribunal_groups` — модуль `scripts/research/synthesizer.py`
- `load_verdicts` — модуль `scripts/research/judge_brief.py`
- `main` — модуль `scripts/research/judge_brief.py`
- `overlay_tribunal` — модуль `scripts/research/synthesizer.py`

### Researcher
- `build_demo` — модуль `scripts/researcher/demo_r4_2_evidence_slicing.py`
- `verify_claim` — модуль `scripts/researcher/verify_claims.py`

### Scripts
- `register_plugin` — модуль `scripts/register_plugin.py`
- `save_json` — модуль `scripts/register_plugin.py`
- `unregister_plugin` — модуль `scripts/register_plugin.py`

### Writer
- `build_graphs` — модуль `scripts/writer/extractor/graph_builder.py`
- `by_path_or_sha` — модуль `scripts/writer/sources/source_catalog.py`
- `classify_claim` — модуль `scripts/writer/extractor/claim_qa.py`
- `connector_clean` — модуль `scripts/writer/extractor/context_analyzer.py`
- `evidence_is_supported` — модуль `scripts/writer/extractor/context_analyzer.py`
- `extract_all` — модуль `scripts/writer/extractor/extraction_engine.py`
- `extract_claims_a` — модуль `scripts/writer/extractor/extraction_engine.py`
- `extract_discourse_c` — модуль `scripts/writer/extractor/extraction_engine.py`
- `extract_from_sentences` — модуль `scripts/writer/extractor/c5_number.py`
- `extract_object_b` — модуль `scripts/writer/extractor/extraction_engine.py`
- `extract_quantities` — модуль `scripts/writer/extractor/c5_number.py`
- `extract_style_d` — модуль `scripts/writer/extractor/extraction_engine.py`
- `get` — модуль `scripts/writer/sources/source_catalog.py`
- `get_context` — модуль `scripts/writer/extractor/context_analyzer.py`
- `has_marker_in_window` — модуль `scripts/writer/extractor/context_analyzer.py`
- `infer_case_from_context` — модуль `scripts/writer/extractor/context_analyzer.py`
- `is_rhetorical_repetition` — модуль `scripts/writer/extractor/context_analyzer.py`
- `list_sources` — модуль `scripts/writer/sources/source_catalog.py`
- `main` — модуль `scripts/writer/citation_trace.py`
- `qa_claims` — модуль `scripts/writer/extractor/claim_qa.py`
- `qa_objects` — модуль `scripts/writer/extractor/claim_qa.py`
- `run` — модуль `scripts/writer/citation_trace.py`
- `span_grounded` — модуль `scripts/writer/extractor/claim_qa.py`
- `span_locate` — модуль `scripts/writer/extractor/claim_qa.py`
- `store_graphs` — модуль `scripts/writer/extractor/graph_builder.py`
- `to_yaml` — модуль `scripts/writer/extractor/claim_qa.py`
- `upsert` — модуль `scripts/writer/sources/source_catalog.py`
- `versions` — модуль `scripts/writer/sources/source_catalog.py`

### Writer Core Handoff
- `build_semantic_mismatch_environment` — модуль `scripts/writer_core_handoff/src_skeleton/writer_core_ir/adaptive_control.py`

## Предупреждения

- контур 'capsules': 8 модулей в base, 0 в target
- контур 'capsules': 25 функций в base, 0 в target
- контур 'kanban': 1 модулей в base, 0 в target
- контур 'memory': 3 модулей в base, 0 в target
- контур 'memory': 7 функций в base, 0 в target
- контур 'remote_acceptance': 3 модулей в base, 0 в target
- контур 'remote_acceptance': 5 функций в base, 0 в target
- контур 'research': 6 модулей в base, 0 в target
- контур 'research': 19 функций в base, 0 в target
- контур 'writer': 10 модулей в base, 0 в target
- контур 'writer': 28 функций в base, 0 в target
- контур 'writer_core_handoff': 6 модулей в base, 0 в target
- контур 'writer_core_handoff': 1 функций в base, 0 в target
