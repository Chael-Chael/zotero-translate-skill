#!/usr/bin/env python3
"""Clean a managed Zotero Translate run directory."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean managed Zotero Translate artifacts.")
    parser.add_argument("--run-dir", "-RunDir", required=True)
    parser.add_argument("--cleanup-policy", "-CleanupPolicy", choices=("success", "always", "never"), default="success")
    parser.add_argument("--keep-artifacts", "-KeepArtifacts", action="store_true")
    parser.add_argument("--confirm-attached", "-ConfirmAttached", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    managed_root = (Path(tempfile.gettempdir()) / "zotero-translate-runs").resolve()

    if args.keep_artifacts or args.cleanup_policy == "never":
        print(json.dumps({"cleaned": False, "reason": "Cleanup skipped by policy.", "runDir": str(run_dir)}, ensure_ascii=False, indent=2))
        return 0

    if not is_within(run_dir, managed_root):
        raise RuntimeError(f"Refusing to clean unmanaged path: {run_dir}")
    if not (run_dir / "run_manifest.json").exists():
        raise RuntimeError(f"Refusing to clean a directory without run_manifest.json: {run_dir}")
    if args.cleanup_policy == "success" and not args.confirm_attached:
        raise RuntimeError("Refusing to clean final outputs until Zotero attachment has been confirmed. Re-run with --confirm-attached after attaching.")

    shutil.rmtree(run_dir)
    print(json.dumps({"cleaned": True, "runDir": str(run_dir), "policy": args.cleanup_policy}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
