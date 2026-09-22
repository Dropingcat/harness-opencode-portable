#!/usr/bin/env python3
"""LLM-клиент блока «Писатель» через AITunnel.

Единственная точка LLM-вызовов: llm_call() для одиночных, call_parallel() для свиты.
Параметры берутся из writer_config.yaml (config_loader.get / llm_params).
Ключ — AITUNNEL_KEY из .env профиля или окружения.

При content=None — retry с max_tokens >= 2000 (до max_retries раз, конфиг).
"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from config_loader import load_config, get, llm_params


def profile_dir() -> Path:
    env = os.environ.get("HERMES_PROFILE_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


def _load_api_key() -> str:
    key = os.environ.get("AITUNNEL_KEY")
    if key:
        return key
    env_file = profile_dir() / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("AITUNNEL_KEY="):
                    return line.split("=", 1)[1].strip()
    raise RuntimeError("AITUNNEL_KEY not found: set env or add to profile .env")


def _first_content(data: dict):
    if not data.get("choices"):
        return None, None
    msg = data["choices"][0].get("message", {})
    content = msg.get("content")
    if content:
        return content, None
    reasoning = msg.get("reasoning")
    if reasoning:
        return reasoning, None
    finish = data["choices"][0].get("finish_reason")
    return None, finish


def llm_call(system: str, user: str, temperature: float = None,
             max_tokens: int = None, role: str = None) -> str:
    """Одиночный вызов AITunnel. Параметры роли подставляются из конфига."""
    cfg = load_config()
    llm = cfg.get("llm", {})
    base_url = llm.get("base_url", "https://api.aitunnel.ru/v1/")
    url = base_url.rstrip("/") + "/chat/completions"
    model = llm.get("default_model", "deepseek-v4-flash")
    timeout = llm.get("timeout_seconds", 120)
    retry_on_none = llm.get("retry_on_content_none", True)
    max_retries = llm.get("max_retries", 2)

    if role:
        params = llm_params(role)
        if temperature is None:
            temperature = params["temperature"]
        if max_tokens is None:
            max_tokens = params["max_tokens"]
        model = params.get("model", model) or model
    if temperature is None:
        temperature = get("temperature.writer", 0.3)
    if max_tokens is None:
        max_tokens = get("max_tokens.writer", 2048)

    key = _load_api_key()
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    attempts = 0
    while True:
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            attempts += 1
            if attempts > max_retries:
                return "[llm error: " + str(e) + "]"
            continue

        content, finish = _first_content(data)
        if content:
            return content

        if retry_on_none and attempts < max_retries:
            payload["max_tokens"] = max(payload.get("max_tokens", 0), 2000)
            attempts += 1
            continue

        return "[empty response, finish_reason=" + str(finish) + "]"


def _run_one(task: dict) -> str:
    return llm_call(
        task.get("system", ""),
        task.get("user", ""),
        temperature=task.get("temperature"),
        max_tokens=task.get("max_tokens"),
        role=task.get("role"),
    )


def call_parallel(tasks: list, max_workers: int = None) -> list:
    """Параллельный вызов свиты. До max_workers (по умолчанию 3 при waves_parallel)."""
    if max_workers is None:
        max_workers = 3 if get("budget.waves_parallel", True) else 1
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_run_one, t) for t in tasks]
        return [f.result() for f in futures]


if __name__ == "__main__":
    print("model:", llm_params("writer")["model"])
    print("temp:", llm_params("writer")["temperature"])
    print("call_parallel max_workers:", 3 if get("budget.waves_parallel", True) else 1)
