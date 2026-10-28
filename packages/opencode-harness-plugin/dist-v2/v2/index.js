/**
 * Dependency-free OpenCode V2 Promise definition. No V1 SDK or semantic API.
 * Contract evidence and limitations: ../../V2_DETERMINISTIC.md.
 */
import { existsSync } from "node:fs"
import { createHash } from "node:crypto"
import { resolve, join } from "node:path"
import { fileURLToPath } from "node:url"

const PLUGIN_VERSION = "0.1.0"
const forbidden = new Set(["writer_draft_internal", "writer_repair_internal", "semantic.execute_internal"])

async function openBridge(ctx) {
  // Both src/v2 and dist-v2/v2 live two levels below the package root.
  const packageRoot = fileURLToPath(new URL("../../", import.meta.url))
  const root = resolve(ctx.options?.harnessRoot || process.env.OPENCODE_HARNESS_ROOT || join(packageRoot, "../.."))
  const entry = join(root, "packages", "opencode-harness-plugin", "core", "bridge_peer.py")
  if (!existsSync(entry)) throw new Error(`harness bridge peer not found: ${entry}`)
  const python = ctx.options?.pythonPath || process.env.WRITER_PYTHON || process.env.PYTHON_BIN || process.env.PYTHON
  if (typeof python !== "string" || !python.trim()) {
    throw new Error("Set plugin options.pythonPath or WRITER_PYTHON/PYTHON_BIN/PYTHON explicitly")
  }
  // Lazy import lets source-level contract tests inject an in-memory bridge.
  // build-v2 emits this existing transport separately, without V1 tool imports.
  const { spawnBridgePeer } = await import("../bridge/bridge.js")
  return spawnBridgePeer(python, entry, { OPENCODE_HARNESS_ROOT: root })
}

function nonempty(value, name) {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${name} must be a non-empty string`)
  return value
}

function hostContext(ctx, invocation) {
  // V2 does not provide the V1 directory/worktree fields on tool execution.
  // These deterministic tools are explicitly scoped to the plugin Location.
  const directory = nonempty(ctx.location?.directory, "location.directory")
  return {
    schema: "host-context/1.0", host: "opencode",
    host_version: nonempty(ctx.app?.version, "app.version"), plugin_version: PLUGIN_VERSION,
    session_id: nonempty(invocation.sessionID, "sessionID"),
    message_id: nonempty(invocation.messageID, "messageID"),
    agent_id: nonempty(invocation.agent, "agent"), directory, worktree: directory,
  }
}

function validate(input, name) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("input must be an object")
  const allowed = name === "harness_status" ? ["verbose"] : ["task", "route", "profile"]
  for (const key of Object.keys(input)) if (!allowed.includes(key)) throw new Error(`Unknown input: ${key}`)
  if (name === "harness_status") {
    if (input.verbose !== undefined && typeof input.verbose !== "boolean") throw new Error("verbose must be boolean")
  } else {
    nonempty(input.task, "task")
    if (input.route !== undefined) nonempty(input.route, "route")
    if (input.profile !== undefined && !["soft", "standard", "strict"].includes(input.profile)) throw new Error("Invalid profile")
  }
}

export function createV2Plugin(connect = openBridge) {
  return {
    id: "harness.native.v2.deterministic",
    async setup(ctx) {
      nonempty(ctx.app?.version, "app.version")
      nonempty(ctx.location?.directory, "location.directory")
      const bridge = await connect(ctx)
      let closed = false
      const cleanup = () => { if (!closed) { closed = true; bridge.close() } }
      try {
        bridge.onRequest(async (request) => {
          if (request.method === "bridge.health") return { ok: true, protocol: bridge.protocol, semantic_ready: false }
          throw new Error(`Reverse request disabled in deterministic V2 adapter: ${request.method}`)
        })
        await ctx.tool.hook("execute.before", (event) => {
          if (forbidden.has(event.tool)) throw new Error(`harness plugin BLOCK: forbidden tool ${event.tool}`)
        })
        const execute = (name) => async (input, invocation) => {
          validate(input, name)
          invocation.signal?.throwIfAborted()
          const host = hostContext(ctx, invocation)
          try {
            if (closed) throw new Error("bridge closed")
            let payload
            if (name === "harness_status") {
              const status = await bridge.request("harness.status", { host_context: host })
              payload = { ok: status?.ok === true, bridge_protocol: bridge.protocol, status, host_context: host }
            } else {
              const identity = createHash("sha256").update(`${host.directory}\0${host.worktree}`).digest("hex")
              const result = await bridge.request("harness.run", {
                task: input.task, route: input.route, profile: input.profile, host_context: host,
                workspace_ref: {
                  schema: "workspace-ref/1.0", kind: "local", directory: host.directory,
                  worktree: host.worktree, readonly: true, identity: `sha256:${identity}`,
                },
              })
              payload = { ok: result?.ok === true, result }
            }
            invocation.signal?.throwIfAborted()
            return { content: JSON.stringify({ ...payload, semantic_ready: false }) }
          } catch (error) {
            invocation.signal?.throwIfAborted()
            return { content: JSON.stringify({ ok: false, semantic_ready: false, error: { code: "BRIDGE_ERROR", message: String(error.message ?? error) } }) }
          }
        }
        await ctx.tool.transform((editor) => {
          editor.add({
            name: "harness_status",
            description: "Report deterministic Harness Core status for this plugin Location. Semantic execution is disabled.",
            input: { type: "object", properties: { verbose: { type: "boolean", default: false } }, additionalProperties: false },
            execute: execute("harness_status"),
          })
          editor.add({
            name: "harness_run",
            description: "Resolve a deterministic Harness route/bundle for this plugin Location. Does not execute a semantic model.",
            input: {
              type: "object", properties: {
                task: { type: "string", minLength: 1 }, route: { type: "string", minLength: 1 },
                profile: { type: "string", enum: ["soft", "standard", "strict"] },
              }, required: ["task"], additionalProperties: false,
            },
            execute: execute("harness_run"),
          })
        })
        return cleanup
      } catch (error) { cleanup(); throw error }
    },
  }
}

export default createV2Plugin()
