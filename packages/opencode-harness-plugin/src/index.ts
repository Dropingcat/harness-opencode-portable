/**
 * Harness OpenCode Native Plugin entry.
 *
 * Host adapter only: normalizes OpenCode ToolContext -> HostContext/WorkspaceRef,
 * spawns the Core bridge peer, and exposes deterministic tools. It never selects
 * route/role/evidence/truth.
 */
import type { Hooks, Plugin } from "@opencode-ai/plugin"
import { existsSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { spawnBridgePeer, type BridgeHandle } from "./bridge/bridge.js"
import { harnessStatus } from "./tools/harness_status.js"
import { harnessRun } from "./tools/harness_run.js"
import { semanticExecute } from "./tools/semantic_execute.js"
import { probeClient } from "./host/probe.js"

const PLUGIN_VERSION = "0.1.0"

function resolveCoreEnv(): { pythonPath: string; coreEntry: string; harnessRoot: string } {
  // Resolution order:
  //  1. OPENCODE_HARNESS_ROOT env (explicit)
  //  2. plugin installed in <root>/.opencode/plugins/  -> root
  //  3. plugin running from <root>/packages/opencode-harness-plugin/src/index.ts
  const envRoot = process.env.OPENCODE_HARNESS_ROOT ?? ""
  const here = fileURLToPath(import.meta.url)
  const harnessRoot =
    envRoot ||
    (() => {
      // <root>/.opencode/plugins/opencode-harness-plugin.ts
      if (existsSync(join(dirname(here), "..", "..", "config", "runtime_snapshot.json"))) {
        return join(dirname(here), "..", "..")
      }
      // <root>/packages/opencode-harness-plugin/src/index.ts
      if (existsSync(join(dirname(here), "..", "..", "..", "config", "runtime_snapshot.json"))) {
        return join(dirname(here), "..", "..", "..")
      }
      return ""
    })()
  if (!harnessRoot) {
    throw new Error("harness root not found: set OPENCODE_HARNESS_ROOT or install the plugin inside the harness tree")
  }
  const pythonPath = process.env.WRITER_PYTHON ?? process.env.PYTHON_BIN ?? process.env.PYTHON ?? "python"
  const coreEntry = join(harnessRoot, "packages", "opencode-harness-plugin", "core", "bridge_peer.py")
  if (!existsSync(coreEntry)) {
    throw new Error(`harness bridge peer not found at ${coreEntry}`)
  }
  return { pythonPath, coreEntry, harnessRoot }
}

const plugin: Plugin = async (input) => {
  const { client, directory } = input
  // Host version: prefer the env the opencode runtime sets, else fall back to the
  // API package version the plugin was built against. Exact version is recorded,
  // never assumed to imply capability.
  let detectedHostVersion =
    process.env.OPENCODE_VERSION ??
    process.env.OPENCODE_HOST_VERSION ??
    "1.18.16"
  const pluginVersion = PLUGIN_VERSION

  const hooks: Hooks = {}

  try {
    const coreEnv = resolveCoreEnv()
    const bridge: BridgeHandle = spawnBridgePeer(coreEnv.pythonPath, coreEnv.coreEntry, {
      OPENCODE_HARNESS_ROOT: coreEnv.harnessRoot,
    })

    const snapshot = await probeClient(client, directory)
    const opts = { hostVersion: () => detectedHostVersion, pluginVersion }

    // Full-duplex reverse handler: Core (Python peer) sends semantic.execute
    // requests; the plugin runs the read-only child session. This is the
    // transport Core's Tribunal uses when the plugin is the active provider.
    bridge.onRequest(async (req) => {
      if (req.method === "semantic.execute") {
        const params = (req.params ?? {}) as Record<string, unknown>
        const requestText = typeof params.request === "string" ? params.request : JSON.stringify(params.request ?? {})
        // Build a minimal host context for the reverse call (no real tool session).
        const hostVersion = detectedHostVersion
        const result = await semanticExecute(client, opts).execute(
          { request: requestText },
          {
            sessionID: String(params.host_session_id ?? "reverse"),
            messageID: "reverse",
            agent: "harness-core",
            directory: String(params.directory ?? directory),
            worktree: String(params.directory ?? directory),
          } as never,
        )
        const rawOutput = typeof result === "string" ? result : result.output
        try {
          return { tool_result: JSON.parse(rawOutput) }
        } catch {
          return { tool_result: rawOutput }
        }
      }
      if (req.method === "bridge.health") {
        return { ok: true, protocol: bridge.protocol }
      }
      throw new Error(`harness plugin: unsupported reverse method ${req.method}`)
    })

    // Visible load marker via the exact SDK app.log call shape.
    try {
      await client.app.log({
        body: {
          service: "harness-opencode-plugin",
          level: "info",
          message: `harness plugin loaded protocol=${bridge.protocol} root=${coreEnv.harnessRoot}`,
          extra: {
            host_version: detectedHostVersion,
            plugin_version: pluginVersion,
            directory,
            feature_fingerprint: snapshot.fingerprint,
            required_features_ok: snapshot.required_ok,
          },
        },
        query: { directory },
      })
    } catch {
      // logging is best-effort; do not fail plugin load
    }

    hooks.dispose = async () => {
      bridge.close()
    }
    hooks.tool = {
      harness_status: harnessStatus(bridge, opts),
      harness_run: harnessRun(bridge, opts),
    }
    // P3: semantic_execute is gated behind an explicit flag. Core enables it only
    // after live certification; until then the tool is absent (not just hidden).
    if (process.env.HARNESS_SEMANTIC_ENABLED === "1") {
      hooks.tool.semantic_execute = semanticExecute(client, opts)
    }
    hooks["tool.execute.before"] = async (inputCtx) => {
      const forbidden = ["writer_draft_internal", "writer_repair_internal", "semantic.execute_internal"]
      if (forbidden.includes(inputCtx.tool)) {
        throw new Error(`harness plugin BLOCK: forbidden tool ${inputCtx.tool}`)
      }
    }
    hooks.event = async (ev) => {
      // Capture the real host version from documented events.
      const e = ev.event as {
        type?: string
        properties?: { version?: string; info?: { version?: string } }
      }
      const v =
        e?.type === "installation.updated" || e?.type === "installation.update-available"
          ? e.properties?.version
          : e?.type === "session.created"
            ? e.properties?.info?.version
            : undefined
      if (v) {
        detectedHostVersion = v
      }
    }
  } catch (e) {
    const err = e as Error
    // Degraded startup: expose a minimal status tool that reports the failure.
    const degradedBridge = {
      protocol: "harness-bridge-rpc/1.0",
      request: async (): Promise<never> => {
        throw new Error(`bridge unavailable: ${err.message}`)
      },
    } as unknown as BridgeHandle
    hooks.tool = {
      harness_status: harnessStatus(degradedBridge, { hostVersion: () => detectedHostVersion, pluginVersion }),
      harness_run: harnessRun(degradedBridge, { hostVersion: () => detectedHostVersion, pluginVersion }),
    }
  }

  return hooks
}

export default plugin