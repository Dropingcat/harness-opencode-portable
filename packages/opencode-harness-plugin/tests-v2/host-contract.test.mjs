import test from "node:test"
import assert from "node:assert/strict"
const { createV2Plugin, default: plugin } = await import(
  process.env.HARNESS_V2_ENTRY || new URL("../src/v2/index.js", import.meta.url).href
)

function fixture(overrides = {}) {
  const tools = new Map()
  const hooks = new Map()
  const requests = []
  let closed = 0
  let reverse
  const bridge = {
    protocol: "harness-bridge-rpc/1.0",
    request: async (method, params) => { requests.push({ method, params }); return { ok: true } },
    onRequest: (handler) => { reverse = handler },
    close: () => { closed++ },
    ...overrides,
  }
  const ctx = {
    app: { version: "2.0.29" },
    location: { directory: "C:/workspace", project: { canonical: "C:/canonical" } },
    options: {},
    tool: {
      hook: async (name, fn) => { hooks.set(name, fn) },
      transform: async (fn) => {
        assert.equal(fn({ add: (tool) => tools.set(tool.name, tool) }), undefined)
      },
    },
  }
  return { ctx, tools, hooks, requests, bridge, closed: () => closed, reverse: () => reverse }
}

const invocation = { sessionID: "ses_real", messageID: "msg_real", agent: "coder", signal: new AbortController().signal }

test("default is a genuine V2 definition, not a legacy factory", () => {
  assert.equal(plugin.id, "harness.native.v2.deterministic")
  assert.equal(typeof plugin.setup, "function")
  assert.equal(plugin.server, undefined)
})

test("registers only deterministic tools with JSON Schema and content results", async () => {
  const f = fixture()
  const cleanup = await createV2Plugin(async () => f.bridge).setup(f.ctx)
  assert.deepEqual([...f.tools.keys()], ["harness_status", "harness_run"])
  for (const tool of f.tools.values()) {
    assert.equal(tool.input.type, "object")
    assert.equal(tool.input.additionalProperties, false)
    assert.equal(tool.args, undefined)
  }
  const status = await f.tools.get("harness_status").execute({}, invocation)
  assert.equal(typeof status.content, "string")
  const data = JSON.parse(status.content)
  assert.equal(data.semantic_ready, false)
  assert.equal(data.host_context.host_version, "2.0.29")
  assert.equal(data.host_context.session_id, "ses_real")
  assert.equal(data.host_context.message_id, "msg_real")
  assert.equal(data.host_context.agent_id, "coder")
  assert.equal(data.host_context.directory, "C:/workspace")
  await f.tools.get("harness_run").execute({ task: "Implement a test", profile: "strict" }, invocation)
  assert.equal(f.requests[1].method, "harness.run")
  assert.equal(f.requests[1].params.workspace_ref.readonly, true)
  assert.equal(f.requests[1].params.workspace_ref.worktree, "C:/workspace")
  assert.match(f.requests[1].params.workspace_ref.identity, /^sha256:[a-f0-9]{64}$/)
  cleanup(); cleanup()
  assert.equal(f.closed(), 1)
})

test("guard blocks internal tool names; reverse semantic requests fail closed", async () => {
  const f = fixture()
  await createV2Plugin(async () => f.bridge).setup(f.ctx)
  for (const tool of ["writer_draft_internal", "writer_repair_internal", "semantic.execute_internal"]) {
    assert.throws(() => f.hooks.get("execute.before")({ tool }), /forbidden/)
  }
  assert.doesNotThrow(() => f.hooks.get("execute.before")({ tool: "read" }))
  await assert.rejects(async () => f.reverse()({ method: "semantic.execute" }), /disabled/)
  assert.deepEqual(await f.reverse()({ method: "bridge.health" }), {
    ok: true, protocol: "harness-bridge-rpc/1.0", semantic_ready: false,
  })
  assert.equal(f.requests.length, 0)
})

test("registration failure closes the bridge and propagates failure", async () => {
  const f = fixture()
  f.ctx.tool.transform = async () => { throw new Error("registry failed") }
  await assert.rejects(createV2Plugin(async () => f.bridge).setup(f.ctx), /registry failed/)
  assert.equal(f.closed(), 1)
})

test("invalid input, missing context, cancellation and bridge failures are explicit", async () => {
  const f = fixture({ request: async () => { throw new Error("peer unavailable") } })
  await createV2Plugin(async () => f.bridge).setup(f.ctx)
  const run = f.tools.get("harness_run")
  await assert.rejects(run.execute({ task: " " }, invocation), /task/)
  await assert.rejects(run.execute({ task: "x", profile: "invented" }, invocation), /profile/)
  await assert.rejects(run.execute({ task: "x", unknown: true }, invocation), /Unknown/)
  await assert.rejects(run.execute({ task: "x" }, {}), /sessionID/)
  const controller = new AbortController(); controller.abort()
  await assert.rejects(run.execute({ task: "x" }, { ...invocation, signal: controller.signal }), /abort/i)
  const result = JSON.parse((await f.tools.get("harness_status").execute({}, invocation)).content)
  assert.equal(result.ok, false)
  assert.equal(result.semantic_ready, false)
  assert.equal(result.error.code, "BRIDGE_ERROR")
})

test("default setup rejects absent Core before starting a child", async () => {
  const f = fixture()
  f.ctx.options.harnessRoot = "C:/nonexistent-harness-contract-test"
  await assert.rejects(plugin.setup(f.ctx), /bridge peer not found/)
})
