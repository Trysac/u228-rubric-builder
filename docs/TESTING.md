# Testing

## Running

```sh
pytest tests/test_rubric_builder.py
```

The cached pytest artifact is `tests/__pycache__/test_rubric_builder.cpython-312-pytest-9.2.0.pyc`, produced by pytest 9.2.0.

## Policy

- Tests import the public API from `rubric_builder`.
- Assertions use `pytest.raises` and check `RubricError.code`.
- Tests check frozen dataclass behavior: for example `Example` stores an immutable copy of `scores`, and `Level` converts `anchors` to a tuple.
- Tests are deterministic and use no network or external services.

## Tiers

The test artifact contains a single unit-test module. No separate conformance or external-tool test files are present in the repository tree.

## Layout

`tests/test_rubric_builder.py` is the test module. Named tests visible in the cached artifact include:

- `test_criterion_spec_valid`: valid `CriterionSpec` keeps name, scale and descriptors.
- `test_criterion_spec_invalid_name`: bad criterion name raises `RubricError` with code `invalid_criterion`.
- `test_criterion_spec_invalid_scale`: invalid scale values raise `invalid_criterion`.
- `test_criterion_spec_descriptors_missing_score`: a missing descriptor for a score in the scale raises `invalid_criterion`.
- `test_criterion_spec_descriptors_can_have_extra_keys`: descriptors may contain keys beyond the scale.
- `test_example_immutable_scores`: `Example` converts `scores` to a dictionary copy.
- `test_level_anchors_converted_to_tuple`: `Level` converts `anchors` to a tuple.

The cached bytecode is stored under `tests/__pycache__/`.
