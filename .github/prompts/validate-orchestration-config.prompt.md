---
name: validate-orchestration-config
description: "Use when checking whether an orchestration design or config is complete, safe, and testable."
agent: orchestrator
argument-hint: "Paste the orchestration config, assumptions, and target reliability constraints."
---
Validate the provided orchestration setup against this checklist:

1. Role clarity: each agent has a single clear responsibility.
2. Contract clarity: every handoff has typed input/output expectations.
3. Guardrails: timeout, retry, and max-step limits are defined.
4. Failure handling: invalid output, tool error, and timeout paths are explicit.
5. Observability: trace events are sufficient for replay and diagnosis.
6. Testability: includes at least one happy-path and two failure-path tests.

Return:

1. Pass/fail per check
2. Missing items
3. Highest-risk gap
4. Minimal fix plan in priority order
