#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml>=0.18"]
# ///
"""Tidy a deployment repository's apps/values.yaml without changing what runs.

- A service entry with no value (`svc:`) becomes `svc: {}`. Helm v4 drops
  null-valued keys, so a null entry removes the service from the render.
- A service's `targetRevision` that equals `source.targetRevision` is removed:
  it changes nothing, and it stops the service following its revision line.
- `labels` entries with no value are removed, and so is `labels` if it is
  left empty.

Comments and layout are kept. Prints each change; with --check, changes
nothing and exits 1 if any change is needed.
"""

import sys
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


def tidy(values: CommentedMap) -> list[str]:
    changes: list[str] = []
    services = values.get("services")
    if not services:
        return changes
    default_revision = (values.get("source") or {}).get("targetRevision")

    for name in list(services):
        entry = services[name]
        if entry is None:
            services[name] = CommentedMap()
            changes.append(f"{name}: null entry -> {{}}")
            continue

        if default_revision and entry.get("targetRevision") == default_revision:
            del entry["targetRevision"]
            changes.append(f"{name}: removed targetRevision: {default_revision}")

        labels = entry.get("labels")
        if isinstance(labels, dict):
            for key in [k for k, v in labels.items() if v is None]:
                del labels[key]
                changes.append(f"{name}: removed empty label {key}")
        if "labels" in entry and not entry["labels"]:
            del entry["labels"]
            changes.append(f"{name}: removed empty labels")

    return changes


def main() -> None:
    args = sys.argv[1:]
    check = "--check" in args
    paths = [Path(a) for a in args if a != "--check"] or [Path("apps/values.yaml")]

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096

    needed = False
    for path in paths:
        values = yaml.load(path)
        changes = tidy(values)
        for change in changes:
            print(f"{path}: {change}")
        if changes:
            needed = True
            if not check:
                yaml.dump(values, path)
    sys.exit(1 if check and needed else 0)


if __name__ == "__main__":
    main()
