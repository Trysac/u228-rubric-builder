# trysac-rubric-builder

[![PyPI version](https://badge.fury.io/py/trysac-rubric-builder.svg)](https://badge.fury.io/py/trysac-rubric-builder)
[![CI](https://github.com/Trysac/u228-rubric-builder/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u228-rubric-builder/actions/workflows/ci.yml)

Build versioned grading rubrics from human-scored examples. The import name is `rubric_builder`; the package has no runtime dependencies. Scores are anchored to example IDs, rubric content has a SHA-256 fingerprint, and `Rubric.next_version` computes a semantic version from the difference between two rubrics.

## Installation

```sh
pip install trysac-rubric-builder
```

## Usage

```python
from rubric_builder import build_rubric, CriterionSpec, Example

spec = CriterionSpec("accuracy", "Facts are correct.", (1, 2), {1: "Has errors.", 2: "No errors."})
examples = [
    Example("e1", "Paris is in Spain.", {"accuracy": 1}),
    Example("e2", "Paris is in France.", {"accuracy": 2}),
]
rubric = build_rubric("helpfulness", [spec], examples, anchors_per_level=1)
print(rubric.render_prompt(examples))
```

## Public API

- `CriterionSpec(name, description, scale, descriptors)`: frozen dataclass. `name` must match `[a-z][a-z0-9_]{0,39}`. `scale` is `(min, max)` with `min >= 0`, `max > min` and `max - min <= 9`. `descriptors` must contain every integer score in the scale.
- `Example(id, text, scores)`: frozen dataclass for one human-scored example.
- `Level(score, descriptor, anchors)` and `Criterion(name, description, scale, levels)`: frozen dataclasses used inside a built rubric. `anchors` is a tuple of example IDs sorted ascending.
- `Rubric(name, version, criteria)`: frozen dataclass. Methods: `to_dict()`, `to_json()`, `from_json(text, *, max_chars=1_000_000)`, `fingerprint()`, `next_version(old)` and `render_prompt(examples, *, max_example_chars=300)`.
- `build_rubric(name, criteria, examples, *, version='1.0.0', anchors_per_level=2, allow_missing_anchors=False) -> Rubric`: builds levels and anchors. `anchors_per_level` must be 1-5. If `allow_missing_anchors=False`, a level with no matching example raises `missing_anchor`; if `True`, that level gets an empty anchors tuple.

## Errors, limits and options

`RubricError` has a machine-readable `code` attribute: `invalid_criterion`, `invalid_options`, `missing_anchor`, `score_out_of_scale`, `unknown_criterion`, `duplicate_example`, `missing_example`, `invalid_version`, `too_many_criteria`, `too_many_examples`, `input_too_large`, `invalid_json`. Error messages can contain criterion names, example IDs and scores; they do not include example text.

Limits: at most 20 criteria, at most 10,000 examples, JSON input at most 1,000,000 characters, JSON nesting depth at most 8, and a scale span of at most 9 (`max - min <= 9`). `from_json` also rejects unknown or missing keys and validates version, scale and level coverage. `render_prompt` truncates example text longer than `max_example_chars` and appends `...`.

## Why not a prose rubric in a prompt file

A prose rubric has no anchors that show what each score level looks like, no content fingerprint that proves which rubric scored a run, and no rule for deciding whether an edit is a patch, minor or major change. This library makes anchors explicit, excludes `version` from the fingerprint, and computes the next version in the order: removed criterion or changed scale -> major; added criterion or changed anchors -> minor; otherwise -> patch.

## Security

See [docs/SECURITY.md](docs/SECURITY.md).
