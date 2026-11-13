"""
Test suite for llm_client.py

Run directly: python test_llm_client.py
No network needed — a fake "post" and a fake "sleep" replace the real ones.
"""

import os

import requests

from llm_client import (
    LLMError,
    LLMFatalError,
    build_tool_messages,
    call_model,
    max_tokens_from_env,
    models_from_env,
    parse_tool_arguments,
)

SECRET = "sk-or-TEST-SECRET-123"
GOOD = {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}


class FakeResponse:
    def __init__(self, status=200, body=None, text=None, bad_json=False):
        self.status_code = status
        self._body = body
        self._bad_json = bad_json
        self.text = text if text is not None else str(body)

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._body


class FakePost:
    """Returns scripted replies per model name and records every call."""

    def __init__(self, script):
        self.script = {m: list(replies) for m, replies in script.items()}
        self.calls = []  # list of (model, headers, payload)

    def __call__(self, url, headers=None, json=None, timeout=None):
        model = json["model"]
        self.calls.append((model, headers, json))
        reply = self.script[model].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def count(self, model):
        return sum(1 for c in self.calls if c[0] == model)


class FakeSleep:
    def __init__(self):
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)


def run_call(script, models, **kw):
    post = FakePost(script)
    sleep = FakeSleep()
    result = call_model(
        [{"role": "user", "content": "x"}],
        [{"type": "function"}],
        api_key=SECRET,
        url="http://fake",
        models=models,
        post=post,
        sleep=sleep,
        **kw,
    )
    return result, post, sleep


def expect_error(script, models, exc_type):
    post = FakePost(script)
    sleep = FakeSleep()
    try:
        call_model(
            [], [], api_key=SECRET, url="http://fake", models=models,
            post=post, sleep=sleep,
        )
    except exc_type as exc:
        return exc, post, sleep
    except Exception as exc:  # wrong kind of error
        return exc, post, sleep
    return None, post, sleep


