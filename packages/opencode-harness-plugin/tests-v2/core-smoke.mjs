// Explicit, bounded local Core test. No MCP, daemon or model is started.
import assert from "node:assert/strict"
import { fileURLToPath } from "node:url"
import plugin from "../dist-v2/v2/index.js"

assert.ok(process.argv[2], "Pass an explicit Python interpreter")
const tools = new Map()
const root = fileURLToPath(new URL("../../../", import.meta.url))
const cleanup = await plugin.setup({
  app: { version: "2.0.29" },
  location: { directory: root },
  options: { harnessRoot: root, pythonPath: process.argv[2] },
  tool: {
    hook: async () => {},
    transform: async (fn) => fn({ add: (tool) => tools.set(tool.name, tool) }),
  },
})
try {
  const context = { sessionID: "ses_offline_contract", messageID: "msg_offline_contract", agent: "coder", signal: new AbortController().signal }
  const status = JSON.parse((await tools.get("harness_status").execute({}, context)).content)
  assert.equal(status.ok, true)
  assert.equal(status.semantic_ready, false)
  assert.equal(status.status.runtime_policy_present, true)
  const run = JSON.parse((await tools.get("harness_run").execute({ task: "Implement a unit test", route: "code-implementation" }, context)).content)
  assert.equal(run.ok, true, JSON.stringify(run))
  assert.equal(run.semantic_ready, false)
  assert.equal(tools.has("semantic_execute"), false)
  console.log("PASS built V2 entrypoint + real local Core: status and deterministic route; semantic_ready=false")
} finally {
  cleanup()
}
