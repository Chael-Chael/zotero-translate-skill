#!/usr/bin/env python3
"""Validate and merge terminology extraction results into a glossary CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Iterable


WHITESPACE_RE = re.compile(r"\s+")


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def normalize_key(text: str) -> str:
    return normalize_text(text).casefold()


def normalize_language(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def iter_result_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if not path.exists():
        raise ValueError(f"Results path does not exist: {path}")
    for result in sorted(path.glob("*.jsonl")):
        yield result


def expand_item(item: object) -> Iterable[dict]:
    if isinstance(item, list):
        for child in item:
            yield from expand_item(child)
        return
    if isinstance(item, dict) and isinstance(item.get("terms"), list):
        for child in item["terms"]:
            yield from expand_item(child)
        return
    if isinstance(item, dict):
        yield item


def read_terms(path: Path) -> Iterable[tuple[int, dict]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL: {exc}") from exc
            for term in expand_item(item):
                yield lineno, term


def term_source(term: dict) -> str:
    return normalize_text(str(term.get("source") or term.get("src") or ""))


def term_target(term: dict) -> str:
    return normalize_text(str(term.get("target") or term.get("tgt") or ""))


def term_language(term: dict) -> str:
    return normalize_language(str(term.get("tgt_lng") or term.get("targetLanguage") or term.get("target_language") or ""))


def merge_glossary(results_path: Path, output_path: Path, target_language: str | None = None) -> dict:
    expected_language = normalize_language(target_language)
    merged: list[dict] = []
    seen: set[str] = set()
    warnings: list[str] = []
    scanned = 0

    for result_file in iter_result_files(results_path):
        for lineno, term in read_terms(result_file):
            scanned += 1
            source = term_source(term)
            target = term_target(term)
            language = term_language(term) or expected_language
            location = f"{result_file}:{lineno}"
            if not source or not target:
                warnings.append(f"{location}: skipped empty source or target")
                continue
            if len(source) >= 100:
                warnings.append(f"{location}: skipped overlong source term")
                continue
            if normalize_key(source) == normalize_key(target) and len(source) < 3:
                warnings.append(f"{location}: skipped trivial identical term")
                continue
            if expected_language and language and language != expected_language:
                warnings.append(f"{location}: skipped target language {language!r}")
                continue
            key = normalize_key(source)
            if key in seen:
                continue
            seen.add(key)
            merged.append({"source": source, "target": target, "tgt_lng": language})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "target", "tgt_lng"])
        writer.writeheader()
        writer.writerows(merged)

    return {
        "status": "ok",
        "resultsPath": str(results_path),
        "glossaryPath": str(output_path),
        "scannedTerms": scanned,
        "mergedTerms": len(merged),
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="term result JSONL file or directory")
    parser.add_argument("--output", type=Path, required=True, help="CSV path to write")
    parser.add_argument("--target-language", help="target language filter for tgt_lng rows")
    args = parser.parse_args()

    try:
        summary = merge_glossary(
            args.results.expanduser().resolve(),
            args.output.expanduser().resolve(),
            target_language=args.target_language,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    for warning in summary["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
