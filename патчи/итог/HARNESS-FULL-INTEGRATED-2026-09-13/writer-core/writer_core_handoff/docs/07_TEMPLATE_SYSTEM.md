# 07. Template System

## 1. Template != prompt

Template is a versioned executable specification.

Required fields:

```yaml
id:
version:
kind:
preconditions:
slots:
relations:
constraints:
postconditions:
metrics:
```

## 2. Template families

- `DocumentTemplate`
- `SectionTemplate`
- `DiscoursePattern`
- `ArgumentScheme`
- `EvidencePattern`
- `RealizationPattern`
- `ArtifactTemplate`
- `CitationTemplate`
- `RepairTemplate`
- `ValidationProfile`
- `ExportTemplate`

## 3. Reference learning boundary

Corpus text is not a template.

```text
reference text
 -> structural/argument abstraction
 -> candidate pattern
 -> evaluation
 -> promoted template
```

Style is extracted separately into `StyleProfile`.

## 4. Template selection

Selection inputs:

```text
discourse intent
claim kinds
argument need
genre/domain/risk policy
artifact requirements
budget
```

Output is `TemplateInstantiation`, containing filled slot IDs and the exact template version.

## 5. Template promotion lifecycle

```text
CANDIDATE -> SHADOW -> EVALUATED -> PROMOTED -> DEPRECATED
```

LLM self-rating alone cannot promote a template.
