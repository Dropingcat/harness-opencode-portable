/**
 * harness-bridge-rpc/1.0 message contracts.
 * Line-delimited JSON-RPC over child-process stdio, full duplex.
 */
export const BRIDGE_PROTOCOL = "harness-bridge-rpc/1.0";
export function isBridgeRequest(m) {
    return "id" in m && "method" in m;
}
export function encodeBridgeMessage(m) {
    return JSON.stringify(m);
}
export function decodeBridgeMessage(line) {
    const parsed = JSON.parse(line);
    if (!parsed || typeof parsed !== "object") {
        throw new Error("bridge: non-object message");
    }
    return parsed;
}
export function okResponse(id, result) {
    return { id, ok: true, result };
}
export function errorResponse(id, code, message, detail) {
    return { id, ok: false, error: { code, message, detail } };
}
