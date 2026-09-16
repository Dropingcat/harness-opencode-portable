"""R3 deterministic admission, structure, and writer-gate validators.

Each validator is small, versioned, side-effect free, and inspects only
snapshot-like inputs. Admission/shape validators return ``ValidationOutcome``;
gap/conflict/risk builders return deterministic derived descriptors.
"""

from __future__ import annotations

from collections import defaultdict
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from researcher_core.r0.enums import ValidationResult, WriterEligibility
from researcher_core.r0.ids import EntityId


_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ALLOWED_SOURCE_TYPES = frozenset(
    {"journal_article", "book", "report", "dataset", "web", "patent", "preprint", "other"}
)
_COMPOSITE_PATTERNS = (
    ("и", re.compile(r"\bи\b")),
    ("также", re.compile(r"\bтакже\b")),
    ("однако", re.compile(r"\bоднако\b")),
    ("причём", re.compile(r"\bприч(?:е|ё)м\b")),
    ("кроме того", re.compile(r"\bкроме\s+того\b")),
    ("and", re.compile(r"\band\b")),
    ("also", re.compile(r"\balso\b")),
    ("however", re.compile(r"\bhowever\b")),
)
_RATIO_PROPERTIES = frozenset({"efficiency", "accuracy", "concentration", "rate"})
_SCOPE_MATCHES = frozenset({"MATCH", "PARTIAL", "MAJOR_SHIFT", "DISJOINT", "UNKNOWN"})
_SHORT_NAMESPACE_ALIASES = {
    "A": "ASM",
    "AS": "ASM",
    "C": "CLM",
    "CF": "CNF",
    "D": "DRV",
    "E": "EVD",
    "EDG": "EDG",
    "EDGE": "EDG",
    "G": "GAP",
    "Q": "QTY",
    "R": "REC",
    "S": "SRC",
    "SC": "SCP",
}
_ALLOWED_EDGE_RELATIONS = frozenset(
    {
        "PRODUCED",
        "SUPPORTS",
        "PARTIALLY_SUPPORTS",
        "CONTRADICTS",
        "BACKGROUNDS",
        "DERIVED_FROM",
        "ASSUMES",
        "GENERALIZES",
        "EXTRAPOLATES_FROM",
        "CAUSES",
        "CORRELATES_WITH",
        "JUSTIFIES",
        "DEPENDS_ON",
        "BLOCKS",
        "CREATES_GAP",
        "RESOLVES",
        "INCLUDED_IN",
        "CHANGED_STATUS_OF",
        "TRIGGERED",
        "SUPERSEDES",
        "HAS_GAP",
        "IN_CONFLICT",
        "QUANTIFIES",
    }
)
_SUPPORT_RELATIONS = frozenset({"SUPPORTS", "PARTIALLY_SUPPORTS", "CONTRADICTS", "BACKGROUNDS", "JUSTIFIES"})
_POSITIVE_RELATIONS = frozenset({"SUPPORTS", "PARTIALLY_SUPPORTS"})
_CONTRADICT_RELATIONS = frozenset({"CONTRADICTS"})
_CYCLE_RELATIONS = frozenset(
    {
        "DERIVED_FROM",
        "ASSUMES",
        "GENERALIZES",
        "EXTRAPOLATES_FROM",
        "CAUSES",
        "CORRELATES_WITH",
        "DEPENDS_ON",
        "BLOCKS",
        "CREATES_GAP",
        "RESOLVES",
        "INCLUDED_IN",
        "CHANGED_STATUS_OF",
        "TRIGGERED",
        "SUPERSEDES",
        "HAS_GAP",
        "IN_CONFLICT",
        "QUANTIFIES",
    }
)
_WEAK_DIRECTNESS = frozenset({"INDIRECT", "PARTIAL"})
_WEAK_EDGE_STATUSES = frozenset({"WEAK", "INDIRECT", "PARTIAL"})
_RELATION_ENDPOINTS = {
    "SUPPORTS": (frozenset({"EVD", "CLM", "QTY", "SRC"}), frozenset({"CLM", "REC", "ASM", "QTY"})),
    "PRODUCED": (frozenset({"EVD", "CLM", "QTY", "SRC", "ASM", "DRV"}), frozenset({"CLM", "REC", "ASM", "QTY", "EVD"})),
    "PARTIALLY_SUPPORTS": (frozenset({"EVD", "CLM", "QTY", "SRC"}), frozenset({"CLM", "REC", "ASM", "QTY"})),
    "CONTRADICTS": (frozenset({"EVD", "CLM", "QTY", "SRC"}), frozenset({"CLM", "REC", "ASM", "QTY"})),
    "BACKGROUNDS": (frozenset({"EVD", "CLM", "SRC"}), frozenset({"CLM", "REC", "ASM", "QTY"})),
    "JUSTIFIES": (frozenset({"EVD", "CLM", "ASM"}), frozenset({"CLM", "REC"})),
    "DERIVED_FROM": (frozenset({"CLM", "QTY", "ASM"}), frozenset({"CLM", "REC", "QTY"})),
    "ASSUMES": (frozenset({"ASM", "CLM"}), frozenset({"CLM", "REC", "DRV", "QTY"})),
    "GENERALIZES": (frozenset({"CLM", "QTY"}), frozenset({"CLM", "REC", "QTY"})),
    "EXTRAPOLATES_FROM": (frozenset({"CLM", "QTY"}), frozenset({"CLM", "REC", "QTY"})),
    "CAUSES": (frozenset({"CLM"}), frozenset({"CLM"})),
    "CORRELATES_WITH": (frozenset({"CLM", "QTY"}), frozenset({"CLM", "QTY"})),
    "DEPENDS_ON": (frozenset({"CLM", "REC", "QTY"}), frozenset({"CLM", "ASM", "QTY", "GAP"})),
    "BLOCKS": (frozenset({"GAP", "CNF"}), frozenset({"CLM", "REC", "DRV", "QTY", "GAP"})),
    "CREATES_GAP": (frozenset({"CLM", "QTY", "DRV", "ASM"}), frozenset({"GAP"})),
    "RESOLVES": (frozenset({"CLM", "EVD", "QTY", "DRV"}), frozenset({"GAP", "CNF"})),
    "INCLUDED_IN": (frozenset({"CLM", "QTY", "REC", "GAP"}), frozenset({"SCP", "CLM", "REC"})),
    "CHANGED_STATUS_OF": (frozenset({"EVT", "CNF", "GAP"}), frozenset({"CLM", "REC", "QTY"})),
    "TRIGGERED": (frozenset({"EVT", "GAP", "CNF"}), frozenset({"OPR", "QST", "CLM", "REC"})),
    "SUPERSEDES": (frozenset({"CLM", "REC", "SRC"}), frozenset({"CLM", "REC", "SRC"})),
    "HAS_GAP": (frozenset({"CLM", "REC"}), frozenset({"GAP"})),
    "IN_CONFLICT": (frozenset({"CNF"}), frozenset({"CLM", "REC"})),
    "QUANTIFIES": (frozenset({"QTY"}), frozenset({"CLM"})),
}


