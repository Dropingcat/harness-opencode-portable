/**
 * Normalized DTOs that cross the Harness Core <-> OpenCode plugin boundary.
 * No raw OpenCode SDK objects ever cross this boundary.
 */
import type { ToolContext } from "@opencode-ai/plugin"
import { createHash } from "node:crypto"

export const HOST_CONTEXT_SCHEMA = "host-context/1.0"
export const WORKSPACE_REF_SCHEMA = "workspace-ref/1.0"
export const SEMANTIC_REQUEST_SCHEMA = "semantic-execution-request/1.0"
export const SEMANTIC_RESULT_SCHEMA = "semantic-execution-result/1.0"

export interface HostContext {
  schema: "host-context/1.0"
  host: "opencode"
  host_version: string
  plugin_version: string
  session_id: string
  message_id: string
  agent_id: string
  directory: string
  worktree: string
  project_ref?: string
  features_fingerprint?: string
}

export interface WorkspaceRef {
  schema: "workspace-ref/1.0"
  kind: "local"
  directory: string
  worktree: string
  readonly: boolean
  identity: string
}

export type SemanticPurpose =
  | "TRIBUNAL_ROLE"
  | "WRITER_DRAFT"
  | "WRITER_REPAIR"
  | "WRITER_REVIEW"
  | "CODE_WORK"
  | "CODE_REVIEW"
  | "CODE_TEST_ANALYSIS"

export interface SemanticExecutionRequest {
  schema: "semantic-execution-request/1.0"
  execution_id: string
  purpose: SemanticPurpose
  contract_schema: string
  role_ref?: string
  parent_host_session_id: string
  bounded_input: Record<string, unknown>
  expected_output: Record<string, unknown>
  model_policy: {
    provider_id?: string
    model_id?: string
    agent?: string
  }
  permission_profile: string
  timeout_ms: number
  trace: Record<string, unknown>
}

export type RuntimeStatus =
  | "COMPLETED"
  | "FAILED"
  | "TIMED_OUT"
  | "CANCELLED"
  | "REJECTED_BY_HOST"
  | "AUTH_REQUIRED"
  | "HOST_UNAVAILABLE"

export interface SemanticExecutionResult {
  schema: "semantic-execution-result/1.0"
  execution_id: string
  runtime_status: RuntimeStatus
  host_session_id?: string
  provider_id?: string
  model_id?: string
  structured_output: Record<string, unknown>
  raw_output_ref?: string | null
  usage?: Record<string, unknown>
  timing?: Record<string, unknown>
  host_error?: string | null
  host_features_fingerprint?: string | null
}

/**
 * Normalize an OpenCode ToolContext into a host-independent HostContext.
 * This is the ONLY place that reads OpenCode-specific context fields.
 */
export function normalizeHostContext(
  ctx: ToolContext,
  opts: { hostVersion: string; pluginVersion: string },
): HostContext {
  return {
    schema: HOST_CONTEXT_SCHEMA,
    host: "opencode",
    host_version: opts.hostVersion,
    plugin_version: opts.pluginVersion,
    session_id: ctx.sessionID,
    message_id: ctx.messageID,
    agent_id: ctx.agent,
    directory: ctx.directory,
    worktree: ctx.worktree,
  }
}

/**
 * Build a WorkspaceRef from a normalized directory/worktree pair.
 * `readonly` is derived from the permission profile (semantic workers are readonly).
 */
export function buildWorkspaceRef(
  directory: string,
  worktree: string,
  readonly = true,
): WorkspaceRef {
  const identity = sha256(directory + "\u0000" + worktree)
  return {
    schema: WORKSPACE_REF_SCHEMA,
    kind: "local",
    directory,
    worktree,
    readonly,
    identity: `sha256:${identity}`,
  }
}

export function sha256(input: string): string {
  return createHash("sha256").update(input).digest("hex")
}