import test from "node:test"
import assert from "node:assert/strict"
import { pathToFileURL } from "node:url"
import { join } from "node:path"
import { createPlanningPlugin, PLANNING_MARKER } from "../src/index.js"

assert.ok(process.env.SUPERPOWERS_ROOT, "Set SUPERPOWERS_ROOT to the reviewed upstream checkout")
const { default: upstream } = await import(pathToFileURL(join(process.env.SUPERPOWERS_ROOT, "index.js")))
let sequence = 0

function fixture({ child = false, existing = [] } = {}) {
  const sessionID = `ses_planning_${++sequence}`
  const skills = new Map(existing.map(s => [s.id, s]))
  const hooks = []
  let skillDisposals = 0
  const agents = [{ id: "reviewer", mode: "subagent", permissions: [{ action: "edit", effect: "deny" }] }]
  const ctx = {
    app: { version: "2.0.32" },
    agent: { list: async () => agents, transform: () => assert.fail("Must not rewrite agents") },
    tool: { transform: () => assert.fail("Must not change tools or permissions") },
    skill: { transform: async callback => {
      callback({ get: id => skills.get(id), list: () => [...skills.values()], add: skill => skills.set(skill.id, skill) })
      return { dispose() { skillDisposals++ } }
    } },
    session: {
      get: async () => ({ id: sessionID, ...(child ? { parentID: "ses_parent" } : {}) }),
      hook: async (name, callback) => {
        assert.equal(name, "context")
        const record = { callback, active: true }
        hooks.push(record)
        return { dispose() { record.active = false } }
      },
      prompt: () => assert.fail("Must not send synthetic tasks or interrupt sessions"),
    },
  }
  const event = (messages = [{ role: "user", content: [{ type: "text", text: "Return the requested JSON only." }] }]) => ({
    sessionID, agent: "reviewer", system: [{ type: "text", text: "Existing role contract" }],
    messages, tools: { read: { description: "read only" } }, options: {},
  })
  const invoke = async e => { for (const h of hooks) if (h.active) await h.callback(e); return e }
  return { ctx, skills, hooks, agents, event, invoke, skillDisposals: () => skillDisposals }
}

test("controller gets upstream Superpowers plus the basic planning cycle", async () => {
  const f = fixture()
  const plugin = createPlanningPlugin(upstream)
  assert.equal(typeof plugin.setup, "function")
  await plugin.setup(f.ctx)
  const e = await f.invoke(f.event())
  assert.ok(e.system.some(p => p.text.includes(PLANNING_MARKER)))
  assert.ok(e.messages[0].content.some(p => p.text.includes("You have superpowers")))
  assert.ok(f.skills.has("brainstorming"))
})

test("child gets the same short cycle without restarting controller brainstorming", async () => {
  const f = fixture({ child: true })
  await createPlanningPlugin(upstream).setup(f.ctx)
  const e = f.event()
  const originalMessages = structuredClone(e.messages)
  await f.invoke(e)
  assert.ok(e.system.some(p => p.text.includes(PLANNING_MARKER)))
  assert.deepEqual(e.messages, originalMessages)
  assert.ok(f.skills.has("executing-plans"))
})

test("existing user skills, agent contracts and read-only tool sets are preserved", async () => {
  const local = { id: "test-driven-development", name: "Local TDD", path: "C:/user/SKILL.md", content: "User-owned instructions" }
  const f = fixture({ existing: [local], child: true })
  const agentsBefore = structuredClone(f.agents)
  await createPlanningPlugin(upstream).setup(f.ctx)
  const e = f.event()
  const toolsBefore = structuredClone(e.tools)
  await f.invoke(e)
  assert.deepEqual(f.skills.get(local.id), local)
  assert.deepEqual(f.agents, agentsBefore)
  assert.deepEqual(e.tools, toolsBefore)
  assert.equal(e.system[0].text, "Existing role contract")
})

test("policy is injected once per outgoing context, without keyword triggers", async () => {
  const f = fixture({ child: true })
  await createPlanningPlugin(upstream).setup(f.ctx)
  const e = f.event([{ role: "user", content: [{ type: "text", text: "Rename a heading." }] }])
  await f.invoke(e)
  await f.invoke(e)
  assert.equal(e.system.filter(p => p.text.includes(PLANNING_MARKER)).length, 1)
  const policy = e.system.find(p => p.text.includes(PLANNING_MARKER)).text
  for (const state of ["PLAN", "ACT", "CHECK", "WAIT_CHILDREN", "DONE", "BLOCKED"]) assert.ok(policy.includes(state))
})

