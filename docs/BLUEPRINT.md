# OBSIDIAN AI — MASTER BLUEPRINT

## 00. Identity

**Name:** Obsidian
**Owner:** Ahmad Suleiman
**Project:** Obsidian AI
**Purpose:** Personal autonomous AI agent and long-term digital assistant.

Obsidian is designed to evolve from a software-engineering agent into a persistent personal AI capable of conversation, reasoning, memory, computer control, automation, vision, voice interaction, and eventually portable multi-device operation.

---

## 01. Mission

Build a safe, modular, extensible personal AI system that can:

* Understand natural-language objectives.
* Reason through multi-step tasks.
* Use controlled tools.
* Modify and test software.
* Maintain persistent memory.
* Understand its identity and owner.
* Maintain project/context awareness.
* Operate with cloud or local models.
* Eventually operate offline.
* Eventually interact with the operating system, voice, vision, devices, and external services.

Safety and control come before autonomy.

---

## 02. Core Architecture

```text
                         OBSIDIAN
                            │
                     ┌──────▼──────┐
                     │    Agent    │
                     └──────┬──────┘
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
         Identity        Context         Memory
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                        Reasoning
                            │
                            ▼
                       LLM Router
                            │
                            ▼
                      Tool Registry
                            │
                            ▼
                       Action Gate
                            │
                            ▼
                        Executor
                            │
                    ┌───────┴───────┐
                    ▼               ▼
                  Audit          Recovery
```

The architecture must remain modular so that individual components can be replaced without rewriting the entire system.

---

## 03. Current Components

### Agent

Canonical implementation:

`agent_core/agent.py`

Responsible for orchestration and coordination between identity, context, memory, reasoning, tools, and execution.

### Reasoning

Canonical implementation:

`agent_core/reasoning.py`

Responsible for the ReAct-style reasoning loop and interpreting model decisions.

### LLM

Canonical direction:

`agent_core/llm.py`

Responsible for communication with model providers.

Current production runtime still uses OpenRouter directly through:

`ai.py`

This is temporary technical debt.

### Tool Registry

Canonical direction:

`agent_core/tools.py`

Responsible for registering and exposing tools to the agent.

### Executor

Canonical direction:

`agent_core/executor.py`

Responsible for controlled tool execution.

### Identity

`agent_core/identity.py`

Defines Obsidian's persistent identity, capabilities, limitations, persona, and behavioral traits.

### Owner Profile

`agent_core/owner_profile.py`

Stores owner-specific configuration, preferences, workspace information, tasks, knowledge, and key facts.

### Grounded Context

`agent_core/grounded_context.py`

Provides dynamic context such as:

* Time
* System environment
* Workspace state
* Owner information
* Memory context
* Project information

### Context Injection

`agent_core/context_injector.py`

Combines identity, owner information, grounded context, memory, capabilities, limitations, and task context into model-ready context.

### Memory

Canonical direction:

`agent_core/memory.py`

Provides working, persistent, and knowledge memory layers.

### Safety

Current safety components:

* `action_gate.py`
* `killswitch.py`
* `agent_core/executor.py`
* safety logic inside `agent_core/reasoning.py`

These are currently duplicated and must eventually be consolidated.

### Audit

Current implementations:

* `audit_log.py`
* `agent_core/audit_log.py`

These require consolidation.

### Web

Current production implementation:

`web_tools.py`

The placeholder web-search implementation in `agent_core/tools.py` is not yet canonical.

---

## 04. Security & Control

Safety is a foundational layer.

Required controls:

1. Kill switch
2. Action classification
3. SAFE / CONFIRM / BLOCK permissions
4. Tool registry
5. Execution limits
6. Command timeout
7. Recursion / loop protection
8. Audit logging
9. Emergency recovery
10. Workspace boundary enforcement

No autonomous capability should bypass the control kernel.

The final execution path should be:

```text
Model decision
      ↓
Tool Registry
      ↓
Action Gate
      ↓
Permission decision
      ↓
Executor
      ↓
Audit
```

Reasoning must not independently execute tools outside this path.

---

## 05. Memory Architecture

Target memory hierarchy:

```text
Working Memory
      ↓
Session Context
      ↓
Persistent Memory
      ↓
Knowledge Base
```

Memory must eventually support:

* Owner identity
* Preferences
* Important facts
* Projects
* Long-term goals
* Learned information
* Conversation-relevant context
* Task history

Memory must not blindly store every interaction.

---

## 06. Model Architecture

Obsidian must support interchangeable model providers.

Target:

```text
                  Model Router
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Cloud        Local       Fallback
       Model        Model        Model
```

Potential future providers:

* OpenRouter
* Ollama
* Other compatible APIs

The agent's memory and identity must remain independent from the selected model.

Changing models must not change who Obsidian is.

---

## 07. Tool Architecture

Tools must be registered through a central registry.

Target categories:

### File Tools

* Read
* Write
* Create
* List
* Directory management

### System Tools

* Command execution
* Application launching
* System information

### Web Tools

* Search
* Fetch
* Research

### Memory Tools

* Remember
* Recall
* Forget

### Future Tools

* Calendar
* Email
* Messaging
* Browser automation
* Computer control
* Voice
* Vision
* IoT

Every tool must pass through the control kernel.

---

## 08. Runtime Architecture

Current working runtime:

```text
ai.py
 ├── OpenRouter
 ├── MemorySystem
 ├── AuditLog
 ├── WebTools
 ├── ActionGate
 └── KillSwitch
```

Target runtime:

