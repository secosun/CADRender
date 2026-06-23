#!/usr/bin/env python3
"""Load CADRender environment from docs/environment_config.md and optional .env.

Priority (when override=False):
  1. Existing os.environ values — never overwritten
  2. Repo-root .env file
  3. ```cadrender-env``` block in environment_config.md

Used by:
  - scripts/load_calibration_env.ps1
  - blenderworker/scripts/calibrate.py (auto on startup)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DOC = _REPO_ROOT / "docs" / "environment_config.md"
_ENV_BLOCK_LANG = "cadrender-env"


def _parse_env_lines(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def _read_dotenv(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    return _parse_env_lines(path.read_text(encoding="utf-8"))


def _extract_cadrender_env_block(doc_path: Path) -> Dict[str, str]:
    if not doc_path.is_file():
        return {}
    text = doc_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"```{_ENV_BLOCK_LANG}\s*\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return {}
    return _parse_env_lines(match.group(1))


def collect_documented_env(
    repo_root: Path | None = None,
    doc_path: Path | None = None,
    dotenv_path: Path | None = None,
) -> Dict[str, str]:
    root = repo_root or _REPO_ROOT
    doc = doc_path or root / "docs" / "environment_config.md"
    env_file = dotenv_path or root / ".env"
    merged: Dict[str, str] = {}
    merged.update(_extract_cadrender_env_block(doc))
    merged.update(_read_dotenv(env_file))
    return merged


def apply_documented_env(
    override: bool = False,
    repo_root: Path | None = None,
    doc_path: Path | None = None,
    dotenv_path: Path | None = None,
) -> Dict[str, str]:
    """Apply documented env to os.environ. Returns keys that were set."""
    merged = collect_documented_env(repo_root, doc_path, dotenv_path)
    applied: Dict[str, str] = {}
    for key, value in merged.items():
        if not override and os.environ.get(key):
            continue
        os.environ[key] = value
        applied[key] = value
    return applied


def _export_lines(applied: Dict[str, str], shell: str) -> Iterable[str]:
    for key, value in sorted(applied.items()):
        escaped = value.replace("'", "''") if shell == "ps1" else value.replace('"', '\\"')
        if shell == "ps1":
            yield f"$env:{key} = '{escaped}'"
        elif shell == "bash":
            yield f"export {key}='{escaped}'"
        else:
            yield f"{key}={value}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load CADRender env from docs and .env")
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--doc", type=Path, default=None, help="Path to environment_config.md")
    parser.add_argument("--dotenv", type=Path, default=None, help="Path to .env (default: repo .env)")
    parser.add_argument("--override", action="store_true", help="Overwrite existing env vars")
    parser.add_argument(
        "--export",
        choices=("ps1", "bash", "dotenv"),
        help="Print shell exports or dotenv lines instead of applying",
    )
    parser.add_argument("--write", type=Path, metavar="PATH", help="Write merged config to a .env file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be applied")
    args = parser.parse_args(argv)

    doc = args.doc or args.repo_root / "docs" / "environment_config.md"
    dotenv = args.dotenv or args.repo_root / ".env"
    merged = collect_documented_env(args.repo_root, doc, dotenv)

    if args.write:
        lines = [f"{k}={v}" for k, v in sorted(merged.items())]
        args.write.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {len(lines)} variables to {args.write}")
        return 0

    if args.export:
        # For export, show vars that would be applied (respect override flag)
        to_export: Dict[str, str] = {}
        for key, value in merged.items():
            if not args.override and os.environ.get(key):
                continue
            to_export[key] = value
        for line in _export_lines(to_export, args.export):
            print(line)
        return 0

    if args.dry_run:
        for key, value in sorted(merged.items()):
            status = "skip (set)" if os.environ.get(key) and not args.override else "apply"
            print(f"{status:12} {key}={value}")
        return 0

    applied = apply_documented_env(
        override=args.override,
        repo_root=args.repo_root,
        doc_path=doc,
        dotenv_path=dotenv,
    )
    if applied:
        print(f"Applied {len(applied)} variables from {doc.name} / .env")
    else:
        print("No new variables applied (all already set or config empty)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
