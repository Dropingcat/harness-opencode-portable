# OSINT 02. Fingerprint Feature Ontology

Separate feature spaces:
1. lexical: function words, char n-grams, punctuation, rare choices;
2. syntactic: dependency depth, clauses, passive/relative/coordination patterns;
3. discourse: paragraph topology, move order, transitions, limitation placement;
4. epistemic/argument: qualification habits, evidence density, causal language, rebuttal behavior;
5. citation: age, source classes, placement, neighborhoods, self-citation patterns;
6. artifact/format: figure/table typography, decimals, captions, equations, software/export signatures;
7. temporal/process: style drift, coauthor/editor regimes, tooling transitions;
8. code (optional): formatting, identifier patterns, API idioms, AST metrics.

Each feature stores extraction method/version, confidence/quality, domain/genre/language scope and normalization.
