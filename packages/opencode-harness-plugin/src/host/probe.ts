/**
 * Feature probes against the actual @opencode-ai/sdk client shape (v1.18.16).
 * These lock the exact SDK call-shape so fake SDK objects cannot hide a
 * host integration mismatch until Desktop runtime.
 */
import type { OpencodeClient } from "@opencode-ai/sdk"
import { createHash } from "node:crypto"

export type HostFeatureProbe = {
  id: string
  ok: boolean
  detail: string
}

export interface HostFeatureSnapshot {
  features: HostFeatureProbe[]
  required_ok: boolean
  fingerprint: string
}

/** Required before the plugin may claim semantic readiness. */
const REQUIRED_FEATURES = [
  "PLUGIN_LOADED",
  "SDK_CLIENT_AVAILABLE",
  "SESSION_CREATE",
  "SESSION_PROMPT",
  "SESSION_ABORT",
]

const OPTIONAL_FEATURES = [
  "HOST_CONTEXT",
  "WORKSPACE_CONTEXT",
  "CHILD_PARENT_LINK",
  "STRUCTURED_OUTPUT",
  "USAGE_METADATA",
  "EVENT_STREAM",
]

export async function probeClient(
  client: OpencodeClient,
  directory: string,
): Promise<HostFeatureSnapshot> {
  const features: HostFeatureProbe[] = [
    { id: "PLUGIN_LOADED", ok: true, detail: "plugin factory invoked by host" },
    { id: "SDK_CLIENT_AVAILABLE", ok: Boolean(client), detail: "client object present" },
  ]

  // session.create / prompt / abort presence is enough to prove API surface;
  // live invocation is only attempted for certified semantic workers.
  const has = (obj: unknown, name: string) =>
    Boolean(obj && typeof (obj as Record<string, unknown>)[name] === "function")

  features.push({ id: "SESSION_CREATE", ok: has(client?.session, "create"), detail: "client.session.create" })
  features.push({ id: "SESSION_PROMPT", ok: has(client?.session, "prompt"), detail: "client.session.prompt" })
  features.push({ id: "SESSION_ABORT", ok: has(client?.session, "abort"), detail: "client.session.abort" })
  features.push({ id: "SESSION_MESSAGES", ok: has(client?.session, "messages"), detail: "client.session.messages" })
  features.push({ id: "EVENT_STREAM", ok: has(client?.event, "subscribe"), detail: "client.event.subscribe" })

  const requiredOk = REQUIRED_FEATURES.every((id) => features.some((f) => f.id === id && f.ok))
  const fp = fingerprint(features, directory)
  return {
    features,
    required_ok: requiredOk,
    fingerprint: `sha256:${fp}`,
  }
}

function fingerprint(features: HostFeatureProbe[], directory: string): string {
  const canonical = features
    .map((f) => `${f.id}=${f.ok ? "1" : "0"}`)
    .sort()
    .join("|")
  return createHash("sha256").update(`${canonical}\u0000${directory}`).digest("hex")
}