# Linguistic IR and Graph Stack

The linguistic subsystem uses multiple linked projections rather than a universal language graph.

## G13 Linguistic Structure Graph
Represents form:
- `DocumentSpan`, `Sentence`, `Clause`, `Token`, `Lexeme`, `Phrase`, `PredicativeCenter`, `Modifier`, `Parenthetical`, `CoordinationGroup`.
- morphology: lemma, POS, case, number, gender, aspect, voice, tense, person.
- syntax: head/dependency relations, clause membership, predication, coordination, subordination, apposition.

## G14 Cohesion and Information-Flow Graph
Represents textual linkage:
- `Mention`, `EntityRef`, `EventRef`, `LexicalChain`, `Theme`, `Rheme`, `Given`, `New`, `CoreferenceHypothesis`.
- edges: `REFERS_TO`, `COREFERS_WITH`, `LEXICALLY_CONTINUES`, `THEME_TO_RHEME`, `INTRODUCES`, `RESUMES`.

The graph explicitly distinguishes cohesion from coherence.

## G15 Pragmatic/Rhetorical Graph
Represents communicative use:
- speech acts: `REPORT`, `ASSERT`, `HEDGE`, `INFER`, `EVALUATE`, `CONTRAST`, `CONCEDE`, `DEFINE`, `RECOMMEND`;
- discourse relations: `ELABORATION`, `CAUSE`, `CONSEQUENCE`, `CONTRAST`, `CONCESSION`, `EXAMPLE`, `GENERALIZATION`, `SPECIFICATION`, `BACKGROUND`, `INTERPRETATION`, `LIMITATION`, `SUMMARY`;
- implicit structures: `PRESUPPOSES`, `IMPLICATES`, `USES_AS_WARRANT`.

## G16 Linguistic Memory Graph
Stores observations about language usage and outcomes:
- `ConstructionCandidate`, `Collocation`, `ValencyPattern`, `AuthorPreference`, `RejectedPattern`, `RepairEpisode`, `StyleProfileRevision`;
- provenance distinguishes `AUTHOR_ORIGINAL`, `AUTHOR_ACCEPTED`, `MODEL_GENERATED`, `EDITOR_INSERTED`, `JOURNAL_REQUIRED`, `REFERENCE_CORPUS`.

## Actionable semantic fields
The IR MUST prioritize distinctions that matter to Writer/RTT:
- predicate and arguments;
- entity/event identity;
- negation and quantifier scope;
- modality/hedging;
- causal force;
- temporal/aspectual meaning;
- conditions and validity scope;
- comparison semantics;
- attribution/source voice;
- discourse relation;
- presuppositions;
- terminology bindings;
- quantity bindings.

The project explicitly rejects the goal of encoding the entire Russian language in a proprietary DSL.
