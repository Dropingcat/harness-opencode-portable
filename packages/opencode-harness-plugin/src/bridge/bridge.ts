/**
 * NDJSON full-duplex bridge transport over child-process stdio.
 * Both peers can send requests at any time; correlation is by `id`.
 */
import { createInterface } from "node:readline"
import { spawn, type ChildProcess } from "node:child_process"
import { EventEmitter } from "node:events"
import {
  type BridgeMessage,
  type BridgeRequest,
  type BridgeResponse,
  BRIDGE_PROTOCOL,
  decodeBridgeMessage,
  encodeBridgeMessage,
  errorResponse,
} from "./protocol.js"

export interface BridgePeerOptions {
  /** Timeout in ms for a single request. Default 30000. */
  requestTimeoutMs?: number
  onEvent?: (method: string, params: Record<string, unknown>) => void
}

export interface BridgeHandle {
  readonly protocol: string
  request<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T>
  notify(method: string, params: Record<string, unknown>): void
  onRequest(handler: (req: BridgeRequest) => Promise<unknown> | unknown): void
  close(): void
}

class BridgeEndpoint extends EventEmitter implements BridgeHandle {
  readonly protocol = BRIDGE_PROTOCOL
  private pending = new Map<string, { resolve: (v: unknown) => void; reject: (e: Error) => void; timer: NodeJS.Timeout }>()
  private requestHandler: ((req: BridgeRequest) => Promise<unknown> | unknown) | null = null
  private closed = false

  constructor(
    private child: ChildProcess,
    private opts: BridgePeerOptions,
  ) {
    super()
    this.child.stdout?.setEncoding("utf8")
    const rl = createInterface({ input: this.child.stdout!, crlfDelay: Infinity })
    rl.on("line", (line) => {
      if (!line.trim()) return
      let msg: BridgeMessage
      try {
        msg = decodeBridgeMessage(line)
      } catch {
        return
      }
      if ("type" in msg && msg.type === "event") {
        this.opts.onEvent?.(msg.method, msg.params)
        return
      }
      if ("method" in msg && "id" in msg) {
        // Request from the peer.
        void this.dispatch(msg as BridgeRequest)
        return
      }
      if ("id" in msg && ("ok" in msg || "error" in msg)) {
        const resp = msg as BridgeResponse
        const entry = this.pending.get(resp.id)
        if (!entry) return
        clearTimeout(entry.timer)
        this.pending.delete(resp.id)
        if (resp.ok) entry.resolve(resp.result)
        else entry.reject(new Error(`${resp.error?.code}: ${resp.error?.message}`))
      }
    })

    this.child.stderr?.setEncoding("utf8")
    this.child.stderr?.on("data", (d) => this.emit("stderr", String(d)))
    this.child.on("exit", (code, signal) => {
      this.closed = true
      for (const [, entry] of this.pending) {
        clearTimeout(entry.timer)
        entry.reject(new Error(`bridge peer exited code=${code} signal=${signal ?? ""}`))
      }
      this.pending.clear()
      this.emit("exit", code, signal)
    })
  }

  private async dispatch(req: BridgeRequest): Promise<void> {
    if (!this.requestHandler) {
      this.write(errorResponse(req.id, "NO_HANDLER", "no request handler registered"))
      return
    }
    try {
      const result = await this.requestHandler(req)
      this.write({ id: req.id, ok: true, result })
    } catch (e) {
      const err = e as Error
      this.write(errorResponse(req.id, "HANDLER_ERROR", err.message))
    }
  }

  request<T = unknown>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (this.closed) return Promise.reject(new Error("bridge closed"))
    const id = crypto.randomUUID()
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`bridge request timeout: ${method}`))
      }, this.opts.requestTimeoutMs ?? 30000)
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, timer })
      this.write({ id, method: method as never, params })
    })
  }

  notify(method: string, params: Record<string, unknown>): void {
    this.write({ type: "event", method, params })
  }

  onRequest(handler: (req: BridgeRequest) => Promise<unknown> | unknown): void {
    this.requestHandler = handler
  }

  private write(msg: BridgeMessage): void {
    this.child.stdin?.write(encodeBridgeMessage(msg) + "\n")
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    try {
      this.child.stdin?.end()
    } catch {
      /* already closed */
    }
    // Give the peer a moment to flush, then kill if needed.
    const t = setTimeout(() => {
      try {
        this.child.kill()
      } catch {
        /* already gone */
      }
    }, 500)
    t.unref()
  }
}

/**
 * Spawn the Python bridge peer (Harness Core side).
 * `pythonPath` should point to the Harness Python interpreter.
 */
export function spawnBridgePeer(
  pythonPath: string,
  coreEntry: string,
  env: Record<string, string> = {},
): BridgeHandle {
  const child = spawn(pythonPath, [coreEntry], {
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env, ...env },
    cwd: env.OPENCODE_HARNESS_ROOT || process.env.OPENCODE_HARNESS_ROOT || process.cwd(),
  })
  return new BridgeEndpoint(child, {})
}

export function createEndpoint(
  child: ChildProcess,
  opts: BridgePeerOptions = {},
): BridgeHandle {
  return new BridgeEndpoint(child, opts)
}