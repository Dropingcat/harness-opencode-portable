/**
 * semantic_execute tool: bounded, read-only semantic execution in an isolated
 * child session. This is the ONLY place the plugin drives a model.
 *
 * Design constraints (from the interface-control):
 *  - read-only worker: no harness tools, no mutating tools (`tools: {}`),
 *  - isolated child session linked to the parent host session,
 *  - model comes from SemanticExecutionRequest.model_policy (Core authority),
 *  - timeout + abort handled here; Core revalidates output.
 */
import { tool } from "@opencode-ai/plugin"
import type { OpencodeClient } from "@opencode-ai/sdk"
import { normalizeHostContext, type SemanticExecutionRequest, SEMANTIC_REQUEST_SCHEMA } from "../host/types.js"

export const semanticExecute = (
  client: OpencodeClient,
  opts: { hostVersion: () => string; pluginVersion: string },
) =>
  tool({
    description:
      "Execute a bounded read-only semantic request in an isolated child session. Core supplies the request; the plugin only transports it. Never exposes harness internals or mutating tools.",
    args: {
      request: tool.schema.string().describe("Serialized SemanticExecutionRequest/1.0 JSON"),
    },
    async execute(args, ctx) {
      let parsed: SemanticExecutionRequest
      try {
        parsed = JSON.parse(args.request) as SemanticExecutionRequest
      } catch {
        return { output: JSON.stringify({ ok: false, error: { code: "BAD_REQUEST", message: "invalid JSON request" } }) }
      }
      if (parsed.schema !== SEMANTIC_REQUEST_SCHEMA) {
        return { output: JSON.stringify({ ok: false, error: { code: "BAD_SCHEMA", message: `expected ${SEMANTIC_REQUEST_SCHEMA}` } }) }
      }

      const hostCtx = normalizeHostContext(ctx, { hostVersion: opts.hostVersion(), pluginVersion: opts.pluginVersion })
      const { model_policy, timeout_ms, execution_id, purpose } = parsed
      const startedAt = Date.now()

      try {
        // 1. Create an isolated child session linked to the parent.
        const created = await client.session.create({
          body: { parentID: hostCtx.session_id, title: `harness-semantic:${purpose}:${execution_id}` },
          query: { directory: hostCtx.directory },
        })
        const sessionID = created.data?.id
        if (!sessionID) {
          return { output: JSON.stringify({ ok: false, error: { code: "NO_SESSION", message: "session.create returned no id" } }) }
        }

        const model = model_policy?.model_id
          ? { providerID: model_policy.provider_id ?? "opencode", modelID: model_policy.model_id }
          : undefined

        // 2. Timeout wrapper: abort the child session if the model overruns.
        const timeout = new Promise<never>((_, reject) =>
          setTimeout(() => {
            void client.session.abort({ path: { id: sessionID }, query: { directory: hostCtx.directory } })
            reject(new Error("semantic execute timed out"))
          }, timeout_ms),
        )

        // 3. Run the read-only prompt with NO tools.
        const result = await Promise.race([
          client.session.prompt({
            body: {
              model,
              parts: [{ type: "text", text: JSON.stringify(parsed.bounded_input) }],
              tools: {},
              noReply: false,
            },
            path: { id: sessionID },
            query: { directory: hostCtx.directory },
          }),
          timeout,
        ])

        // 4. Extract text output from parts.
        const parts = result.data?.parts ?? []
        const textParts = parts
          .filter((p) => p.type === "text")
          .map((p) => (p as { text?: string }).text ?? "")
          .join("\n")

        return {
          output: JSON.stringify(
            {
              ok: true,
              schema: "semantic-execution-result/1.0",
              execution_id,
              runtime_status: "COMPLETED",
              host_session_id: sessionID,
              provider_id: model?.providerID,
              model_id: model?.modelID,
              structured_output: { text: textParts },
              timing: { started_at: startedAt, ended_at: Date.now(), duration_ms: Date.now() - startedAt },
            },
            null,
            2,
          ),
          metadata: { tool: "semantic_execute", execution_id, purpose, session_id: sessionID },
        }
      } catch (e) {
        const err = e as Error
        const isTimeout = err.message.includes("timed out")
        return {
          output: JSON.stringify(
            {
              ok: false,
              schema: "semantic-execution-result/1.0",
              execution_id,
              runtime_status: isTimeout ? "TIMED_OUT" : "FAILED",
              host_error: err.message,
            },
            null,
            2,
          ),
          metadata: { tool: "semantic_execute", execution_id, error: err.message },
        }
      }
    },
  })