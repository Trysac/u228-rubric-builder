"""Build versioned grading rubrics from human-scored examples.

Provides typed data classes, validation, fingerprinting, semantic-version
bumps from rubric diffs, and an exact judge-prompt renderer.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

__all__ = [
    "Criterion",
    "CriterionSpec",
    "Example",
    "Level",
    "Rubric",
    "RubricError",
    "build_rubric",
]

# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

RubricErrorCodes = Literal[
    "invalid_criterion",
    "invalid_options",
    "missing_anchor",
    "score_out_of_scale",
    "unknown_criterion",
    "duplicate_example",
    "missing_example",
    "invalid_version",
    "too_many_criteria",
    "too_many_examples",
    "input_too_large",
    "invalid_json",
]


class RubricError(Exception):
    """Base error for the rubric builder with a stable machine-readable code."""

    def __init__(self, code: RubricErrorCodes, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Logging (no global configuration, NullHandler)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CriterionSpec:
    """Specification for a single criterion used to build a rubric.

    Attributes:
        name: Machine-readable name, must match ``[a-z][a-z0-9_]{0,39}``.
        description: Human-readable description.
        scale: Inclusive integer range ``(min, max)`` with ``min >= 0``,
            ``max > min``, and ``max - min <= 9``.
        descriptors: Mapping from every integer in the scale to a
            human-readable descriptor for that score.
    """

    name: str
    description: str
    scale: tuple[int, int]
    descriptors: Mapping[int, str]

    def __post_init__(self) -> None:
        # Validate name
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", self.name):
            raise RubricError(
                "invalid_criterion",
                "criterion name must match [a-z][a-z0-9_]{0,39}",
            )
        # Validate scale
        min_score, max_score = self.scale
        if min_score < 0 or max_score <= min_score or max_score - min_score > 9:
            raise RubricError(
                "invalid_criterion",
                "scale must have min >= 0, max > min, and max - min <= 9",
            )
        # Validate descriptors cover every integer in the scale
        for score in range(min_score, max_score + 1):
            if score not in self.descriptors:
                raise RubricError(
                    "invalid_criterion",
                    f"missing descriptor for score {score}",
                )
        # Convert to immutable types
        object.__setattr__(self, "scale", (min_score, max_score))
        object.__setattr__(self, "descriptors", dict(self.descriptors))


@dataclass(frozen=True)
class Example:
    """A single human-scored example.

    Attributes:
        id: Unique identifier for the example.
        text: The example text.
        scores: Mapping from criterion name to the integer score given.
    """

    id: str
    text: str
    scores: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scores", dict(self.scores))


@dataclass(frozen=True)
class Level:
    """A single score level within a criterion.

    Attributes:
        score: The integer score.
        descriptor: Human-readable descriptor for this score.
        anchors: Tuple of example IDs that anchor this score level, ordered
            ascending by ID.
    """

    score: int
    descriptor: str
    anchors: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchors", tuple(self.anchors))


@dataclass(frozen=True)
class Criterion:
    """A fully built criterion with score levels and anchors."""

    name: str
    description: str
    scale: tuple[int, int]
    levels: tuple[Level, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scale", tuple(self.scale))
        object.__setattr__(self, "levels", tuple(self.levels))


@dataclass(frozen=True)
class Rubric:
    """A complete rubric with a version and a sequence of criteria."""

    name: str
    version: str
    criteria: tuple[Criterion, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "criteria", tuple(self.criteria))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return the rubric as a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "criteria": [
                {
                    "name": crit.name,
                    "description": crit.description,
                    "scale": [crit.scale[0], crit.scale[1]],
                    "levels": [
                        {
                            "score": lev.score,
                            "descriptor": lev.descriptor,
                            "anchors": list(lev.anchors),
                        }
                        for lev in crit.levels
                    ],
                }
                for crit in self.criteria
            ],
        }

    def to_json(self) -> str:
        """Return the rubric as a pretty-printed JSON string."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, text: str, *, max_chars: int = 1_000_000) -> Rubric:
        """Parse a rubric from JSON text.

        Args:
            text: JSON string.
            max_chars: Maximum allowed length of ``text``.  Defaults to
                1_000_000.  Exceeding this raises ``input_too_large``.

        Raises:
            RubricError: with appropriate code for malformed JSON, invalid
                version, too many criteria, too deep nesting, or structural
                violations.
        """
        if len(text) > max_chars:
            raise RubricError("input_too_large", "JSON input exceeds size limit")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RubricError("invalid_json", "Invalid JSON syntax") from exc
        except RecursionError as exc:
            raise RubricError("invalid_json", "JSON nesting too deep") from exc

        # Enforce nesting depth <= 8
        def check_depth(obj: Any, depth: int) -> None:
            if depth > 8:
                raise RubricError("invalid_json", "JSON nesting too deep")
            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, depth + 1)
            elif isinstance(obj, list):
                for value in obj:
                    check_depth(value, depth + 1)

        try:
            check_depth(data, 0)
        except RubricError:
            raise

        # Validate top-level structure
        if not isinstance(data, dict):
            raise RubricError("invalid_json", "Expected a JSON object")
        if set(data.keys()) != {"name", "version", "criteria"}:
            raise RubricError("invalid_json", "Unexpected or missing top-level keys")
        name = data["name"]
        version = data["version"]
        criteria_data = data["criteria"]
        if (
            not isinstance(name, str)
            or not isinstance(version, str)
            or not isinstance(criteria_data, list)
        ):
            raise RubricError("invalid_json", "Invalid types for top-level fields")
        if not _is_valid_version_string(version):
            raise RubricError("invalid_version", "Invalid version string")
        if len(criteria_data) > 20:
            raise RubricError("too_many_criteria", "Too many criteria")

        criteria: list[Criterion] = []
        for crit_data in criteria_data:
            if not isinstance(crit_data, dict):
                raise RubricError("invalid_json", "Each criterion must be an object")
            if set(crit_data.keys()) != {"name", "description", "scale", "levels"}:
                raise RubricError("invalid_json", "Unexpected or missing criterion keys")
            crit_name = crit_data["name"]
            crit_desc = crit_data["description"]
            scale_data = crit_data["scale"]
            levels_data = crit_data["levels"]
            if (
                not isinstance(crit_name, str)
                or not isinstance(crit_desc, str)
                or not isinstance(scale_data, list)
                or len(scale_data) != 2
                or not all(isinstance(x, int) for x in scale_data)
                or not isinstance(levels_data, list)
            ):
                raise RubricError("invalid_json", "Invalid criterion field types")
            scale_min, scale_max = scale_data
            if not _valid_scale(scale_min, scale_max):
                raise RubricError("invalid_json", "Invalid scale in criterion")
            levels: list[Level] = []
            seen_scores: set[int] = set()
            for lev_data in levels_data:
                if not isinstance(lev_data, dict):
                    raise RubricError("invalid_json", "Each level must be an object")
                if set(lev_data.keys()) != {"score", "descriptor", "anchors"}:
                    raise RubricError("invalid_json", "Unexpected or missing level keys")
                score = lev_data["score"]
                descriptor = lev_data["descriptor"]
                anchors = lev_data["anchors"]
                if (
                    not isinstance(score, int)
                    or not isinstance(descriptor, str)
                    or not isinstance(anchors, list)
                    or not all(isinstance(a, str) for a in anchors)
                ):
                    raise RubricError("invalid_json", "Invalid level field types")
                if score < scale_min or score > scale_max:
                    raise RubricError("invalid_json", "Level score out of scale")
                if score in seen_scores:
                    raise RubricError("invalid_json", "Duplicate level score")
                seen_scores.add(score)
                levels.append(Level(score, descriptor, tuple(anchors)))
            if seen_scores != set(range(scale_min, scale_max + 1)):
                raise RubricError("invalid_json", "Levels do not cover the entire scale")
            criteria.append(Criterion(crit_name, crit_desc, (scale_min, scale_max), tuple(levels)))

        return cls(name, version, tuple(criteria))

    # ------------------------------------------------------------------
    # Fingerprinting
    # ------------------------------------------------------------------

    def fingerprint(self) -> str:
        """Return a SHA-256 fingerprint of the rubric content (version excluded)."""
        d = self.to_dict()
        d.pop("version", None)
        canonical = json.dumps(
            d,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    # ------------------------------------------------------------------
    # Version bump
    # ------------------------------------------------------------------

    def next_version(self, old: Rubric) -> str:
        """Compute the semantic version for this rubric given the previous rubric.

        Rules (in order):
        1. If fingerprints are equal, return the old version unchanged.
        2. If any criterion was removed or any scale changed, bump major.
        3. If any criterion was added or any anchors tuple changed, bump minor.
        4. Otherwise (descriptions or descriptors changed), bump patch.

        Args:
            old: The previous Rubric.

        Returns:
            The new version string (MAJOR.MINOR.PATCH).
        """
        if self.fingerprint() == old.fingerprint():
            return old.version

        old_crits = {c.name: c for c in old.criteria}
        new_crits = {c.name: c for c in self.criteria}
        removed = set(old_crits) - set(new_crits)
        added = set(new_crits) - set(old_crits)
        common = set(old_crits) & set(new_crits)

        # Check for major: removed criteria or scale change
        major_change = bool(removed)
        if not major_change:
            for name in common:
                if old_crits[name].scale != new_crits[name].scale:
                    major_change = True
                    break
        if major_change:
            return _increment_version(old.version, "major")

        # Check for minor: added criteria or anchor tuple change
        minor_change = bool(added)
        if not minor_change:
            for name in common:
                old_levels = {lev.score: lev.anchors for lev in old_crits[name].levels}
                new_levels = {lev.score: lev.anchors for lev in new_crits[name].levels}
                if old_levels != new_levels:
                    minor_change = True
                    break
        if minor_change:
            return _increment_version(old.version, "minor")

        # Otherwise patch (descriptions or descriptors changed)
        return _increment_version(old.version, "patch")

    # ------------------------------------------------------------------
    # Prompt rendering
    # ------------------------------------------------------------------

    def render_prompt(
        self,
        examples: Sequence[Example],
        *,
        max_example_chars: int = 300,
    ) -> str:
        """Render the rubric as an exact judge prompt.

        Args:
            examples: The examples corresponding to ``Example`` objects.
            max_example_chars: Maximum number of characters of example text
                to include before truncation.  Defaults to 300.

        Returns:
            The prompt string.  Every line ends with ``\n``; consecutive
            criteria are separated by one empty line.

        Raises:
            RubricError: with code ``missing_example`` if an anchor ID does
                not match any provided example.
        """
        example_by_id = {ex.id: ex for ex in examples}
        parts: list[str] = []
        for crit in self.criteria:
            block: list[str] = []
            block.append(f"Criterion: {crit.name} ({crit.scale[0]}-{crit.scale[1]})")
            block.append(crit.description)
            for lev in crit.levels:
                block.append(f"{lev.score}: {lev.descriptor}")
                for anchor_id in lev.anchors:
                    if anchor_id not in example_by_id:
                        raise RubricError(
                            "missing_example", f"Missing example for anchor '{anchor_id}'"
                        )
                    example = example_by_id[anchor_id]
                    text = example.text.replace("\n", " ").replace("\r", " ")
                    if len(text) > max_example_chars:
                        text = text[:max_example_chars] + "..."
                    block.append(f"  Example {anchor_id}: {text}")
            parts.append("\n".join(block))
        header = f"Rubric: {self.name} v{self.version}\n\n"
        body = "\n\n".join(parts)
        return header + body + "\n"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _valid_scale(min_score: int, max_score: int) -> bool:
    return min_score >= 0 and max_score > min_score and max_score - min_score <= 9


def _is_valid_version_string(version: str) -> bool:
    parts = version.split(".")
    if len(parts) != 3:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        if len(part) > 1 and part[0] == "0":
            return False
    return True


def _increment_version(version: str, component: Literal["major", "minor", "patch"]) -> str:
    major, minor, patch = map(int, version.split("."))
    if component == "major":
        major += 1
        minor = 0
        patch = 0
    elif component == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


# ---------------------------------------------------------------------------
# Public builder function
# ---------------------------------------------------------------------------


def build_rubric(
    name: str,
    criteria: Sequence[CriterionSpec],
    examples: Sequence[Example],
    *,
    version: str = "1.0.0",
    anchors_per_level: int = 2,
    allow_missing_anchors: bool = False,
) -> Rubric:
    """Build a Rubric from specifications and scored examples.

    Args:
        name: The rubric name.
        criteria: Sequence of CriterionSpec.
        examples: Sequence of Example used to anchor score levels.
        version: Semantic version string (must be MAJOR.MINOR.PATCH with
            non-negative integers and no leading zeros).  Defaults to
            ``"1.0.0"``.
        anchors_per_level: Number of example anchors to select per level
            (1-5).  Defaults to 2.
        allow_missing_anchors: If True, levels with no matching examples get
            an empty anchors tuple instead of raising ``missing_anchor``.
            Defaults to False.

    Returns:
        A fully constructed Rubric.

    Raises:
        RubricError: with appropriate code for validation failures, duplicate
            example IDs, unknown criteria in example scores, score out of
            scale, missing anchor, invalid options, or input limits.
    """
    # Validate version
    if not _is_valid_version_string(version):
        raise RubricError("invalid_version", "Invalid version string")
    # Validate options
    if anchors_per_level < 1 or anchors_per_level > 5:
        raise RubricError("invalid_options", "anchors_per_level must be between 1 and 5")
    # Enforce limits
    if len(criteria) > 20:
        raise RubricError("too_many_criteria", "Too many criteria")
    if len(examples) > 10_000:
        raise RubricError("too_many_examples", "Too many examples")

    # Check duplicate example IDs and validate example scores
    seen_ids: set[str] = set()
    for ex in examples:
        if ex.id in seen_ids:
            raise RubricError("duplicate_example", f"Duplicate example id: {ex.id}")
        seen_ids.add(ex.id)
        for crit_name, score in ex.scores.items():
            # Find criterion spec by name
            crit_spec = next((c for c in criteria if c.name == crit_name), None)
            if crit_spec is None:
                raise RubricError("unknown_criterion", f"Unknown criterion: {crit_name}")
            if score < crit_spec.scale[0] or score > crit_spec.scale[1]:
                raise RubricError(
                    "score_out_of_scale", f"Score out of scale for criterion {crit_name}"
                )

    # Build rubric criteria
    rubric_criteria: list[Criterion] = []
    for crit_spec in criteria:
        levels: list[Level] = []
        for score in range(crit_spec.scale[0], crit_spec.scale[1] + 1):
            matching_ids = [ex.id for ex in examples if ex.scores.get(crit_spec.name) == score]
            matching_ids.sort()
            selected = tuple(matching_ids[:anchors_per_level])
            if not selected and not allow_missing_anchors:
                raise RubricError(
                    "missing_anchor",
                    f"No example for score {score} in criterion {crit_spec.name}",
                )
            levels.append(Level(score, crit_spec.descriptors[score], selected))
        rubric_criteria.append(
            Criterion(crit_spec.name, crit_spec.description, crit_spec.scale, tuple(levels))
        )

    return Rubric(name, version, tuple(rubric_criteria))