def run_all_tests():
    results = []

    def check(ok, label):
        print(f"{'PASS' if ok else 'FAIL'}: {label}")
        results.append(bool(ok))

    # ---------- call_model: happy path ----------
    (data, used), post, sleep = run_call({"A": [FakeResponse(200, GOOD)]}, ["A"])
    check(data == GOOD and used == "A" and post.count("A") == 1, "success on first try returns data and model used")

    _, headers, payload = post.calls[0]
    check(headers["Authorization"] == f"Bearer {SECRET}", "API key is sent in the Authorization header")
    check(payload["tool_choice"] == "auto" and payload["max_tokens"] == 4096 and "tools" in payload,
          "payload keeps tools, tool_choice and max_tokens")

    # ---------- retry on temporary errors ----------
    (data, used), post, sleep = run_call(
        {"A": [FakeResponse(429, {"error": {"message": "slow down"}}), FakeResponse(200, GOOD)]}, ["A"])
    check(used == "A" and post.count("A") == 2 and sleep.waits == [1], "429 is retried once with a 1-second wait, then succeeds")

    (data, used), post, sleep = run_call(
        {"A": [FakeResponse(503, {"error": "down"})] * 3, "B": [FakeResponse(200, GOOD)]}, ["A", "B"])
    check(used == "B" and post.count("A") == 3 and sleep.waits == [1, 2],
          "5xx is retried 3 times with growing waits, then falls back to the next model")

    # ---------- network problems ----------
    (data, used), post, sleep = run_call(
        {"A": [requests.Timeout("t")] * 3, "B": [FakeResponse(200, GOOD)]}, ["A", "B"])
    check(used == "B" and post.count("A") == 3, "timeouts are retried then fall back to the next model")

    (data, used), post, sleep = run_call(
        {"A": [requests.ConnectionError("c"), FakeResponse(200, GOOD)]}, ["A"])
    check(used == "A" and post.count("A") == 2, "a dropped connection is retried")

    # ---------- model not available -> skip straight to next ----------
    (data, used), post, sleep = run_call(
        {"A": [FakeResponse(404, {"error": {"message": "no such model"}})], "B": [FakeResponse(200, GOOD)]}, ["A", "B"])
    check(used == "B" and post.count("A") == 1 and sleep.waits == [], "404 skips to the next model immediately with no retry")

    # ---------- hidden errors inside a 200 ----------
    (data, used), post, sleep = run_call(
        {"A": [FakeResponse(200, {"error": {"message": "provider hiccup"}}), FakeResponse(200, GOOD)]}, ["A"])
    check(used == "A" and post.count("A") == 2, "an error hidden inside a 200 reply is retried")

    (data, used), post, sleep = run_call(
        {"A": [FakeResponse(200, bad_json=True, text="<html>oops</html>"), FakeResponse(200, GOOD)]}, ["A"])
    check(used == "A" and post.count("A") == 2, "a 200 reply that is not JSON is retried")

    # ---------- fatal problems must NOT fall back ----------
    exc, post, sleep = expect_error(
        {"A": [FakeResponse(401, {"error": {"message": "bad key"}})], "B": [FakeResponse(200, GOOD)]}, ["A", "B"], LLMFatalError)
    check(isinstance(exc, LLMFatalError) and "API key" in str(exc) and post.count("B") == 0,
          "401 stops immediately with a clear key message and never tries other models")

    # 402 (out of credits) used to stop everything. A free model later in the
    # chain can still work, so it now moves on to the next model instead.
    (data, used), post, sleep = run_call(
        {"A": [FakeResponse(402, {"error": {"message": "no credits"}})], "B": [FakeResponse(200, GOOD)]}, ["A", "B"])
    check(used == "B" and post.count("A") == 1 and sleep.waits == [],
          "402 on a paid model falls through to the next model with no retry")

    exc, post, sleep = expect_error(
        {"A": [FakeResponse(402, {"error": {"message": "no credits"}})]}, ["A"], LLMFatalError)
    check(isinstance(exc, LLMFatalError) and "credits" in str(exc) and "OBSIDIAN_MODELS" in str(exc),
          "402 with no other model gives a clear credits message that says how to fix it")

    exc, post, sleep = expect_error(
        {"A": [FakeResponse(402, {"error": {"message": "no credits"}})], "B": [FakeResponse(404, {"error": "gone"})]}, ["A", "B"], LLMFatalError)
    check(isinstance(exc, LLMFatalError) and "credits" in str(exc) and "A:" in str(exc) and "B:" in str(exc),
          "if every model fails and one was a 402, the error still points at credits and lists each model")

    exc, post, sleep = expect_error(
        {"A": [FakeResponse(402, {"error": {"message": "no credits"}})]}, ["A"], LLMFatalError)
    check(SECRET not in str(exc), "the API key never appears in a credits error")

    exc, post, sleep = expect_error(
        {"A": [FakeResponse(400, {"error": {"message": "bad request"}})], "B": [FakeResponse(200, GOOD)]}, ["A", "B"], LLMFatalError)
    check(isinstance(exc, LLMFatalError) and post.count("B") == 0, "400 stops immediately (switching models cannot fix it)")

    # ---------- everything failed ----------
    exc, post, sleep = expect_error(
        {"A": [FakeResponse(404, {"error": "gone"})], "B": [FakeResponse(404, {"error": "gone"})]}, ["A", "B"], LLMError)
    check(isinstance(exc, LLMError) and not isinstance(exc, LLMFatalError)
          and "A:" in str(exc) and "B:" in str(exc), "when every model fails, the error lists what happened for each")
    check(SECRET not in str(exc), "the API key never appears in error messages")

    exc, post, sleep = expect_error({}, [], LLMFatalError)
    check(isinstance(exc, LLMFatalError), "an empty model list is rejected clearly")

    # ---------- models_from_env ----------
    os.environ.pop("OBSIDIAN_MODELS", None)
    check(models_from_env(["default/m"]) == ["default/m"], "no env var -> default model list")
    os.environ["OBSIDIAN_MODELS"] = " a/x , b/y ,, c/z "
    check(models_from_env(["default/m"]) == ["a/x", "b/y", "c/z"], "env var is split on commas and trimmed")
    os.environ["OBSIDIAN_MODELS"] = "  "
    check(models_from_env(["default/m"]) == ["default/m"], "blank env var -> default model list")
    os.environ.pop("OBSIDIAN_MODELS", None)

    # ---------- M10: max_tokens_from_env ----------
    os.environ.pop("OBSIDIAN_MAX_TOKENS", None)
    check(max_tokens_from_env() == 2000, "no env var -> default reply cap is 2000 tokens")
    os.environ["OBSIDIAN_MAX_TOKENS"] = " 1500 "
    check(max_tokens_from_env() == 1500, "env var value is used (spaces trimmed)")
    os.environ["OBSIDIAN_MAX_TOKENS"] = "abc"
    check(max_tokens_from_env() == 2000, "non-numeric env var -> default")
    os.environ["OBSIDIAN_MAX_TOKENS"] = "  "
    check(max_tokens_from_env() == 2000, "blank env var -> default")
    os.environ["OBSIDIAN_MAX_TOKENS"] = "5"
    check(max_tokens_from_env() == 256, "tiny value is raised to the safe minimum (256)")
    os.environ["OBSIDIAN_MAX_TOKENS"] = "-50"
    check(max_tokens_from_env() == 256, "negative value is raised to the safe minimum (256)")
    os.environ["OBSIDIAN_MAX_TOKENS"] = "999999"
    check(max_tokens_from_env() == 16000, "huge value is capped at 16000")
    os.environ["OBSIDIAN_MAX_TOKENS"] = "1.5"
    check(max_tokens_from_env() == 2000, "decimal value is not a valid whole number -> default")
    os.environ.pop("OBSIDIAN_MAX_TOKENS", None)
    check(max_tokens_from_env(default=777) == 777, "custom default is respected when env var is missing")

    # the chosen cap really reaches the model request
    (data, used), post, sleep = run_call({"A": [FakeResponse(200, GOOD)]}, ["A"], max_tokens=1200)
    check(post.calls[0][2]["max_tokens"] == 1200, "call_model sends the max_tokens it is given")

    # 402 that mentions tokens gets the lower-the-cap hint; plain 402 does not
    token_msg = "This request requires more credits, or fewer max_tokens. You requested up to 4096 tokens, but can only afford 1500"
    err, _, _ = expect_error({"A": [FakeResponse(402, {"error": {"message": token_msg}})]}, ["A"], LLMFatalError)
    check(isinstance(err, LLMFatalError) and "OBSIDIAN_MAX_TOKENS" in str(err), "402 about tokens tells the user to lower OBSIDIAN_MAX_TOKENS")
    err, _, _ = expect_error({"A": [FakeResponse(402, {"error": {"message": "no credits"}})]}, ["A"], LLMFatalError)
    check(isinstance(err, LLMFatalError) and "OBSIDIAN_MAX_TOKENS" not in str(err), "a plain 402 does not mention the token cap")

    # ---------- parse_tool_arguments ----------
    check(parse_tool_arguments('{"path": "a.txt"}') == ({"path": "a.txt"}, None), "valid JSON arguments are parsed")
    args, err = parse_tool_arguments("{bad json")
    check(args is None and err and "valid JSON" in err, "invalid JSON gives an error instead of crashing")
    args, err = parse_tool_arguments("[1, 2]")
    check(args is None and err, "JSON that is not an object is rejected")
    check(parse_tool_arguments("") == ({}, None) and parse_tool_arguments(None) == ({}, None),
          "empty arguments mean no arguments")

    # ---------- build_tool_messages: the history-corruption bug ----------
    quiet = lambda *_a, **_k: None
    ran = []

    def fake_execute(name, arguments):
        ran.append((name, arguments))
        if name == "boom":
            raise RuntimeError("kaboom")
        if name == "none":
            return None
        return f"ok:{name}"

    calls = [
        {"id": "c1", "function": {"name": "list_files", "arguments": "{}"}},
        {"id": "c2", "function": {"name": "read_file", "arguments": "{bad json"}},
        {"id": "c3", "function": {"name": "boom", "arguments": "{}"}},
        {"id": "c4", "function": {"name": "none", "arguments": "{}"}},
    ]
    msgs = build_tool_messages(calls, fake_execute, log=quiet)
    check(len(msgs) == len(calls) and [m["tool_call_id"] for m in msgs] == ["c1", "c2", "c3", "c4"],
          "every tool call gets exactly one tool reply, in order, with matching ids")
    check(msgs[1]["content"].startswith("Error:") and ("read_file", {}) not in ran
          and all(n != "read_file" for n, _ in ran), "malformed arguments produce an error reply and the tool is NOT run")
    check("crashed" in msgs[2]["content"] and "kaboom" in msgs[2]["content"], "a crashing tool becomes an error reply, not a crash")
    check(msgs[3]["content"] == "" and all(isinstance(m["content"], str) for m in msgs),
          "tool reply content is always a string")

    msgs = build_tool_messages([{"function": {"name": "list_files", "arguments": "{}"}}], fake_execute, log=quiet)
    check(msgs[0]["tool_call_id"] == "call_0", "a missing call id gets a safe placeholder")
    check(build_tool_messages(None, fake_execute, log=quiet) == [], "no tool calls -> no messages")

    passed = sum(results)
    total = len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("[SUCCESS] LLM client logic verified.")
    else:
        print("[FAILURE] Some tests failed — review above.")

    return passed == total


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
