#!/usr/bin/env python3
"""Record the shipped ORT ABI and statically check a candidate shared library.

This program only reads ELF files through GNU readelf. It never loads a shared
library. A passing receipt is not an Android, inference, provider, or 16 KiB
runtime acceptance result. Use ort-api-smoke.c separately on the target device.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "docs/licensing/ort-shipped-abi.json"
APK_SHA256 = "b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497"
ORT_SHA256 = "f826d8efb03adf0a84f10e7ba408f9d4cd11b0a2ccd8d08aeb0f7451fb50cacc"
ORT_COMMIT = "da9b5e364c465de65c49d91e696cd6485270757f"
SONAME = "libonnxruntime.so"
VERSION = "VERS_1.28.0"
C_FUNCTIONS = {
    "OrtGetApiBase",
    "OrtSessionOptionsAppendExecutionProvider_CPU",
    "OrtSessionOptionsAppendExecutionProvider_Nnapi",
}
PROVIDERS = ["CPUExecutionProvider", "NnapiExecutionProvider",
             "XnnpackExecutionProvider", "WebGpuExecutionProvider"]
READELF_OPTIONS = {
    "header": "--file-header", "programHeaders": "--program-headers",
    "dynamic": "--dynamic", "symbols": "--dyn-syms",
    "versions": "--version-info", "notes": "--notes",
}
LIMITATIONS = [
    "Static ELF inspection does not execute the library or verify its API table.",
    "Provider names and implementation availability require separate runtime/build evidence.",
    "PT_LOAD alignment is not final APK ZIP alignment or 16 KiB device acceptance.",
    "This gate does not prove minimum Android API symbol availability, model inference, or absence of a startup crash.",
]


class AbiError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AbiError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_readelf(executable, option, path=None):
    command = [str(executable), option]
    if path is not None:
        command.extend(["--wide", str(Path(path).resolve())])
    result = subprocess.run(command, capture_output=True, text=True, timeout=45,
                            env={**os.environ, "LC_ALL": "C"}, check=False)
    require(result.returncode == 0, "readelf failed: " + result.stderr.strip())
    require(not result.stderr.strip(), "readelf diagnostic: " + result.stderr.strip())
    return result.stdout


def parse_header(text):
    pairs = dict(re.findall(r"^\s*(Class|Data|Type|Machine):\s*(.+)$", text, re.M))
    require(set(pairs) == {"Class", "Data", "Type", "Machine"}, "Incomplete ELF header")
    return {"class": pairs["Class"], "encoding": pairs["Data"],
            "type": pairs["Type"].split()[0], "machine": pairs["Machine"]}


def parse_dynamic(text):
    def values(kind):
        return re.findall(r"\(" + kind + r"\).*?\[([^\]]+)\]", text)
    sonames = values("SONAME")
    require(len(sonames) <= 1, "Duplicate SONAME")
    needed = values("NEEDED")
    require(len(needed) == len(set(needed)), "Duplicate DT_NEEDED")
    return {"soname": sonames[0] if sonames else None, "needed": sorted(needed),
            "runpath": values("RUNPATH"), "rpath": values("RPATH"),
            "hasTextRelocations": bool(re.search(r"\(TEXTREL\)|\(FLAGS\).*TEXTREL", text))}


def parse_program_headers(text):
    records = {"loadSegments": [], "relroSegments": [], "stackSegments": []}
    names = {"LOAD": "loadSegments", "GNU_RELRO": "relroSegments", "GNU_STACK": "stackSegments"}
    pattern = re.compile(r"^\s*(LOAD|GNU_RELRO|GNU_STACK)\s+"
                         r"(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+"
                         r"(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+([RWE ]*)\s+(0x[0-9a-fA-F]+|0)\s*$")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            kind, offset, virtual, physical, filesz, memsz, flags, alignment = match.groups()
            records[names[kind]].append({
                "offset": int(offset, 16), "virtualAddress": int(virtual, 16),
                "physicalAddress": int(physical, 16), "fileSize": int(filesz, 16),
                "memorySize": int(memsz, 16), "flags": flags.replace(" ", ""),
                "alignment": int(alignment, 16),
            })
        elif re.match(r"^\s*(LOAD|GNU_RELRO|GNU_STACK)\s", line):
            raise AbiError("Unparsed ELF program header: " + line.strip())
    require(records["loadSegments"], "No ELF LOAD segments parsed")
    return records


def parse_symbols(text):
    require(".dynsym" in text, "No dynamic symbol table")
    pattern = re.compile(r"^\s*\d+:\s+[0-9a-fA-F]+\s+(?:0x[0-9a-fA-F]+|\d+)\s+"
                         r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(\S+)(?:\s+\((\d+)\))?)?\s*$")
    symbols = []
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            require(not re.match(r"^\s*\d+:", line), "Unparsed dynamic symbol: " + line.strip())
            continue
        kind, binding, visibility, index, decorated, version_index = match.groups()
        if not decorated:
            continue
        name, separator, version = decorated.partition("@@")
        default = bool(separator)
        if not separator:
            name, separator, version = decorated.partition("@")
        symbols.append({"name": name, "version": version or None,
                        "defaultVersion": default, "type": kind, "binding": binding,
                        "visibility": visibility, "undefined": index == "UND",
                        "versionIndex": int(version_index) if version_index else None})
    require(symbols, "Empty dynamic symbol table")
    return symbols


def parse_versions(text):
    section, provider = None, None
    definitions, needs = [], {}
    for line in text.splitlines():
        if line.startswith("Version definition section"):
            section = "definitions"
        elif line.startswith("Version needs section"):
            section = "needs"
        elif line.startswith("Version symbols section"):
            section = "symbols"
        if section == "definitions":
            match = re.search(r"\bName:\s*(\S+)", line)
            if match:
                definitions.append(match.group(1))
        elif section == "needs":
            match = re.search(r"\bFile:\s*(\S+)", line)
            if match:
                provider = match.group(1)
            match = re.search(r"\bName:\s*(\S+)\s+Flags:.*\bVersion:\s*(\d+)", line)
            if match:
                require(provider is not None, "Version need has no provider")
                index = int(match.group(2))
                require(index not in needs, "Duplicate version need index")
                needs[index] = {"name": match.group(1), "provider": provider}
    return {"definitions": sorted(definitions), "needs": needs}


def symbol_identity(symbol):
    return {key: symbol[key] for key in
            ("name", "version", "defaultVersion", "type", "binding", "visibility")}


def inspect_elf(path, readelf="readelf"):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Expected regular ELF file: " + str(path))
    raw = {key: run_readelf(readelf, option, path) for key, option in READELF_OPTIONS.items()}
    symbols = parse_symbols(raw["symbols"])
    versions = parse_versions(raw["versions"])
    for symbol in symbols:
        if symbol["undefined"] and symbol["versionIndex"] is not None:
            need = versions["needs"].get(symbol["versionIndex"])
            require(need is not None and need["name"] == symbol["version"],
                    "Unresolved symbol version provider for " + symbol["name"])
            symbol["versionProvider"] = need["provider"]
        else:
            symbol["versionProvider"] = None
    build_ids = re.findall(r"Build ID:\s*([0-9a-fA-F]+)", raw["notes"])
    require(len(build_ids) <= 1, "Multiple build IDs")
    return {"filename": path.name, "bytes": path.stat().st_size, "sha256": digest(path),
            "elf": parse_header(raw["header"]), **parse_dynamic(raw["dynamic"]),
            **parse_program_headers(raw["programHeaders"]),
            "buildId": build_ids[0].lower() if build_ids else None,
            "versionDefinitions": versions["definitions"], "symbols": symbols,
            "readelfEvidenceSha256": {key: text_hash(value) for key, value in raw.items()}}


def exports(info):
    return [symbol_identity(s) for s in info["symbols"]
            if not s["undefined"] and s["binding"] in ("GLOBAL", "WEAK", "UNIQUE")
            and s["visibility"] in ("DEFAULT", "PROTECTED")]


def record_contract(apk, libraries, readelf):
    require(digest(apk) == APK_SHA256, "Baseline APK differs from the fixed signed 1.1.1 artifact")
    libraries = Path(libraries)
    inspected = []
    with zipfile.ZipFile(apk) as archive:
        members = [i for i in archive.infolist()
                   if re.fullmatch(r"lib/arm64-v8a/[^/]+\.so", i.filename)]
        require(len(members) == 12 and len({i.filename for i in members}) == 12,
                "Expected the twelve unique shipped ARM64 ELF members")
        for member in sorted(members, key=lambda i: i.filename):
            path = libraries / Path(member.filename).name
            require(path.is_file() and not path.is_symlink(), "Missing extracted library: " + path.name)
            with archive.open(member) as stream:
                apk_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            require(path.stat().st_size == member.file_size and digest(path) == apk_hash,
                    "Extracted library differs from APK member: " + member.filename)
            info = inspect_elf(path, readelf)
            info["apkMember"] = member.filename
            inspected.append(info)
    ort = next(i for i in inspected if i["filename"] == SONAME)
    require(ort["sha256"] == ORT_SHA256, "Unexpected shipped ORT identity")
    ort_exports = sorted(exports(ort), key=lambda s: (s["name"], s["version"] or ""))
    exported_names = {s["name"] for s in ort_exports}
    required = {s["name"]: s for s in ort_exports if s["name"] in C_FUNCTIONS}
    require(set(required) == C_FUNCTIONS, "Shipped C export inventory differs")
    for info in inspected:
        imports = []
        if info["filename"] != SONAME:
            for symbol in info["symbols"]:
                if symbol["undefined"] and (symbol["versionProvider"] == SONAME or
                        (SONAME in info["needed"] and symbol["name"] in exported_names)):
                    imports.append({**symbol_identity(symbol),
                                    "versionProvider": symbol["versionProvider"]})
                    matches = [s for s in ort_exports if s["name"] == symbol["name"]
                               and (s["version"] == symbol["version"] if symbol["version"]
                                    else s["version"] is None or s["defaultVersion"])]
                    require(len(matches) == 1, "Unresolved shipped ORT import: " + symbol["name"])
                    required[symbol["name"]] = matches[0]
        info["ortUndefinedSymbols"] = sorted(imports, key=lambda s: s["name"])
        del info["symbols"]
    return {
        "schemaVersion": 1, "kind": "lantype-ort-static-abi-contract",
        "baseline": {
            "appVersion": "1.1.1", "abi": "arm64-v8a", "ortCommit": ORT_COMMIT,
            "apk": {"filename": Path(apk).name, "bytes": Path(apk).stat().st_size,
                    "sha256": APK_SHA256,
                    "url": "https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/"
                           "LanType-1.1.1-offline-arm64-v8a.apk"},
            "readelfVersion": run_readelf(readelf, "--version").splitlines()[0],
            "readelfOptions": READELF_OPTIONS, "libraries": inspected, "ortExports": ort_exports,
        },
        "contract": {
            "soname": SONAME, "elf": ort["elf"], "neededLibraries": ort["needed"],
            "requiredExports": sorted(required.values(), key=lambda s: s["name"]),
            "requiredVersionDefinitions": [VERSION], "minimumLoadAlignmentBytes": 16384,
            "requireRelro": bool(ort["relroSegments"]),
            "ortApiVersionForSeparateRuntimeProbe": 28,
            "providersForSeparateRuntimeProbe": PROVIDERS,
            "unconsumedObjectExportsAreInformational": True,
        },
        "limitations": LIMITATIONS,
    }


def validate_contract(document):
    require(document.get("schemaVersion") == 1 and
            document.get("kind") == "lantype-ort-static-abi-contract", "Unsupported ABI contract")
    baseline, contract = document["baseline"], document["contract"]
    require(baseline["apk"]["sha256"] == APK_SHA256 and baseline["ortCommit"] == ORT_COMMIT,
            "Contract is not for the fixed shipped baseline")
    libraries = baseline["libraries"]
    require(len(libraries) == 12 and len({i["filename"] for i in libraries}) == 12,
            "Incomplete shipped library inventory")
    ort = next((i for i in libraries if i["filename"] == SONAME), None)
    require(ort is not None and ort["sha256"] == ORT_SHA256, "Missing fixed shipped ORT identity")
    require(contract["soname"] == SONAME and contract["elf"] == ort["elf"] and
            contract["neededLibraries"] == ort["needed"], "Contract differs from recorded baseline")
    require(contract["elf"] == {"class": "ELF64", "encoding": "2's complement, little endian",
                                "type": "DYN", "machine": "AArch64"}, "Unexpected baseline architecture")
    required = contract["requiredExports"]
    require(C_FUNCTIONS <= {s["name"] for s in required}, "Missing required ORT C exports")
    require(all(s["version"] == VERSION and s["type"] == "FUNC" and s["defaultVersion"]
                for s in required if s["name"] in C_FUNCTIONS), "Wrong required C symbol versions")
    require(contract["requiredVersionDefinitions"] == [VERSION] and
            contract["minimumLoadAlignmentBytes"] == 16384, "Wrong version/alignment contract")
    return contract


def check_candidate(candidate, document):
    contract = validate_contract(document)
    checks = []

    def check(name, passed, expected, actual):
        checks.append({"name": name, "passed": bool(passed), "expected": expected, "actual": actual})

    check("elf-format", candidate["elf"] == contract["elf"], contract["elf"], candidate["elf"])
    check("soname", candidate["soname"] == contract["soname"], contract["soname"], candidate["soname"])
    check("needed-libraries", candidate["needed"] == contract["neededLibraries"],
          contract["neededLibraries"], candidate["needed"])
    check("version-definitions", set(contract["requiredVersionDefinitions"]) <= set(candidate["versionDefinitions"]),
          contract["requiredVersionDefinitions"], candidate["versionDefinitions"])
    candidate_exports = exports(candidate)
    for expected in contract["requiredExports"]:
        matches = [s for s in candidate_exports if s["name"] == expected["name"] and
                   s["version"] == expected["version"] and s["type"] == expected["type"] and
                   s["binding"] == expected["binding"] and s["visibility"] == expected["visibility"] and
                   (not expected["defaultVersion"] or s["defaultVersion"])]
        check("export:" + expected["name"], bool(matches), expected, matches)
    minimum = contract["minimumLoadAlignmentBytes"]
    segments = candidate["loadSegments"]
    aligned = bool(segments) and all(s["alignment"] >= minimum and
                s["alignment"] & (s["alignment"] - 1) == 0 and
                (s["virtualAddress"] - s["offset"]) % s["alignment"] == 0 and
                (s["virtualAddress"] - s["offset"]) % minimum == 0 and
                s["fileSize"] <= s["memorySize"] and
                s["offset"] + s["fileSize"] <= candidate["bytes"] for s in segments)
    check("load-alignment", aligned, {"minimumBytes": minimum, "offsetAddressCongruence": True}, segments)
    check("relro-present", bool(candidate["relroSegments"]) or not contract["requireRelro"],
          contract["requireRelro"], bool(candidate["relroSegments"]))
    check("no-text-relocations", not candidate["hasTextRelocations"], False, candidate["hasTextRelocations"])
    summary = {key: value for key, value in candidate.items() if key != "symbols"}
    summary["exports"] = candidate_exports
    observed_objects = [s for s in document["baseline"]["ortExports"] if s["type"] == "OBJECT"]
    return {"schemaVersion": 1, "kind": "lantype-ort-static-abi-result",
            "passed": all(c["passed"] for c in checks), "scope": "static-elf-only",
            "nativeCodeExecuted": False, "runtimeProviderAcceptance": "not-run",
            "androidStartupAcceptance": "not-run", "modelInferenceAcceptance": "not-run",
            "baselineApkSha256": APK_SHA256, "candidate": summary, "checks": checks,
            "informationalShippedObjectExports": observed_objects, "limitations": LIMITATIONS}


def write_new_json(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record", help="Record only the fixed shipped 1.1.1 APK")
    record.add_argument("--readelf", default="readelf", help="GNU readelf executable")
    record.add_argument("--apk", type=Path, required=True)
    record.add_argument("--libraries", type=Path, required=True, help="Previously extracted ARM64 .so directory")
    record.add_argument("--output", type=Path, required=True, help="New contract JSON; existing files are preserved")
    verify = subparsers.add_parser("verify", help="Read and compare a candidate ELF without loading it")
    verify.add_argument("--readelf", default="readelf", help="GNU readelf executable")
    verify.add_argument("--library", type=Path, required=True)
    verify.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    verify.add_argument("--output", type=Path, help="New receipt JSON; otherwise print JSON to stdout")
    argv = list(sys.argv[1:])
    if not argv or argv[0] not in ("record", "verify", "-h", "--help"):
        argv.insert(0, "verify")
    args = parser.parse_args(argv)
    try:
        tool_version = run_readelf(args.readelf, "--version").splitlines()[0]
        require(tool_version.startswith("GNU readelf"), "This parser requires GNU readelf output")
        if args.command == "record":
            document = record_contract(args.apk, args.libraries, args.readelf)
            validate_contract(document)
            write_new_json(args.output, document)
            print(json.dumps({"contract": str(args.output), "sha256": digest(args.output),
                              "libraries": len(document["baseline"]["libraries"])}))
            return 0
        document = json.loads(args.contract.read_text(encoding="utf-8"))
        result = check_candidate(inspect_elf(args.library, args.readelf), document)
        result["contractSha256"] = digest(args.contract)
        result["readelfVersion"] = tool_version
        if args.output:
            write_new_json(args.output, result)
            print(json.dumps({"receipt": str(args.output), "sha256": digest(args.output),
                              "passed": result["passed"], "scope": result["scope"]}))
        else:
            print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    except (AbiError, OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError,
            zipfile.BadZipFile) as error:
        print(json.dumps({"kind": "lantype-ort-static-abi-error", "passed": False,
                          "nativeCodeExecuted": False, "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
