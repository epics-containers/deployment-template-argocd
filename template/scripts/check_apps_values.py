#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.18", "PyYAML>=6.0"]
# ///
"""Validate apps/values.yaml in CI.

Helm's own schema validation never sees this file: this repo's
apps/templates/all_apps.yaml renders the argocd-apps library chart with
`{{- include "ec-helm-charts.argocd-apps" . -}}`, which hands the root
values context straight through instead of nesting it under a dependency
name, so Helm validates an empty subtree against the chart's schema, not
this file (epics-containers/ec-helm-charts#135). This script is the only
place left to catch mistakes such as a null service entry -- e.g.
`services: {foo:}` -- before Argo CD prunes the service, or a `group` with
no matching `versions` entry.

The chart (and so schema) version comes from the
'# yaml-language-server: $schema=...' comment copier writes at the top of
apps/values.yaml -- one pin (argocd_apps_chart_version in copier.yml), read
here rather than duplicated into this script.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCHEMA_COMMENT_RE = re.compile(r"^#\s*yaml-language-server:\s*\$schema=(\S+)\s*$")


def find_schema_url(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = SCHEMA_COMMENT_RE.match(stripped)
        if match:
            return match.group(1)
        if not stripped.startswith("#"):
            break
    raise SystemExit(
        "no '# yaml-language-server: $schema=...' comment found "
        "at the top of the values file"
    )


def fetch_schema(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.load(response)


def check_groups(values: dict) -> list[str]:
    """Cross-field check a JSON Schema can't express: every service's
    `group`, if set, must name an entry in the root `versions` map."""
    versions = values.get("versions") or {}
    errors = []
    for name, entry in (values.get("services") or {}).items():
        if not isinstance(entry, dict):
            continue  # schema validation below already flags this
        group = entry.get("group")
        if group and group not in versions:
            errors.append(
                f"services.{name}.group: {group!r} has no matching entry in "
                f"versions (known: {sorted(versions)})"
            )
    return errors


def describe(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return f"{path or '<root>'}: {error.message}"


def check_pins(values: dict) -> list[str]:
    """Report every service that overrides `targetRevision` for itself,
    instead of following its group's line (or source.targetRevision).
    Not an error: a pin is an exception to clear before a maintenance
    window ends, and this is that checklist."""
    versions = values.get("versions") or {}
    warnings = []
    for name, entry in (values.get("services") or {}).items():
        if not isinstance(entry, dict):
            continue
        revision = entry.get("targetRevision")
        if not revision:
            continue
        group = entry.get("group")
        if group:
            follows = f"versions.{group}: {versions.get(group)!r}"
        else:
            follows = f"source.targetRevision: {values.get('source', {}).get('targetRevision')!r}"
        warnings.append(f"services.{name}: pinned to {revision!r} (would otherwise follow {follows})")
    return warnings


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "apps/values.yaml")
    text = path.read_text()
    schema_url = find_schema_url(text)
    print(f"{path}: validating against {schema_url}")
    schema = fetch_schema(schema_url)

    values = yaml.safe_load(text)

    if not isinstance(values, dict):
        print(f"{path}: FAILED")
        print(f"  - expected a mapping of apps values, got {type(values).__name__}")
        sys.exit(1)

    # apps/ is the deployment repo's own chart and may carry templates of its
    # own, whose values sit beside argocd-apps' at the top level. The schema
    # stays strict below the top level, where argocd-apps' own keys live.
    known = set(schema.get("properties", {}))
    extra = sorted(key for key in values if key not in known)
    schema = {**schema, "additionalProperties": True}

    validator = Draft202012Validator(schema)
    errors = [describe(e) for e in validator.iter_errors(values)]
    errors += check_groups(values)

    if errors:
        print(f"{path}: FAILED")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print(f"{path}: OK")
    if extra:
        print(f"  top-level keys for this repo's own templates (not checked): {', '.join(extra)}")

    pins = check_pins(values)
    if pins:
        verb = "services pin their" if len(pins) != 1 else "service pins its"
        print(f"WARNING: {len(pins)} {verb} own targetRevision (clear these when the window ends):")
        for pin in pins:
            print(f"  - {pin}")


if __name__ == "__main__":
    main()