```text
ai.py
   │
   ▼
Agent
   │
   ├── Identity
   ├── Owner Profile
   ├── Context
   ├── Memory
   ├── Reasoning
   ├── Model Router
   ├── Tool Registry
   ├── Action Gate
   ├── Executor
   └── Audit / Recovery
```

`ai.py` should eventually become a thin application entry point rather than containing duplicated agent architecture.

---

## 09. JARVIS / FRIDAY Roadmap

### Phase 1 — Voice & Conversation

* Speech-to-text
* Text-to-speech
* Wake word
* Continuous listening

Potential technologies:

* Whisper
* pyttsx3
* edge-tts
* Porcupine

### Phase 2 — Vision & Awareness

* Screen capture
* Screen analysis
* Webcam
* OCR

Potential technologies:

* OpenCV
* PIL
* pytesseract
* vision-capable models

### Phase 3 — System Control

* Window management
* Application launching
* Keyboard/mouse control
* System statistics

Potential technologies:

* PyAutoGUI
* pywin32
* psutil

### Phase 4 — Memory & Context

* Long-term knowledge
* Session context
* Learned preferences
* Vector/search memory

Potential technologies:

* SQLite
* ChromaDB
* Custom memory systems

### Phase 5 — Real-Time Data & Automation

* News
* Weather
* Calendar
* Email
* SMS
* Task automation

### Phase 6 — IoT & Hardware

* Smart home
* Bluetooth
* Wi-Fi devices
* Arduino
* Raspberry Pi

Future expansion may include:

* Android / Termux
* Linux
* Portable USB deployment
* Drone
* AR glasses
* RC systems
* Other connected devices

---

## 10. Completed Milestones

### M0.1 — Action Gate

**Status:** COMPLETE

Result:

`35/35 PASS`

Implemented:

* Command classification
* SAFE / APPROVAL / BLOCK behavior
* Gate checks
* Safety tests

---

### M0.2 — Identity, Owner & Grounded Context

**Status:** COMPLETE

Result:

`45/45 PASS`

Implemented:

* Agent identity
* Identity configuration
* Owner profile
* Preferences
* Key facts
* Active tasks
* Current project
* Grounded context
* Context injection
* Agent integration
* Context inspection

---

## 11. Current State

Current architecture contains two generations.

### Generation A — Active Runtime

```text
ai.py
action_gate.py
killswitch.py
audit_log.py
memory_system.py
web_tools.py
```

This is currently the working runtime.

### Generation B — Agent Core

```text
workspace/agent_core/
    agent.py
    reasoning.py
    executor.py
    llm.py
    tools.py
    memory.py
    identity.py
    owner_profile.py
    grounded_context.py
    context_injector.py
```

This contains the richer architectural foundation and has verified M0.2 functionality.

The two generations must be consolidated rather than maintained independently.

---

## 12. Known Problems

### Architecture Duplication

There are currently two implementations for several responsibilities.

### LLM Duplication

`ai.py` communicates with OpenRouter directly while `agent_core/llm.py` provides another provider abstraction.

### Tool Duplication

`ai.py` contains hard-coded tool execution while `agent_core/tools.py` provides a registry.

### Memory Duplication

Two memory systems exist:

* `memory_system.py`
* `agent_core/memory.py`

### Safety Duplication

Safety checks exist in:

* `action_gate.py`
* `reasoning.py`
* `executor.py`

### Audit Duplication

Two audit implementations exist.

### Context Integration Gap

M0.2 exists and passes its tests, but the current root `ai.py` does not yet fully use the richer identity/context architecture.

### Project State Gap

There is currently no authoritative machine-readable project-state file.

---

## 13. Next Milestone — M0.3

### Architecture Consolidation

Objectives:

1. Establish one canonical agent architecture.
2. Establish one canonical tool system.
3. Establish one canonical memory system.
4. Establish one canonical execution path.
5. Establish one authoritative safety gate.
6. Establish one audit system.
7. Integrate M0.2 into the active runtime.
8. Create machine-readable project state.
9. Preserve working functionality during migration.
10. Retest after every migration step.

No deletion should occur until the replacement is verified.

---

## 14. Development Rules

### Rule 1 — Evidence over claims

A feature is not considered complete because code exists.

It is complete when:

```text
Implementation
      ↓
Test
      ↓
Pass
      ↓
State update
```

### Rule 2 — Safety before autonomy

New autonomous capabilities must not bypass:

* Action Gate
* Executor
* Audit
* Kill switch

### Rule 3 — One responsibility, one canonical implementation

Duplicate systems should eventually be removed or archived.

### Rule 4 — Preserve working behavior

Migration must be incremental.

### Rule 5 — Do not delete before replacement

Any component marked for removal must first have:

* Replacement identified
* Dependencies checked
* Tests passed
* Migration completed

### Rule 6 — Architecture changes require verification

Major architecture changes must be documented and tested.

### Rule 7 — Model independence

Identity, memory, owner context, and project state must not depend on one specific model.

---

## 15. Future Expansion

Obsidian is intended to evolve toward:

```text
Conversation
     ↓
Reasoning
     ↓
Memory
     ↓
Tools
     ↓
Computer Control
     ↓
Voice
     ↓
Vision
     ↓
Automation
     ↓
Devices
     ↓
Portable Personal AI
```

The system should remain modular enough that future capabilities can be added as controlled tools and services rather than rewriting the core agent.

---

## Architectural Principle

**Obsidian should become more capable without becoming less controllable.**

Autonomy is built on top of control, not instead of it.
