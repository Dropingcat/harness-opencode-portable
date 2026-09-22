"""R4.3 adapter for one Tribunal role over the existing Job/Attempt runtime.

This is deliberately a thin adapter.  It does not schedule a panel, pick roles,
or grant evidence/tool authority.  Those decisions are already frozen in the
InquiryContract + TribunalEvidenceSlice.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from scripts.jobs import job_ctl
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.tribunal_evidence import TribunalEvidenceSlice, tribunal_evidence_slice_to_dict
from researcher_core.tribunal_role_handbook import (
    RoleInstructionPack,
    RoleVariantKind,
    role_instruction_pack_to_dict,
    validate_role_instruction_pack_integrity,
)
from researcher_core.tribunal_inquiry import (
    ArgumentArtifact,
    InquiryContract,
    InquiryExecutionArtifacts,
    InquiryTurn,
    RoleWorkerDraft,
    TribunalInquiryError,
    argument_artifact_to_dict,
    inquiry_contract_to_dict,
    inquiry_turn_to_dict,
    materialize_role_worker_draft,
    validate_inquiry_contract_integrity,
)


class TribunalRoleRuntimeError(RuntimeError):
    pass


class TribunalRoleWorker(Protocol):
    worker_id: str

    def execute(self, *, contract: InquiryContract, evidence_slice: TribunalEvidenceSlice, instruction: RoleInstructionPack) -> RoleWorkerDraft: ...


@dataclass(frozen=True, slots=True)
class TribunalRoleExecutionResult:
    contract_id: EntityId
    child_job_id: str
    attempt_id: str
    artifact_path: str
    turn: InquiryTurn
    argument: ArgumentArtifact

    def __post_init__(self) -> None:
        if self.contract_id.namespace != "IQC":
            raise ValueError("contract_id must use IQC prefix")
        if not self.child_job_id or not self.attempt_id or not self.artifact_path:
            raise ValueError("runtime result requires child/attempt/artifact path")


class JobCtlTribunalRoleAdapter:
    """Execute one role as one child Job with one first-pass Attempt."""

    def __init__(self, *, state_dir: str | Path, artifact_dir: str | Path):
        self.state_dir = Path(state_dir)
        self.artifact_dir = Path(artifact_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def child_state_path(self, child_job_id: str) -> Path:
        return self.state_dir / f"{child_job_id.replace('/', '_')}.json"

    def execute(
        self,
        *,
        parent_state_path: str | Path,
        contract: InquiryContract,
        evidence_slice: TribunalEvidenceSlice,
        worker: TribunalRoleWorker,
        instruction: RoleInstructionPack,
        id_factory: EntityIdFactory,
        actor: ActorRef,
        created_at: datetime,
    ) -> TribunalRoleExecutionResult:
        validate_inquiry_contract_integrity(contract)
        validate_role_instruction_pack_integrity(instruction)
        if evidence_slice.role_id != contract.role_id:
            raise TribunalRoleRuntimeError("worker slice does not match InquiryContract role")
        if (
            instruction.role_id != contract.role_id
            or instruction.instruction_id != contract.role_instruction_id
            or instruction.instruction_fingerprint != contract.role_instruction_fingerprint
        ):
            raise TribunalRoleRuntimeError("role instruction does not match InquiryContract")
        if instruction.expected_output_contract != contract.expected_output_contract:
            raise TribunalRoleRuntimeError("role instruction output contract mismatch")
        if instruction.variant is not RoleVariantKind.FIRST_PASS:
            raise TribunalRoleRuntimeError("R4.3 independent-first-pass runtime requires first_pass role instruction")
        if not getattr(worker, "worker_id", ""):
            raise TribunalRoleRuntimeError("worker_id is required")

        parent_path = Path(parent_state_path)
        parent = job_ctl.load(parent_path)
        if parent.get("status") not in {"RUNNING", "DEGRADED", "WAITING_RETRY"}:
            raise TribunalRoleRuntimeError("parent Job is not executable")

        child_job_id = f"tribunal-{contract.role_id}-{str(contract.meta.id)}"
        if any(
            child.get("child_id") == child_job_id
            or child.get("external_task_id") == str(contract.meta.id)
            for child in parent.get("children", ())
        ):
            raise TribunalRoleRuntimeError("InquiryContract already has a child Job in parent")

        child_path = self.child_state_path(child_job_id)
        if child_path.exists():
            raise TribunalRoleRuntimeError("child Job state already exists")

        child_contract = {
            "schema": "tribunal-role-job/1.0",
            "inquiry_contract": inquiry_contract_to_dict(contract),
            "evidence_slice": tribunal_evidence_slice_to_dict(evidence_slice),
            "worker_id": worker.worker_id,
            "role_instruction": role_instruction_pack_to_dict(instruction),
            "authority_boundary": "worker receives only bound InquiryContract + EvidenceSlice",
        }
        child = job_ctl.create(child_job_id, child_contract, ["first_pass"])
        job_ctl.save(child, child_path)

        child_record = {
            "child_id": child_job_id,
            "mode": "required",
            "external_task_id": str(contract.meta.id),
            "status": "RUNNING",
            "created_at": job_ctl.now(),
        }
        parent.setdefault("children", []).append(child_record)
        job_ctl.event(parent, "CHILD_ADDED", child_record)
        job_ctl.save(parent, parent_path)

        attempt_id = self._start_attempt(child_path, contract, worker.worker_id)
        try:
            draft = worker.execute(contract=contract, evidence_slice=evidence_slice, instruction=instruction)
            artifacts = materialize_role_worker_draft(
                contract=contract,
                evidence_slice=evidence_slice,
                draft=draft,
                id_factory=id_factory,
                actor=actor,
                created_at=created_at,
            )
            artifact_path = self._write_artifacts(
                contract, evidence_slice, artifacts, attempt_id=attempt_id, worker_id=worker.worker_id, instruction=instruction
            )
            self._finish_child_success(
                child_path=child_path,
                parent_path=parent_path,
                child_job_id=child_job_id,
                attempt_id=attempt_id,
                artifact_id=str(artifacts.argument.meta.id),
                artifact_path=artifact_path,
            )
            return TribunalRoleExecutionResult(
                contract_id=contract.meta.id,
                child_job_id=child_job_id,
                attempt_id=attempt_id,
                artifact_path=str(artifact_path),
                turn=artifacts.turn,
                argument=artifacts.argument,
            )
        except Exception as exc:
            self._finish_child_failure(
                child_path=child_path,
                parent_path=parent_path,
                child_job_id=child_job_id,
                attempt_id=attempt_id,
                reason=f"{exc.__class__.__name__}: {exc}",
            )
            if isinstance(exc, TribunalInquiryError):
                raise
            raise TribunalRoleRuntimeError(str(exc)) from exc

    def _start_attempt(self, child_path: Path, contract: InquiryContract, worker_id: str) -> str:
        child = job_ctl.load(child_path)
        external = str(contract.meta.id)
        if any(x.get("external_task_id") == external for x in child.get("attempts", ())):
            raise TribunalRoleRuntimeError("InquiryContract attempt already exists in child Job")
        attempt_id = "ATT-" + contract.contract_fingerprint.split(":", 1)[-1][:12]
        rec = {
            "attempt_id": attempt_id,
            "agent": worker_id,
            "stage": "first_pass",
            "external_task_id": external,
            "status": "RUNNING",
            "started_at": job_ctl.now(),
            "heartbeat": None,
            "artifacts": [],
        }
        child["attempts"].append(rec)
        child["stages"]["first_pass"]["status"] = "RUNNING"
        child["stages"]["first_pass"]["updated_at"] = job_ctl.now()
        job_ctl.event(child, "ATTEMPT_STARTED", rec)
        job_ctl.save(child, child_path)
        return attempt_id

    def _write_artifacts(
        self,
        contract: InquiryContract,
        evidence_slice: TribunalEvidenceSlice,
        artifacts: InquiryExecutionArtifacts,
        *,
        attempt_id: str,
        worker_id: str,
        instruction: RoleInstructionPack,
    ) -> Path:
        path = self.artifact_dir / f"{artifacts.argument.meta.id}.json"
        payload = {
            "schema": "tribunal-role-execution-output/1.0",
            "contract_id": str(contract.meta.id),
            "contract_fingerprint": contract.contract_fingerprint,
            "slice_fingerprint": evidence_slice.slice_fingerprint,
            "runtime": {
                "attempt_id": attempt_id,
                "worker_id": worker_id,
                "role_instruction_id": instruction.instruction_id,
                "role_instruction_fingerprint": instruction.instruction_fingerprint,
            },
            "turn": inquiry_turn_to_dict(artifacts.turn),
            "argument": argument_artifact_to_dict(artifacts.argument),
        }
        job_ctl.atomic_write(path, payload)
        return path

    def _finish_child_success(
        self,
        *,
        child_path: Path,
        parent_path: Path,
        child_job_id: str,
        attempt_id: str,
        artifact_id: str,
        artifact_path: Path,
    ) -> None:
        child = job_ctl.load(child_path)
        attempt = job_ctl.attempt_by(child, attempt_id)
        attempt["status"] = "COMPLETED"
        attempt["finished_at"] = job_ctl.now()
        attempt["artifacts"] = [artifact_id]
        child["artifacts"][artifact_id] = {
            "path": str(artifact_path),
            "sha256": _sha256_file(artifact_path),
            "registered_at": job_ctl.now(),
        }
        stage = child["stages"]["first_pass"]
        stage["status"] = "COMPLETED"
        stage["updated_at"] = job_ctl.now()
        stage["artifacts"] = [artifact_id]
        child["status"] = "COMPLETED"
        job_ctl.event(child, "ARTIFACT_REGISTERED", {"artifact_id": artifact_id, "path": str(artifact_path)})
        job_ctl.event(child, "ATTEMPT_FINISHED", {"attempt_id": attempt_id, "status": "COMPLETED", "artifacts": [artifact_id]})
        job_ctl.event(child, "STAGE_UPDATED", {"stage": "first_pass", "status": "COMPLETED", "artifacts": [artifact_id]})
        job_ctl.event(child, "JOB_COMPLETED", {})
        job_ctl.save(child, child_path)

        parent = job_ctl.load(parent_path)
        record = job_ctl.child_by(parent, child_job_id)
        record["status"] = "COMPLETED"
        record["finished_at"] = job_ctl.now()
        job_ctl.event(parent, "CHILD_FINISHED", {"child_id": child_job_id, "status": "COMPLETED"})
        job_ctl.save(parent, parent_path)

    def _finish_child_failure(
        self,
        *,
        child_path: Path,
        parent_path: Path,
        child_job_id: str,
        attempt_id: str,
        reason: str,
    ) -> None:
        if child_path.exists():
            child = job_ctl.load(child_path)
            try:
                attempt = job_ctl.attempt_by(child, attempt_id)
                attempt["status"] = "FAILED"
                attempt["finished_at"] = job_ctl.now()
                attempt["error"] = reason
            except KeyError:
                pass
            stage = child["stages"].get("first_pass")
            if stage is not None:
                stage["status"] = "FAILED"
                stage["updated_at"] = job_ctl.now()
            child["status"] = "FAILED_NO_OUTPUT"
            job_ctl.event(child, "ATTEMPT_FINISHED", {"attempt_id": attempt_id, "status": "FAILED", "reason": reason})
            job_ctl.event(child, "JOB_FAILED", {"reason": reason})
            job_ctl.save(child, child_path)

        parent = job_ctl.load(parent_path)
        record = job_ctl.child_by(parent, child_job_id)
        record["status"] = "FAILED"
        record["finished_at"] = job_ctl.now()
        job_ctl.event(parent, "CHILD_FINISHED", {"child_id": child_job_id, "status": "FAILED", "reason": reason})
        job_ctl.save(parent, parent_path)


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
