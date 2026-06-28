#!/usr/bin/env python3
"""pdf2zh CLI translator that looks up translated segments by stable hash."""

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


def load_translations(path: Path) -> dict[str, str]:
    translations: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"Translations file does not exist: {path}")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        sid = str(item.get("id", ""))
        target = item.get("target", item.get("translation"))
        if sid and target is not None:
            translations[sid] = str(target)
    return translations


def append_missing(path: Path, sid: str, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": sid,
        "source": source,
        "normalizedSource": normalize(source),
        "missingAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Look up a translated pdf2zh segment.")
    parser.add_argument("--translations-path", "-TranslationsPath", required=True)
    parser.add_argument("--missing-path", "-MissingPath", required=True)
    args = parser.parse_args()

    source = sys.stdin.read()
    sid = segment_id(source)
    translations = load_translations(Path(args.translations_path).expanduser().resolve())
    target = translations.get(sid)
    if target is None:
        append_missing(Path(args.missing_path).expanduser().resolve(), sid, source)
        print(f"Missing translation for segment id {sid}. See missing_segments.jsonl.", file=sys.stderr)
        return 2

    sys.stdout.write(target)
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
