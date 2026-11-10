# Record architecture decisions

Status: accepted (generated, pending human review)

## Context

The rubric builder needs a clear design for anchoring, versioning, and JSON safety.

## Decision

Use immutable dataclasses, hash-based fingerprinting, rule-driven semantic versioning, and strict JSON validation with depth/size limits.

## Consequences

The library is safe against malformed input, deterministic, and easy to audit. Version bumps are predictable and reproducible.
