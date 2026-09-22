"""Read-only LocalCorpus capsule backed by a JSONL literature index.

Bounded deterministic adapter inspired by legacy literature_index/server, but
reduced to local JSONL search only. No network, no MCP runtime dependency.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from researcher_core.capsules import CapsuleDescriptor, CapsuleObservation, CapsuleRequest, SideEffectClass


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


@dataclass(frozen=True, slots=True)
class LocalCorpusCapsule:
    index_path: Path

    descriptor = CapsuleDescriptor(
        capsule_id="capsule.local-corpus",
        version="0.1.0",
        capabilities=("literature.search_local", "literature.sources_local"),
        side_effect_class=SideEffectClass.READ_ONLY,
        input_schema_version="capsule-request/0.1",
        output_schema_version="capsule-observation/0.1",
        policy_keys=("research.literature.local_first_enabled",),
    )

    def run(self, request: CapsuleRequest) -> CapsuleObservation:
        if request.capability == "literature.search_local":
            query = str(request.payload.get("query", ""))
            limit = int(request.payload.get("limit", 5))  # debt-scan: ignore-line -- bounded search default
            hits = self.search(query, limit)
            return CapsuleObservation(
                request_id=request.request_id,
                capsule_id=self.descriptor.capsule_id,
                capability=request.capability,
                output_schema_version=self.descriptor.output_schema_version,
                payload={"hits": hits},
                provenance={"index_path": str(self.index_path), "capsule_version": self.descriptor.version},
            )
        if request.capability == "literature.sources_local":
            topics = request.payload.get("topics", ())
            limit = int(request.payload.get("limit", 5))  # debt-scan: ignore-line -- bounded source default
            hits = self.sources(topics, limit)
            return CapsuleObservation(
                request_id=request.request_id,
                capsule_id=self.descriptor.capsule_id,
                capability=request.capability,
                output_schema_version=self.descriptor.output_schema_version,
                payload={"sources": hits},
                provenance={"index_path": str(self.index_path), "capsule_version": self.descriptor.version},
            )
        raise ValueError(f"unsupported capability: {request.capability}")

    def search(self, query: str, limit: int) -> tuple[dict[str, object], ...]:
        terms = [term for term in re.split(r"\s+", query.lower()) if len(term) >= 2]
        hits: list[dict[str, object]] = []
        for rec in self._load_index():
            text = _norm(str(rec.get("text", "")))
            if all(term in text for term in terms):
                hits.append(
                    {
                        "path": str(rec.get("path", "")),
                        "name": str(rec.get("name", "")),
                        "page": int(rec.get("page", 0)),
                        "excerpt": str(rec.get("text", ""))[:160],  # debt-scan: ignore-line -- excerpt cap
                    }
                )
            if len(hits) >= limit:
                break
        return tuple(hits)

    def sources(self, topics: object, limit: int) -> tuple[dict[str, object], ...]:
        topic_list = [str(topic).lower() for topic in (topics if isinstance(topics, (list, tuple)) else [topics]) if str(topic)]
        stats: dict[str, dict[str, object]] = {}
        for rec in self._load_index():
            text = _norm(str(rec.get("text", "")))
            if topic_list and not any(topic in text for topic in topic_list):
                continue
            path = str(rec.get("path", ""))
            entry = stats.setdefault(path, {"path": path, "name": str(rec.get("name", "")), "hit_pages": 0})
            entry["hit_pages"] = int(entry["hit_pages"]) + 1
        ranked = sorted(stats.values(), key=lambda item: -int(item["hit_pages"]))
        return tuple(ranked[:limit])

    def _load_index(self) -> tuple[dict[str, object], ...]:
        recs: list[dict[str, object]] = []
        if not self.index_path.is_file():
            return ()
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if isinstance(rec, dict):
                recs.append(rec)
        return tuple(recs)
