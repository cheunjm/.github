#!/usr/bin/env python3
"""Push pipeline secrets from 1Password to every cheunjm repo (INF-1983, D14).

The manifest (secrets.manifest.toml) lists names, 1Password references and the
repos (and GitHub Environment) each one goes to; it never holds values. Each
value is read with `op read` and handed to `gh secret set` / `gh variable set`
on stdin, so it never appears in argv, logs or this script's output.

    python3 scripts/sync-secrets.py --dry-run           # check every op:// ref resolves
    python3 scripts/sync-secrets.py                     # set everything
    python3 scripts/sync-secrets.py --repo ui --name EXPO_TOKEN

Output is one line per (name, repo[, env]): ok / missing (dry run) or set /
missing / failed. Exit 1 if anything is missing or failed, 2 on a bad manifest.
"""

import argparse
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "secrets.manifest.toml"


@dataclass(frozen=True)
class Target:
    name: str
    ref: str
    repo: str
    env: str | None
    kind: str


def load_targets(path: Path) -> list[Target]:
    data = tomllib.loads(path.read_text())
    repos = list(data.get("repos", {}))
    targets = []
    for entry in data.get("secret", []):
        name, ref = entry["name"], entry["ref"]
        kind = entry.get("kind", "secret")
        if kind not in ("secret", "variable"):
            raise ValueError(f"{name}: kind must be secret or variable, got {kind!r}")
        if not ref.startswith("op://"):
            raise ValueError(f"{name}: ref must be an op:// reference")
        wanted = repos if entry["repos"] == "all" else entry["repos"]
        for repo in wanted:
            if repo not in repos:
                raise ValueError(f"{name}: repo {repo!r} is not declared under [repos]")
            targets.append(Target(name, ref, repo, entry.get("env"), kind))
    return targets


def read_ref(ref: str) -> str | None:
    result = subprocess.run(
        ["op", "read", "--no-newline", ref], capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def set_value(target: Target, value: str, owner: str) -> bool:
    cmd = ["gh", target.kind, "set", target.name, "--repo", f"{owner}/{target.repo}"]
    if target.env:
        cmd += ["--env", target.env]
    result = subprocess.run(cmd, input=value, capture_output=True, text=True)
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--owner", default="cheunjm")
    parser.add_argument("--repo", help="only this repo")
    parser.add_argument("--name", help="only this secret or variable name")
    parser.add_argument(
        "--dry-run", action="store_true", help="check refs resolve; set nothing"
    )
    args = parser.parse_args()

    try:
        targets = load_targets(args.manifest)
    except (KeyError, ValueError, tomllib.TOMLDecodeError) as err:
        print(f"bad manifest: {err}", file=sys.stderr)
        return 2
    targets = [
        t
        for t in targets
        if (args.repo is None or t.repo == args.repo)
        and (args.name is None or t.name == args.name)
    ]

    values: dict[str, str | None] = {}
    bad = False
    for target in targets:
        if target.ref not in values:
            values[target.ref] = read_ref(target.ref)
        value = values[target.ref]
        label = " ".join(
            part for part in (target.name, target.repo, target.env) if part
        )
        if value is None:
            status = "missing"
        elif args.dry_run:
            status = "ok"
        else:
            status = "set" if set_value(target, value, args.owner) else "failed"
        bad = bad or status in ("missing", "failed")
        print(f"{label} {status}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
