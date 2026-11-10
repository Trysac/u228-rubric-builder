# rubric-builder

[![PyPI version](https://img.shields.io/pypi/v/trysac-rubric-builder)](https://pypi.org/project/trysac-rubric-builder/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-rubric-builder)](LICENSE)
[![CI](https://github.com/Trysac/u228-rubric-builder/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u228-rubric-builder/actions/workflows/ci.yml)

Build versioned grading rubrics from human-scored examples: anchors per score level, a content fingerprint, semver bumps from rubric diffs and an exact judge prompt

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-rubric-builder
# or
uv add trysac-rubric-builder
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import rubric_builder

# normalize() trims surrounding whitespace and lower-cases the text.
print(rubric_builder.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    rubric_builder.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
