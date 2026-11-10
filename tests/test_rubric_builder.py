"""Behavior tests for the public API of rubric_builder."""

from __future__ import annotations

import pytest

import rubric_builder


def test_normalize_trims_and_lowercases() -> None:
    assert rubric_builder.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        rubric_builder.normalize(value)


def test_version_is_semver() -> None:
    parts = rubric_builder.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
