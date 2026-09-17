/**
 * harness_run tool: deterministic Harness routing/bundle through Core.
 * No semantic execution on P1.
 */
import { tool } from "@opencode-ai/plugin"
import type { BridgeHandle } from "../bridge/bridge.js"
import { buildWorkspaceRef, normalizeHostContext } from "../host/types.js"

export const harnessRun = (
  bridge: BridgeHandle,
  opts: { hostVersion: () => string; pluginVersion: string },
) =>
  tool({
    description:
      "Run a deterministic Harness request through Core routing (Writer/Researcher/Coder route resolution and bundle). Returns route/bundle/readiness. This tool does not execute a semantic model.",
    args: {
      task: tool.schema.string().describe("Task text to route").min(1),
      route: tool.schema.string().optional().describe("Explicit route id (e.g. academic-research, code-implementation, writing-prose)"),
      profile: tool.schema.enum(["soft", "standard", "strict"]).optional(),
    },
    async execute(args, ctx) {
      try {
        const hostCtx = normalizeHostContext(ctx, {
          hostVersion: opts.hostVersion(),
          pluginVersion: opts.pluginVersion,
        })
        const ws = buildWorkspaceRef(ctx.directory, ctx.worktree, true)
        const result = await bridge.request("harness.run", {
          task: args.task,
          route: args.route,
          profile: args.profile,
          host_context: hostCtx,
          workspace_ref: ws,
        })
        return {
          output: JSON.stringify({ ok: true, result }, null, 2),
          metadata: { tool: "harness_run", agent: ctx.agent, route: args.route ?? null },
        }
      } catch (e) {
        const err = e as Error
        return {
          output: JSON.stringify({ ok: false, error: { code: "BRIDGE_ERROR", message: err.message } }, null, 2),
          metadata: { tool: "harness_run", error: err.message },
        }
      }
    },
  })