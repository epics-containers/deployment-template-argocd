#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml>=0.18"]
# ///
"""Set services.<svc>.group in a deployment repo's apps/values.yaml from the
services repository's CODEOWNERS.

Reads CODEOWNERS top to bottom, as git does: for each `/services/<pattern>`
line under a `[Data Acquisition]` or `[Tech UI]` section header, the *last*
matching line for a service decides its team -- CODEOWNERS' own last-match-
wins rule, so a specific Data Acquisition or Tech UI entry placed below a
broader Controls glob wins, which is the section order DLS deployment repos
use (`[Controls]` first, then `[Data Acquisition]`, then `[Tech UI]`).
Controls, any other section, and services matched by no `/services/` line
get no `group`: they follow `source.targetRevision`. A section header may
have a leading `# ` (GitHub's CODEOWNERS has no sections, so the services
repo's template writes them as comments there).

Only the `group` key is touched: set to "daq" / "techui" where CODEOWNERS
says so, removed where a service no longer resolves to one, so re-running
after a CODEOWNERS change corrects it. Comments and layout are kept
(ruamel round-trip). `--check` reports without writing.

Usage:
    assign_groups.py <apps/values.yaml> --codeowners <path/to/CODEOWNERS> [--check]
"""

import argparse
import fnmatch
import re
import sys
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

# Section header text (case-insensitive) -> the group name the template and
# argocd-apps chart use (epics-containers/ec-helm-charts#135).
SECTION_TO_GROUP = {
    "data acquisition": "daq",
    "tech ui": "techui",
}

SECTION_RE = re.compile(r"^(?:#\s*)?\[(?P<name>[^\]]+)\]")
PATTERN_RE = re.compile(r"^(?P<pattern>\S+)")


def parse_codeowners(text: str) -> list[tuple[str, str | None]]:
    """Return [(glob under /services/, section name or None), ...] in file order."""
    entries: list[tuple[str, str | None]] = []
    section: str | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        header = SECTION_RE.match(stripped)
        if header:
            section = header.group("name").strip()
            continue
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = PATTERN_RE.match(line)
        if not match:
            continue
        pattern = match.group("pattern")
        if not pattern.startswith("/services/"):
            continue
        glob = pattern[len("/services/") :].rstrip("/")
        if not glob:
            continue
        entries.append((glob, section))
    return entries


def resolve_group(service: str, entries: list[tuple[str, str | None]]) -> str | None:
    """The group for `service`, from the last CODEOWNERS line that matches it."""
    group = None
    for glob, section in entries:
        if fnmatch.fnmatchcase(service, glob):
            group = SECTION_TO_GROUP.get((section or "").strip().lower())
    return group


def assign(values: CommentedMap, entries: list[tuple[str, str | None]]) -> list[str]:
    changes: list[str] = []
    services = values.get("services")
    if not services:
        return changes

    for name in list(services):
        entry = services[name]
        if entry is None:
            entry = services[name] = CommentedMap()

        wanted = resolve_group(name, entries)
        current = entry.get("group")
        if wanted == current:
            continue

        if wanted is None:
            del entry["group"]
            changes.append(f"{name}: removed group: {current}")
        elif current is None:
            entry["group"] = wanted
            changes.append(f"{name}: group -> {wanted}")
        else:
            entry["group"] = wanted
            changes.append(f"{name}: group: {current} -> {wanted}")

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "values", type=Path, nargs="?", default=Path("apps/values.yaml")
    )
    parser.add_argument("--codeowners", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    entries = parse_codeowners(args.codeowners.read_text())

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096

    values = yaml.load(args.values)
    changes = assign(values, entries)
    for change in changes:
        print(f"{args.values}: {change}")
    if changes and not args.check:
        yaml.dump(values, args.values)
    sys.exit(1 if args.check and changes else 0)


if __name__ == "__main__":
    main()
