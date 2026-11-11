# Security notes

## Threat model

`trysac-rubric-builder` is a pure library: it performs no network, file, subprocess or environment access. Callers pass Python objects or JSON text and receive Python objects or strings.

### Defended

- Oversized JSON text: `Rubric.from_json` rejects input longer than `max_chars` (default 1,000,000) with `input_too_large` before parsing.
- Deeply nested JSON: nesting deeper than 8 is rejected with `invalid_json`; `RecursionError` from the parser is also mapped to `invalid_json`.
- Malformed structure: `from_json` requires exactly the top-level keys `name`, `version`, `criteria`, and exact key sets on criteria and levels.
- Too many criteria: more than 20 raises `too_many_criteria`.
- Invalid versions: versions must be `MAJOR.MINOR.PATCH` with non-negative integers and no leading zeros; otherwise `invalid_version`.
- Duplicate example IDs: `build_rubric` raises `duplicate_example`.
- Unknown criteria in example scores: `unknown_criterion`.
- Scores outside a criterion scale: `score_out_of_scale`.
- Missing anchors: `missing_anchor` unless `allow_missing_anchors=True`.
- Invalid anchor option: `anchors_per_level` outside 1-5 raises `invalid_options`.
- Invalid criterion definitions: bad name, bad scale or missing descriptor raises `invalid_criterion`.
- Missing example for an anchor in `render_prompt`: `missing_example`.

### Not defended

- Example text, descriptors, names and IDs are not sanitized for secrets or sensitive data. They are stored in the rubric and example objects and can appear in rendered prompts.
- `render_prompt` replaces newline and carriage-return characters in example text with spaces and truncates to `max_example_chars`; it does not escape or validate prompt content.
- The library does not authenticate, sign or encrypt rubrics. A fingerprint detects content changes relative to a known value; it is not a signature or access control.
- The library does not enforce that examples are unbiased, correct or safe; it only validates scores against declared scales.
- No protection exists against a caller deliberately constructing `Rubric`, `Criterion` or `Level` objects directly and bypassing `build_rubric` validation.

## Publishing

The package code contains no publishing, credential or token handling. Release automation and PyPI credentials are outside this library.
