# Multi-Agent Lab Guidelines

This workspace is an experimentation lab for building multi-agent orchestration applications.

## Scope

- Prioritize a working planner-executor-reviewer loop before advanced features.
- Prefer small, typed contracts between components over implicit behavior.
- Keep proposals implementation-ready and biased toward fast iteration.

## Working Style

- When drafting architecture, include assumptions, trade-offs, and failure modes.
- When proposing code changes, suggest the smallest safe change first.
- Keep runtime local-first and deterministic where possible for repeatable experiments.

## Quality Gates

- Include traceability for handoffs, tool calls, and decisions.
- Include guardrails: timeout budget, retry budget, and max-turn limits.
- Prefer structured outputs that can be evaluated across repeated runs.

## Output Expectations

- For design requests, return: goal, architecture, contracts, risks, and next actions.
- For implementation requests, return: files to change, key logic, and validation steps.
- If context is ambiguous, ask concise clarifying questions before making risky assumptions.