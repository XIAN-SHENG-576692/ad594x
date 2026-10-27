#!/usr/bin/env python3
"""Render the fully expanded prefix-only register release, without source data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

from jinja2 import Environment, StrictUndefined, meta

KEYWORDS = frozenset("auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while _Alignas _Alignof _Atomic _Bool _Complex _Generic _Imaginary _Noreturn _Static_assert _Thread_local".split())


def render(prefix: str, output: Path, replace: bool = False) -> None:
    root = Path(__file__).resolve().parents[1]
    if prefix and (not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", prefix) or prefix in KEYWORDS):
        raise ValueError("prefix must be empty or a non-keyword lower_snake_case identifier starting with a letter")
    lower = prefix + "_" if prefix else ""
    context = {"lower_prefix": lower, "upper_prefix": lower.upper()}
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    files: dict[str, bytes] = {}
    source_templates: dict[str, str] = {}
    seen: set[str] = set()
    for path in sorted((root / "templates").rglob("*.j2")):
        raw = path.read_text()
        parsed = env.parse(raw)
        if meta.find_undeclared_variables(parsed) - context.keys() or re.search(r"{%|{#", raw):
            raise ValueError(f"template contains operations beyond prefix substitution: {path.name}")
        name = env.from_string(path.relative_to(root / "templates").as_posix()[:-3]).render(**context)
        relative = PurePosixPath(name)
        if not name or "\\" in name or relative.is_absolute() or any(part in (".", "..") for part in relative.parts) or relative.as_posix() != name or name in files:
            raise ValueError(f"unsafe or duplicate output path: {name}")
        content = env.from_string(raw).render(**context)
        if name.endswith(".h"):
            for symbol in re.findall(r"^#define\s+(\S+)", content, re.MULTILINE):
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", symbol) or "__" in symbol or symbol in KEYWORDS or symbol in seen:
                    raise ValueError(f"invalid, reserved or duplicate C macro: {symbol}")
                seen.add(symbol)
        files[name] = content.encode()
        source_templates[name] = path.relative_to(root).as_posix()
    if not files:
        raise ValueError("no prefix templates found")
    resolved = output.resolve()
    if resolved == root or resolved in root.parents or (root / "templates").resolve() in (resolved, *resolved.parents):
        raise ValueError("output would overwrite package inputs")
    if output.exists() and any(output.iterdir()) and not replace:
        raise ValueError("output is nonempty; use --replace to replace it")
    if output.exists() and replace:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(files.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    manifest = {"format_version": 1, "prefix": prefix, "files": [{"path": name, "sha256": hashlib.sha256(content).hexdigest(), "template": source_templates[name]} for name, content in sorted(files.items())]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="ad594x")
    parser.add_argument("--output", type=Path, default=Path("rendered"))
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    render(args.prefix, args.output, args.replace)
    print(f"Rendered register package into {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"render failed: {error}", file=sys.stderr)
        raise SystemExit(1)
