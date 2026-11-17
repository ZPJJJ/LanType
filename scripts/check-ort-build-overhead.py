#!/usr/bin/env python3
"""Measure job-owned space outside the bounded native volume at a checkpoint.

This is a 512 MiB checkpoint assertion, not a filesystem quota or a continuous
whole-job peak measurement. The GitHub-hosted job layout keeps downloaded action
code in the sibling _actions directory next to RUNNER_TEMP. Existing SDK/tool
caches and runner service files outside the three declared roots are not scanned.
No file contents are read and symbolic links are never followed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import time

LIMIT_BYTES = 512 * 1024**2
RECEIPT_ALLOWANCE_BYTES = 64 * 1024
CHECKPOINTS = (
    "before-prepare", "before-configure", "before-build",
    "after-candidate", "before-evidence-upload",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def real_directory(value, label):
    path = Path(value)
    require(path.is_absolute(), label + " must be absolute")
    require(path == path.resolve(strict=True), label + " must not traverse symlinks or dot components")
    require(stat.S_ISDIR(path.lstat().st_mode), label + " must be a directory")
    return path


def measure(roots, excluded):
    """Count allocated blocks once per inode across all roots, using lstat."""
    seen = set()
    rows = []
    for label, root in roots:
        row = {"name": label, "path": str(root), "allocatedBytes": 0,
               "uniqueInodes": 0, "duplicateInodePaths": 0,
               "regularFiles": 0, "directories": 0, "symlinks": 0,
               "otherInodes": 0, "excludedPaths": 0}
        device = root.lstat().st_dev
        pending = [root]
        while pending:
            path = pending.pop()
            if path in excluded:
                row["excludedPaths"] += 1
                continue
            info = path.lstat()
            require(info.st_dev == device, "Unexpected filesystem below measured root: " + str(path))
            identity = (info.st_dev, info.st_ino)
            if identity in seen:
                row["duplicateInodePaths"] += 1
                continue
            seen.add(identity)
            require(info.st_blocks >= 0, "Negative allocated block count")
            row["allocatedBytes"] += info.st_blocks * 512
            row["uniqueInodes"] += 1
            if stat.S_ISLNK(info.st_mode):
                row["symlinks"] += 1
            elif stat.S_ISDIR(info.st_mode):
                row["directories"] += 1
                with os.scandir(path) as entries:
                    pending.extend(Path(entry.path) for entry in entries)
            elif stat.S_ISREG(info.st_mode):
                row["regularFiles"] += 1
            else:
                row["otherInodes"] += 1
        rows.append(row)
    return {"roots": rows, "allocatedBytes": sum(row["allocatedBytes"] for row in rows),
            "deduplicatedInodes": len(seen)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, choices=CHECKPOINTS)
    args = parser.parse_args()
    result = {"schemaVersion": 1, "kind": "lantype-ort-outside-volume-checkpoint",
              "checkpoint": args.checkpoint,
              "observedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "limitBytes": LIMIT_BYTES, "enforcement": "checkpoint-assertion",
              "wholeTaskHardQuota": False, "continuousPeakMeasured": False,
              "allocationMethod": "lstat.st_blocks * 512; global (device,inode) deduplication",
              "symlinksFollowed": False,
              "limitations": ["Only the three named job-owned roots are measured.",
                              "Allocations between checkpoints and after the final check are not bounded by this helper.",
                              "The native volume has its own independent capacity limit."]}
    receipt = None
    stream = None
    try:
        temporary = real_directory(os.environ["RUNNER_TEMP"], "RUNNER_TEMP")
        receipt_dir = temporary / "lantype-ort-overhead"
        require(not receipt_dir.is_symlink(), "Receipt directory must not be a symlink")
        receipt_dir.mkdir(exist_ok=True)
        real_directory(str(receipt_dir), "Receipt directory")
        receipt = receipt_dir / (args.checkpoint + ".json")
        # A distinct receipt per checkpoint preserves any previous run record.
        stream = receipt.open("xb")
        workspace = real_directory(os.environ["GITHUB_WORKSPACE"], "GITHUB_WORKSPACE")
        actions = real_directory(str(temporary.parent / "_actions"), "Hosted job action code")
        native_root = Path(os.environ["LANTYPE_ORT_WORK_ROOT"])
        volume = Path(os.environ["LANTYPE_ORT_VOLUME"])
        require(native_root == temporary / "lantype-ort-work", "Unexpected native work exclusion")
        require(volume == temporary / "lantype-ort-volume.img", "Unexpected native image exclusion")
        require(not native_root.is_symlink() and native_root.is_dir(), "Native work exclusion must be a directory")
        require(stat.S_ISREG(volume.lstat().st_mode), "Native image exclusion must be a regular file")
        roots = [("checkout", workspace), ("runnerTemporary", temporary), ("hostedJobActionsCode", actions)]
        for i, (_, left) in enumerate(roots):
            for _, right in roots[i + 1:]:
                require(not left.is_relative_to(right) and not right.is_relative_to(left), "Measurement roots must not overlap")
        result["excludedNativePaths"] = [str(volume), str(native_root)]
        result.update(measure(roots, {volume, native_root}))
        # The empty receipt inode and its directory have already been counted.
        # Reserve enough blocks for writing this small JSON after measurement.
        result["receiptAdditionalAllowanceBytes"] = RECEIPT_ALLOWANCE_BYTES
        result["budgetChargeBytes"] = result["allocatedBytes"] + RECEIPT_ALLOWANCE_BYTES
        result["passed"] = result["budgetChargeBytes"] <= LIMIT_BYTES
        code = 0 if result["passed"] else 1
    except (KeyError, OSError, ValueError) as error:
        result["passed"] = False
        result["error"] = str(error)[:2048]
        code = 2
    try:
        if stream is not None:
            payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
            require(len(payload) <= RECEIPT_ALLOWANCE_BYTES, "Receipt exceeds reserved allocation")
            with stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
    except (OSError, ValueError) as error:
        print(json.dumps({"passed": False, "checkpoint": args.checkpoint,
                          "error": "Could not save overhead receipt: " + str(error)}), file=sys.stderr)
        return 2
    summary = {key: result[key] for key in ("checkpoint", "passed", "allocatedBytes", "budgetChargeBytes", "limitBytes", "error") if key in result}
    if receipt is not None:
        summary["receipt"] = str(receipt)
    print(json.dumps(summary))
    return code


if __name__ == "__main__":
    sys.exit(main())
