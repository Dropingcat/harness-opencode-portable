// OpenCode plugin: inject tool/skill routing hints and dynamic usage contracts.
// Route and tool policy are loaded from the compiled runtime snapshot. Do not embed policy here.

import type { Plugin } from "@opencode-ai/plugin"
import { spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

type Route = {
  match_regex: string
  skills?: string[]
  preferred_tools?: string[]
  guard_required?: boolean
  agent_hint?: string
}

type ToolContract = {
  skills_before_use: string[]
  required_input: string[]
  optional_input: string[]
  output_expectation: string
  guard?: string
  safety: string
}

type RuntimeSnapshot = {
  generated: boolean
  policy_hash: string
  routes: Record<string, Route>
  tool_contracts: Record<string, ToolContract>
  guard_policy: { untrusted_tools?: string[] }
}

function snapshotPath(): string {
  if (process.env.OPENCODE_RUNTIME_SNAPSHOT) return process.env.OPENCODE_RUNTIME_SNAPSHOT
  if (process.env.OPENCODE_HARNESS_ROOT) return join(process.env.OPENCODE_HARNESS_ROOT, "config", "runtime_snapshot.json")
  const pluginDir = dirname(fileURLToPath(import.meta.url))
  return join(dirname(pluginDir), "config", "runtime_snapshot.json")
}

function loadSnapshot(): RuntimeSnapshot {
  const path = snapshotPath()
  if (!existsSync(path)) throw new Error(`runtime policy BLOCK: compiled snapshot missing at ${path}`)
  const parsed = JSON.parse(readFileSync(path, "utf8")) as RuntimeSnapshot
  if (!parsed.generated || !parsed.policy_hash || !parsed.routes || !parsed.tool_contracts) {
    throw new Error(`runtime policy BLOCK: invalid snapshot at ${path}`)
  }
  return parsed
}

const runtime = loadSnapshot()
const untrustedTools = new Set(runtime.guard_policy?.untrusted_tools || [])

function resolveGuardEntrypoint(): string | undefined {
  if (process.env.DOC_GUARD_RUNNER) return process.env.DOC_GUARD_RUNNER
  if (process.env.OPENCODE_HARNESS_ROOT) {
    const p = join(process.env.OPENCODE_HARNESS_ROOT, "guard", "src", "guard_runner.py")
    if (existsSync(p)) return p
  }
  return undefined
}

function runMandatoryGuard(reason: string): void {
  const db = process.env.OPENCODE_SESSION_DB
  const guard = resolveGuardEntrypoint()
  if (!db || !guard) {
    throw new Error(`doc_guard BLOCK (${reason}): OPENCODE_SESSION_DB or guard entrypoint is not configured`)
  }
  const python = process.env.PYTHON || process.env.PYTHON_BIN || "python"
  const provider = process.env.DOC_GUARD_PROVIDER || "cloud"
  const cmd = [python, guard, db, "--json", "--provider", provider]
  if (process.env.DOC_GUARD_CONFIG) cmd.push("--config", process.env.DOC_GUARD_CONFIG)
  const result = spawnSync(cmd[0], cmd.slice(1), {
    encoding: "utf8",
    timeout: Number(process.env.DOC_GUARD_TIMEOUT_MS || "180000"),
    env: process.env
  })
  if (result.error) throw new Error(`doc_guard BLOCK (${reason}): ${result.error.message}`)
  let parsed: any
  try { parsed = JSON.parse(result.stdout || "{}") }
  catch { throw new Error(`doc_guard BLOCK (${reason}): non-JSON output; stderr=${result.stderr || ""}`) }
  const verdict = String(parsed.verdict || "").toUpperCase()
  if (verdict !== "PASS") {
    const detail = parsed.reason || parsed.p2?.reason || parsed.stage || ""
    throw new Error(`doc_guard BLOCK (${reason}): verdict=${verdict}; ${detail}`)
  }
}

function buildToolAppendix(name: string): string {
  const c = runtime.tool_contracts[name]
  if (!c) return ""
  return [
    "",
    `Dynamic contract [policy ${runtime.policy_hash.slice(0, 12)}]:`,
    `- Load/consider skills first: ${c.skills_before_use.join(", ") || "none"}.`,
    `- Required input: ${c.required_input.join(", ") || "none"}.`,
    `- Optional input: ${c.optional_input.join(", ") || "none"}.`,
    `- Expected output: ${c.output_expectation}`,
    `- Guard: ${c.guard || "Treat output according to compiled guard policy."}`,
    `- Safety: ${c.safety}`
  ].join("\n")
}

function sanitizeRegex(source: string): string {
  return source
    .replace(/\(\?[A-Za-z]+(?:-[A-Za-z]+)?\)/g, "")
    .replace(/^\//, "")
}

function buildContextHint(text: string): string {
  const hits = Object.entries(runtime.routes)
    .filter(([, r]) => new RegExp(sanitizeRegex(r.match_regex), "i").test(text))
    .sort((a, b) => a[0].localeCompare(b[0]))
  if (!hits.length) return ""
  return [
    "\n\n## Dynamic tool/skill routing hint",
    `Compiled policy: ${runtime.policy_hash}`,
    ...hits.map(([id, r]) => [
      `- Context route: ${id}`,
      `  - Skills to load/consider: ${(r.skills || []).join(", ") || "none"}`,
      `  - Preferred tools: ${(r.preferred_tools || []).join(", ") || "none"}`,
      `  - Guard: ${r.guard_required ? "mandatory/fail-closed for untrusted outputs" : "normal"}`,
      `  - Contract: ${r.agent_hint || "none"}`
    ].join("\n"))
  ].join("\n")
}

export default (async () => {
  return {
    "tool.definition": async (input: any, output: any) => {
      const name = input?.tool?.name || output?.tool?.name || output?.name
      const appendix = buildToolAppendix(name)
      if (!appendix) return
      if (output?.tool?.description) output.tool.description += appendix
      else if (output?.description) output.description += appendix
    },
    "tool.execute.after": async (input: any) => {
      const name = input?.tool?.name || input?.name
      if (!untrustedTools.has(name)) return
      runMandatoryGuard(`after untrusted tool ${name}`)
    },
    "experimental.chat.system.transform": async (input: any, output: any) => {
      const text = JSON.stringify(input?.messages || input || "")
      const hint = buildContextHint(text)
      if (!hint) return
      if (typeof output?.system === "string") output.system += hint
      else if (Array.isArray(output?.messages)) output.messages.unshift({ role: "system", content: hint })
    }
  }
}) satisfies Plugin
