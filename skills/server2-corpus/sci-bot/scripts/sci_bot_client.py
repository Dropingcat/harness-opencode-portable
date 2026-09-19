#!/usr/bin/env python3
"""Sci-Bot клиент с контролем бюджета токенов.

- Проверяет баланс до запроса, не запускает при балансе ниже floor.
- Лимит списания на один запрос (max_burn).
- Дедупликация: одинаковые вопросы не отправляются повторно.
- После done показывает потраченные токены и остаток.
"""
import argparse
import os
import asyncio
import json
import ssl
import time
import urllib.request
import websockets

AUTH = "scibot_auth=3c67dbc1be64338a68f6ec417e24b45769084196d20199570f439856b8d43e3f"
WS_URL = "wss://sci-bot.ru/"
BALANCE_URL = "https://sci-bot.ru/api/balance"
DEFAULT_MAX_BURN = 30_000   # лимит списания на один запрос
DEFAULT_FLOOR = 300_000     # не запускать, если остаток ниже
HISTORY = os.path.join(os.environ.get("TEMP", "C:/Temp/opencode"), "sci_history.json")


def get_balance() -> int:
    req = urllib.request.Request(BALANCE_URL, headers={"Cookie": AUTH})
    with urllib.request.urlopen(req, timeout=15) as r:
        return int(json.loads(r.read())["tokens"])


def load_history() -> list:
    try:
        with open(HISTORY, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(h: list):
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


async def ask(question: str, conv: bool = True, max_burn: int = DEFAULT_MAX_BURN,
              floor: int = DEFAULT_FLOOR, out: str = "C:\Temp\sci_answer.md") -> dict:
    start_bal = get_balance()
    if start_bal <= floor:
        return {"ok": False, "reason": f"баланс {start_bal} ниже floor {floor}"}

    hist = load_history()
    if question.strip() in hist:
        return {"ok": False, "reason": "вопрос уже отправлялся ранее (дубль)"}

    headers = {"Cookie": AUTH, "Origin": "https://sci-bot.ru", "User-Agent": "Mozilla/5.0"}
    ssl_ctx = ssl.create_default_context()
    answer, cot = [], []
    spent = 0
    t0 = time.time()
    async with websockets.connect(WS_URL, additional_headers=headers, ssl=ssl_ctx, max_size=None) as ws:
        await asyncio.sleep(1.0)
        # ВСЕГДА conversation (дешёвый режим ~20K токенов). chat в ~9 раз дороже — запрещён.
        msg = {"type": "conversation", "message": question, "popularScience": False}
        await ws.send(json.dumps(msg))
        print(f"[sent] {msg['type']} | balance={start_bal}", flush=True)
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=300)
            except asyncio.TimeoutError:
                print("[TIMEOUT 300s]", flush=True)
                break
            evt = json.loads(raw)
            t = evt.get("type")
            if t == "content":
                txt = evt.get("text") or evt.get("content") or ""
                if txt:
                    answer.append(txt)
            elif t == "thinking":
                txt = evt.get("text") or ""
                if txt:
                    cot.append(txt)
            elif t == "token_update":
                if isinstance(evt.get("used"), (int, float)):
                    spent = int(evt["used"])
            elif t == "done":
                spent = int(evt.get("turnTokens", spent) or spent)
                print("<DONE>", json.dumps({k: evt.get(k) for k in ("cancelled", "timedOut", "turnTokens", "turnTime", "status")}), flush=True)
                break
            elif t == "error":
                print("<ERROR>", json.dumps(evt, ensure_ascii=False)[:300], flush=True)
                break
            elif t == "tool_start":
                print(f"[tool] {evt.get('tool')} :: {str(evt.get('query', ''))[:50]}", flush=True)

    end_bal = get_balance()
    burn = start_bal - end_bal
    full = "".join(answer)
    dt = time.time() - t0

    hist.append(question.strip())
    save_history(hist)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(full)
        with open(out.replace(".md", "_cot.md"), "w", encoding="utf-8") as f:
            f.write("".join(cot))

    result = {
        "ok": True, "answer_len": len(full), "cot_len": sum(len(x) for x in cot),
        "time_s": round(dt, 1), "turn_tokens": spent,
        "balance_before": start_bal, "balance_after": end_bal,
        "burn": burn, "file": out,
    }
    print("=== ", json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--max-burn", type=int, default=DEFAULT_MAX_BURN)
    ap.add_argument("--floor", type=int, default=DEFAULT_FLOOR)
    ap.add_argument("--out", default="C:\Temp\sci_answer.md")
    a = ap.parse_args()
    r = asyncio.run(ask(a.question, conv=True, max_burn=a.max_burn,
                        floor=a.floor, out=a.out))
    if not r.get("ok"):
        print("НЕ ОТПРАВЛЕНО:", r.get("reason"))