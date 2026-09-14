import test from "node:test"
import assert from "node:assert/strict"
import { spawnBridgePeer, createEndpoint } from "../src/bridge/bridge.js"
import { encodeBridgeMessage, decodeBridgeMessage, BRIDGE_PROTOCOL, errorResponse } from "../src/bridge/protocol.js"
import { normalizeHostContext, buildWorkspaceRef, sha256 } from "../src/host/types.js"

const ROOT = process.env.OPENCODE_HARNESS_ROOT ?? ""

test("protocol: round-trip encode/decode", () => {
  const msg = { id: "1", method: "harness.status", params: {} }
  const decoded = decodeBridgeMessage(encodeBridgeMessage(msg))
  assert.deepEqual(decoded, msg)
})

test("protocol: errorResponse shape", () => {
  const err = errorResponse("x", "NO_METHOD", "boom", { detail: 1 })
  assert.equal(err.ok, false)
  assert.equal(err.error.code, "NO_METHOD")
})

test("host types: normalizeHostContext", () => {
  const ctx = {
    sessionID: "ses-1",
    messageID: "msg-1",
    agent: "build",
    directory: "C:/proj",
    worktree: "C:/proj",
  }
  const hc = normalizeHostContext(ctx as never, { hostVersion: "1.18.16", pluginVersion: "0.1.0" })
  assert.equal(hc.schema, "host-context/1.0")
  assert.equal(hc.host, "opencode")
  assert.equal(hc.session_id, "ses-1")
})

test("host types: buildWorkspaceRef", () => {
  const ws = buildWorkspaceRef("C:/p", "C:/p", true)
  assert.equal(ws.schema, "workspace-ref/1.0")
  assert.equal(ws.readonly, true)
  assert.ok(ws.identity.startsWith("sha256:"))
})

test("host types: sha256 deterministic", () => {
  assert.equal(sha256("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
})

test("bridge: full E2E against Python peer", async () => {
  assert.ok(ROOT, "OPENCODE_HARNESS_ROOT must be set")
  const bridge = spawnBridgePeer(
    process.env.WRITER_PYTHON ?? "python",
    `${ROOT}/packages/opencode-harness-plugin/core/bridge_peer.py`,
    { OPENCODE_HARNESS_ROOT: ROOT },
  )
  try {
    const hello = await bridge.request<Record<string, unknown>>("bridge.hello", {
      plugin_semver: "0.1.0",
    })
    assert.equal(hello.schema, BRIDGE_PROTOCOL)
    assert.equal(hello.bridge_protocol_supported[0], BRIDGE_PROTOCOL)

    const status = await bridge.request<Record<string, unknown>>("harness.status", {})
    assert.equal(status.ok, true)

    const run = await bridge.request<Record<string, unknown>>("harness.run", { task: "провести научное исследование по теме" })
    assert.equal(run.ok, true)
    assert.ok(run.result && typeof run.result === "object")
  } finally {
    bridge.close()
  }
})

test("bridge: reverse request while parent pending", async () => {
  // The Python peer issues a reverse request to the plugin; the plugin's onRequest
  // handler must answer while the parent request is still pending.
  assert.ok(ROOT, "OPENCODE_HARNESS_ROOT must be set")
  const bridge = spawnBridgePeer(
    process.env.WRITER_PYTHON ?? "python",
    `${ROOT}/packages/opencode-harness-plugin/core/bridge_peer.py`,
    { OPENCODE_HARNESS_ROOT: ROOT },
  )
  let answered = false
  bridge.onRequest(async (req) => {
    if (req.method === "semantic.execute") {
      answered = true
      return { echo: req.params.value }
    }
    throw new Error("unexpected method")
  })
  try {
    const result = await bridge.request<Record<string, unknown>>("bridge.reverse_echo_test", { value: 42 })
    assert.equal(answered, true)
    assert.deepEqual(result.reverse_result, { echo: 42 })
  } finally {
    bridge.close()
  }
})

test("bridge: missing method returns error", async () => {
  assert.ok(ROOT, "OPENCODE_HARNESS_ROOT must be set")
  const bridge = spawnBridgePeer(
    process.env.WRITER_PYTHON ?? "python",
    `${ROOT}/packages/opencode-harness-plugin/core/bridge_peer.py`,
    { OPENCODE_HARNESS_ROOT: ROOT },
  )
  try {
    await assert.rejects(
      bridge.request("no.such.method", {}),
      /NO_METHOD/,
    )
  } finally {
    bridge.close()
  }
})