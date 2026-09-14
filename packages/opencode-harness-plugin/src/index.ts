/**
 * Harness OpenCode Native Plugin entry.
 *
 * Host adapter only: normalizes OpenCode ToolContext -> HostContext/WorkspaceRef,
 * spawns the Core bridge peer, and exposes deterministic tools. It never selects
 * route/role/evidence/truth.
 */
import type { Hooks, Plugin } from "@opencode-ai/plugin"
import { existsSync } from "node:fs"
import { join } from "node:path"
import { spawnBridgePeer, type BridgeHandle } from "./bridge/bridge.js"
import { harnessStatus } from "./tools/harness_status.js"
import { harnessRun } from "./tools/harness_run.js"
import { probeClient } from "./host/probe.js"

const PLUGIN_VERSION = "0.1.0"

function resolveCoreEnv(): { pythonPath: string; coreEntry: string; harnessRoot: string } {
  const harnessRoot = process.env.OPENCODE_HARNESS_ROOT ?? ""
  const pythonPath = process.env.WRITER_PYTHON ?? process.env.PYTHON_BIN ?? process.env.PYTHON ?? "python"
  const coreEntry = join(harnessRoot, "packages", "opencode-harness-plugin", "core", "bridge_peer.py")
  if (!existsSync(coreEntry)) {
    throw new Error(`harness bridge peer not found at ${coreEntry}`)
  }
  return { pythonPath, coreEntry, harnessRoot }
}

const plugin: Plugin = async (input) => {
  const { client, directory } = input
  const hostVersion = "1.18.16"
  const pluginVersion = PLUGIN_VERSION

  const hooks: Hooks = {}

  try {
    const coreEnv = resolveCoreEnv()
    const bridge: BridgeHandle = spawnBridgePeer(coreEnv.pythonPath, coreEnv.coreEntry, {
      OPENCODE_HARNESS_ROOT: coreEnv.harnessRoot,
    })

    const snapshot = await probeClient(client, directory)
    const opts = { hostVersion, pluginVersion }

    hooks.dispose = async () => {
      bridge.close()
    }
    hooks.tool = {
      harness_status: harnessStatus(bridge, opts),
      harness_run: harnessRun(bridge, opts),
    }
    hooks["tool.execute.before"] = async (inputCtx) => {
      const forbidden = ["writer_draft_internal", "writer_repair_internal", "semantic.execute_internal"]
      if (forbidden.includes(inputCtx.tool)) {
        throw new Error(`harness plugin BLOCK: forbidden tool ${inputCtx.tool}`)
      }
    }
    hooks.event = async (ev) => {
      void ev
      void snapshot
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
      harness_status: harnessStatus(degradedBridge, { hostVersion, pluginVersion }),
      harness_run: harnessRun(degradedBridge, { hostVersion, pluginVersion }),
    }
  }

  return hooks
}

export default plugin