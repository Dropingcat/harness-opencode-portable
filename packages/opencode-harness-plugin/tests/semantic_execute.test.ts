import test from "node:test"
import assert from "node:assert/strict"
import { semanticExecute } from "../src/tools/semantic_execute.js"

function fakeClient(overrides: Record<string, unknown> = {}) {
  const calls: string[] = []
  const client = {
    session: {
      create: async (opts: { body?: { parentID?: string } }) => {
        calls.push("create")
        return { data: { id: "child-1", parentID: opts.body?.parentID } }
      },
      prompt: async () => {
        calls.push("prompt")
        return { data: { info: {}, parts: [{ type: "text", text: "ANSWER" }] } }
      },
      abort: async () => {
        calls.push("abort")
        return { data: {} }
      },
    },
    ...overrides,
  }
  return { client, calls }
}

const request = (overrides: Record<string, unknown> = {}) => ({
  schema: "semantic-execution-request/1.0",
  execution_id: "ex-1",
  purpose: "TRIBUNAL_ROLE",
  contract_schema: "tribunal-role/1.0",
  parent_host_session_id: "parent-1",
  bounded_input: { question: "q" },
  expected_output: {},
  model_policy: { provider_id: "opencode", model_id: "big-pickle" },
  permission_profile: "readonly",
  timeout_ms: 10000,
  trace: {},
  ...overrides,
})

function toolCtx(sessionID = "parent-1") {
  return {
    sessionID,
    messageID: "m-1",
    agent: "build",
    directory: "C:/p",
    worktree: "C:/p",
  } as never
}

test("semantic_execute: happy path returns completed result", async () => {
  const { client, calls } = fakeClient()
  const toolDef = semanticExecute(client as never, { hostVersion: () => "1.18.30", pluginVersion: "0.1.0" })
  const out = await (toolDef as unknown as { execute: (a: Record<string, unknown>, c: unknown) => Promise<{ output: string }> })
    .execute({ request: JSON.stringify(request()) }, toolCtx())
  const parsed = JSON.parse(out.output) as Record<string, unknown>
  assert.equal(parsed.ok, true)
  assert.equal(parsed.runtime_status, "COMPLETED")
  assert.equal(parsed.host_session_id, "child-1")
  assert.equal((parsed.structured_output as { text: string }).text, "ANSWER")
  assert.deepEqual(calls, ["create", "prompt"])
})

test("semantic_execute: rejects wrong schema", async () => {
  const { client } = fakeClient()
  const toolDef = semanticExecute(client as never, { hostVersion: () => "1.18.30", pluginVersion: "0.1.0" })
  const out = await (toolDef as unknown as { execute: (a: Record<string, unknown>, c: unknown) => Promise<{ output: string }> })
    .execute({ request: JSON.stringify(request({ schema: "wrong" })) }, toolCtx())
  const parsed = JSON.parse(out.output) as Record<string, unknown>
  assert.equal(parsed.ok, false)
  assert.equal(parsed.error.code, "BAD_SCHEMA")
})

test("semantic_execute: timeout aborts child and returns TIMED_OUT", async () => {
  const { client, calls } = fakeClient({
    session: {
      create: async () => ({ data: { id: "child-1" } }),
      // prompt never resolves -> timeout wins
      prompt: () => new Promise(() => {}),
      abort: async () => {
        calls.push("abort")
        return { data: {} }
      },
    },
  })
  const toolDef = semanticExecute(client as never, { hostVersion: () => "1.18.30", pluginVersion: "0.1.0" })
  const out = await (toolDef as unknown as { execute: (a: Record<string, unknown>, c: unknown) => Promise<{ output: string }> })
    .execute({ request: JSON.stringify(request({ timeout_ms: 50 })) }, toolCtx())
  const parsed = JSON.parse(out.output) as Record<string, unknown>
  assert.equal(parsed.ok, false)
  assert.equal(parsed.runtime_status, "TIMED_OUT")
  assert.ok(calls.includes("abort"))
})

test("semantic_execute: parent session id is linked", async () => {
  let linkedParent: string | undefined
  const { client } = fakeClient({
    session: {
      create: async (opts: { body?: { parentID?: string } }) => {
        linkedParent = opts.body?.parentID
        return { data: { id: "child-1" } }
      },
      prompt: async () => ({ data: { info: {}, parts: [{ type: "text", text: "X" }] } }),
      abort: async () => ({ data: {} }),
    },
  })
  const toolDef = semanticExecute(client as never, { hostVersion: () => "1.18.30", pluginVersion: "0.1.0" })
  await (toolDef as unknown as { execute: (a: Record<string, unknown>, c: unknown) => Promise<{ output: string }> })
    .execute({ request: JSON.stringify(request()) }, toolCtx("parent-42"))
  assert.equal(linkedParent, "parent-42")
})