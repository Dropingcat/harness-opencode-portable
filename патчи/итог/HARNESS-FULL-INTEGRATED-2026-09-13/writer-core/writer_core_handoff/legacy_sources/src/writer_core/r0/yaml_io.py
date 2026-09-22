"""YAML I/O for writer-core: load/dump with validation, tree walk, canonical order."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from yaml import SafeLoader, SafeDumper

from writer_core.r0.entities import (
    EntityMeta, WriterDocument, WriterEvent, WriterUnit,
    WriterTransaction, WriterSnapshot, WriterEvent, WriterUnitProposal,
    ObjectPayload, UnitRelation
)
from writer_core.r0.ids import EntityId
from writer_core.r0.validation import ValidationReport, ValidationResult


class YAMLValidationError(ValueError):
    """Raised when YAML fails validation."""
    pass


class YAMLLoader:
    """Load YAML with validation."""

    def __init__(self) -> None:
        self._loader = yaml.SafeLoader

    def load_file(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.load(f, Loader=yaml.SafeLoader)

    def load_string(self, content: str) -> dict:
        return yaml.load(content, Loader=yaml.SafeLoader)

    def load_unit(self, data: dict) -> dict:
        required = ["id", "level", "type"]
        for field in required:
            if field not in data:
                raise YAMLValidationError(f"missing required field: {field}")
        return data


class YAMLDumper:
    """Dump Python objects to YAML with canonical ordering."""

    def __init__(self) -> None:
        self._dumper = yaml.SafeDumper

    def dump_file(self, path: Path, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, Dumper=yaml.SafeDumper, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def dump_string(self, data: dict) -> str:
        return yaml.dump(data, Dumper=yaml.SafeDumper, allow_unicode=True, sort_keys=False, default_flow_style=False)


class YAMLValidator:
    """Validate YAML against schemas."""

    def __init__(self) -> None:
        self._schemas: dict = {}

    def validate_unit(self, data: dict) -> list[str]:
        errors = []
        if "id" not in data:
            errors.append("missing required field: id")
        if "level" not in data:
            errors.append("missing required field: level")
        if "type" not in data:
            errors.append("missing required field: type")
        return errors

    def validate_skeleton(self, data: dict) -> list[str]:
        errors = []
        if "document" not in data:
            errors.append("missing 'document' root")
        if "skeleton" not in data:
            errors.append("missing 'skeleton' root")
        return errors


class YAMLTreeWalker:
    """Walk YAML tree in canonical order."""

    def __init__(self, data: dict) -> None:
        self.data = data

    def walk_units(self, node: dict = None, path: list = None):
        if node is None:
            node = self.data
        if path is None:
            path = []

        if isinstance(node, dict):
            if "children" in node:
                for i, child in enumerate(node["children"]):
                    yield from self.walk_units(child, path + [str(i)])

    def get_unit_by_id(self, unit_id: str, node: dict = None):
        if node is None:
            node = self.data
        if node.get("id") == unit_id:
            return node
        if "children" in node:
            for child in node["children"]:
                result = self.get_unit_by_id(unit_id, child)
                if result:
                    return result
        return None


class YAMLSerializer:
    """Serialize/deserialize writer-core entities to/from YAML."""

    def __init__(self) -> None:
        self.loader = YAMLLoader()
        self.dumper = YAMLDumper()
        self.validator = YAMLValidator()

    def serialize_unit(self, unit) -> dict:
        if hasattr(unit, "__dict__"):
            return asdict(unit)
        return dict(unit)

    def deserialize_unit(self, data: dict):
        return data

    def serialize_skeleton(self, skeleton: dict) -> dict:
        return skeleton

    def deserialize_skeleton(self, data: dict):
        return data

    def serialize_work(self, work) -> dict:
        if hasattr(work, "__dict__"):
            return asdict(work)
        return dict(work)

    def deserialize_work(self, data: dict):
        return data


class CanonicalYAMLDumper(SafeDumper):
    """Dumper that preserves key order."""

    def represent_dict(self, data):
        return self.represent_mapping("tag:yaml.org,2002:map", data.items())


CanonicalYAMLDumper.add_representer(dict, CanonicalYAMLDumper.represent_dict)


def load_yaml_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def dump_yaml_file(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=yaml.SafeDumper, allow_unicode=True, sort_keys=False, default_flow_style=False)


def validate_yaml_against_schema(data: dict, schema_type: str) -> list[str]:
    validator = YAMLValidator()
    if schema_type == "unit":
        return validator.validate_unit(data)
    elif schema_type == "skeleton":
        return validator.validate_skeleton(data)
    return ["unknown schema type"]


def walk_skeleton_tree(skeleton: dict, callback) -> None:
    def _walk(node, path):
        callback(node, path)
        if "children" in node:
            for i, child in enumerate(node["children"]):
                _walk(child, path + [str(i)])
    _walk(skeleton, [])