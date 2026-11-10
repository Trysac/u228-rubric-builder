# Architecture

## Design decisions for rubric_builder

- **Data model** uses immutable dataclasses (`@dataclass(frozen=True)`) to prevent accidental mutation of rubric content. `CriterionSpec` validates its name (regex `[a-z][a-z0-9_]{0,39}`), scale constraints (`min ≥ 0`, `max > min`, `max - min ≤ 9`), and descriptor coverage.
- **Anchoring** selects the first `anchors_per_level` (1–5) example IDs sorted ascending that have the exact score for a criterion. Missing anchors can raise `missing_anchor` or, if `allow_missing_anchors=True`, produce an empty tuple.
- **Fingerprint** is a SHA-256 over the rubric's dictionary serialization excluding `version`, using compact JSON (`sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=False`). This ensures version changes alone do not alter the fingerprint.
- **Semantic version bumps** are computed by comparing two rubrics:
  1. Equal fingerprints → same version.
  2. Criterion removed or scale changed → major bump.
  3. Criterion added or any anchors tuple changed → minor bump.
  4. Otherwise (description or descriptor text changed) → patch bump.
- **Prompt rendering** produces a deterministic multi-line string with exact formatting. Example text has newlines replaced with spaces and is truncated at `max_example_chars` plus an ellipsis. Missing anchor IDs raise `missing_example`.
- **JSON serialization** uses `sort_keys=True`, `indent=2`, `ensure_ascii=False`. `Rubric.from_json` enforces a 1,000,000-character input limit, JSON nesting depth ≤8, strict key sets, version format validation, scale completeness, and level score coverage.
- **Error handling** uses a single `RubricError` exception with a machine-readable `code` attribute from a closed set. Messages never include example text or secrets.
- **Logging** uses `logging.getLogger(__name__)` with a `NullHandler`; no global configuration.
