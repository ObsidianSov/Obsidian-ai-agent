"""
llm_client.py — resilient model calls and safe tool-call handling for Obsidian AI.

What this module does:
  1. call_model(): sends the chat to OpenRouter. Temporary problems (timeouts,
     rate limits, server errors) are retried with a short wait. If one model
     keeps failing, it moves on to the next model in the chain. Problems that
     switching models cannot fix (bad API key, no credits) stop immediately
     with a plain-English message.
  2. build_tool_messages(): runs the tool calls the model asked for and ALWAYS
     returns exactly one tool reply per call, even when the arguments were
     garbage or the tool crashed. This keeps the chat history valid so the
     next request does not break.

No network is needed to test this module (see test_llm_client.py).
"""

import json
import os
import time

import requests


class LLMError(Exception):
    """Every model in the chain failed. Message lists what happened."""


class LLMFatalError(LLMError):
    """A problem that trying another model cannot fix (key, credits, bad request)."""


# HTTP status codes grouped by what to do about them
FATAL_STATUS = {
    400: "The request was rejected as malformed. Switching models will not fix this.",
    401: "OpenRouter rejected the API key (missing, wrong, or revoked). "
         "Check OPENROUTER_API_KEY.",
    403: "OpenRouter refused the request (key permissions or content "
         "moderation).",
}
CREDITS_HINT = ("OpenRouter says the account is out of credits for this model. "
                "Add credits, or put a free model (like openrouter/free) in "
                "OBSIDIAN_MODELS.")
NEXT_MODEL_STATUS = {404}                     # model/endpoint not found or no tool support
RETRY_STATUS = {408, 429, 500, 502, 503, 504}  # temporary


def models_from_env(default, env_var="OBSIDIAN_MODELS"):
    """Read a comma-separated model list from the environment, else use default."""
    raw = os.getenv(env_var, "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models if models else list(default)


def _error_text(data, response_text=""):
    """Pull a short readable error message out of an OpenRouter reply."""
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err)[:300]
        if err:
            return str(err)[:300]
    return (response_text or "no details")[:300]


def call_model(
    messages,
    tools,
    *,
    api_key,
    url,
    models,
    max_tokens=4096,
    max_retries=2,
    timeout=180,
    post=requests.post,
    sleep=time.sleep,
):
    """
    Returns (data, model_used).
    Raises LLMFatalError for unfixable problems, LLMError if every model failed.
    `post` and `sleep` can be replaced in tests so no network or waiting is needed.
    """
    if not models:
        raise LLMFatalError("No models configured.")

    history = []  # one line per failed attempt, for the final error message
    out_of_credits = False  # set if any model answered 402

    for model in models:
        attempt = 0
        while attempt <= max_retries:
            attempt += 1
            try:
                response = post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "auto",
                        "max_tokens": max_tokens,
                    },
                    timeout=timeout,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                history.append(f"{model}: network problem ({type(exc).__name__})")
                if attempt <= max_retries:
                    sleep(2 ** (attempt - 1))
                    continue
                break  # out of retries -> next model

            status = response.status_code

            try:
                data = response.json()
            except Exception:
                data = None

            if status in FATAL_STATUS:
                raise LLMFatalError(
                    f"{FATAL_STATUS[status]} (HTTP {status}: "
                    f"{_error_text(data, getattr(response, 'text', ''))})"
                )

            if status == 402:
                # Credits only matter for paid models. A free model later in
                # the chain may still work, so move on instead of stopping.
                out_of_credits = True
                history.append(
                    f"{model}: out of credits (HTTP 402: "
                    f"{_error_text(data, getattr(response, 'text', ''))})"
                )
                break

            if status in NEXT_MODEL_STATUS:
                history.append(
                    f"{model}: not available (HTTP {status}: "
                    f"{_error_text(data, getattr(response, 'text', ''))})"
                )
                break  # no point retrying -> next model

            if status in RETRY_STATUS:
                history.append(
                    f"{model}: temporary error (HTTP {status}: "
                    f"{_error_text(data, getattr(response, 'text', ''))})"
                )
                if attempt <= max_retries:
                    sleep(2 ** (attempt - 1))
                    continue
                break

            if status != 200:
                history.append(
                    f"{model}: unexpected HTTP {status}: "
                    f"{_error_text(data, getattr(response, 'text', ''))}"
                )
                break

            # status 200 — but OpenRouter can still hide an error inside the body
            if not isinstance(data, dict) or "choices" not in data or not data["choices"]:
                history.append(
                    f"{model}: bad reply body ({_error_text(data, getattr(response, 'text', ''))})"
                )
                if attempt <= max_retries:
                    sleep(2 ** (attempt - 1))
                    continue
                break

            return data, model

    details = "\n  ".join(history) if history else "no details"

    if out_of_credits:
        raise LLMFatalError(f"{CREDITS_HINT}\n  {details}")

    raise LLMError(f"All models failed:\n  {details}")


def parse_tool_arguments(raw):
    """
    Safely turn the model's tool arguments into a dict.
    Returns (arguments_dict, error_message). error_message is None on success.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return {}, None  # some models send nothing for no-argument tools
    if isinstance(raw, dict):
        return raw, None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        return None, f"tool arguments were not valid JSON ({exc})"
    if not isinstance(parsed, dict):
        return None, "tool arguments must be a JSON object"
    return parsed, None


def build_tool_messages(tool_calls, execute, log=print):
    """
    Run every tool call and return one tool message per call (same order).
    Never raises: a bad call becomes an 'Error: ...' message so the chat
    history always stays valid.
    """
    out = []
    for index, tool_call in enumerate(tool_calls or []):
        call_id = (tool_call or {}).get("id") or f"call_{index}"
        function = (tool_call or {}).get("function") or {}
        name = function.get("name") or "unknown"

        arguments, error = parse_tool_arguments(function.get("arguments"))

        if error:
            result = f"Error: {error}. Re-send this tool call with valid JSON arguments."
            log(f"[TOOL] {name} (bad arguments)")
        else:
            log(f"[TOOL] {name} {arguments}")
            try:
                result = execute(name, arguments)
            except Exception as exc:  # a crashing tool must not break the history
                result = f"Error: tool '{name}' crashed: {type(exc).__name__}: {exc}"

        if not isinstance(result, str):
            result = "" if result is None else str(result)

        log(f"[RESULT] {result[:500]}")
        out.append({"role": "tool", "tool_call_id": call_id, "content": result})
    return out
