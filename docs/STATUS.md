# Obsidian AI — Status

Single source of truth. Updated at the end of every milestone.
Rule: an item is "done" only with (1) a test file that was run with
visible output and (2) a pushed git commit. Claims alone do not count.

## Done (tested + pushed)

| Milestone | What | Commit | Tests |
|-----------|------|--------|-------|
| M1 | Root `.gitignore`; private runtime data untracked | 18bd7c0 | — |
| M2 | `llm_client.py`: retry/backoff, model fallback chain (`OBSIDIAN_MODELS`), safe tool-call handling | cff4d04 | test_llm_client |
| M3 | Secrets scrubbed from command env; risky-command patterns in Action Gate | c1d90e5 | test_gate_hardening (54) |
| M4 | Out-of-credits (402) falls through to the next model | 083b6ab | test_llm_client (32) |
| M5 | `fetch_url` SSRF hardening: all IP spellings, IPv6-wrapped IPv4, CGNAT, unique-local, metadata hosts, DNS check, per-hop redirect check | 042ddfa | test_web_tools (89); live check on the phone passed 2026-10-13 (internal addresses BLOCKED, real weather data fetched) |
| M6 | `script_gate.py`: scripts the agent runs need human approval (code shown); remembered per session for the exact content incl. same-folder files; wired into `gated_run_command`; a "no" sticks for the rest of that request so the model can't loop on it | 3c02784 | test_script_gate (107) |
| M6.1 | `ai.py` system prompt and missing-key message no longer assume Windows (`py`, CMD); they say Termux/`python`/POSIX | 4f553ea | test_ai_source (9) |
| M7 | Repo cleanup: removed the old `agent_core` agent, both RainCast projects, 13 stale status docs, 11 old tests and `ai_backup.py` (archived outside the repo, still in git history); blueprint moved to `docs/BLUEPRINT.md`; `workspace/` (the agent's sandbox) is no longer tracked; root `requirements.txt` added | 2c1b8b1 | test_repo_layout (16) |
| M7.1 | `ai.py`: chat loop moved into `main()`, so importing it starts nothing; missing API key now exits with code 1. New `test_ai_agent.py` drives the real tool pipeline (files, command gates, script approval, secret scrubbing, audit log, kill switch) with no model | 9e2e60b | test_ai_agent (36); live model check on the phone passed 2026-10-13 |
| M7.2 | `ai.py` checks the API key's shape before starting: cleans pasted quotes/newlines, refuses keys that belong to other services (GitHub, Anthropic, OpenAI, Google, AWS, Slack) or contain spaces, warns on unfamiliar shapes, never prints the key. Added after a GitHub token was pasted by mistake | 3e5ea3a | test_ai_agent (52) |
| M7.3 | Found from the BlackRidge dashboard run: new `console_input.py` (a pasted multi-line brief is ONE message, sent when you press Enter so its last line isn't lost; approval prompts discard leftover pasted text, so a stray `yes` can't approve); script gate no longer flags `node --version 2>/dev/null`; system prompt now says inspect before building, obey inspect/plan-first requests, state only tool-verified facts; empty model replies no longer print `None` | 3fab43c | test_console_input (13), test_script_gate (121), test_ai_source (19) |

Older suites still passing: test_action_gate (34), test_audit_log (6), test_killswitch (7), test_llm_client (32), test_gate_hardening (54), test_script_gate (107), test_ai_source (9), test_web_tools (89).

## Known gaps (not done)

- M6 limits: code a script imports from other folders/packages is not inspected; `npm run`, `make`, `pip install` (setup.py) and `python -m <not a workspace file>` are not covered; the shell parser can be fooled by `$(...)`, aliases, functions. It only helps if you read the code in the prompt. `ai.py` runs its chat loop on import, so it is tested by reading its source and by running the real `gated_run_command` with stubs, not by running the full agent.
- `fetch_url`: DNS rebinding not closed (name validated, then re-resolved at connect time). No response size cap.
- Blueprint layers not built: Task Engine, Planner, Verification, Recovery, Learning.
- Agent memory is only what is in `workspace/memory/memories.json`. It does not know who its owner is; the old owner-profile loading went away with `agent_core`. (Parked on purpose.)
- Nothing in code enforces 'inspect and plan before writing'; the new prompt rules are only a request to the model. A Task Engine with a read-only first phase is the planned enforcement.
- No safe tool for looking inside a zip archive (the agent can only try shell commands).
- Not tested by anything automatic: the model itself (OpenRouter), real internet beyond `fetch_url`, and the model's judgement. Those are checked by hand on the phone.
- Default model in `ai.py` is `minimax/minimax-m2.7` (paid). The phone overrides it via `OBSIDIAN_MODELS` (banner shows `openrouter/free`). If that variable is not set in a new Termux session, the paid default is used.
- RainCast and `agent_core` are removed from the repo but still in git HISTORY on GitHub. If the repo is public and that work is private, history would need rewriting (not done).
