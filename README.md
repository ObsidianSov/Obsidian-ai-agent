# Obsidian AI

A personal command-line AI coding agent, built and run entirely from a
phone (Termux). Owner: Ahmad Suleiman ("Obsidian").

Run it:

```
export OPENROUTER_API_KEY="your key"      # never commit this
python ai.py
```

Optional: `OBSIDIAN_MODELS` = comma-separated list of OpenRouter model
slugs, tried in order (fallback chain).

## How it works

`ai.py` is the agent. It asks a model (via OpenRouter) what to do and
runs tools: read/write/list files, create folders, run commands,
fetch a URL, search a small set of reference sites, remember/recall.

Every tool call passes through safety layers:

| Layer | File | Job |
|-------|------|-----|
| Kill switch | `killswitch.py` | emergency stop, checked first |
| Action Gate | `action_gate.py` | commands are ALLOW / APPROVAL / BLOCK; secrets are stripped from the command environment |
| Web safety | `web_tools.py` | `fetch_url` refuses internal/private addresses, re-checks every redirect |
| Audit log | `audit_log.py` | every tool call recorded as JSON lines |
| Model client | `llm_client.py` | retry, backoff, fallback to the next model (including on out-of-credits) |
| Memory | `memory_system.py` | remember / recall across sessions |

The agent can only touch files inside `workspace/`.

## Tests

Run all of them before and after every change:

```
for t in test_action_gate test_audit_log test_killswitch test_web_tools test_llm_client test_gate_hardening; do python $t.py | grep RESULTS; done
```

## Status and rules

See `docs/STATUS.md`. Rule: nothing is listed as done unless it has a
test file AND a git commit.

## Do not commit

`.env`, `memory/`, `knowledge/owner.json`, logs. They are in `.gitignore`.
