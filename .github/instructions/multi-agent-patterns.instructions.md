---
name: multi-agent-patterns
description: "Use when designing orchestration flows, agent responsibilities, delegation logic, retries, timeouts, and workflow guardrails in multi-agent systems."
applyTo:
  - "**/*orchestrat*.py"
  - "**/*agent*.py"
  - "**/*workflow*.py"
  - "**/*scheduler*.py"
---
# Multi-Agent Pattern Rules

- Prefer explicit state transitions over implicit branching.
- Keep agent responsibilities single-purpose and bounded.
- Define retry policy per step and cap max retries.
- Define max turn/depth limits to prevent loop escalation.
- Record handoff reason and expected output for each delegation.

# Output Requirements

- For each proposed flow, include: trigger, owner agent, expected output, and fallback path.
- Call out failure behavior explicitly for timeout, invalid output, and tool failure.
