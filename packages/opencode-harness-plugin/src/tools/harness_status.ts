/**
 * harness_status tool: reports plugin/bridge/core state without any semantic execution.
 */
import { tool } from "@opencode-ai/plugin"
import type { BridgeHandle } from "../bridge/bridge.js"
import { normalizeHostContext } from "../host/types.js"

export const harnessStatus = (
  bridge: BridgeHandle,
  opts: { hostVersion: () => string; pluginVersion: string },
) =>
  tool({
    description:
      "Report Harness plugin, bridge and core readiness. Returns protocol, core root, policy presence and host context. No semantic execution.",
    args: {
      verbose: tool.schema.boolean().optional().default(false),
    },
    async execute(args, ctx) {
      try {
        const hostCtx = normalizeHostContext(ctx, {
          hostVersion: opts.hostVersion(),
          pluginVersion: opts.pluginVersion,
        })
        const status = await bridge.request("harness.status", {
          host_context: hostCtx,
        })
        return {
          output: JSON.stringify(
            {
              ok: true,
              bridge_protocol: bridge.protocol,
              status,
              host_context: hostCtx,
            },
            null,
            2,
          ),
          metadata: { tool: "harness_status", agent: ctx.agent, sessionID: ctx.sessionID },
        }
      } catch (e) {
        const err = e as Error
        return {
          output: JSON.stringify({ ok: false, error: { code: "BRIDGE_ERROR", message: err.message } }, null, 2),
          metadata: { tool: "harness_status", error: err.message },
        }
      }
    },
  })