#!/usr/bin/env python3
"""Render the reviewed register inventory and reproducible, self-contained releases."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from verify_registers import expected_macros

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = frozenset("auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while _Alignas _Alignof _Atomic _Bool _Complex _Generic _Imaginary _Noreturn _Static_assert _Thread_local".split())


@dataclass(frozen=True)
class RenderConfig:
    prefix: str
    output: Path
    metadata: Path

    @property
    def lower_prefix(self) -> str:
        return self.prefix + "_" if self.prefix else ""

    @property
    def upper_prefix(self) -> str:
        return self.lower_prefix.upper()


def validate_prefix(prefix: str) -> None:
    if prefix and (not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", prefix) or prefix in KEYWORDS):
        raise ValueError("prefix must be empty or a non-keyword lower_snake_case identifier starting with a letter")


def integer(value: object, label: str, maximum: int = 0xFFFFFFFF) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label}: boolean is not an integer")
    result = int(value, 0) if isinstance(value, str) else int(value) if isinstance(value, int) else -1
    if not 0 <= result <= maximum:
        raise ValueError(f"{label}: unresolved or out-of-range value {value!r}")
    return result


def optional_integer(value: object, label: str, maximum: int = 0xFFFFFFFF) -> int | None:
    return None if value is None else integer(value, label, maximum)


def safe_path(name: str) -> str:
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or any(part in (".", "..") for part in path.parts) or path.as_posix() != name:
        raise ValueError(f"unsafe output path: {name!r}")
    return name


def check_symbol(name: str, seen: set[str]) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or "__" in name or name in KEYWORDS:
        raise ValueError(f"invalid or reserved C name: {name}")
    if name in seen:
        raise ValueError(f"generated C name collision: {name}")
    seen.add(name)


def prepare(data: dict, config: RenderConfig) -> dict:
    validate_prefix(config.prefix)
    seen: set[str] = set()
    paths: set[str] = set()
    blocks = []
    for raw_block in sorted(data["blocks"], key=lambda item: item["name"]):
        block = dict(raw_block)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*", block["name"]):
            raise ValueError(f"invalid block filename: {block['name']}")
        block["slug"] = block["name"].lower()
        stem = "registers_" + block["slug"]
        path = safe_path(f"include/{config.lower_prefix}{stem}.h")
        if path in paths:
            raise ValueError(f"output path collision: {path}")
        paths.add(path)
        check_symbol(config.upper_prefix + stem.upper() + "_H", seen)
        registers = []
        for raw_register in sorted(block["registers"], key=lambda item: (integer(item["address"], "address") if item["address"] is not None else 0x100000000, item["name"])):
            register = dict(raw_register)
            if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*", register["name"]):
                raise ValueError(f"invalid register name: {register['name']}")
            for key in ("address", "reset", "writable_mask", "reserved_mask"):
                register[key] = optional_integer(register[key], register["name"] + "." + key)
            width = integer(register.get("storage_width", 32), "storage_width", 32)
            if width not in (8, 16, 32):
                raise ValueError("register storage_width must be 8, 16 or 32")
            register["storage_width"] = width
            if any(register[key] is not None and register[key] >= 1 << width for key in ("reset", "writable_mask", "reserved_mask")) or (register["writable_mask"] is not None and register["reserved_mask"] is not None and register["writable_mask"] & register["reserved_mask"]):
                raise ValueError(f"invalid reset or overlapping writable/reserved masks: {register['name']}")
            base = config.upper_prefix + register["name"]
            for key, suffix in (("address", "REG_ADDR"), ("reset", "REG_RESET_VALUE"), ("writable_mask", "WRITABLE_MASK"), ("reserved_mask", "RESERVED_MASK")):
                if register[key] is not None:
                    check_symbol(base + "_" + suffix, seen)
            fields = []
            occupied = 0
            for raw_field in sorted(register.get("fields", []), key=lambda item: (item["position"], item["name"])):
                field = dict(raw_field)
                field["reserved"] = bool(field.get("reserved", False) or field["name"].upper().startswith("RESERVED"))
                field["position"] = integer(field["position"], "position", 31)
                field["width"] = integer(field["width"], "width", 32)
                if not field["width"] or field["position"] + field["width"] > width:
                    raise ValueError(f"invalid field extent: {register['name']}.{field['name']}")
                field["reset"] = optional_integer(field["reset"], "field reset", (1 << field["width"]) - 1)
                field["mask"] = ((1 << field["width"]) - 1) << field["position"]
                field["range_resolved"] = not bool(field.get("range_conflict"))
                # Source aggregates belong in legacy_aliases, not the public
                # field inventory. Prose notes cannot authorize overlapping
                # public definitions.
                if occupied & field["mask"]:
                    raise ValueError(f"overlapping fields: {register['name']}.{field['name']}")
                occupied |= field["mask"]
                if field["range_resolved"] and field["reset"] is not None and register["reset"] is not None and field["reset"] != (register["reset"] & field["mask"]) >> field["position"]:
                    raise ValueError(f"register/field reset disagreement: {register['name']}.{field['name']}")
                field["enumerations"] = sorted(field.get("enumerations", []), key=lambda item: (integer(item["value"], "enum value"), item["name"]))
                if not field["reserved"]:
                    if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*", field["name"]):
                        raise ValueError(f"invalid field name: {field['name']}")
                    field_base = base + "_" + field["name"]
                    for suffix in (("POSITION", "WIDTH", "MASK") if field["range_resolved"] else ()) + (("RESET_VALUE",) if field["reset"] is not None else ()):
                        check_symbol(field_base + "_" + suffix, seen)
                    for enumeration in field["enumerations"]:
                        if not re.fullmatch(r"[A-Z0-9]+(?:_[A-Z0-9]+)*", enumeration["name"]):
                            raise ValueError(f"invalid enumeration name: {enumeration['name']}")
                        enumeration["value"] = integer(enumeration["value"], "enum value", (1 << field["width"]) - 1)
                        check_symbol(field_base + "_ENUM_" + enumeration["name"], seen)
                fields.append(field)
            register["fields"] = fields
            registers.append(register)
        block["registers"] = registers
        blocks.append(block)
    check_symbol(config.upper_prefix + "REGISTERS_H", seen)
    return {**data, "blocks": blocks}


def environment() -> Environment:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), undefined=StrictUndefined, keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)
    env.filters["hex32"] = lambda value: f"UINT32_C(0x{value:08X})"
    env.filters["comment"] = lambda value: str(value).replace("*/", "* /").replace("\r", "").replace("\n", "\n * ")
    env.filters["json"] = lambda value: json.dumps(value, ensure_ascii=True, sort_keys=True)
    return env


def render_files(data: dict, config: RenderConfig, prefix_only: bool = False) -> dict[str, tuple[bytes, str]]:
    env = environment()
    lower = "{{ lower_prefix }}" if prefix_only else config.lower_prefix
    upper = "{{ upper_prefix }}" if prefix_only else config.upper_prefix
    context = {"data": data, "lower_prefix": lower, "upper_prefix": upper}
    files: dict[str, tuple[bytes, str]] = {}
    def add(path: str, template: str, **extra: object) -> None:
        if path in files:
            raise ValueError(f"output path collision: {path}")
        files[path] = (env.get_template(template).render(**context, **extra).encode(), template)
    for block in data["blocks"]:
        add(f"include/{lower}registers_{block['slug']}.h", "include/registers_block.h.j2", block=block)
    add(f"include/{lower}registers.h", "include/registers.h.j2")
    add(f"examples/{lower}registers_example.c", "examples/registers_example.c.j2")
    registers = {reg["name"]: reg for block in data["blocks"] for reg in block["registers"]}
    macros = expected_macros(registers, config.prefix)
    if prefix_only:
        macros = {upper + name[len(config.upper_prefix):]: value for name, value in macros.items()}
    add(f"tests/{lower}registers_assertions.c", "tests/registers_assertions.c.j2", umbrella=lower + "registers.h", macros=macros)
    add("CMakeLists.txt", "release/CMakeLists.txt.j2")
    return files


def manifest(files: dict[str, tuple[bytes, str]], prefix: str, digest: str) -> bytes:
    return (json.dumps({"format_version": 1, "prefix": prefix, "metadata_sha256": digest, "files": [{"path": name, "sha256": hashlib.sha256(content).hexdigest(), "template": template} for name, (content, template) in sorted(files.items())]}, indent=2, sort_keys=True) + "\n").encode()


def write_files(output: Path, files: dict[str, tuple[bytes, str]], prefix: str, digest: str) -> None:
    # Validate the entire render before touching its destination.
    for name in files:
        safe_path(name)
    if (ROOT / "generated").resolve() not in output.resolve().parents:
        raise ValueError("output must be below this repository's ignored generated/ directory")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name, (content, _) in sorted(files.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (output / "manifest.json").write_bytes(manifest(files, prefix, digest))


def archive(directory: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                content = path.read_bytes()
                info = tarfile.TarInfo(directory.name + "/" + path.relative_to(directory).as_posix())
                info.size, info.mtime, info.mode = len(content), 0, 0o644
                tar.addfile(info, io.BytesIO(content))
    with directory.with_suffix(".tar.gz").open("wb") as target:
        with gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0) as compressed:
            compressed.write(buffer.getvalue())


def releases(data: dict, config: RenderConfig, raw: bytes, digest: str) -> None:
    env = environment()
    for prefix_only, name in ((False, "ad594x-registers"), (True, "ad594x-registers-prefix-template")):
        release_config = RenderConfig("ad594x", ROOT / "generated/releases" / name, config.metadata)
        release_data = prepare(data, release_config)
        rendered = render_files(release_data, release_config, prefix_only)
        if prefix_only:
            rendered = {"templates/" + path + ".j2": item for path, item in rendered.items()}
            rendered["scripts/render.py"] = ((ROOT / "scripts/render_prefix.py").read_bytes(), "scripts/render_prefix.py")
            rendered["requirements.txt"] = (b"Jinja2>=3.1,<4\n", "requirements-dev.txt")
        rendered["data/registers.json"] = (raw, "data/registers.json")
        for filename, template in (("README.md", "release/README.md.j2"), ("PROVENANCE.md", "release/PROVENANCE.md.j2"), ("DATA_FORMAT.md", "release/DATA_FORMAT.md.j2")):
            rendered[filename] = (env.get_template(template).render(data=release_data, prefix_only=prefix_only).encode(), template)
        write_files(release_config.output, rendered, "prefix-only" if prefix_only else "ad594x", digest)
        archive(release_config.output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="ad594x")
    parser.add_argument("--output", type=Path, default=ROOT / "generated/registers")
    parser.add_argument("--metadata", type=Path, default=ROOT / "data/registers.json")
    parser.add_argument("--releases", action="store_true")
    args = parser.parse_args()
    config = RenderConfig(args.prefix, args.output, args.metadata.resolve())
    raw = config.metadata.read_bytes()
    data = json.loads(raw)
    prepared = prepare(data, config)
    files = render_files(prepared, config)
    digest = hashlib.sha256(raw).hexdigest()
    write_files(config.output, files, config.prefix, digest)
    if args.releases:
        releases(data, config, raw, digest)
    print(f"Rendered {len(prepared['blocks'])} blocks into {config.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as error:
        print(f"generation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
