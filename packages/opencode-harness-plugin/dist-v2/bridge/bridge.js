/**
 * NDJSON full-duplex bridge transport over child-process stdio.
 * Both peers can send requests at any time; correlation is by `id`.
 */
import { createInterface } from "node:readline";
import { spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { BRIDGE_PROTOCOL, decodeBridgeMessage, encodeBridgeMessage, errorResponse, } from "./protocol.js";
class BridgeEndpoint extends EventEmitter {
    child;
    opts;
    protocol = BRIDGE_PROTOCOL;
    pending = new Map();
    requestHandler = null;
    closed = false;
    constructor(child, opts) {
        super();
        this.child = child;
        this.opts = opts;
        this.child.stdout?.setEncoding("utf8");
        const rl = createInterface({ input: this.child.stdout, crlfDelay: Infinity });
        rl.on("line", (line) => {
            if (!line.trim())
                return;
            let msg;
            try {
                msg = decodeBridgeMessage(line);
            }
            catch {
                return;
            }
            if ("type" in msg && msg.type === "event") {
                this.opts.onEvent?.(msg.method, msg.params);
                return;
            }
            if ("method" in msg && "id" in msg) {
                // Request from the peer.
                void this.dispatch(msg);
                return;
            }
            if ("id" in msg && ("ok" in msg || "error" in msg)) {
                const resp = msg;
                const entry = this.pending.get(resp.id);
                if (!entry)
                    return;
                clearTimeout(entry.timer);
                this.pending.delete(resp.id);
                if (resp.ok)
                    entry.resolve(resp.result);
                else
                    entry.reject(new Error(`${resp.error?.code}: ${resp.error?.message}`));
            }
        });
        this.child.stderr?.setEncoding("utf8");
        this.child.stderr?.on("data", (d) => this.emit("stderr", String(d)));
        this.child.on("exit", (code, signal) => {
            this.closed = true;
            for (const [, entry] of this.pending) {
                clearTimeout(entry.timer);
                entry.reject(new Error(`bridge peer exited code=${code} signal=${signal ?? ""}`));
            }
            this.pending.clear();
            this.emit("exit", code, signal);
        });
    }
    async dispatch(req) {
        if (!this.requestHandler) {
            this.write(errorResponse(req.id, "NO_HANDLER", "no request handler registered"));
            return;
        }
        try {
            const result = await this.requestHandler(req);
            this.write({ id: req.id, ok: true, result });
        }
        catch (e) {
            const err = e;
            this.write(errorResponse(req.id, "HANDLER_ERROR", err.message));
        }
    }
    request(method, params = {}) {
        if (this.closed)
            return Promise.reject(new Error("bridge closed"));
        const id = crypto.randomUUID();
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(id);
                reject(new Error(`bridge request timeout: ${method}`));
            }, this.opts.requestTimeoutMs ?? 30000);
            this.pending.set(id, { resolve: resolve, reject, timer });
            this.write({ id, method: method, params });
        });
    }
    notify(method, params) {
        this.write({ type: "event", method, params });
    }
    onRequest(handler) {
        this.requestHandler = handler;
    }
    write(msg) {
        this.child.stdin?.write(encodeBridgeMessage(msg) + "\n");
    }
    close() {
        if (this.closed)
            return;
        this.closed = true;
        try {
            this.child.stdin?.end();
        }
        catch {
            /* already closed */
        }
        // Give the peer a moment to flush, then kill if needed.
        const t = setTimeout(() => {
            try {
                this.child.kill();
            }
            catch {
                /* already gone */
            }
        }, 500);
        t.unref();
    }
}
/**
 * Spawn the Python bridge peer (Harness Core side).
 * `pythonPath` should point to the Harness Python interpreter.
 */
export function spawnBridgePeer(pythonPath, coreEntry, env = {}) {
    const child = spawn(pythonPath, [coreEntry], {
        stdio: ["pipe", "pipe", "pipe"],
        env: { ...process.env, ...env },
        cwd: env.OPENCODE_HARNESS_ROOT || process.env.OPENCODE_HARNESS_ROOT || process.cwd(),
    });
    return new BridgeEndpoint(child, {});
}
export function createEndpoint(child, opts = {}) {
    return new BridgeEndpoint(child, opts);
}
