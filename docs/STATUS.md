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
| M7 | Repo cleanup: removed the old `agent_core` agent, both RainCast projects, 13 stale status docs, 11 old tests and `ai_backup.py` (archived outside the repo, still in git history); blueprint moved to `docs/BLUEPRINT.md`; `workspace/` (the agent's sandbox) is no longer tracked; root `requirements.txt` added | (fill in after push) | test_repo_layout |

Older suites still passing: test_action_gate (34), test_audit_log (6), test_killswitch (7), test_llm_client (32), test_gate_hardening (54).

## Known gaps (not done)

- M6 limits: code a script imports from other folders/packages is not inspected; `npm run`, `make`, `pip install` (setup.py) and `python -m <not a workspace file>` are not covered; the shell parser can be fooled by `$(...)`, aliases, functions. It only helps if you read the code in the prompt. `ai.py` runs its chat loop on import, so it is tested by reading its source and by running the real `gated_run_command` with stubs, not by running the full agent.
- `fetch_url`: DNS rebinding not closed (name validated, then re-resolved at connect time). No response size cap.
- Blueprint layers not built: Task Engine, Planner, Verification, Recovery, Learning.
- `ai.py` runs its chat loop the moment it is imported, so it cannot be loaded by tests (they read its source or lift single functions). A `main()` guard is the planned fix.
- Default model in `ai.py` is `minimax/minimax-m2.7` (paid). The phone overrides it via `OBSIDIAN_MODELS` (banner shows `openrouter/free`). If that variable is not set in a new Termux session, the paid default is used.
- RainCast and `agent_core` are removed from the repo but still in git HISTORY on GitHub. If the repo is public and that work is private, history would need rewriting (not done).
