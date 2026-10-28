/**
 * Paper Review System — OpenCode V2 plugin.
 *
 * Port of the Claude plugin's SessionStart hook (hooks/hooks.json -> check-deps.sh)
 * to the OpenCode plugin model:
 *   - on plugin setup, run the dependency check (check-deps.py) with the harness
 *     .venv interpreter and remember the result,
 *   - on every session "context" hook, if required dependencies are missing,
 *     push a short system note so agents/dev see the state early.
 *
 * The Claude originals (.claude-plugin/plugin.json, .mcp.json, hooks/hooks.json)
 * are Claude-specific and not interpreted by OpenCode; this module and the
 * .opencode/opencode.json mcp section are their OpenCode equivalents.
 *
 * Dependency-free V2 Promise definition (mirrors packages/opencode-harness-plugin).
 */
import { existsSync } from "node:fs"
import { resolve, join } from "node:path"
import { fileURLToPath } from "node:url"
import { spawn } from "node:child_process"

const PLUGIN_VERSION = "2.2.0"

function harnessRoot(ctx) {
  const packageRoot = fileURLToPath(new URL("../../", import.meta.url)) // packages/paper-review-plugin/
  const defaultRoot = resolve(packageRoot, "../..")                     // E:\opencode_harness_portable
  return resolve(ctx.options?.harnessRoot || process.env.OPENCODE_HARNESS_ROOT || defaultRoot)
}

function pythonPath(ctx, root) {
  const candidates = [
    ctx.options?.pythonPath,
    process.env.WRITER_PYTHON,
    process.env.PYTHON_BIN,
    process.env.PYTHON,
    join(root, ".venv", "Scripts", "python.exe"),
  ].filter(Boolean)
  return candidates[0]
}

function runDepsCheck(python, script) {
  return new Promise((resolveP) => {
    const child = spawn(python, [script, "--json"], {
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    })
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (d) => { stdout += String(d) })
    child.stderr.on("data", (d) => { stderr += String(d) })
    child.on("error", (err) => resolveP({ ok: false, error: String(err.message || err) }))
    child.on("close", (code) => {
      let report = {}
      try { report = JSON.parse(stdout) } catch { /* tolerate non-json */ }
      resolveP({
        ok: code === 0 && report.all_required_ok === true,
        exit_code: code,
        missing: report.missing || [],
        optional_installed: report.optional_installed || [],
        stderr: (stderr || "").trim(),
      })
    })
  })
}

export function createV2Plugin(connect = null) {
  return {
    id: "paper-review.system.v2",
    version: PLUGIN_VERSION,
    async setup(ctx) {
      // Never let plugin failures break the app, but DO surface them in the
      // opencode server log so a silently-unregistered hook is detectable.
      // ctx.session.hook("context", ...) is the documented model-request hook
      // (docs: Sessions -> Model requests -> context), pushed into the assembled
      // system instructions on every agent-loop model call.
      try {
        const root = harnessRoot(ctx)
        const python = pythonPath(ctx, root)
        const script = join(root, "scripts", "paper-review", "check-deps.py")
        const deps = existsSync(script) && python
          ? await runDepsCheck(python, script)
          : { ok: false, error: `check-deps not runnable (script=${script}, python=${python})` }

        await ctx.storage.set("paper-review.deps", {
          checked_at: new Date().toISOString(),
          ok: deps.ok,
          missing: deps.missing || [],
          optional_installed: deps.optional_installed || [],
          plugin_version: PLUGIN_VERSION,
        })

        const note = deps.ok
          ? null
          : `Paper Review System: missing runtime dependencies (${(deps.missing || []).join(", ") || deps.error}). ` +
            "Run check-deps or install requirements before PDF parsing/verification workflows."

        const registration = await ctx.session.hook("context", (event) => {
          if (!note) return
          try { event.system.push({ type: "text", text: note }) } catch (err) {
            console.error(`[paper-review] context hook push failed: ${err && (err.message || err)}`)
          }
        })

        console.log(`[paper-review] setup ok (deps=${deps.ok ? "ok" : "missing"}, hook=context registered)`)
        return async () => {
          try { await registration.dispose(); console.log("[paper-review] context hook disposed") }
          catch (err) { console.error(`[paper-review] hook dispose failed: ${err && (err.message || err)}`) }
        }
      } catch (error) {
        // Surface, do not rethrow: the harness plugin remains authoritative and
        // a failing setup must never crash the server.
        console.error(`[paper-review] setup failed: ${error && (error.message || error)}`)
        const safe = async () => {}
        return safe
      }
    },
  }
}

export default createV2Plugin()