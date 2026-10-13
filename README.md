# Obsidian AI

A personal command-line AI coding agent, built and run entirely from a
phone (Termux). Owner: Ahmad Suleiman ("Obsidian").

Run it:

```
export OPENROUTER_API_KEY="your key"      # never commit this
python ai.py
```

The key must be an OpenRouter key (starts with `sk-or-`). On Termux, save it
once with this single line (the key is not shown on screen and is never
printed by the agent). Run it alone, not as part of a bigger paste:

```
read -s -p "Paste OpenRouter key: " K; echo; echo "export OPENROUTER_API_KEY=\"$K\"" >> ~/.bashrc; unset K; source ~/.bashrc
```

The agent refuses to start if the value looks like a key for another
service (GitHub, Anthropic, OpenAI, Google, AWS...), so a wrong secret is
never sent to OpenRouter. Never paste a key into a chat.

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
| Script gate | `script_gate.py` | scripts the agent runs (`python x.py`, `bash x.sh`, `node x.js`) need your approval; the prompt shows the code; approval is remembered for the session only for that exact content |
| Web safety | `web_tools.py` | `fetch_url` refuses internal/private addresses, re-checks every redirect |
| Audit log | `audit_log.py` | every tool call recorded as JSON lines |
| Model client | `llm_client.py` | retry, backoff, fallback to the next model (including on out-of-credits) |
| Memory | `memory_system.py` | remember / recall across sessions |

The agent can only touch files inside `workspace/`.

## Tests

Run all of them before and after every change. `test_ai_agent.py` drives the real tool pipeline (write file, run command, approval gates, audit log, kill switch) with no model and no internet:

```
for t in test_action_gate test_audit_log test_killswitch test_web_tools test_llm_client test_gate_hardening test_script_gate test_ai_source test_repo_layout test_ai_agent; do python $t.py | grep RESULTS; done
```

## Repo layout

| Path | What it is |
|------|-----------|
| `ai.py` | the agent (the only entry point) |
| `*_gate.py`, `llm_client.py`, `web_tools.py`, `audit_log.py`, `killswitch.py`, `memory_system.py` | the layers in the table above |
| `test_*.py` | one test file per layer; run them all (see Tests) |
| `docs/STATUS.md` | what is done, with commits and tests |
| `docs/BLUEPRINT.md` | the long-term plan. A plan, NOT a status report |
| `requirements.txt` | Python packages (`pip install -r requirements.txt`) |
| `workspace/` | the agent's sandbox. Its contents are deliberately NOT tracked by git |

The old `agent_core` agent, the RainCast projects and the old status
documents were removed in M7. They are archived outside the repo and
remain in git history.

## Status and rules

See `docs/STATUS.md`. Rule: nothing is listed as done unless it has a
test file AND a git commit.

## Do not commit

`.env`, `memory/`, `knowledge/owner.json`, logs. They are in `.gitignore`.
