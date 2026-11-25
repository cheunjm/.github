#!/usr/bin/env python3
"""Apply the standard default-branch ruleset to cheunjm repos (INF-1983, D18).

Reads `[repos.<name>]` from secrets.manifest.toml. The ruleset, named
`default-branch`, requires `ci / gate`, `changeset / check` and the repo's
`extra_checks`, each pinned to the GitHub Actions app so another app cannot
satisfy them. Repository admins can bypass it (D22.5). An existing ruleset of
that name is updated in place.

    python3 scripts/apply-rulesets.py --repo ui --dry-run   # print the payload
    python3 scripts/apply-rulesets.py --repo ui
    python3 scripts/apply-rulesets.py --all                 # every repo with ruleset = true

Private repos need GitHub Pro for rulesets; public repos work on Free.
"""

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "secrets.manifest.toml"
RULESET_NAME = "default-branch"
GITHUB_ACTIONS_APP_ID = 15368
ADMIN_ROLE_ID = 5


def payload(extra_checks: list[str]) -> dict:
    contexts = ["ci / gate", "changeset / check", *extra_checks]
    return {
        "name": RULESET_NAME,
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": False,
                    "required_status_checks": [
                        {"context": c, "integration_id": GITHUB_ACTIONS_APP_ID}
                        for c in contexts
                    ],
                },
            }
        ],
        "bypass_actors": [
            {
                "actor_id": ADMIN_ROLE_ID,
                "actor_type": "RepositoryRole",
                "bypass_mode": "always",
            }
        ],
    }


def gh_api(args: list[str], body: dict | None = None) -> str:
    result = subprocess.run(
        ["gh", "api", *args],
        input=json.dumps(body) if body is not None else None,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"gh api {' '.join(args)} failed")
    return result.stdout


def apply(owner: str, repo: str, body: dict) -> str:
    existing = json.loads(gh_api([f"repos/{owner}/{repo}/rulesets"]) or "[]")
    match = next((r for r in existing if r.get("name") == RULESET_NAME), None)
    if match:
        gh_api(
            [
                "-X",
                "PUT",
                f"repos/{owner}/{repo}/rulesets/{match['id']}",
                "--input",
                "-",
            ],
            body,
        )
        return "updated"
    gh_api(["-X", "POST", f"repos/{owner}/{repo}/rulesets", "--input", "-"], body)
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--repo", help="one repo, whatever its ruleset flag")
    target.add_argument(
        "--all", action="store_true", help="every repo with ruleset = true"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--owner", default="cheunjm")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the payload; change nothing"
    )
    args = parser.parse_args()

    repos = tomllib.loads(args.manifest.read_text()).get("repos", {})
    if args.repo:
        if args.repo not in repos:
            print(f"{args.repo} is not declared under [repos]", file=sys.stderr)
            return 2
        selected = [args.repo]
    else:
        selected = [name for name, cfg in repos.items() if cfg.get("ruleset")]

    failed = False
    for repo in selected:
        body = payload(repos[repo].get("extra_checks", []))
        if args.dry_run:
            print(json.dumps(body, indent=2))
            print(f"{repo}: dry run", file=sys.stderr)
            continue
        try:
            print(f"{repo}: {apply(args.owner, repo, body)}", file=sys.stderr)
        except RuntimeError as err:
            failed = True
            print(f"{repo}: failed: {err}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
