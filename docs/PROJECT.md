# Project record

## Objective

Build versioned grading rubrics from human-scored examples: anchors per score level, a content fingerprint, semver bumps from rubric diffs and an exact judge prompt.

## Scope

- Public API: `CriterionSpec`, `Example`, `Level`, `Criterion`, `Rubric`, `RubricError` and `build_rubric` from `rubric_builder`.
- Building a rubric selects example IDs for each criterion level: matching scores sorted ascending by ID, first `anchors_per_level` (1-5).
- `Rubric.fingerprint` is SHA-256 over the rubric dictionary without `version`.
- `Rubric.next_version` applies ordered rules: equal fingerprints keep the version; removed criterion or changed scale bumps major; added criterion or changed anchors bumps minor; otherwise patch.
- `Rubric.render_prompt` emits the exact judge prompt format with newline normalization and truncation.
- JSON round-trip through `to_json` and `from_json` with the limits described in the README.
- Validation failures raise `RubricError` with a stable code.

## Out of scope

- Generating descriptors with an LLM.
- Scoring outputs or judging model responses.
- Inter-rater statistics.
- Storing rubric history; callers keep JSON files in git.
- Runtime dependencies and I/O; the package uses only the Python standard library.

## Timeline

No dated milestones are recorded in the repository.

## Effort metrics

Measured values only; a value that has not been measured stays 'pending measurement'.

| Metric | Value |
|---|---|
| Tokens (input / output) | 667785 / 56046 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.0924 |

## Factory run u228 (measured from API usage)

| Date (UTC) | Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|---|
| 2026-11-10 | generation | deepseek-v4-pro | yes | 1904 | 24086 | 0 | 3200 | 0.0490 |
| 2026-11-10 | fix-1 | deepseek-flash | no | 16151 | 2296 | 0 | 70144 | 0.0040 |
| 2026-11-10 | audit | deepseek-flash | no | 33690 | 17945 | 0 | 408576 | 0.0170 |
| 2026-11-10 | fix-2 | deepseek-flash | no | 12392 | 808 | 0 | 32640 | 0.0024 |
| 2026-11-10 | docs | deepseek-flash | no | 88832 | 10911 | 0 | 256 | 0.0199 |

Total: $0.0924. Prices: deepseek line, as measured by its adapter. Providers serve the current version of each model id, so the date tells which version answered; versions, launch stages and price sources per line are in the factory's model register (docs/MODELS.md).
