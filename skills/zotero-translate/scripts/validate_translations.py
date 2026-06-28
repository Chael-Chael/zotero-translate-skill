#!/usr/bin/env python3
"""Validate subagent translation JSONL and merge it into translations.jsonl."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable


PLACEHOLDER_PATTERNS = [
    re.compile(r"\{v\d+\}"),
    re.compile(r"\{\{[^{}\n]{1,80}\}\}"),
    re.compile(r"<\|[^|\n]{1,80}\|>"),
    re.compile(r"</?[biu]\d+>"),
    re.compile(r"<formula_\d+>"),
    re.compile(r"@@[^@\s]{1,80}@@"),
]
URL_RE = re.compile(r"https?://[^\s)\]}>,;]+", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s)\]}>,;]+", re.IGNORECASE)
ARXIV_RE = re.compile(r"\barXiv:\s*\d{4}\.\d{4,5}(?:v\d+)?\b", re.IGNORECASE)
CITATION_RE = re.compile(r"\[(?:\d{1,3}|[A-Z][A-Za-z-]+(?:\s+et\s+al\.)?,?\s+\d{4}[a-z]?)(?:[;,]\s*(?:\d{1,3}|[A-Z][A-Za-z-]+(?:\s+et\s+al\.)?,?\s+\d{4}[a-z]?))*\]")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
TRAILING_TOKEN_PUNCTUATION = ".,;:!?。，、；：！？"
REFERENCE_ENTRY_START_RE = re.compile(r"^\s*(?:\[\d+\]|\d+\.)")
REFERENCE_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")
REFERENCE_SOURCE_RE = re.compile(
    r"\b(?:doi|arxiv|proceedings|conference|journal|transactions|workshop|symposium|press|vol\.|pp\.|pages?|isbn|https?://)\b",
    re.IGNORECASE,
)
PROSE_START_RE = re.compile(
    r"^(?:we|our|this|these|in this|another|because|however|therefore|specifically|finally|first|second|third)\b",
    re.IGNORECASE,
)
AUTHOR_LIST_RE = re.compile(r"^[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)*,\s+.+?(?:,\s+and\s+|\s+and\s+)")
ET_AL_START_RE = re.compile(r"^[A-Z][A-Za-z']+\s+et\s+al\.", re.IGNORECASE)


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def segment_id(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> Iterable[tuple[int, dict]]:
    if not path.exists():
        raise ValueError(f"JSONL file does not exist: {path}")
    with path.open("r", encoding="utf-8-sig") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"{path}:{lineno}: JSONL item must be an object")
            yield lineno, item


def iter_result_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if not path.exists():
        raise ValueError(f"Results path does not exist: {path}")
    for result in sorted(path.glob("*.jsonl")):
        if result.name == "batch_manifest.json":
            continue
        yield result


def source_text(segment: dict) -> str:
    return str(segment.get("source") or segment.get("translation_input") or "")


def inferred_tokens(text: str) -> list[str]:
    found: list[str] = []
    for pattern in PLACEHOLDER_PATTERNS:
        found.extend(pattern.findall(text))
    for pattern in (URL_RE, DOI_RE, ARXIV_RE, CITATION_RE):
        found.extend(pattern.findall(text))
    normalized = [token.rstrip(TRAILING_TOKEN_PUNCTUATION) for token in found if token.rstrip(TRAILING_TOKEN_PUNCTUATION)]
    return list(dict.fromkeys(normalized))


def rich_text_tags(text: str) -> list[str]:
    return re.findall(r"</?[biu]\d+>", text)


def starts_like_bibliography_author(text: str) -> bool:
    first_sentence = text.split(".", 1)[0].strip()
    if AUTHOR_LIST_RE.search(text[:180]):
        return True
    if ET_AL_START_RE.search(text):
        return True
    return bool(first_sentence and len(first_sentence) <= 80 and "," in text[:120])


def looks_like_reference(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact or PROSE_START_RE.search(compact):
        return False
    has_year = bool(REFERENCE_YEAR_RE.search(compact))
    has_source = bool(REFERENCE_SOURCE_RE.search(compact))
    if REFERENCE_ENTRY_START_RE.search(compact):
        return has_year and (has_source or compact.count(".") >= 2)
    return starts_like_bibliography_author(compact) and (has_year or has_source)


def load_segments(path: Path) -> tuple[list[str], dict[str, dict], list[str]]:
    order: list[str] = []
    segments: dict[str, dict] = {}
    errors: list[str] = []
    for lineno, segment in read_jsonl(path):
        sid = str(segment.get("id") or "")
        text = source_text(segment)
        if not sid:
            errors.append(f"{path}:{lineno}: missing id")
            continue
        if not text:
            errors.append(f"{path}:{lineno}: missing source")
            continue
        expected_id = segment_id(text)
        if sid != expected_id:
            errors.append(f"{path}:{lineno}: id does not match normalized source hash for {sid}")
        if sid in segments:
            errors.append(f"{path}:{lineno}: duplicate segment id: {sid}")
            continue
        segment["protectedTokens"] = list(dict.fromkeys([str(token) for token in segment.get("protectedTokens") or []] + inferred_tokens(text)))
        segment["richTextTags"] = list(segment.get("richTextTags") or rich_text_tags(text))
        segments[sid] = segment
        order.append(sid)
    return order, segments, errors


def result_id(result: dict) -> str:
    return str(result.get("id") or result.get("unit_id") or "")


def result_target(result: dict) -> str | None:
    value = result.get("target", result.get("translated_text", result.get("translation")))
    if value is None:
        return None
    return str(value)


def validate_no_unexpected_tokens(target: str, expected: list[str], sid: str) -> list[str]:
    expected_set = set(expected)
    errors: list[str] = []
    for token in inferred_tokens(target):
        if token not in expected_set:
            errors.append(f"{sid}: unexpected protected token in target: {token!r}")
    return errors


def validate(
    segments_path: Path,
    results_path: Path,
    *,
    fail_on_reference_translation: bool = False,
) -> tuple[list[dict], list[str], list[str], list[dict]]:
    order, segments, errors = load_segments(segments_path)
    warnings: list[str] = []
    results: dict[str, dict] = {}

    if errors:
        return [], errors, warnings, []

    for result_file in iter_result_files(results_path):
        for lineno, result in read_jsonl(result_file):
            sid = result_id(result)
            if not sid:
                errors.append(f"{result_file}:{lineno}: missing id")
                continue
            if sid not in segments:
                errors.append(f"{result_file}:{lineno}: unknown id: {sid}")
                continue
            if sid in results:
                errors.append(f"{result_file}:{lineno}: duplicate translated id: {sid}")
                continue

            target = result_target(result)
            if target is None or not target.strip():
                errors.append(f"{result_file}:{lineno}: empty target for {sid}")
                continue

            result_source = result.get("source")
            if result_source is not None and segment_id(str(result_source)) != sid:
                errors.append(f"{result_file}:{lineno}: source text does not match id for {sid}")
                continue

            source = source_text(segments[sid])
            for token in segments[sid].get("protectedTokens", []):
                if token and token not in target:
                    errors.append(f"{result_file}:{lineno}: missing protected token {token!r} for {sid}")
            errors.extend(f"{result_file}:{lineno}: {error}" for error in validate_no_unexpected_tokens(target, segments[sid].get("protectedTokens", []), sid))

            expected_tags = segments[sid].get("richTextTags", [])
            actual_tags = rich_text_tags(target)
            if actual_tags != expected_tags:
                errors.append(f"{result_file}:{lineno}: rich-text tag sequence changed for {sid}: expected {expected_tags!r}, got {actual_tags!r}")

            if looks_like_reference(source) and not CJK_RE.search(source) and CJK_RE.search(target):
                message = f"{result_file}:{lineno}: reference-like segment appears translated for {sid}"
                if fail_on_reference_translation:
                    errors.append(message)
                else:
                    warnings.append(message)

            source_len = max(1, len(source))
            if len(target) / source_len > 5:
                warnings.append(f"{result_file}:{lineno}: target is unusually long for {sid}")

            results[sid] = {
                "id": sid,
                "source": source,
                "target": target,
                "notes": str(result.get("notes") or ""),
            }

    missing = [{"id": sid, "source": source_text(segments[sid]), "normalizedSource": normalize(source_text(segments[sid]))} for sid in order if sid not in results]
    for item in missing:
        errors.append(f"missing translation for {item['id']}")

    merged = [results[sid] for sid in order if sid in results]
    return merged, errors, warnings, missing


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segments", type=Path, help="segments.jsonl from the collect phase")
    parser.add_argument("results", type=Path, help="batch_results directory or a JSONL result file")
    parser.add_argument("--write-translations", type=Path, required=True, help="write merged translations.jsonl here")
    parser.add_argument("--missing-path", type=Path, help="write missing segments JSONL here when validation fails")
    parser.add_argument("--fail-on-reference-translation", action="store_true")
    args = parser.parse_args()

    try:
        merged, errors, warnings, missing = validate(
            args.segments.expanduser().resolve(),
            args.results.expanduser().resolve(),
            fail_on_reference_translation=args.fail_on_reference_translation,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if args.missing_path and missing:
            write_jsonl(args.missing_path.expanduser().resolve(), missing)
        print(json.dumps({
            "status": "failed",
            "errors": len(errors),
            "warnings": len(warnings),
            "mergedTranslations": len(merged),
            "missingTranslations": len(missing),
        }, ensure_ascii=False, indent=2))
        return 2

    write_jsonl(args.write_translations.expanduser().resolve(), merged)
    print(json.dumps({
        "status": "ok",
        "warnings": len(warnings),
        "mergedTranslations": len(merged),
        "translationsPath": str(args.write_translations.expanduser().resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
