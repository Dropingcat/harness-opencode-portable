import test from "node:test"
import assert from "node:assert/strict"

const { createV2Plugin } = await import(process.env.HARNESS_V2_ENTRY || new URL("../src/v2/index.js", import.meta.url).href)

function fixture(request = async () => ({ ok: true })) {
  const tools = new Map()
  let calls = 0
  let closed = 0
  const bridge = {
    protocol: "harness-bridge-rpc/1.0",
    onRequest() {},
    request: async (...args) => { calls++; return request(...args) },
    close: () => { closed++ },
  }
  const ctx = {
    app: { version: "2.0.29" }, location: { directory: "C:/independent-workspace" },
    tool: { hook: async () => {}, transform: async (fn) => fn({ add: (tool) => tools.set(tool.name, tool) }) },
  }
  return { ctx, bridge, tools, calls: () => calls, closed: () => closed }
}
const invocation = { sessionID: "ses_tester", messageID: "msg_tester", agent: "tester" }

test("independent: invalid input matrix and missing host identity never reach RPC", async () => {
  const f = fixture()
  const cleanup = await createV2Plugin(async () => f.bridge).setup(f.ctx)
  try {
    for (const input of [null, [], "status", { verbose: "true" }, { extra: true }]) {
      await assert.rejects(f.tools.get("harness_status").execute(input, invocation))
    }
    for (const input of [{ task: "x", route: " " }, { task: 42 }, { task: "x", profile: null }]) {
      await assert.rejects(f.tools.get("harness_run").execute(input, invocation))
    }
    for (const key of ["sessionID", "messageID", "agent"]) {
      await assert.rejects(f.tools.get("harness_status").execute({}, { ...invocation, [key]: " " }))
    }
    assert.equal(f.calls(), 0)
  } finally { cleanup() }
})

test("independent: cancellation during RPC rejects, cleanup is idempotent, closed tools cannot dispatch", async () => {
  const controller = new AbortController()
  const f = fixture(async () => { controller.abort(); return { ok: true } })
  const cleanup = await createV2Plugin(async () => f.bridge).setup(f.ctx)
  try {
    await assert.rejects(f.tools.get("harness_status").execute({}, { ...invocation, signal: controller.signal }), /abort/i)
  } finally { cleanup(); cleanup() }
  const result = JSON.parse((await f.tools.get("harness_run").execute({ task: "x" }, invocation)).content)
  assert.equal(result.ok, false)
  assert.equal(result.semantic_ready, false)
  assert.equal(result.error.code, "BRIDGE_ERROR")
  assert.equal(f.calls(), 1)
  assert.equal(f.closed(), 1)
})

test("independent: hook-registration failure closes owned bridge exactly once", async () => {
  const f = fixture()
  f.ctx.tool.hook = async () => { throw new Error("independent hook failure") }
  await assert.rejects(createV2Plugin(async () => f.bridge).setup(f.ctx), /independent hook failure/)
  assert.equal(f.closed(), 1)
  assert.equal(f.calls(), 0)
  assert.equal(f.tools.size, 0)
})
