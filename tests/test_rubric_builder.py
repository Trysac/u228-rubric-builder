"""Tests for rubric_builder."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import pytest

from rubric_builder import (
    CriterionSpec,
    Example,
    Level,
    Rubric,
    RubricError,
    build_rubric,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(
    name: str = "accuracy",
    scale: tuple[int, int] = (1, 2),
    descriptors: Mapping[int, str] | None = None,
) -> CriterionSpec:
    if descriptors is None:
        descriptors = {1: "Has errors.", 2: "No errors."}
    return CriterionSpec(name, "Facts are correct.", scale, descriptors)


def _make_example(
    id: str = "e1",
    text: str = "Paris is in Spain.",
    scores: Mapping[str, int] | None = None,
) -> Example:
    if scores is None:
        scores = {"accuracy": 1}
    return Example(id, text, scores)


# ---------------------------------------------------------------------------
# CriterionSpec validation
# ---------------------------------------------------------------------------


def test_criterion_spec_valid() -> None:
    spec = _make_spec()
    assert spec.name == "accuracy"
    assert spec.scale == (1, 2)
    assert spec.descriptors == {1: "Has errors.", 2: "No errors."}


def test_criterion_spec_invalid_name() -> None:
    with pytest.raises(RubricError) as exc_info:
        CriterionSpec("BadName", "desc", (1, 2), {1: "a", 2: "b"})
    assert exc_info.value.code == "invalid_criterion"
    with pytest.raises(RubricError) as exc_info:
        CriterionSpec("", "desc", (1, 2), {1: "a", 2: "b"})
    assert exc_info.value.code == "invalid_criterion"
    with pytest.raises(RubricError) as exc_info:
        CriterionSpec("a" * 41, "desc", (1, 2), {1: "a", 2: "b"})  # 41 chars > 40
    assert exc_info.value.code == "invalid_criterion"


def test_criterion_spec_invalid_scale() -> None:
    with pytest.raises(RubricError) as exc_info:
        CriterionSpec("accuracy", "desc", (-1, 2), {0: "a", 1: "b", 2: "c"})
    assert exc_info.value.code == "invalid_criterion"
    with pytest.raises(RubricError) as exc_info:
        CriterionSpec("accuracy", "desc", (2, 1), {1: "a", 2: "b"})
    assert exc_info.value.code == "invalid_criterion"
    with pytest.raises(RubricError) as exc_info:
        CriterionSpec("accuracy", "desc", (1, 11), {i: str(i) for i in range(1, 12)})
    assert exc_info.value.code == "invalid_criterion"


def test_criterion_spec_descriptors_missing_score() -> None:
    with pytest.raises(RubricError) as exc_info:
        CriterionSpec("accuracy", "desc", (1, 2), {1: "only one"})
    assert exc_info.value.code == "invalid_criterion"


def test_criterion_spec_descriptors_can_have_extra_keys() -> None:
    # extra keys are allowed and ignored
    spec = CriterionSpec("accuracy", "desc", (1, 2), {1: "a", 2: "b", 3: "c"})
    assert spec.descriptors == {1: "a", 2: "b", 3: "c"}


# ---------------------------------------------------------------------------
# Example and Level basic
# ---------------------------------------------------------------------------


def test_example_immutable_scores() -> None:
    scores = {"accuracy": 1}
    ex = Example("e1", "text", scores)
    scores["accuracy"] = 2  # mutate original dict, ex.scores should not change
    assert ex.scores == {"accuracy": 1}


def test_level_anchors_converted_to_tuple() -> None:
    lev = Level(1, "desc", ["a", "b"])
    assert lev.anchors == ("a", "b")
    assert isinstance(lev.anchors, tuple)


# ---------------------------------------------------------------------------
# build_rubric acceptance tests
# ---------------------------------------------------------------------------


def test_build_rubric_basic() -> None:
    spec = _make_spec()
    ex1 = _make_example("e1", "Paris is in Spain.", {"accuracy": 1})
    ex2 = _make_example("e2", "Paris is in France.", {"accuracy": 2})
    rubric = build_rubric("helpfulness", [spec], [ex1, ex2], anchors_per_level=1)
    assert rubric.version == "1.0.0"
    assert len(rubric.criteria) == 1
    crit = rubric.criteria[0]
    assert crit.name == "accuracy"
    assert crit.scale == (1, 2)
    assert crit.levels == (
        Level(1, "Has errors.", ("e1",)),
        Level(2, "No errors.", ("e2",)),
    )


def test_build_rubric_anchor_sorting_and_limit() -> None:
    spec = _make_spec(scale=(1, 2), descriptors={1: "a", 2: "b"})
    examples = [
        Example("b", "text", {"accuracy": 2}),
        Example("a", "text", {"accuracy": 2}),
        Example("c", "text", {"accuracy": 2}),
        Example("z", "text", {"accuracy": 1}),
    ]
    rubric = build_rubric("r", [spec], examples, anchors_per_level=2)
    crit = rubric.criteria[0]
    # level 2 should have first two sorted ids: 'a', 'b'
    assert crit.levels[1].anchors == ("a", "b")
    # level 1 has only one example 'z'
    assert crit.levels[0].anchors == ("z",)


def test_build_rubric_invalid_options() -> None:
    spec = _make_spec()
    ex = _make_example()
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], [ex], anchors_per_level=0)
    assert exc_info.value.code == "invalid_options"
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], [ex], anchors_per_level=6)
    assert exc_info.value.code == "invalid_options"


def test_build_rubric_too_many_criteria() -> None:
    specs = [CriterionSpec(f"c{i}", "desc", (1, 2), {1: "a", 2: "b"}) for i in range(21)]
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", specs, [])
    assert exc_info.value.code == "too_many_criteria"


def test_build_rubric_too_many_examples() -> None:
    spec = _make_spec()
    examples = [Example(f"e{i}", "text", {"accuracy": 1}) for i in range(10_001)]
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], examples)
    assert exc_info.value.code == "too_many_examples"


def test_build_rubric_duplicate_example_ids() -> None:
    spec = _make_spec()
    ex1 = _make_example("dup", "text", {"accuracy": 1})
    ex2 = _make_example("dup", "text", {"accuracy": 1})
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], [ex1, ex2])
    assert exc_info.value.code == "duplicate_example"


def test_build_rubric_unknown_criterion() -> None:
    spec = _make_spec()
    ex = _make_example(scores={"tone": 1})
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], [ex])
    assert exc_info.value.code == "unknown_criterion"


def test_build_rubric_score_out_of_scale() -> None:
    spec = _make_spec()
    ex = _make_example(scores={"accuracy": 3})
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], [ex])
    assert exc_info.value.code == "score_out_of_scale"


def test_build_rubric_missing_anchor() -> None:
    spec = _make_spec()
    ex = _make_example(scores={"accuracy": 2})  # only level 2 has an example
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], [ex], anchors_per_level=1)
    assert exc_info.value.code == "missing_anchor"


def test_build_rubric_allow_missing_anchors() -> None:
    spec = _make_spec()
    ex = _make_example(scores={"accuracy": 2})
    rubric = build_rubric(
        "r",
        [spec],
        [ex],
        anchors_per_level=1,
        allow_missing_anchors=True,
    )
    crit = rubric.criteria[0]
    assert crit.levels[0].anchors == ()
    assert crit.levels[1].anchors == ("e1",)


def test_build_rubric_invalid_version() -> None:
    spec = _make_spec()
    ex = _make_example()
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], [ex], version="1.2")
    assert exc_info.value.code == "invalid_version"
    with pytest.raises(RubricError) as exc_info:
        build_rubric("r", [spec], [ex], version="01.0.0")
    assert exc_info.value.code == "invalid_version"


# ---------------------------------------------------------------------------
# Rubric.to_dict / to_json / from_json
# ---------------------------------------------------------------------------


def test_to_dict_and_to_json_roundtrip() -> None:
    spec = _make_spec()
    ex1 = _make_example("e1", "Paris is in Spain.", {"accuracy": 1})
    ex2 = _make_example("e2", "Paris is in France.", {"accuracy": 2})
    rubric = build_rubric("helpfulness", [spec], [ex1, ex2], anchors_per_level=1)
    d = rubric.to_dict()
    assert d["name"] == "helpfulness"
    assert d["version"] == "1.0.0"
    assert d["criteria"][0]["scale"] == [1, 2]
    assert d["criteria"][0]["levels"][0]["anchors"] == ["e1"]
    json_str = rubric.to_json()
    parsed = json.loads(json_str)
    assert parsed == d
    # roundtrip
    rubric2 = Rubric.from_json(json_str)
    assert rubric2 == rubric


def test_from_json_acceptance_and_config() -> None:
    # Build a rubric, convert to json, parse back
    spec = _make_spec()
    ex1 = _make_example("e1", "text1", {"accuracy": 1})
    ex2 = _make_example("e2", "text2", {"accuracy": 2})
    rubric = build_rubric("r", [spec], [ex1, ex2], anchors_per_level=1)
    json_str = rubric.to_json()
    parsed = Rubric.from_json(json_str)
    assert parsed == rubric


def test_from_json_unknown_key() -> None:
    good = build_rubric(
        "r",
        [_make_spec()],
        [_make_example("e1", "t", {"accuracy": 1}), _make_example("e2", "t", {"accuracy": 2})],
        anchors_per_level=1,
    ).to_dict()
    good["extra"] = "bad"
    json_str = json.dumps(good)
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(json_str)
    assert exc_info.value.code == "invalid_json"


def test_from_json_input_too_large() -> None:
    # Create a string longer than 1_000_000 characters
    long_str = " " * 1_000_001
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(long_str)
    assert exc_info.value.code == "input_too_large"


def test_from_json_invalid_version() -> None:
    d = {
        "name": "r",
        "version": "1.2",
        "criteria": [],
    }
    json_str = json.dumps(d)
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(json_str)
    assert exc_info.value.code == "invalid_version"


def test_from_json_too_many_criteria() -> None:
    d = {
        "name": "r",
        "version": "1.0.0",
        "criteria": [
            {
                "name": f"c{i}",
                "description": "desc",
                "scale": [1, 2],
                "levels": [
                    {"score": 1, "descriptor": "a", "anchors": []},
                    {"score": 2, "descriptor": "b", "anchors": []},
                ],
            }
            for i in range(21)
        ],
    }
    json_str = json.dumps(d)
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(json_str)
    assert exc_info.value.code == "too_many_criteria"


def test_from_json_nesting_too_deep() -> None:
    # Create nested depth > 8
    deep = {}
    cur = deep
    for _ in range(9):
        cur["a"] = {}
        cur = cur["a"]
    json_str = json.dumps(deep)
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(json_str)
    assert exc_info.value.code == "invalid_json"


def test_from_json_malformed_json() -> None:
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json("not json")
    assert exc_info.value.code == "invalid_json"


def test_from_json_deeply_nested_payload_does_not_crash() -> None:
    hostile = "[" * 2000 + "]" * 2000
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(hostile)
    assert exc_info.value.code == "invalid_json"


def test_from_json_scale_violation() -> None:
    d = {
        "name": "r",
        "version": "1.0.0",
        "criteria": [
            {
                "name": "c",
                "description": "d",
                "scale": [1, 1],  # max <= min
                "levels": [{"score": 1, "descriptor": "a", "anchors": []}],
            }
        ],
    }
    json_str = json.dumps(d)
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(json_str)
    assert exc_info.value.code == "invalid_json"


def test_from_json_levels_not_cover_scale() -> None:
    d = {
        "name": "r",
        "version": "1.0.0",
        "criteria": [
            {
                "name": "c",
                "description": "d",
                "scale": [1, 2],
                "levels": [
                    {"score": 1, "descriptor": "a", "anchors": []},
                    # missing score 2
                ],
            }
        ],
    }
    json_str = json.dumps(d)
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(json_str)
    assert exc_info.value.code == "invalid_json"


def test_from_json_duplicate_level_score() -> None:
    d = {
        "name": "r",
        "version": "1.0.0",
        "criteria": [
            {
                "name": "c",
                "description": "d",
                "scale": [1, 2],
                "levels": [
                    {"score": 1, "descriptor": "a", "anchors": []},
                    {"score": 1, "descriptor": "b", "anchors": []},
                    {"score": 2, "descriptor": "c", "anchors": []},
                ],
            }
        ],
    }
    json_str = json.dumps(d)
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(json_str)
    assert exc_info.value.code == "invalid_json"


def test_from_json_level_score_out_of_scale() -> None:
    d = {
        "name": "r",
        "version": "1.0.0",
        "criteria": [
            {
                "name": "c",
                "description": "d",
                "scale": [1, 2],
                "levels": [
                    {"score": 0, "descriptor": "a", "anchors": []},
                    {"score": 1, "descriptor": "b", "anchors": []},
                    {"score": 2, "descriptor": "c", "anchors": []},
                ],
            }
        ],
    }
    json_str = json.dumps(d)
    with pytest.raises(RubricError) as exc_info:
        Rubric.from_json(json_str)
    assert exc_info.value.code == "invalid_json"


# ---------------------------------------------------------------------------
# fingerprint tests
# ---------------------------------------------------------------------------


def _make_rubric_for_fingerprint() -> Rubric:
    spec = _make_spec()
    ex1 = _make_example("e1", "t1", {"accuracy": 1})
    ex2 = _make_example("e2", "t2", {"accuracy": 2})
    return build_rubric("r", [spec], [ex1, ex2], anchors_per_level=1)


def test_fingerprint_matches_spec() -> None:
    rubric = _make_rubric_for_fingerprint()
    d = rubric.to_dict()
    d.pop("version", None)
    expected = hashlib.sha256(
        json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert rubric.fingerprint() == expected


def test_fingerprint_ignores_version() -> None:
    rubric1 = _make_rubric_for_fingerprint()
    rubric2 = Rubric(rubric1.name, "9.9.9", rubric1.criteria)
    assert rubric1.fingerprint() == rubric2.fingerprint()


# ---------------------------------------------------------------------------
# next_version tests
# ---------------------------------------------------------------------------


def _make_old_rubric() -> Rubric:
    spec = _make_spec()
    ex1 = _make_example("e1", "t1", {"accuracy": 1})
    ex2 = _make_example("e2", "t2", {"accuracy": 2})
    return build_rubric("r", [spec], [ex1, ex2], anchors_per_level=1, version="1.2.3")


def _make_new_rubric(
    *,
    specs=None,
    examples=None,
    anchors_per_level=1,
    version="0.0.0",
) -> Rubric:
    if specs is None:
        specs = [_make_spec()]
    if examples is None:
        examples = [
            _make_example("e1", "t1", {"accuracy": 1}),
            _make_example("e2", "t2", {"accuracy": 2}),
        ]
    return build_rubric(
        "r",
        specs,
        examples,
        anchors_per_level=anchors_per_level,
        version=version,
    )


def test_next_version_equal_fingerprint() -> None:
    old = _make_old_rubric()
    new = _make_new_rubric()  # identical content
    assert new.next_version(old) == "1.2.3"


def test_next_version_criterion_removed_major() -> None:
    old = _make_old_rubric()
    # remove the only criterion
    new = Rubric("r", "0.0.0", ())
    assert new.next_version(old) == "2.0.0"


def test_next_version_scale_changed_major() -> None:
    old = _make_old_rubric()
    spec = _make_spec(scale=(1, 3), descriptors={1: "a", 2: "b", 3: "c"})
    examples = [
        _make_example("e1", "t1", {"accuracy": 1}),
        _make_example("e2", "t2", {"accuracy": 2}),
        _make_example("e3", "t3", {"accuracy": 3}),
    ]
    new = build_rubric("r", [spec], examples, anchors_per_level=1, version="0.0.0")
    assert new.next_version(old) == "2.0.0"


def test_next_version_criterion_added_minor() -> None:
    old = _make_old_rubric()
    spec1 = _make_spec("accuracy")
    spec2 = _make_spec("tone", scale=(1, 2), descriptors={1: "a", 2: "b"})
    examples = [
        _make_example("e1", "t1", {"accuracy": 1, "tone": 1}),
        _make_example("e2", "t2", {"accuracy": 2, "tone": 2}),
    ]
    new = build_rubric("r", [spec1, spec2], examples, anchors_per_level=1, version="0.0.0")
    assert new.next_version(old) == "1.3.0"


def test_next_version_anchors_changed_minor() -> None:
    old = _make_old_rubric()
    # Change anchor order; with anchors_per_level=2 and two examples, order may differ
    spec = _make_spec()
    ex1 = _make_example("e1", "t1", {"accuracy": 1})
    ex2 = _make_example("e2", "t2", {"accuracy": 2})
    ex3 = _make_example("e3", "t3", {"accuracy": 2})  # adds another anchor for level 2
    new = build_rubric("r", [spec], [ex1, ex2, ex3], anchors_per_level=2, version="0.0.0")
    assert new.next_version(old) == "1.3.0"


def test_next_version_description_changed_patch() -> None:
    old = _make_old_rubric()
    spec = _make_spec()
    # change description
    spec2 = CriterionSpec(spec.name, "Different description.", spec.scale, spec.descriptors)
    new = build_rubric(
        "r",
        [spec2],
        [_make_example("e1", "t1", {"accuracy": 1}), _make_example("e2", "t2", {"accuracy": 2})],
        anchors_per_level=1,
        version="0.0.0",
    )
    assert new.next_version(old) == "1.2.4"


def test_next_version_descriptor_changed_patch() -> None:
    old = _make_old_rubric()
    spec = _make_spec(descriptors={1: "Different descriptor.", 2: "No errors."})
    new = build_rubric(
        "r",
        [spec],
        [_make_example("e1", "t1", {"accuracy": 1}), _make_example("e2", "t2", {"accuracy": 2})],
        anchors_per_level=1,
        version="0.0.0",
    )
    assert new.next_version(old) == "1.2.4"


# ---------------------------------------------------------------------------
# render_prompt tests
# ---------------------------------------------------------------------------


def test_render_prompt_acceptance_exact() -> None:
    spec = _make_spec()
    ex1 = _make_example("e1", "Paris is in Spain.", {"accuracy": 1})
    ex2 = _make_example("e2", "Paris is in France.", {"accuracy": 2})
    rubric = build_rubric("helpfulness", [spec], [ex1, ex2], anchors_per_level=1)
    expected = (
        "Rubric: helpfulness v1.0.0\n"
        "\n"
        "Criterion: accuracy (1-2)\n"
        "Facts are correct.\n"
        "1: Has errors.\n"
        "  Example e1: Paris is in Spain.\n"
        "2: No errors.\n"
        "  Example e2: Paris is in France.\n"
    )
    assert rubric.render_prompt([ex1, ex2]) == expected


def test_render_prompt_two_criteria_separator() -> None:
    spec1 = _make_spec("accuracy")
    spec2 = _make_spec("tone", scale=(1, 2), descriptors={1: "a", 2: "b"})
    examples = [
        _make_example("e1", "t1", {"accuracy": 1, "tone": 1}),
        _make_example("e2", "t2", {"accuracy": 2, "tone": 2}),
    ]
    rubric = build_rubric("r", [spec1, spec2], examples, anchors_per_level=1)
    prompt = rubric.render_prompt(examples)
    # There should be exactly one blank line between the last line of first criterion
    # and the first line of second criterion.
    lines = prompt.splitlines()
    # Find index of first "Criterion: tone"
    idx = lines.index("Criterion: tone (1-2)")
    # Previous line should be empty
    assert lines[idx - 1] == ""
    # And the line before that should be the last anchor of accuracy (or descriptor)
    # Since accuracy has two levels, the last anchor line is the one for score 2.
    # We can assert that there is exactly one blank line between criteria blocks.
    # More direct: join the relevant part.
    # Also assert the full expected string for this specific case.
    expected = (
        "Rubric: r v1.0.0\n"
        "\n"
        "Criterion: accuracy (1-2)\n"
        "Facts are correct.\n"
        "1: Has errors.\n"
        "  Example e1: t1\n"
        "2: No errors.\n"
        "  Example e2: t2\n"
        "\n"
        "Criterion: tone (1-2)\n"
        "Facts are correct.\n"
        "1: a\n"
        "  Example e1: t1\n"
        "2: b\n"
        "  Example e2: t2\n"
    )
    assert prompt == expected


def test_render_prompt_newlines_replaced_and_truncation() -> None:
    spec = _make_spec()
    ex1 = _make_example(
        "e1",
        "Line1\nLine2\nLine3ThisIsALongTextThatShouldBeTruncated",
        {"accuracy": 1},
    )
    ex2 = _make_example("e2", "short", {"accuracy": 2})
    rubric = build_rubric("r", [spec], [ex1, ex2], anchors_per_level=1)
    prompt = rubric.render_prompt([ex1, ex2], max_example_chars=10)
    # Example e1 text: newlines -> spaces, then truncate to 10 chars + '...'
    processed = "Line1 Line2 "  # after newline replacement, length? compute
    # Actually "Line1\nLine2\nLine3ThisIsALongTextThatShouldBeTruncated"
    # newlines replace: "Line1 Line2 Line3ThisIsALongTextThatShouldBeTruncated"
    # len >10, so take first 10 chars: "Line1 Line" then add "..." => "Line1 Line..."
    expected_text = "Line1 Line..."
    assert f"  Example e1: {expected_text}\n" in prompt
    # Ensure newlines are gone
    assert "\n" not in processed  # but processed may have spaces; we just check prompt


def test_render_prompt_missing_example() -> None:
    spec = _make_spec()
    ex1 = _make_example("e1", "t1", {"accuracy": 1})
    ex2 = _make_example("e2", "t2", {"accuracy": 2})
    rubric = build_rubric("r", [spec], [ex1, ex2], anchors_per_level=1)
    # Remove ex2 from the input to render
    with pytest.raises(RubricError) as exc_info:
        rubric.render_prompt([ex1])
    assert exc_info.value.code == "missing_example"


def test_render_prompt_unicode_descriptor_roundtrip() -> None:
    spec = CriterionSpec(
        "uni",
        "desc",
        (1, 2),
        {1: "Mauvais 😞", 2: "Bon 👍"},
    )
    ex1 = Example("e1", "text", {"uni": 1})
    ex2 = Example("e2", "text", {"uni": 2})
    rubric = build_rubric("r", [spec], [ex1, ex2], anchors_per_level=1)
    json_str = rubric.to_json()
    parsed = Rubric.from_json(json_str)
    assert parsed == rubric
    prompt = parsed.render_prompt([ex1, ex2])
    assert "Mauvais 😞" in prompt
    assert "Bon 👍" in prompt


def test_render_prompt_allow_missing_anchors_empty_anchor() -> None:
    spec = _make_spec()
    ex = _make_example("e1", "t", {"accuracy": 2})  # only score 2
    rubric = build_rubric(
        "r",
        [spec],
        [ex],
        anchors_per_level=1,
        allow_missing_anchors=True,
    )
    prompt = rubric.render_prompt([ex])
    # Level 1 should have no anchor line
    assert "1: Has errors.\n" in prompt
    # There should be no "Example" line after the descriptor for score 1
    lines = prompt.splitlines()
    idx = lines.index("1: Has errors.")
    # Next line should be score 2, not Example
    assert lines[idx + 1] == "2: No errors."


# ---------------------------------------------------------------------------
# Logging exists with NullHandler
# ---------------------------------------------------------------------------


def test_logger_has_null_handler() -> None:
    import logging

    from rubric_builder import logger

    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)
