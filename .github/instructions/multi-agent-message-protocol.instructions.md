---
name: multi-agent-message-protocol
description: "Use when defining message schemas, trace events, run artifacts, validation envelopes, and structured inter-agent contracts."
applyTo:
  - "**/*message*.py"
  - "**/*event*.py"
  - "**/*trace*.py"
  - "**/*schema*.py"
  - "**/*contract*.py"
---
# Message and Trace Contract Rules

- Use explicit versioned payloads for agent messages.
- Include required fields: run_id, step_id, actor, intent, payload, timestamp.
- Treat message validation failures as first-class errors.
- Emit trace events for: plan, handoff, tool_call, tool_result, and decision.

# Validation Requirements

- Distinguish recoverable errors from terminal errors in output envelopes.
- Keep field names stable to support replay and benchmark comparisons.
