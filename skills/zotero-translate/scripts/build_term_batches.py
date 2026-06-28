#!/usr/bin/env python3
"""Build small terminology-extraction batches from collected PDF segments."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")


def read_jsonl(path: Path) -> Iterable[tuple[int, dict]]:
    if not path.exists():
        raise SystemExit(f"JSONL file does not exist: {path}")
    with path.open("r", encoding="utf-8-sig") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSONL: {exc}") from exc
            if not isinstance(item, dict):
                raise SystemExit(f"{path}:{lineno}: JSONL item must be an object")
            yield lineno, item


def source_text(segment: dict) -> str:
    return str(segment.get("source") or segment.get("translation_input") or "")


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def useful_for_terms(text: str) -> bool:
    compact = normalize_text(text)
    if len(compact) < 20:
        return False
    return len(LETTER_RE.findall(compact)) >= 3


def clear_old_batches(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("term_batch_*.jsonl", "term_batch_*.prompt.md", "term_batch_manifest.json"):
        for path in output_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def prompt_text(target_language: str) -> str:
    return f"""# Term Extraction Batch

Extract key terms from the assigned source text and translate them into {target_language}.

Output JSONL only, one object per term:

```json
{{"source":"<source term>","target":"<target term>","tgt_lng":"{target_language}","notes":""}}
```

Rules:

- Include domain-specific nouns or noun phrases, named methods, datasets, metrics, and named entities that are essential to the paper.
- Use minimal terms, not full sentences or long clauses.
- Do not extract math variables, formulas, citation markers, URLs, DOI strings, or generic words.
- Extract a source term once in its first clear form.
- Prefer established academic translations; omit uncertain terms instead of guessing.
"""


def compact_segment(segment: dict) -> dict:
    return {
        "id": str(segment.get("id") or ""),
        "source": normalize_text(source_text(segment)),
        "sourceLanguage": segment.get("sourceLanguage", "en"),
        "targetLanguage": segment.get("targetLanguage"),
    }


def write_batch(output_dir: Path, index: int, segments: list[dict], target_language: str) -> dict:
    jsonl_path = output_dir / f"term_batch_{index:04d}.jsonl"
    prompt_path = output_dir / f"term_batch_{index:04d}.prompt.md"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for segment in segments:
            handle.write(json.dumps(compact_segment(segment), ensure_ascii=False, separators=(",", ":")) + "\n")
    prompt_path.write_text(prompt_text(target_language), encoding="utf-8")
    return {
        "batch": jsonl_path.name,
        "path": str(jsonl_path),
        "promptPath": str(prompt_path),
        "segments": len(segments),
        "chars": sum(len(source_text(segment)) for segment in segments),
    }


def build_term_batches(
    segments_path: Path,
    output_dir: Path,
    max_segments: int,
    max_chars: int,
    target_language: str | None = None,
) -> dict:
    clear_old_batches(output_dir)
    manifest: list[dict] = []
    batch: list[dict] = []
    batch_chars = 0
    total_segments = 0
    candidate_segments = 0
    inferred_target_language = target_language

    for lineno, segment in read_jsonl(segments_path):
        total_segments += 1
        sid = str(segment.get("id") or "")
        text = source_text(segment)
        if not sid:
            raise SystemExit(f"{segments_path}:{lineno}: missing id")
        if not text:
            raise SystemExit(f"{segments_path}:{lineno}: missing source")
        if not inferred_target_language and segment.get("targetLanguage"):
            inferred_target_language = str(segment["targetLanguage"])
        if not useful_for_terms(text):
            continue

        candidate_segments += 1
        text_len = len(text)
        would_exceed_segments = len(batch) >= max_segments
        would_exceed_chars = bool(batch) and batch_chars + text_len > max_chars
        if would_exceed_segments or would_exceed_chars:
            manifest.append(write_batch(output_dir, len(manifest) + 1, batch, inferred_target_language or "target language"))
            batch = []
            batch_chars = 0
        batch.append(segment)
        batch_chars += text_len

    if batch:
        manifest.append(write_batch(output_dir, len(manifest) + 1, batch, inferred_target_language or "target language"))

    summary = {
        "segmentsPath": str(segments_path),
        "outputDir": str(output_dir),
        "totalSegments": total_segments,
        "candidateSegments": candidate_segments,
        "batchCount": len(manifest),
        "maxSegments": max_segments,
        "maxChars": max_chars,
        "targetLanguage": inferred_target_language,
        "batches": manifest,
    }
    (output_dir / "term_batch_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segments", type=Path, help="segments.jsonl from the collect phase")
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for term_batch_*.jsonl files")
    parser.add_argument("--target-language", help="target language for extracted term translations")
    parser.add_argument("--max-segments", type=int, default=12)
    parser.add_argument("--max-chars", type=int, default=3200)
    args = parser.parse_args()

    if args.max_segments <= 0:
        raise SystemExit("--max-segments must be positive")
    if args.max_chars <= 0:
        raise SystemExit("--max-chars must be positive")

    summary = build_term_batches(
        args.segments.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
        args.max_segments,
        args.max_chars,
        target_language=args.target_language,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
