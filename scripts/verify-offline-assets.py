#!/usr/bin/env python3
"""Verify LanType's merged assets or final APK; performs no network access.

Use --assets after :app:prepareLanTypeAssets, or --apk to inspect a final APK's
ZIP assets/ entries directly without extracting it. Rime .gz assets are checked
after decompression, matching AAPT/AssetManager behavior. Every shipped-model
file must match its exact size and SHA-256. This checks packaging, not runtime.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODELS = {"ochwpro", "speaker-campplus-zh", "sensevoice-multilingual-int8"}
CORE_ASSETS = (
    "rime_chinese/t9_ngram.lm",
    "rime_chinese/t9_pinyin.schema.yaml",
    "rime_chinese/pinyin_14jian.schema.yaml",
    "rime_chinese/double_pinyin_flypy_14jian.schema.yaml",
    "rime_chinese/cyime_k14_english.schema.yaml",
    "english.txt", "english_trie.bin", "english_bigrams.txt", "english_glide_words.txt",
    "english_us_spelling.tsv", "english_typo_corrections.tsv",
    "ocr/ppocr-v5/ch_PP-OCRv5_det_mobile.onnx",
    "ocr/ppocr-v5/ch_PP-OCRv5_rec_mobile.onnx",
    "ocr/ppocr-v5/ppocrv5-characters.txt",
)


@contextmanager
def open_asset(source: Path | ZipFile, relative: str):
    """Open an AssetManager-style name, optionally backed by a gzip asset."""
    name = PurePosixPath(relative)
    if not relative or name.is_absolute() or ".." in name.parts or "\\" in relative:
        raise ValueError(f"Unsafe asset path: {relative}")
    if isinstance(source, ZipFile):
        try:
            entry = source.getinfo(f"assets/{relative}")
            compressed_asset = False
        except KeyError:
            try:
                entry = source.getinfo(f"assets/{relative}.gz")
                compressed_asset = True
            except KeyError:
                raise FileNotFoundError(relative) from None
        if entry.is_dir():
            raise IsADirectoryError(relative)
        with source.open(entry) as raw:
            if compressed_asset:
                with gzip.GzipFile(fileobj=raw, mode="rb") as stream:
                    yield stream
            else:
                yield raw
        return
    path = (source / relative).resolve()
    if not path.is_relative_to(source.resolve()):
        raise ValueError(f"Unsafe asset path: {relative}")
    if path.is_file():
        stream = path.open("rb")
    elif path.with_name(path.name + ".gz").is_file():
        stream = gzip.open(path.with_name(path.name + ".gz"), "rb")
    else:
        raise FileNotFoundError(relative)
    with stream:
        yield stream


def read_asset_text(source: Path | ZipFile, relative: str) -> str:
    with open_asset(source, relative) as stream:
        return stream.read().decode("utf-8")


def digest_asset(source: Path | ZipFile, relative: str) -> tuple[int, str]:
    sha = hashlib.sha256()
    size = 0
    with open_asset(source, relative) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            sha.update(block)
    return size, sha.hexdigest()


def verify(source: Path | ZipFile) -> dict:
    failures: list[str] = []
    rime_rows = []
    model_rows = []
    core_rows = []

    def check(relative: str, expected_size: int | None = None, expected_sha: str | None = None) -> dict:
        row = {"asset": relative}
        try:
            size, sha = digest_asset(source, relative)
            row.update(size=size, sha256=sha)
            if size <= 0 or expected_size is not None and size != expected_size:
                raise ValueError(f"Size {size}, expected {expected_size}")
            if expected_sha is not None and sha.lower() != expected_sha.lower():
                raise ValueError(f"SHA-256 {sha}, expected {expected_sha}")
            row["status"] = "passed"
        except (OSError, ValueError, EOFError, BadZipFile) as error:
            row.update(status="failed", error=str(error))
            failures.append(f"{relative}: {error}")
        return row

    for line_number, line in enumerate(read_asset_text(source, "rime-bundled-manifest.tsv").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 4:
            failures.append(f"rime manifest line {line_number}: expected four columns")
            continue
        sha, size, relative, _destination = fields
        rime_rows.append(check(relative, int(size), sha))
    if len(rime_rows) != 143:
        failures.append(f"Expected 143 Rime manifest entries, found {len(rime_rows)}")

    models = json.loads(read_asset_text(source, "bundled-models/manifest.json"))
    ids = {model["id"] for model in models}
    if ids != EXPECTED_MODELS or len(models) != 3:
        failures.append(f"Expected three bundled model groups, found {len(models)}: {sorted(ids)}")
    model_file_count = sum(len(model["files"]) for model in models)
    if model_file_count != 5:
        failures.append(f"Expected five bundled model files, found {model_file_count}")
    for model in models:
        rows = [check(f"bundled-models/{model['id']}/{entry['name']}", entry["size"], entry["sha256"])
                for entry in model["files"]]
        model_rows.append({"id": model["id"], "version": model["version"], "files": rows,
                           "total_bytes": sum(row.get("size", 0) for row in rows)})

    for relative in CORE_ASSETS:
        core_rows.append(check(relative))
    if isinstance(source, ZipFile):
        origin = {"source_kind": "apk", "apk_path": str(Path(source.filename).resolve()),
                  "scope": "Final APK supplied through --apk; ZIP assets/ streamed directly without extraction. "
                           "Size/hash and core-file presence only; no Android runtime claim."}
    else:
        origin = {"source_kind": "assets_directory", "assets_directory": str(source.resolve()),
                  "scope": "Gradle prepareLanTypeAssets directory; size/hash and core-file presence only; "
                           "not a final APK or an Android runtime check."}
    return {"status": "failed" if failures else "passed", **origin,
            "rime_manifest_entries": len(rime_rows), "bundled_model_count": len(models),
            "bundled_model_file_count": model_file_count, "core_asset_count": len(core_rows),
            "rime": rime_rows, "bundled_models": model_rows, "core_assets": core_rows, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--assets", type=Path, help="Merged asset directory (default: app/build/generated/lantype-assets)")
    inputs.add_argument("--apk", type=Path, help="Final APK; stream ZIP assets/ without extraction")
    parser.add_argument("--json", type=Path, help="Write complete verification evidence")
    args = parser.parse_args()
    if args.apk is not None:
        with ZipFile(args.apk) as archive:
            report = verify(archive)
    else:
        report = verify(args.assets or ROOT / "app/build/generated/lantype-assets")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "source_kind", "rime_manifest_entries", "bundled_model_count", "bundled_model_file_count", "core_asset_count", "failures")}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
