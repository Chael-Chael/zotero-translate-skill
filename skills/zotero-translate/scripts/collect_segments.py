#!/usr/bin/env python3
"""pdf2zh CLI translator that records source segments and returns them unchanged."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def segment_id(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def read_jsonl_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("id"):
            ids.add(str(item["id"]))
    return ids


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def update_manifest(path: Path, segment_count: int) -> None:
    if not path.exists():
        return
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["segmentCount"] = segment_count
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a pdf2zh text segment.")
    parser.add_argument("--segments-path", "-SegmentsPath", required=True)
    parser.add_argument("--manifest-path", "-ManifestPath")
    parser.add_argument("--source-language", "-SourceLanguage", default="en")
    parser.add_argument("--target-language", "-TargetLanguage", required=True)
    args = parser.parse_args()
    if not args.target_language.strip():
        raise ValueError("TargetLanguage must not be empty.")

    source = sys.stdin.read()
    normalized = normalize(source)
    sid = segment_id(source)
    segments_path = Path(args.segments_path).expanduser().resolve()
    segments_path.parent.mkdir(parents=True, exist_ok=True)

    existing = read_jsonl_ids(segments_path)
    if sid not in existing:
        entry = {
            "id": sid,
            "source": source,
            "normalizedSource": normalized,
            "sourceLanguage": args.source_language,
            "targetLanguage": args.target_language,
            "status": "pending",
        }
        with segments_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")

    if args.manifest_path:
        update_manifest(Path(args.manifest_path).expanduser().resolve(), count_jsonl(segments_path))

    sys.stdout.write(source)
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
