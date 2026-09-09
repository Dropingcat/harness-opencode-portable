# OSINT 03. Confounder Graph

Observed style may be caused by Author, Topic, Genre, Journal, Language, Institution, Template, Editor, Coauthor, Software, LLM or Time.

The forensic engine must model these as competing explanations. No author score is admissible without reporting corpus balance and major confounders.

Controls:
- cross-topic evaluation;
- cross-genre evaluation;
- time-split evaluation;
- leave-one-journal/template-out;
- coauthor-aware splits;
- OOD detection.
