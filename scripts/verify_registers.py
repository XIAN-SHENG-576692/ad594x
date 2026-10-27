#!/usr/bin/env python3
"""Offline independent metadata, generated-header, and package verification.

No network or /tmp reference checkout is required. Source anchors below were
reviewed independently; they supplement, rather than prove, source completeness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
IDENT = re.compile(r"[A-Z][A-Z0-9_]*\Z")
COMPONENT = re.compile(r"[A-Z0-9][A-Z0-9_]*\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def number(value: object) -> int:
    require(isinstance(value, (int, str)) and not isinstance(value, bool), f"invalid integer: {value!r}")
    return int(value, 0) if isinstance(value, str) else value


def refs(item: dict, label: str, sources: set[str]) -> None:
    require(bool(item.get("source_refs")), f"missing evidence: {label}")
    for ref in item["source_refs"]:
        require(ref["source"] in sources and bool(ref.get("location")), f"invalid evidence: {label}")


def metadata_checks(data: dict) -> dict[str, dict]:
    require(data["schema_version"] == 1, "unsupported schema")
    sources = {source["id"] for source in data["sources"]}
    require(sources == {"driver", "datasheet"}, "only the two allowed references may be recorded")
    require({source["url"] for source in data["sources"]} == {
        "https://github.com/analogdevicesinc/no-OS/tree/main/drivers/afe/ad5940",
        "https://www.analog.com/media/en/technical-documentation/data-sheets/ad5940-5941.pdf",
    }, "unexpected reference URL")
    enum_settings = [setting for group in data["driver_enum_declarations"] for setting in group["settings"]]
    enum_expected = {"SPI_POINTER_" + name: value for name, value in zip(
        ("SPI", "AGPIO", "AFECON", "WUPTMR", "ALLON", "INTC", "AFE", "USER0", "USER1", "USER2"),
        (0, 1, 2, 4, 6, 7, 11, 13, 14, 15))}
    enum_expected.update({"AFERESULT_" + name: value for value, name in enumerate(
        ("SINC3", "SINC2", "TEMPSENSOR", "DFTREAL", "DFTIMAGE", "STATSMEAN", "STATSVAR", "COUNT"))})
    require(len(enum_settings) == 18 and {item["name"]: number(item["value"]) for item in enum_settings} == enum_expected, "reviewed C enum selector inventory changed")
    for group in data["driver_enum_declarations"]:
        require(group["kind"] in ("protocol-context", "software-selector") and bool(group["reason"]), "non-register selector lacks disposition")
        for setting in group["settings"]:
            refs(setting, setting["name"], sources)
    registers = {}
    notes = json.loads((ROOT / "data/block_notes.json").read_text())
    require({block["name"] for block in data["blocks"]} == set(notes), "block-note inventory differs from metadata blocks")
    for block in data["blocks"]:
        require(block.get("notes") == [note["description"] for note in notes[block["name"]]], f"block context not preserved: {block['name']}")
        for note in notes[block["name"]]:
            require(bool(note["description"]), "empty block context")
            refs(note, block["name"], sources)
            require(all(ref in block["source_refs"] for ref in note["source_refs"]), f"block context lost references: {block['name']}")
    addresses = set()
    for block in data["blocks"]:
        require(bool(IDENT.fullmatch(block["name"].upper())), "invalid block name")
        for reg in block["registers"]:
            name = reg["name"]
            require(bool(IDENT.fullmatch(name)), f"invalid register name {name}")
            require(name not in registers, f"block-free register collision: {name}")
            registers[name] = reg
            address = number(reg["address"])
            reset = number(reg["reset"]) if reg["reset"] is not None else None
            width = reg["storage_width"]
            require(width in (16, 32), f"invalid register storage width: {name}")
            require(0 <= address <= 0xFFFF and address % 4 == 0, f"invalid address: {name}")
            require(address not in addresses, f"duplicate register address: {name}")
            addresses.add(address)
            require(reset is None or 0 <= reset < (1 << width), f"reset out of range: {name}")
            refs(reg, name, sources)
            require(reg.get("evidence_status") not in (None, "", "unreviewed"), f"unreviewed register: {name}")
            fields, used, writable = set(), 0, 0
            for field in reg["fields"]:
                label = f'{name}_{field["name"]}'
                require(bool(IDENT.fullmatch(field["name"])), f"invalid field name {label}")
                require(not re.search(r"RESERV|RESEVER|RESRVD|RESVD", field["name"]) or field.get("reserved", False), f"reserved or misspelled reserved field exposed publicly: {label}")
                require(field["name"] not in fields, f"duplicate field: {label}")
                fields.add(field["name"])
                pos, size = field["position"], field["width"]
                require(isinstance(pos, int) and isinstance(size, int) and 0 <= pos < width and 1 <= size <= width - pos, f"invalid field bounds: {label}")
                mask = ((1 << size) - 1) << pos
                require(not (mask & used), f"overlapping public fields: {label}")
                used |= mask
                field_reset = number(field["reset"]) if field["reset"] is not None else None
                require(field_reset is None or 0 <= field_reset < (1 << size), f"field reset not unshifted: {label}")
                require(field_reset is None or reset is None or field_reset == ((reset & mask) >> pos), f"field/register reset mismatch: {label}")
                refs(field, label, sources)
                require(field.get("evidence_status") not in (None, "", "unreviewed"), f"unreviewed field: {label}")
                if "W" in field["access"]:
                    writable |= mask
                enum_names = set()
                for enum in field["enumerations"]:
                    refs(enum, label + "_ENUM_" + enum["name"], sources)
                    require(bool(COMPONENT.fullmatch(enum["name"])), f"invalid enumeration name: {label}")
                    require(enum["name"] not in enum_names, f"duplicate enumeration: {label}")
                    enum_names.add(enum["name"])
                    require(0 <= number(enum["value"]) < (1 << size), f"enumeration not unshifted: {label}")
            reserved = number(reg["reserved_mask"]) if reg["reserved_mask"] is not None else None
            write = number(reg["writable_mask"]) if reg["writable_mask"] is not None else None
            require(reserved is None or 0 <= reserved <= 0xFFFFFFFF, f"reserved mask out of range: {name}")
            require(write is None or 0 <= write <= 0xFFFFFFFF, f"write mask out of range: {name}")
            if reserved is not None and reserved & used:
                for field in reg["fields"]:
                    if field.get("reserved", False) or field["name"].startswith("RESERVED"):
                        continue
                    mask = ((1 << field["width"]) - 1) << field["position"]
                    if mask & reserved:
                        require(field["access"] == "?" and any(c["register"] == name and c["attribute"] == f"field.{field['name']}.access" for c in data["conflicts"]), f"unexplained reserved/field overlap: {name}_{field['name']}")
            require(reserved is None or write is None or not (reserved & write), f"reserved/writable overlap: {name}")
            require(write is None or write == writable, f"writable mask disagrees with field access: {name}")
    # Independently counted from the reviewed driver snapshot: 162 address
    # declarations and 560 paired BITP/BITM definitions, not a metadata claim.
    require(len(registers) == 162, "reviewed driver register inventory must contain 162 registers")
    require(sum(any(ref["source"] == "driver" for ref in reg["source_refs"]) for reg in registers.values()) == 162, "driver register coverage lost")
    require(data["coverage"]["registers"] == len(registers), "coverage register count disagrees")
    require(data["coverage"]["fields"] == sum(len(reg["fields"]) for reg in registers.values()), "coverage field count disagrees")
    require(data["coverage"]["pdf_indexed_lines"] == 6284, "full reviewed PDF text coverage changed")
    # Datasheet Rev G p28 Tables11-13; pp25,58,61,93,99,129,132.
    anchors = {
        "ADIID": (0x400, 0x4144),
        "AFECON": (0x2000, 0x80000), "ADCFILTERCON": (0x2044, 0x301),
        "DFTCON": (0x20D0, 0x90), "SEQCON": (0x2004, 2),
        "WGCON": (0x2014, 0x30), "LPMODECON": (0x2114, 0x102),
        "CLKCON0": (0x408, 0x441),
    }
    for name, (address, reset) in anchors.items():
        require(name in registers, f"missing independently reviewed register: {name}")
        require(number(registers[name]["address"]) == address and (registers[name]["reset"] is None or number(registers[name]["reset"]) == reset), f"datasheet anchor failed: {name}")
    adiid = next(field for field in registers["ADIID"]["fields"] if field["name"] == "ADIID")
    require(adiid["position"] == 0 and adiid["width"] == 16 and number(adiid["reset"]) == 0x4144 and adiid["access"] == "R", "ADIID field regression")
    require(number(registers["ADIID"]["writable_mask"]) == 0, "ADIID must be read-only")
    pmbw = registers["PMBW"]
    fields = {field["name"]: field for field in pmbw["fields"]}
    require(fields["SYSHS"]["position"] == 0 and fields["SYSBW"]["position"] == 2 and fields["SYSBW"]["width"] == 2, "PMBW field range regression")
    require(number(pmbw["reserved_mask"]) == 0xFFFFFFF2 and number(pmbw["writable_mask"]) == 0xD, "PMBW mask regression")
    require(any(e["name"] == "50KHZ" and number(e["value"]) == 1 for e in fields["SYSBW"]["enumerations"]), "PMBW 50KHZ encoding regression")
    for name in ("CALDATLOCK", "CLKEN1"):
        require(registers[name]["reset"] is None and any(c["register"] == name and c["attribute"] == "reset" and c["resolution"] == "unresolved" for c in data["conflicts"]), f"true reset conflict must remain explicitly unresolved: {name}")
    return registers


def driver_settings_checks(registers: dict, path: Path = ROOT / "data/driver_settings.json") -> None:
    ledger = json.loads(path.read_text())
    require(ledger["schema_version"] == 1 and ledger["source"] == "driver", "invalid high-level setting ledger")
    settings = [setting for group in ledger["groups"] for setting in group["settings"]]
    names = [setting["name"] for setting in settings]
    # Independent extraction from active driver #defines, lines2397–3532;
    # excludes C comments before parsing, includes function-like macro names.
    digest = hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest()
    require(len(names) == len(set(names)) == 428 and digest == "02443d635b7e5585a75793d0f5d2b1a529ee90f176cf00e863f7d461acc2f84b", "high-level declaration inventory differs from independently reviewed driver")
    expressions = sorted([[setting["name"], setting["source_value"], setting["source_line"]] for setting in settings])
    expression_digest = hashlib.sha256(json.dumps(expressions, separators=(",", ":")).encode()).hexdigest()
    require(expression_digest == "42b93fb4a449d78a07e8e879cbda4191cb224bc7c81d4e5efd67a8ed26df9e40", "setting expressions/locations differ from independently reviewed driver")
    statuses = {status: 0 for status in ("direct", "composite", "unresolved", "excluded")}
    mappings = 0
    for group in ledger["groups"]:
        status = group["status"]
        require(status in statuses, f"invalid high-level setting category: {status}")
        statuses[status] += len(group["settings"])
        require(bool(group["settings"]), "empty setting group")
        require(status == "direct" or bool(group.get("notes")), "non-direct setting lacks disposition explanation")
        if status == "excluded":
            require(not group["targets"], "excluded setting has register targets")
        else:
            require(bool(group["targets"]), "mapped setting lacks targets")
            require(status != "direct" or bool(group["evidence_lines"]), f"direct setting lacks implementation evidence: {group['family']}")
        for target in group["targets"]:
            require(target["register"] in registers, f"setting references missing register: {target}")
            if status != "direct":
                continue
            field = next((f for f in registers[target["register"]]["fields"] if f["name"] == target["field"]), None)
            require(field is not None, f"direct setting references missing field: {target}")
            for setting in group["settings"]:
                refs(setting, setting["name"], {"driver"})
                value = number(setting["value"])
                require(0 <= value < (1 << field["width"]), f"mapped setting exceeds field: {setting['name']}")
                location = f"ad5940.h:{setting['source_line']}"
                candidates = [enum for enum in field["enumerations"] if number(enum["value"]) == value and any(ref["source"] == "driver" and ref["location"] == location for ref in enum.get("source_refs", []))]
                require(bool(candidates), f"direct setting lacks corresponding public enumeration/provenance: {setting['name']} -> {target}")
                mappings += 1
    require(ledger["coverage"]["declarations"] == 428 and ledger["coverage"]["by_status"] == statuses, "setting coverage categories disagree")
    require(sum(statuses.values()) == 428, "setting disposition coverage is incomplete")
    require(mappings >= 541, "reviewed direct setting mappings lost")


def expected_macros(registers: dict, prefix: str) -> dict[str, str]:
    upper = prefix.upper() + "_" if prefix else ""
    result = {}
    def add(name: str, value: int, decimal: bool = False) -> None:
        key = upper + name
        require(key not in result, f"macro collision: {key}")
        result[key] = f"{value}U" if decimal else f"UINT32_C(0x{value:08X})"
    for name, reg in registers.items():
        for attr, key in (("REG_ADDR", "address"), ("REG_RESET_VALUE", "reset"), ("WRITABLE_MASK", "writable_mask"), ("RESERVED_MASK", "reserved_mask")):
            if reg[key] is not None:
                add(f"{name}_{attr}", number(reg[key]))
        for field in reg["fields"]:
            if field.get("reserved", False) or field["name"].startswith("RESERVED"):
                continue
            stem = name + "_" + field["name"]
            if not field.get("range_conflict"):
                add(stem + "_POSITION", field["position"], True)
                add(stem + "_WIDTH", field["width"], True)
                add(stem + "_MASK", ((1 << field["width"]) - 1) << field["position"])
            if field["reset"] is not None:
                add(stem + "_RESET_VALUE", number(field["reset"]))
            for enum in field["enumerations"]:
                add(stem + "_ENUM_" + enum["name"], number(enum["value"]))
    return result


def run(args: list[str], cwd: Path = ROOT) -> None:
    proc = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(proc.returncode == 0, f"command failed ({' '.join(args)}):\n{proc.stdout}")


def tree(path: Path) -> dict[str, bytes]:
    return {file.relative_to(path).as_posix(): file.read_bytes() for file in sorted(path.rglob("*")) if file.is_file()}


def header_checks(output: Path, registers: dict, prefix: str, cc: str, template_root: Path = ROOT / "templates") -> None:
    expected = expected_macros(registers, prefix)
    actual = {}
    headers = sorted((output / "include").glob("*.h"))
    require(bool(headers), "no generated headers")
    for header in headers:
        body = header.read_text()
        require("#include <stdint.h>" in body or header.name == ((prefix + "_") if prefix else "") + "registers.h", f"header lacks standalone stdint.h include: {header.name}")
        for name, value in re.findall(r"^#define\s+(\w+)\s+(UINT32_C\([^\n]+\)|\d+U)\s*$", re.sub(r"/\*.*?\*/", "", body, flags=re.S), re.M):
            require(name not in actual, f"duplicate macro definition {name}")
            actual[name] = value
        run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsyntax-only", "-x", "c", "-include", str(header), "-include", str(header), os.devnull])
    require(actual == expected, f"macro catalog mismatch: missing={sorted(expected.keys()-actual.keys())[:8]}, extra={sorted(actual.keys()-expected.keys())[:8]}, wrong={[(k,actual[k],expected[k]) for k in expected.keys() & actual.keys() if actual[k]!=expected[k]][:8]}")
    umbrella = ((prefix + "_") if prefix else "") + "registers.h"
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), undefined=StrictUndefined, keep_trailing_newline=True)
    with tempfile.TemporaryDirectory(prefix="assertions-", dir=ROOT / "generated") as assertion_dir:
        unit = Path(assertion_dir) / "assertions.c"
        unit.write_text(env.get_template("tests/registers_assertions.c.j2").render(umbrella=umbrella, macros=expected))
        run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsyntax-only", "-I", str(output / "include"), str(unit)])
    examples = sorted((output / "examples").glob("*.c"))
    require(bool(examples), "missing generated example")
    for example in examples:
        run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsyntax-only", "-I", str(output / "include"), str(example)])
    manifest = json.loads((output / "manifest.json").read_text())
    paths = set()
    for entry in manifest["files"]:
        path = entry["path"]
        require(path not in paths and not Path(path).is_absolute() and ".." not in Path(path).parts, f"unsafe manifest path: {path}")
        paths.add(path)
        require(hashlib.sha256((output / path).read_bytes()).hexdigest() == entry["sha256"], f"manifest checksum mismatch: {path}")
        if Path(path).suffix in (".c", ".h", ".acsl"):
            template = entry.get("template", "")
            require(not Path(template).is_absolute() and template.endswith(".j2") and ".." not in Path(template).parts and (template_root / template).is_file(), f"C artifact lacks exact existing template provenance: {path}")
    require(paths == set(tree(output)) - {"manifest.json"}, "manifest does not describe exact output file inventory")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=ROOT / "data/registers.json")
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    registers = metadata_checks(json.loads(args.metadata.read_text()))
    driver_settings_checks(registers)
    if not args.metadata_only:
        cc = shutil.which(os.environ.get("CC", "cc"))
        require(cc is not None, "C compiler is required")
        (ROOT / "generated").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="verify-", dir=ROOT / "generated") as temp:
            base = Path(temp)
            for i, prefix in enumerate(("ad594x", "custom_sensor", "")):
                output, repeated = base / str(i), base / (str(i) + "-repeat")
                for dest in (output, repeated):
                    run([sys.executable, str(ROOT / "scripts/generate_registers.py"), "--prefix", prefix, "--output", str(dest)])
                require(tree(output) == tree(repeated), f"nondeterministic output for prefix {prefix!r}")
                header_checks(output, registers, prefix, cc)
            for case in ("path", "register_collision", "field_collision", "reset_overflow", "overlap", "overlap_notes"):
                bad = json.loads(args.metadata.read_text())
                reg = bad["blocks"][0]["registers"][0]
                if case == "path":
                    bad["blocks"][0]["name"] = "../../escape"
                elif case == "register_collision":
                    bad["blocks"][0]["registers"].append(json.loads(json.dumps(reg)))
                elif case == "field_collision":
                    reg["fields"].append(json.loads(json.dumps(reg["fields"][0])))
                elif case == "reset_overflow":
                    reg["reset"] = 1 << 32
                else:
                    # A new field overlaps a known one and has no ambiguity evidence.
                    clone = json.loads(json.dumps(reg["fields"][0]))
                    clone.update(name="UNEXPLAINED_OVERLAP", notes=["A note must not authorize overlapping public fields."] if case == "overlap_notes" else [], legacy_aggregate=(case == "overlap_notes"))
                    reg["fields"].append(clone)
                bad_path = base / (case + ".json")
                bad_path.write_text(json.dumps(bad))
                destination = base / (case + "-output")
                destination.mkdir()
                (destination / "sentinel").write_text("preserve existing output\n")
                before = tree(destination)
                proc = subprocess.run([sys.executable, str(ROOT / "scripts/generate_registers.py"), "--metadata", str(bad_path), "--output", str(destination)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                require(proc.returncode != 0, f"malformed metadata accepted: {case}")
                require(tree(destination) == before, f"invalid metadata modified destination: {case}")
            run([sys.executable, str(ROOT / "scripts/generate_registers.py"), "--output", str(base / "release-source"), "--releases"])
            releases = ROOT / "generated/releases"
            archives = sorted(releases.glob("*.tar.gz"))
            require(len(archives) == 2, "expected two release archives")
            archive_bytes = {p.name: p.read_bytes() for p in archives}
            run([sys.executable, str(ROOT / "scripts/generate_registers.py"), "--output", str(base / "release-source"), "--releases"])
            require(archive_bytes == {p.name: p.read_bytes() for p in archives}, "nondeterministic release archives")
            with tempfile.TemporaryDirectory(prefix="ad594x-isolated-") as isolated:
                standalone = Path(isolated)
                for archive in archives:
                    with tarfile.open(archive) as bundle:
                        require(all(not Path(m.name).is_absolute() and ".." not in Path(m.name).parts and m.isfile() for m in bundle.getmembers()), "unsafe archive member")
                        bundle.extractall(standalone, filter="data")
                package = standalone / "ad594x-registers-prefix-template"
                # This package must render with no metadata or developer reference files.
                shutil.rmtree(package / "data")
                for i, prefix in enumerate(("ad594x", "custom_sensor", "")):
                    output = standalone / str(i)
                    run([sys.executable, str(package / "scripts/render.py"), "--prefix", prefix, "--output", str(output)], cwd=standalone)
                    rendered_manifest = json.loads((output / "manifest.json").read_text())
                    template_paths = {path.relative_to(package).as_posix() for path in (package / "templates").rglob("*.j2")}
                    require({entry["template"] for entry in rendered_manifest["files"]} == template_paths,
                            f"rendered manifest does not identify exact package templates: {prefix!r}")
                    direct = tree(base / str(i))
                    rendered = tree(output)
                    direct.pop("manifest.json")
                    rendered.pop("manifest.json")
                    require(direct == rendered, f"prefix template differs from direct generator: {prefix!r}")
                    header_checks(output, registers, prefix, cc, package)
                    require(shutil.which("cmake") is not None, "CMake is required")
                    build = standalone / (str(i) + "-build")
                    run(["cmake", "-S", str(output), "-B", str(build)], cwd=standalone)
                    run(["cmake", "--build", str(build)], cwd=standalone)
                    run(["ctest", "--test-dir", str(build), "--output-on-failure"], cwd=standalone)
                compiled = standalone / "ad594x-registers"
                header_checks(compiled, registers, "ad594x", cc)
                require(shutil.which("cmake") is not None, "CMake is required")
                run(["cmake", "-S", str(compiled), "-B", str(standalone / "build")], cwd=standalone)
                run(["cmake", "--build", str(standalone / "build")], cwd=standalone)
                run(["ctest", "--test-dir", str(standalone / "build"), "--output-on-failure"], cwd=standalone)
            for prefix in ("Bad", "_bad", "a__b", "a-b", "1bad", "for"):
                proc = subprocess.run([sys.executable, str(ROOT / "scripts/generate_registers.py"), "--prefix", prefix, "--output", str(base / "invalid")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                require(proc.returncode != 0, f"invalid prefix accepted: {prefix}")
    print(f"Verified {len(registers)} registers, {sum(len(r['fields']) for r in registers.values())} fields, {len(expected_macros(registers, 'ad594x'))} macros, 428 high-level declarations; independent source anchors plus offline structural/generation checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print(f"verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