@dataclass(frozen=True, slots=True)
class GapDescriptor:
    gap_type: str
    target_ids: tuple[str, ...]
    severity: str
    blocks: tuple[str, ...] = ()
    resolution_requirements: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConflictDescriptor:
    conflict_type: str
    member_ids: tuple[str, ...]
    severity: str
    blocks: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StructuralRiskReport:
    result: ValidationResult
    reason_codes: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    fan_out: int = 0
    weak_bridge_count: int = 0
    unsupported_assumption_count: int = 0
    blocked_recommendation_count: int = 0
    score: int = 0


@dataclass(frozen=True, slots=True)
class RecommendationDecision:
    eligibility: WriterEligibility
    reason_codes: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    result: ValidationResult
    reason_codes: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()


def _is_hex64(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX64_RE.match(value))


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _collapsed_text(value: Any) -> str:
    text = _clean_text(value)
    return " ".join(text.lower().split()) if text else ""


def _normalized_token(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        value = getattr(value, "value")
    text = " ".join(str(value).strip().replace("-", "_").split())
    if not text:
        return None
    return text.replace(" ", "_").upper()


def _mapping_get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, (list, set, frozenset)):
        return tuple(value)
    return ()


def _entity_ref(value: Any) -> str | None:
    if isinstance(value, EntityId):
        return str(value)
    raw = getattr(value, "value", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalize_namespace(namespace: str | None) -> str | None:
    if namespace is None:
        return None
    return _SHORT_NAMESPACE_ALIASES.get(namespace.upper(), namespace.upper())


def _entity_namespace(value: Any) -> str | None:
    if isinstance(value, EntityId):
        return value.namespace
    namespace = getattr(value, "namespace", None)
    if isinstance(namespace, str) and namespace.strip():
        return _normalize_namespace(namespace.strip())
    ref = _entity_ref(value)
    if ref is None:
        return None
    if "_" in ref:
        return _normalize_namespace(ref.split("_", 1)[0])
    match = re.match(r"^[A-Za-z]+", ref)
    return _normalize_namespace(match.group(0)) if match else None


def _scope_match(subject: Any) -> str | None:
    value = _mapping_get(subject, "scope_match", None)
    if value is None:
        value = _mapping_get(_edge_metadata(subject), "scope_match", None)
    return _normalized_token(value)


def _directness(subject: Any) -> str | None:
    value = _mapping_get(subject, "directness", None)
    if value is None:
        value = _mapping_get(_edge_metadata(subject), "directness", None)
    return _normalized_token(value)


def _edge_metadata(edge: Any) -> dict[str, Any]:
    for field_name in ("metadata", "attributes", "proposed_metadata"):
        value = _mapping_get(edge, field_name, None)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _edge_source(edge: Any) -> str | None:
    for field_name in ("source_id", "from", "source_entity"):
        ref = _entity_ref(_mapping_get(edge, field_name, None))
        if ref is not None:
            return ref
    return None


def _edge_target(edge: Any) -> str | None:
    for field_name in ("target_id", "to", "target_entity"):
        ref = _entity_ref(_mapping_get(edge, field_name, None))
        if ref is not None:
            return ref
    return None


def _edge_relation(edge: Any) -> str | None:
    relation = _mapping_get(edge, "relation", None)
    if relation is None:
        relation = _mapping_get(edge, "proposed_relation_type", None)
    if relation is None:
        relation = _mapping_get(edge, "edge_kind", None)
    return _normalized_token(relation)


def _snapshot_items(snapshot: Any, *field_names: str) -> tuple[Any, ...]:
    for field_name in field_names:
        value = _mapping_get(snapshot, field_name, None)
        if value is None:
            continue
        if isinstance(value, Mapping):
            return tuple(value.values())
        seq = _sequence(value)
        if seq:
            return seq
    return ()


def _stringify_refs(values: tuple[Any, ...]) -> tuple[str, ...]:
    refs: list[str] = []
    for value in values:
        ref = _entity_ref(value)
        if ref is not None:
            refs.append(ref)
    return tuple(refs)


def _blocked_refs(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        refs: list[str] = []
        for nested in value.values():
            refs.extend(_stringify_refs(_sequence(nested)))
        return tuple(refs)
    return _stringify_refs(_sequence(value))


def _writer_eligibility(value: Any) -> WriterEligibility | None:
    if isinstance(value, WriterEligibility):
        return value
    token = _normalized_token(value)
    if token is None:
        return None
    try:
        return WriterEligibility[token]
    except KeyError:
        return None


class SourceAdmissionValidator:
    """Whether a document is an admissible source (identity + type + hash shape)."""

    version = "source-admission/1.1"

    def evaluate(self, source: Any) -> ValidationOutcome:
        if source is None:
            raise TypeError("expected a Source object, got None")
        title = _clean_text(getattr(source, "title", None))
        locator = _clean_text(getattr(source, "locator", None))
        source_type = getattr(source, "source_type", None)
        content_hash = getattr(source, "content_hash", None)

        reason_codes: list[str] = []
        findings: list[str] = []

        if not title:
            reason_codes.append("source:no_identity")
            findings.append("source.title is empty")
        if not locator:
            reason_codes.append("source:no_locator")
            findings.append("source.locator is empty")
        if source_type not in _ALLOWED_SOURCE_TYPES:
            reason_codes.append("source:unknown_type")
            findings.append(f"source.source_type {source_type!r} is not in allowed set")
        if content_hash is not None and not _is_hex64(content_hash):
            reason_codes.append("source:bad_hash")
            findings.append("source.content_hash must be a 64-character hex string")

        if reason_codes:
            return ValidationOutcome(ValidationResult.FAIL, tuple(reason_codes), tuple(findings))
        return ValidationOutcome(ValidationResult.PASS)


class EvidenceAdmissionValidator:
    """Whether a specific span is an admissible evidence for a claim."""

    version = "evidence-admission/1.1"

    def evaluate(self, evidence: Any) -> ValidationOutcome:
        if evidence is None:
            raise TypeError("expected an EvidenceSpan object, got None")
        exact_text = _clean_text(getattr(evidence, "exact_text", None))
        locator = _clean_text(getattr(evidence, "locator", None))
        text_hash = getattr(evidence, "text_hash", None)
        source_id = getattr(evidence, "source_id", None)
        allow_title = getattr(evidence, "allow_title", False) is True

        reason_codes: list[str] = []
        findings: list[str] = []

        if not exact_text:
            reason_codes.append("evidence:no_text")
            findings.append("evidence.exact_text is empty")
        if not locator:
            reason_codes.append("evidence:no_locator")
            findings.append("evidence.locator is empty")
        if not _is_hex64(text_hash):
            reason_codes.append("evidence:bad_hash")
            findings.append("evidence.text_hash must be a 64-character hex string")
        source_ns = _entity_namespace(source_id)
        if source_ns != "SRC":
            reason_codes.append("evidence:bad_source")
            findings.append("evidence.source_id must use SRC namespace")

        # span must not be just title/abstract unless explicitly allowed
        title_only = getattr(evidence, "is_title_only", False)
        if title_only and not allow_title:
            reason_codes.append("evidence:title_only")
            findings.append("evidence is title-only and allow_title is not set")

        if reason_codes:
            return ValidationOutcome(ValidationResult.FAIL, tuple(reason_codes), tuple(findings))
        return ValidationOutcome(ValidationResult.PASS)


class AtomicityValidator:
    """Whether a claim proposition is atomic rather than composite."""

    version = "atomicity/1.1"

    def evaluate(self, claim: Any) -> ValidationOutcome:
        if claim is None:
            raise TypeError("expected a Claim object, got None")
        proposition = getattr(claim, "proposition", None)
        if not _clean_text(proposition):
            return ValidationOutcome(ValidationResult.FAIL, ("atomicity:empty",), ("claim.proposition is empty",))

        haystack = _collapsed_text(getattr(claim, "normalized_proposition", None) or proposition)
        for marker, pattern in _COMPOSITE_PATTERNS:
            if pattern.search(haystack):
                return ValidationOutcome(
                    ValidationResult.FAIL,
                    ("atomicity:suspect_composite",),
                    (f"proposition contains composite marker {marker!r}",),
                )
        return ValidationOutcome(ValidationResult.PASS)


class NumericValidator:
    """Whether a Quantity is well-formed; warns on missing provenance."""

    version = "numeric/1.1"

    def evaluate(self, quantity: Any) -> ValidationOutcome:
        if quantity is None:
            raise TypeError("expected a Quantity object, got None")
        value = getattr(quantity, "value", None)
        unit = getattr(quantity, "unit", None)
        measured_property = getattr(quantity, "measured_property", None)

        reason_codes: list[str] = []
        findings: list[str] = []

        if not isinstance(value, Decimal):
            reason_codes.append("numeric:bad_value")
            findings.append("quantity.value must be a Decimal")

        # normalize unit/property (strip whitespace) before emptiness/ratio checks
        norm_unit = _collapsed_text(unit)
        norm_property = _collapsed_text(measured_property)

        if not norm_unit:
            reason_codes.append("numeric:no_unit")
            findings.append("quantity.unit is empty")
        if not norm_property:
            reason_codes.append("numeric:no_property")
            findings.append("quantity.measured_property is empty")

        if value is not None and isinstance(value, Decimal) and norm_property in _RATIO_PROPERTIES and value < 0:
            reason_codes.append("numeric:negative_ratio")
            findings.append("ratio property must not be negative")

        if reason_codes:
            return ValidationOutcome(ValidationResult.FAIL, tuple(reason_codes), tuple(findings))

        provenance = getattr(quantity, "provenance_evidence_id", None)
        if provenance is None:
            provenance_block = _mapping_get(quantity, "provenance", None)
            evidence_refs = _sequence(_mapping_get(provenance_block, "evidence_refs", ()))
            provenance = evidence_refs[0] if evidence_refs else None
        if provenance is None or (isinstance(provenance, str) and not provenance.strip()):
            return ValidationOutcome(ValidationResult.WARN, ("numeric:missing_provenance",), ("no provenance_evidence_id set",))
        if _entity_namespace(provenance) != "EVD":
            return ValidationOutcome(
                ValidationResult.WARN,
                ("numeric:bad_provenance",),
                ("provenance_evidence_id must use EVD namespace",),
            )
        return ValidationOutcome(ValidationResult.PASS)


class ScopeValidator:
    """Whether a relation/claim scope match is admissible for writer/runtime use."""

    version = "scope/1.0"

    def evaluate(self, subject: Any) -> ValidationOutcome:
        if subject is None:
            raise TypeError("expected a scoped object, got None")
        scope_match = _scope_match(subject)
        if scope_match is None:
            return ValidationOutcome(ValidationResult.FAIL, ("scope:no_scope_match",), ("scope_match is missing",))
        if scope_match not in _SCOPE_MATCHES:
            return ValidationOutcome(
                ValidationResult.FAIL,
                ("scope:unknown_scope_match",),
                (f"scope_match {scope_match!r} is not supported",),
            )
        if scope_match == "MATCH":
            return ValidationOutcome(ValidationResult.PASS)
        if scope_match == "PARTIAL":
            return ValidationOutcome(ValidationResult.WARN, ("scope:partial",), ("scope match is partial",))
        if scope_match == "UNKNOWN":
            return ValidationOutcome(ValidationResult.WARN, ("scope:unknown",), ("scope match is unknown",))
        if scope_match == "MAJOR_SHIFT":
            return ValidationOutcome(ValidationResult.FAIL, ("scope:major_shift",), ("scope match is a major shift",))
        return ValidationOutcome(ValidationResult.FAIL, ("scope:disjoint",), ("scope match is disjoint",))


class EdgeValidator:
    """Whether an edge proposal/relation has a supported shape and endpoint pairing."""

    version = "edge/1.0"

    def evaluate(self, edge: Any) -> ValidationOutcome:
        if edge is None:
            raise TypeError("expected an edge-like object, got None")

        source_ref = _edge_source(edge)
        target_ref = _edge_target(edge)
        relation = _edge_relation(edge)
        reason_codes: list[str] = []
        findings: list[str] = []

        if source_ref is None:
            reason_codes.append("edge:no_source")
            findings.append("edge source is missing")
        if target_ref is None:
            reason_codes.append("edge:no_target")
            findings.append("edge target is missing")
        if relation is None:
            reason_codes.append("edge:no_relation")
            findings.append("edge relation is missing")
        elif relation not in _ALLOWED_EDGE_RELATIONS:
            reason_codes.append("edge:unknown_relation")
            findings.append(f"edge relation {relation!r} is not supported")

        if source_ref is not None and target_ref is not None and source_ref == target_ref:
            reason_codes.append("edge:self_loop")
            findings.append("edge source and target must differ")

        if relation in _ALLOWED_EDGE_RELATIONS and source_ref is not None and target_ref is not None:
            endpoints = _RELATION_ENDPOINTS.get(relation)
            if endpoints is None:
                reason_codes.append("edge:unvalidated_endpoints")
                findings.append(f"relation {relation!r} has no endpoint pairing policy")
            else:
                allowed_sources, allowed_targets = endpoints
                source_ns = _entity_namespace(source_ref)
                target_ns = _entity_namespace(target_ref)
                if source_ns not in allowed_sources or target_ns not in allowed_targets:
                    reason_codes.append("edge:unsupported_endpoints")
                    findings.append(
                        f"relation {relation!r} does not support endpoints {source_ns!r}->{target_ns!r}"
                    )

        if relation in _SUPPORT_RELATIONS:
            if _directness(edge) is None:
                reason_codes.append("edge:missing_directness")
                findings.append("support/contradiction edges require directness metadata")
            scope_outcome = ScopeValidator().evaluate(edge)
            if scope_outcome.result is ValidationResult.FAIL:
                reason_codes.append("edge:bad_scope")
                findings.extend(scope_outcome.findings)
            elif scope_outcome.result is ValidationResult.WARN:
                if "edge:qualified_scope" not in reason_codes:
                    reason_codes.append("edge:qualified_scope")
                findings.extend(scope_outcome.findings)

        if any(code.startswith("edge:") and code not in {"edge:qualified_scope"} for code in reason_codes):
            return ValidationOutcome(ValidationResult.FAIL, tuple(reason_codes), tuple(findings))
        if reason_codes:
            return ValidationOutcome(ValidationResult.WARN, tuple(reason_codes), tuple(findings))
        return ValidationOutcome(ValidationResult.PASS)


class GraphCycleValidator:
    """Whether the structural graph contains a directed cycle in dependency-like edges."""

    version = "graph-cycle/1.0"

    def evaluate(self, graph: Any) -> ValidationOutcome:
        if graph is None:
            raise TypeError("expected a graph snapshot, got None")

        adjacency: dict[str, list[str]] = defaultdict(list)
        for index, edge in enumerate(
            _snapshot_items(graph, "edges", "graph_edges", "relations") or _sequence(graph)
        ):
            relation = _edge_relation(edge)
            if relation not in _CYCLE_RELATIONS:
                continue
            source_ref = _edge_source(edge)
            target_ref = _edge_target(edge)
            if source_ref is None or target_ref is None:
                return ValidationOutcome(
                    ValidationResult.FAIL,
                    ("graph:bad_edge",),
                    (f"cycle edge at index {index} is missing source or target",),
                )
            adjacency[source_ref].append(target_ref)

        visited: set[str] = set()
        stack: list[str] = []
        active: set[str] = set()

        def visit(node: str) -> tuple[str, ...] | None:
            visited.add(node)
            active.add(node)
            stack.append(node)
            for neighbour in adjacency.get(node, []):
                if neighbour not in visited:
                    cycle = visit(neighbour)
                    if cycle is not None:
                        return cycle
                elif neighbour in active:
                    start = stack.index(neighbour)
                    return tuple(stack[start:] + [neighbour])
            active.remove(node)
            stack.pop()
            return None

        for node in tuple(adjacency):
            if node not in visited:
                cycle = visit(node)
                if cycle is not None:
                    return ValidationOutcome(
                        ValidationResult.FAIL,
                        ("graph:cycle",),
                        ("cycle detected: " + " -> ".join(cycle),),
                    )
        return ValidationOutcome(ValidationResult.PASS)


class GapBuilder:
    """Deterministically derives open gap descriptors from quantities/derivations."""

    version = "gap-builder/1.0"

    def evaluate(self, snapshot: Any) -> tuple[GapDescriptor, ...]:
        if snapshot is None:
            raise TypeError("expected a snapshot, got None")

        gaps: dict[tuple[str, tuple[str, ...]], GapDescriptor] = {}

        def add_gap(
            gap_type: str,
            target_ids: tuple[str, ...],
            severity: str,
            blocks: tuple[str, ...],
            resolution_requirements: tuple[str, ...],
            reason_codes: tuple[str, ...],
        ) -> None:
            key = (gap_type, target_ids)
            if key not in gaps:
                gaps[key] = GapDescriptor(gap_type, target_ids, severity, blocks, resolution_requirements, reason_codes)

        for quantity in _snapshot_items(snapshot, "quantities"):
            provenance = _mapping_get(quantity, "provenance", None)
            provenance_state = _normalized_token(_mapping_get(provenance, "provenance_state", None))
            evidence_refs = _stringify_refs(_sequence(_mapping_get(provenance, "evidence_refs", ())))
            direct_provenance = _entity_ref(_mapping_get(quantity, "provenance_evidence_id", None))
            target = _entity_ref(_mapping_get(quantity, "id", None)) or _entity_ref(_mapping_get(quantity, "attached_to", None))
            target_ids = (target or "quantity",)
            if provenance_state == "MISSING_DIRECT_EVIDENCE" or (direct_provenance is None and not evidence_refs):
                add_gap(
                    "NUMERIC_PROVENANCE_MISSING",
                    target_ids,
                    "high",
                    (),
                    ("evidence_span_with_same_metric_and_scope",),
                    ("NUMERIC_PROVENANCE_MISSING",),
                )

        for derivation in _snapshot_items(snapshot, "derivations"):
            states = _mapping_get(derivation, "states", None)
            arithmetic_status = _normalized_token(_mapping_get(states, "arithmetic_status", None) or _mapping_get(derivation, "arithmetic_status", None))
            epistemic_status = _normalized_token(_mapping_get(states, "epistemic_status", None) or _mapping_get(derivation, "epistemic_status", None))
            target_ids = _stringify_refs(
                (
                    _mapping_get(derivation, "output_claim_id", None),
                    _mapping_get(derivation, "output_claim", None),
                )
            ) + _stringify_refs(_sequence(_mapping_get(derivation, "output_quantities", ())))
            if not target_ids:
                target_ids = (_entity_ref(_mapping_get(derivation, "id", None)) or "derivation",)

            if arithmetic_status in {"NON_CANONICAL_RANGE_TRANSFORM", "NOT_REPRODUCIBLE", "DERIVED_NOT_REPRODUCIBLE"}:
                add_gap(
                    "DERIVATION_NOT_REPRODUCIBLE",
                    target_ids,
                    "high",
                    (),
                    ("reproducible_formula_or_remove_claim",),
                    ("DERIVATION_NOT_REPRODUCIBLE",),
                )
            if epistemic_status in {"UNJUSTIFIED_ASSUMPTION", "UNSUPPORTED_ASSUMPTION", "DERIVED_WITH_UNJUSTIFIED_ASSUMPTION"}:
                add_gap(
                    "UNSUPPORTED_ASSUMPTION",
                    target_ids,
                    "high",
                    (),
                    ("primary_evidence_or_remove_assumption",),
                    ("UNSUPPORTED_ASSUMPTION",),
                )

        return tuple(gaps.values())


class ConflictBuilder:
    """Deterministically derives conflict descriptors from graph relations/claim snapshots."""

    version = "conflict-builder/1.0"

    def evaluate(self, snapshot: Any) -> tuple[ConflictDescriptor, ...]:
        if snapshot is None:
            raise TypeError("expected a snapshot, got None")

        conflicts: list[ConflictDescriptor] = []
        polarity_by_target: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"positive": set(), "negative": set()})
        for edge in _snapshot_items(snapshot, "edges", "graph_edges", "relations"):
            relation = _edge_relation(edge)
            target_ref = _edge_target(edge)
            source_ref = _edge_source(edge)
            if relation is None or target_ref is None or source_ref is None:
                continue
            if relation in _POSITIVE_RELATIONS:
                polarity_by_target[target_ref]["positive"].add(source_ref)
            elif relation in _CONTRADICT_RELATIONS:
                polarity_by_target[target_ref]["negative"].add(source_ref)

        for target_ref, groups in polarity_by_target.items():
            if groups["positive"] and groups["negative"]:
                member_ids = tuple(sorted(groups["positive"] | groups["negative"] | {target_ref}))
                conflicts.append(
                    ConflictDescriptor(
                        "EVIDENCE_POLARITY_CONFLICT",
                        member_ids,
                        "high",
                        (target_ref,),
                        ("EVIDENCE_POLARITY_CONFLICT",),
                    )
                )

        for claim in _snapshot_items(snapshot, "claims"):
            hypotheses = tuple(str(item) for item in _sequence(_mapping_get(claim, "diagnostic_hypotheses", ())))
            collapsed = bool(_mapping_get(claim, "collapsed_to_single_cause", False)) or bool(
                _mapping_get(claim, "selected_hypothesis", None)
            )
            if len(hypotheses) > 1 and collapsed:
                claim_ref = _entity_ref(_mapping_get(claim, "id", None)) or "claim"
                conflicts.append(
                    ConflictDescriptor(
                        "DIAGNOSTIC_COLLAPSE",
                        (claim_ref,),
                        "high",
                        (claim_ref,),
                        ("MULTIPLE_DIAGNOSTIC_HYPOTHESES_COLLAPSED_TO_ONE",),
                    )
                )

        return tuple(conflicts)


