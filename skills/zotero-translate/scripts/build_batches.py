#!/usr/bin/env python3
"""Split collected Zotero Translate segments into subagent-sized JSONL batches."""

from __future__ import annotations

import argparse
import csv
import json
import re
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
TRAILING_TOKEN_PUNCTUATION = ".,;:!?。，、；：！？"
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


def load_translated_ids(path: Path | None) -> set[str]:
    translated: set[str] = set()
    if not path or not path.exists():
        return translated
    for _, item in read_jsonl(path):
        sid = str(item.get("id") or item.get("unit_id") or "")
        target = item.get("target", item.get("translated_text", item.get("translation")))
        if sid and target is not None and str(target).strip():
            translated.add(sid)
    return translated


def parse_glossary(context_pack: Path | None) -> list[tuple[str, str]]:
    if not context_pack or not context_pack.exists():
        return []
    lines = context_pack.read_text(encoding="utf-8-sig").splitlines()
    in_glossary = False
    terms: list[tuple[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_glossary = stripped.lower() == "## glossary"
            continue
        if not in_glossary or "=>" not in stripped:
            continue
        source, target = [part.strip() for part in stripped.split("=>", 1)]
        if source and target and not source.lower().startswith("add one mapping"):
            terms.append((source, target))
    return terms


def normalize_term(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip().casefold()


def normalize_language(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def split_csv_paths(values: list[str] | None) -> list[Path]:
    paths: list[Path] = []
    for value in values or []:
        for part in value.split(","):
            part = part.strip()
            if part:
                paths.append(Path(part).expanduser().resolve())
    return paths


def parse_glossary_csv(path: Path, target_language: str | None = None) -> list[tuple[str, str]]:
    if not path.exists():
        raise SystemExit(f"glossary CSV does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return []
        fields = {field.strip().lower(): field for field in reader.fieldnames if field}
        if "source" not in fields or "target" not in fields:
            raise SystemExit(f"{path}: glossary CSV must contain source and target columns")
        source_field = fields["source"]
        target_field = fields["target"]
        language_field = fields.get("tgt_lng") or fields.get("target_language")
        expected_language = normalize_language(target_language)
        terms: list[tuple[str, str]] = []
        for row in reader:
            language = normalize_language(row.get(language_field)) if language_field else ""
            if expected_language and language and language != expected_language:
                continue
            source = str(row.get(source_field) or "").strip()
            target = str(row.get(target_field) or "").strip()
            if source and target:
                terms.append((source, target))
        return terms


def dedupe_glossary(terms: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for source, target in terms:
        key = normalize_term(source)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append((source, target))
    return deduped


def load_glossary_terms(
    context_pack: Path | None,
    glossary_csvs: list[Path] | None,
    target_language: str | None = None,
) -> list[tuple[str, str]]:
    terms: list[tuple[str, str]] = []
    terms.extend(parse_glossary(context_pack))
    for path in glossary_csvs or []:
        terms.extend(parse_glossary_csv(path, target_language))
    return dedupe_glossary(terms)


def matched_glossary(terms: list[tuple[str, str]], text: str, limit: int = 80) -> list[dict]:
    if not terms:
        return []
    normalized_text = normalize_term(text)
    matches: list[dict] = []
    for source, target in terms:
        if normalize_term(source) in normalized_text:
            matches.append({"source": source, "target": target})
        if len(matches) >= limit:
            break
    return matches


def compact_segment(segment: dict, glossary_terms: list[tuple[str, str]]) -> dict:
    sid = str(segment.get("id") or "")
    text = source_text(segment)
    if not sid:
        raise ValueError("segment is missing id")
    if not text:
        raise ValueError(f"{sid}: segment is missing source text")

    compact = {
        "id": sid,
        "source": text,
        "normalizedSource": str(segment.get("normalizedSource") or ""),
        "sourceLanguage": segment.get("sourceLanguage", "en"),
        "targetLanguage": segment.get("targetLanguage"),
        "protectedTokens": inferred_tokens(text),
        "richTextTags": rich_text_tags(text),
        "sourceCharCount": len(text),
        "outputInstruction": "Return one JSONL object with id, source, target, and optional notes. Translate the target yourself and put only the translated text in target.",
    }
    glossary = matched_glossary(glossary_terms, text)
    if glossary:
        compact["glossary"] = glossary
    return compact


def prompt_text(target_language: str) -> str:
    return f"""# Translation Batch

Translate the assigned JSONL segments into {target_language}.

Output JSONL only, one object per input segment:

```json
{{"id":"<same id>","source":"<same source text>","target":"<translated text>","notes":""}}
```

Rules:

- Prefer a cheap, low-latency model for this subagent unless the parent agent explicitly selected another model or validation/quality failures require escalation.
- Produce segment targets yourself from the assigned JSONL, context pack, and glossary.
- Do not call third-party translation APIs, online translators, local MT/translation libraries, browser/search tools, pdf2zh/BabelDOC translation modes, or another agent/process to generate translated text.
- Preserve `id` and `source` exactly.
- Preserve protected tokens, math, citations, URLs, DOIs, arXiv IDs, XML-like tags, and rich-text tags exactly.
- Use glossary target terms exactly when the source term appears.
- Put only translated text in `target`; do not add explanations, labels, Markdown fences, or summaries.
"""


def write_batch(output_dir: Path, index: int, segments: list[dict], glossary_terms: list[tuple[str, str]], target_language: str) -> dict:
    path = output_dir / f"batch_{index:04d}.jsonl"
    prompt_path = output_dir / f"batch_{index:04d}.prompt.md"
    text = "\n".join(source_text(segment) for segment in segments)
    batch_terms = matched_glossary(glossary_terms, text, limit=120)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for segment in segments:
            handle.write(json.dumps(compact_segment(segment, glossary_terms), ensure_ascii=False, separators=(",", ":")) + "\n")
    prompt_path.write_text(prompt_text(target_language), encoding="utf-8")

    glossary_path = None
    if batch_terms:
        glossary_path = output_dir / f"batch_{index:04d}.glossary.md"
        lines = ["# Batch Glossary", "", "Use these mappings exactly when they appear in this batch.", ""]
        lines.extend(f"- {term['source']} => {term['target']}" for term in batch_terms)
        glossary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "batch": path.name,
        "path": str(path),
        "promptPath": str(prompt_path),
        "segments": len(segments),
        "chars": sum(len(source_text(segment)) for segment in segments),
        "glossaryTerms": len(batch_terms),
    }
    if glossary_path:
        summary["glossaryPath"] = str(glossary_path)
    return summary


def clear_old_batches(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("batch_*.jsonl", "batch_*.prompt.md", "batch_*.glossary.md", "batch_manifest.json"):
        for path in output_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def build_batches(
    segments_path: Path,
    output_dir: Path,
    max_segments: int,
    max_chars: int,
    *,
    max_parallel_agents: int = 16,
    translations_path: Path | None = None,
    include_translated: bool = False,
    context_pack: Path | None = None,
    glossary_csvs: list[Path] | None = None,
    target_language: str | None = None,
) -> dict:
    clear_old_batches(output_dir)
    translated_ids = set() if include_translated else load_translated_ids(translations_path)
    glossary_terms = load_glossary_terms(context_pack, glossary_csvs, target_language)
    batch: list[dict] = []
    batch_chars = 0
    manifest: list[dict] = []
    total_segments = 0
    skipped_translated = 0
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
        if sid in translated_ids:
            skipped_translated += 1
            continue

        text_len = len(text)
        would_exceed_segments = len(batch) >= max_segments
        would_exceed_chars = bool(batch) and batch_chars + text_len > max_chars
        if would_exceed_segments or would_exceed_chars:
            manifest.append(write_batch(output_dir, len(manifest) + 1, batch, glossary_terms, inferred_target_language or "target language"))
            batch = []
            batch_chars = 0
        batch.append(segment)
        batch_chars += text_len

    if batch:
        manifest.append(write_batch(output_dir, len(manifest) + 1, batch, glossary_terms, inferred_target_language or "target language"))

    summary = {
        "segmentsPath": str(segments_path),
        "outputDir": str(output_dir),
        "totalSegments": total_segments,
        "skippedTranslated": skipped_translated,
        "batchedSegments": sum(item["segments"] for item in manifest),
        "batchCount": len(manifest),
        "maxSegments": max_segments,
        "maxChars": max_chars,
        "maxParallelAgents": max_parallel_agents,
        "dispatchWaves": (len(manifest) + max_parallel_agents - 1) // max_parallel_agents if max_parallel_agents else 0,
        "glossaryTermCount": len(glossary_terms),
        "glossaryCsvs": [str(path) for path in glossary_csvs or []],
        "targetLanguage": inferred_target_language,
        "batches": manifest,
    }
    (output_dir / "batch_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segments", type=Path, help="segments.jsonl from the collect phase")
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for batch_*.jsonl files")
    parser.add_argument("--translations-path", type=Path, help="existing translations.jsonl; translated ids are skipped by default")
    parser.add_argument("--include-translated", action="store_true", help="include ids already present in translations.jsonl")
    parser.add_argument("--context-pack", type=Path, help="context_pack.md for optional glossary injection")
    parser.add_argument("--glossary-csv", action="append", default=[], help="BabelDOC-style CSV glossary with source,target,tgt_lng columns; can be repeated or comma-separated")
    parser.add_argument("--target-language", help="target language used to filter glossary CSV rows with tgt_lng")
    parser.add_argument("--max-segments", type=int, default=60)
    parser.add_argument("--max-chars", type=int, default=60000)
    parser.add_argument("--max-parallel-agents", type=int, default=16, help="default concurrent subagent cap for dispatch metadata")
    args = parser.parse_args()

    if args.max_segments <= 0:
        raise SystemExit("--max-segments must be positive")
    if args.max_chars <= 0:
        raise SystemExit("--max-chars must be positive")
    if args.max_parallel_agents <= 0:
        raise SystemExit("--max-parallel-agents must be positive")

    summary = build_batches(
        args.segments.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
        args.max_segments,
        args.max_chars,
        max_parallel_agents=args.max_parallel_agents,
        translations_path=args.translations_path.expanduser().resolve() if args.translations_path else None,
        include_translated=args.include_translated,
        context_pack=args.context_pack.expanduser().resolve() if args.context_pack else None,
        glossary_csvs=split_csv_paths(args.glossary_csv),
        target_language=args.target_language,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
