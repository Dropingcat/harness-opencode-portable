/**
 * harness-bridge-rpc/1.0 message contracts.
 * Line-delimited JSON-RPC over child-process stdio, full duplex.
 */
export const BRIDGE_PROTOCOL = "harness-bridge-rpc/1.0"

export type BridgeMethod =
  | "bridge.hello"
  | "bridge.health"
  | "bridge.shutdown"
  | "bridge.reverse_echo_test"
  | "harness.status"
  | "harness.run"
  | "harness.cancel"
  | "semantic.execute"

export interface BridgeRequest {
  id: string
  method: BridgeMethod
  params: Record<string, unknown>
}

export interface BridgeResponse {
  id: string
  ok: boolean
  result?: unknown
  error?: {
    code: string
    message: string
    detail?: unknown
  }
}

export interface BridgeEvent {
  type: "event"
  method: string
  params: Record<string, unknown>
}

export type BridgeMessage = BridgeRequest | BridgeResponse | BridgeEvent

export function isBridgeRequest(m: BridgeMessage): m is BridgeRequest {
  return "id" in m && "method" in m
}

export function encodeBridgeMessage(m: BridgeMessage): string {
  return JSON.stringify(m)
}

export function decodeBridgeMessage(line: string): BridgeMessage {
  const parsed = JSON.parse(line) as BridgeMessage
  if (!parsed || typeof parsed !== "object") {
    throw new Error("bridge: non-object message")
  }
  return parsed
}

/** Negotiation payload for bridge.hello. */
export interface HelloParams {
  schema: "harness-bridge-rpc/1.0"
  plugin_semver: string
  bridge_protocol_supported: string[]
  core_api_supported: string[]
  contract_schemas: string[]
  host_version: string
}

export function okResponse(id: string, result: unknown): BridgeResponse {
  return { id, ok: true, result }
}

export function errorResponse(id: string, code: string, message: string, detail?: unknown): BridgeResponse {
  return { id, ok: false, error: { code, message, detail } }
}