class StructuralRiskAnalyzer:
    """Computes deterministic structural-risk factors for a snapshot."""

    version = "structural-risk/1.0"

    def evaluate(self, snapshot: Any) -> StructuralRiskReport:
        if snapshot is None:
            raise TypeError("expected a snapshot, got None")

        outgoing_counts: dict[str, int] = defaultdict(int)
        weak_bridge_count = 0
        for edge in _snapshot_items(snapshot, "edges", "graph_edges", "relations"):
            source_ref = _edge_source(edge)
            if source_ref is not None:
                outgoing_counts[source_ref] += 1
            status = _normalized_token(_mapping_get(edge, "status", None))
            if status in _WEAK_EDGE_STATUSES or _directness(edge) in _WEAK_DIRECTNESS:
                weak_bridge_count += 1

        gaps = _snapshot_items(snapshot, "gaps")
        unsupported_assumption_count = sum(
            1 for gap in gaps if _normalized_token(_mapping_get(gap, "gap_type", None)) == "UNSUPPORTED_ASSUMPTION"
        )

        blocked_recommendations: set[str] = set()
        for gap in gaps:
            blocked_recommendations.update(
                ref for ref in _blocked_refs(_mapping_get(gap, "blocks", ())) if _entity_namespace(ref) == "REC"
            )
        for recommendation in _snapshot_items(snapshot, "recommendations"):
            if _writer_eligibility(_mapping_get(recommendation, "eligibility", None)) is WriterEligibility.FORBIDDEN_AS_RECOMMENDATION:
                recommendation_ref = _entity_ref(_mapping_get(recommendation, "id", None))
                if recommendation_ref is not None:
                    blocked_recommendations.add(recommendation_ref)

        fan_out = max(outgoing_counts.values(), default=0)
        blocked_recommendation_count = len(blocked_recommendations)
        score = fan_out + (2 * weak_bridge_count) + (3 * unsupported_assumption_count) + (3 * blocked_recommendation_count)

        reason_codes: list[str] = []
        findings: list[str] = []
        if fan_out >= 5:
            reason_codes.append("risk:high_fan_out")
            findings.append(f"max fan-out is {fan_out}")
        if weak_bridge_count:
            reason_codes.append("risk:weak_bridge")
            findings.append(f"weak/indirect bridge count is {weak_bridge_count}")
        if unsupported_assumption_count:
            reason_codes.append("risk:unsupported_assumption")
            findings.append(f"unsupported assumption gaps: {unsupported_assumption_count}")
        if blocked_recommendation_count:
            reason_codes.append("risk:blocked_recommendations")
            findings.append(f"blocked recommendations: {blocked_recommendation_count}")

        if blocked_recommendation_count or (fan_out >= 5 and weak_bridge_count):
            result = ValidationResult.FAIL
        elif reason_codes:
            result = ValidationResult.WARN
        else:
            result = ValidationResult.PASS

        return StructuralRiskReport(
            result=result,
            reason_codes=tuple(reason_codes),
            findings=tuple(findings),
            fan_out=fan_out,
            weak_bridge_count=weak_bridge_count,
            unsupported_assumption_count=unsupported_assumption_count,
            blocked_recommendation_count=blocked_recommendation_count,
            score=score,
        )


