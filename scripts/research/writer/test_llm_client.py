#!/usr/bin/env python3
"""Тесты llm_client: мок httpx.post — content, retry при content=None, call_parallel."""

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

os.environ["AITUNNEL_KEY"] = "test-key-123"

import llm_client

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("  FAIL: " + msg)


class FakeResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def ok_data(content, finish="stop"):
    return {"choices": [{"message": {"content": content}, "finish_reason": finish}]}


def empty_data(finish="length"):
    return {"choices": [{"message": {"content": None, "reasoning": None}, "finish_reason": finish}]}


def test_llm_call_content():
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return FakeResp(ok_data("(patch-diff ok)"))

    orig = llm_client.httpx.post
    llm_client.httpx.post = fake_post
    try:
        out = llm_client.llm_call("sys", "user")
    finally:
        llm_client.httpx.post = orig

    check(out == "(patch-diff ok)", "content returned")
    check(len(calls) == 1, "one HTTP call")
    payload = calls[0]["json"]
    check(payload["model"] == "deepseek-v4-flash", "default model")
    check(payload["messages"][0]["content"] == "sys", "system message")
    check(payload["messages"][1]["content"] == "user", "user message")
    check(payload["temperature"] == 0.3, "default temperature")
    print("  test_llm_call_content: OK")


def test_llm_call_role_params():
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return FakeResp(ok_data("ok"))

    orig = llm_client.httpx.post
    llm_client.httpx.post = fake_post
    try:
        out = llm_client.llm_call("sys", "user", role="critic")
    finally:
        llm_client.httpx.post = orig

    payload = calls[0]["json"]
    check(payload["temperature"] == 0.2, "critic temperature from config")
    check(payload["max_tokens"] == 1024, "critic max_tokens from config")
    check(out == "ok", "content returned")
    print("  test_llm_call_role_params: OK")


def test_llm_call_retry_on_none():
    calls = []
    sequence = [empty_data(), ok_data("second attempt succeeded")]

    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return FakeResp(sequence.pop(0))

    orig = llm_client.httpx.post
    llm_client.httpx.post = fake_post
    try:
        out = llm_client.llm_call("sys", "user", max_tokens=256)
    finally:
        llm_client.httpx.post = orig

    check(out == "second attempt succeeded", "retry returned content")
    check(len(calls) == 2, "two attempts")
    check(calls[1]["json"]["max_tokens"] >= 2000, "retry bumped max_tokens >= 2000")
    print("  test_llm_call_retry_on_none: OK")


def test_llm_call_gives_up_empty():
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return FakeResp(empty_data())

    orig = llm_client.httpx.post
    llm_client.httpx.post = fake_post
    try:
        out = llm_client.llm_call("sys", "user")
    finally:
        llm_client.httpx.post = orig

    check("[empty response" in out, "gives up with empty response marker")
    check(len(calls) == 3, "initial + 2 retries (max_retries=2)")
    print("  test_llm_call_gives_up_empty: OK")


def test_call_parallel():
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return FakeResp(ok_data("result-" + kwargs["json"]["messages"][1]["content"]))

    orig = llm_client.httpx.post
    llm_client.httpx.post = fake_post
    try:
        tasks = [
            {"system": "s1", "user": "u1", "role": "critic"},
            {"system": "s2", "user": "u2", "role": "proofreader"},
        ]
        outs = llm_client.call_parallel(tasks)
    finally:
        llm_client.httpx.post = orig

    check(len(outs) == 2, "two results")
    check("result-u1" in outs, "first task content")
    check("result-u2" in outs, "second task content")
    check(len(calls) == 2, "two HTTP calls")
    temps = {c["json"]["messages"][1]["content"]: c["json"]["temperature"] for c in calls}
    check(temps["u1"] == 0.2, "critic temp in parallel")
    check(temps["u2"] == 0.1, "proofreader temp in parallel")
    print("  test_call_parallel: OK")


if __name__ == "__main__":
    print("=== test_llm_client ===")
    test_llm_call_content()
    test_llm_call_role_params()
    test_llm_call_retry_on_none()
    test_llm_call_gives_up_empty()
    test_call_parallel()
    print("=== results: %d passed, %d failed ===" % (passed, failed))
    sys.exit(0 if failed == 0 else 1)
