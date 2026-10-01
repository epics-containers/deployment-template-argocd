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
- A filled-out `labels.description` moves to a top-level `description`: the
  schema only allows a Kubernetes label value under `labels`, not free text.
  If `description` is already set too, the move is skipped and
  `labels.description` is dropped instead, with a warning -- moving it would
  silently overwrite the text already in `description`.
- `labels` entries with no value are removed, and so is `labels` if it is
  left empty (including once a `description` move empties it).

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
            description = labels.get("description")
            if description:
                if entry.get("description"):
                    del labels["description"]
                    changes.append(
                        f"{name}: WARNING kept description {entry['description']!r}, "
                        f"dropped labels.description {description!r} -- reconcile by hand"
                    )
                else:
                    entry["description"] = labels.pop("description")
                    changes.append(f"{name}: moved labels.description to description")
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