class RecommendationGate:
    """Computes writer eligibility for a recommendation-like snapshot."""

    version = "recommendation-gate/1.0"

    def evaluate(self, recommendation: Any) -> RecommendationDecision:
        if recommendation is None:
            raise TypeError("expected a recommendation-like object, got None")

        blocking_gaps = _stringify_refs(
            _sequence(_mapping_get(recommendation, "blocking_gap_ids", None) or _mapping_get(recommendation, "blocking_gaps", None))
        )
        unresolved_conflicts = _stringify_refs(
            _sequence(
                _mapping_get(recommendation, "unresolved_conflict_ids", None)
                or _mapping_get(recommendation, "unresolved_conflicts", None)
            )
        )
        benefit_supported = _mapping_get(recommendation, "benefit_supported", None) is True
        risks_considered = _mapping_get(recommendation, "risk_claims_considered", None) is True
        prerequisites_satisfied = _mapping_get(recommendation, "prerequisites_satisfied", None) is True
        scope_match = _scope_match(recommendation) or "UNKNOWN"
        evidence_lineage_count = int(_mapping_get(recommendation, "evidence_lineage_count", 0) or 0)

        forbidden_codes: list[str] = []
        findings: list[str] = []
        if scope_match not in _SCOPE_MATCHES:
            forbidden_codes.append("recommendation:unknown_scope_match")
            findings.append("scope_match value is not recognized")
        if blocking_gaps:
            forbidden_codes.append("recommendation:blocking_gap")
            findings.append("recommendation has blocking gaps")
        if unresolved_conflicts:
            forbidden_codes.append("recommendation:unresolved_conflict")
            findings.append("recommendation has unresolved conflicts")
        if not benefit_supported:
            forbidden_codes.append("recommendation:unsupported_benefit_path")
            findings.append("benefit path is not supported")
        if not risks_considered:
            forbidden_codes.append("recommendation:risks_unreviewed")
            findings.append("risk claims were not considered")
        if not prerequisites_satisfied:
            forbidden_codes.append("recommendation:prerequisites_unmet")
            findings.append("recommendation prerequisites are not satisfied")
        if scope_match in {"MAJOR_SHIFT", "DISJOINT"}:
            forbidden_codes.append("recommendation:scope_mismatch")
            findings.append("target scope does not match")

        if forbidden_codes:
            return RecommendationDecision(
                WriterEligibility.FORBIDDEN_AS_RECOMMENDATION,
                tuple(forbidden_codes),
                tuple(findings),
            )

        qualified_codes: list[str] = []
        if scope_match in {"PARTIAL", "UNKNOWN"}:
            qualified_codes.append("recommendation:qualified_scope")
            findings.append("recommendation needs an explicit scope caveat")
        if evidence_lineage_count == 1:
            qualified_codes.append("recommendation:single_lineage_support")
            findings.append("recommendation rests on a single evidence lineage")
        elif evidence_lineage_count == 0:
            qualified_codes.append("recommendation:no_lineage_support")
            findings.append("recommendation rests on no evidence lineage")

        if qualified_codes:
            return RecommendationDecision(WriterEligibility.QUALIFIED, tuple(qualified_codes), tuple(findings))
        return RecommendationDecision(WriterEligibility.ALLOWED)
