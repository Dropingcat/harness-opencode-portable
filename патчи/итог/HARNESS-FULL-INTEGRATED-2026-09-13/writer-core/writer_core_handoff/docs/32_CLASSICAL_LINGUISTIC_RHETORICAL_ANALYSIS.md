# Classical Linguistic and Rhetorical Analysis

This layer repurposes mature linguistic/literary analysis as actionable Writer tools rather than decorative terminology.

## Lexicology / semasiology
Track term status, polysemy, register, sense, synonym/antonym relations, collocational restrictions and domain specificity. `Lexeme -> Sense -> Concept` is explicit.

## Syntax
Beyond dependency parsing, represent predicative centers, clause hierarchy, coordination, detached constructions, parentheticals and distance between main subject/predicate. Long genitive chains and excessive nominalization are signals, not automatic errors.

## Actual division / information structure
Model `THEME -> RHEME`, `GIVEN/ACCESSIBLE/NEW`, linear thematic progression, constant-theme progression, derived themes and thematic jumps.

## Text linguistics
Separate:
- lexical cohesion: repetition, synonymy, hypernymy, lexical chains;
- grammatical cohesion: pronouns, demonstratives, ellipsis, conjunctions;
- coherence: causal/topic/argument/conceptual continuity.

## Pragmatics
Represent communicative acts, author/source attribution, presupposition, implicature and deixis. A presupposition that introduces an unsupported fact is a first-class issue.

## Metadiscourse
Track transitions, frame markers, endophoric markers, evidentials, hedges, boosters, attitude markers and engagement markers.

## Rhetorical schemes
First-class patterns include:
- claim -> evidence -> interpretation -> limitation;
- problem -> analysis -> solution;
- thesis -> counterclaim -> synthesis;
- definition -> example -> boundary;
- comparison/contrast;
- concession;
- reformulation;
- exemplification;
- classification;
- cause/effect.

## Academic chreia
Chreia is treated as a controlled expansion algorithm, not mandatory antique ornament:
`Claim -> Explication -> Evidence -> Mechanism/Reason -> Counterposition -> Comparison/Example -> Boundary/Qualifier -> Synthesis`.
Steps are optional/configurable by genre and evidence availability.

## Enthymeme / missing warrant
Argument analyzer MAY propose an implicit warrant. If that warrant is absent from admissible knowledge, create `MISSING_WARRANT`; never silently invent it.

## Tropes and figures
Figures are classified by function: parallelism, antithesis, enumeration, gradation, concession, correction, reformulation. Tropes such as analogy or metaphor are permitted as explanatory devices but MUST NOT become evidence. Hyperbolic boosters are high-risk in academic profiles.