test("fresh requests retain the cycle without relying on saved transcript edits", async () => {
  const f = fixture({ child: true })
  await createPlanningPlugin(upstream).setup(f.ctx)
  for (let i = 0; i < 3; i++) {
    const e = await f.invoke(f.event())
    assert.equal(e.system.filter(p => p.text.includes(PLANNING_MARKER)).length, 1)
    assert.equal(e.messages[0].content[0].text, "Return the requested JSON only.")
  }
})

test("after compaction controller recovers its bootstrap and child keeps only the short cycle", async () => {
  for (const child of [false, true]) {
    const f = fixture({ child })
    await createPlanningPlugin(upstream).setup(f.ctx)
    const e = await f.invoke(f.event([{ role: "assistant", content: [{ type: "text", text: "Checkpoint" }] }]))
    assert.ok(e.system.some(p => p.text.includes(PLANNING_MARKER)))
    assert.equal(e.messages.some(m => m.role === "user"), !child)
    assert.equal(e.messages[0].content[0].text, "Checkpoint")
  }
})

test("session lookup failure defers heavy controller bootstrap, but not the common cycle", async () => {
  const f = fixture({ child: true })
  f.ctx.session.get = async () => { throw new Error("temporary session lookup failure") }
  await createPlanningPlugin(upstream).setup(f.ctx)
  const e = await f.invoke(f.event())
  assert.ok(e.system.some(p => p.text.includes(PLANNING_MARKER)))
  assert.equal(e.messages[0].content.length, 1, "An unknown child must not restart controller design")
})

test("mismatched session identity never triggers controller bootstrap", async () => {
  const f = fixture()
  f.ctx.session.get = async () => ({ id: "ses_someone_else" })
  await createPlanningPlugin(upstream).setup(f.ctx)
  const e = await f.invoke(f.event())
  assert.equal(e.messages[0].content.length, 1)
  assert.ok(e.system.some(p => p.text.includes(PLANNING_MARKER)))
})

test("temporary lookup failure is not cached as a controller or child decision", async () => {
  const f = fixture()
  let calls = 0
  const get = f.ctx.session.get
  f.ctx.session.get = async input => {
    if (++calls === 1) throw new Error("retry on the next request")
    return get(input)
  }
  await createPlanningPlugin(upstream).setup(f.ctx)
  const first = await f.invoke(f.event())
  assert.equal(first.messages[0].content.length, 1)
  const recovered = await f.invoke(f.event())
  assert.ok(recovered.messages[0].content.some(p => p.text.includes("You have superpowers")))
})

test("cleanup releases all owned hooks and skill registrations exactly once", async () => {
  const f = fixture()
  const cleanup = await createPlanningPlugin(upstream).setup(f.ctx)
  assert.equal(f.hooks.filter(h => h.active).length, 2)
  await cleanup()
  await cleanup()
  assert.equal(f.hooks.filter(h => h.active).length, 0)
  assert.equal(f.skillDisposals(), 1)
})

test("concurrent cache eviction cannot expose a child to controller bootstrap", async () => {
  const f = fixture({ child: true })
  const attempts = new Map()
  f.ctx.session.get = async ({ sessionID }) => {
    const count = (attempts.get(sessionID) ?? 0) + 1
    attempts.set(sessionID, count)
    if (count > 1) throw new Error("Repeat lookup unavailable after eviction")
    return { id: sessionID, parentID: "ses_parent" }
  }
  await createPlanningPlugin(upstream).setup(f.ctx)
  const events = Array.from({ length: 257 }, (_, i) => ({
    ...f.event(), sessionID: `ses_concurrent_${sequence}_${i}`,
  }))
  await Promise.all(events.map(e => f.invoke(e)))
  const leaked = events.filter(e => e.messages.some(m => m.content.some(p => p.text?.includes("You have superpowers"))))
  assert.equal(leaked.length, 0, "Verified child identity must be held across the hook call")
  assert.ok(events.every(e => e.system.some(p => p.text.includes(PLANNING_MARKER))))
})
