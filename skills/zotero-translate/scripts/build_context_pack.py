#!/usr/bin/env python3
"""Build a bounded current-chat context pack for a PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name)
    return cleaned[:80] if len(cleaned) > 80 else cleaned


def redact_local_paths(text: str) -> str:
    text = re.sub(r'(?i)"(path|filepath|pdfpath|file)"\s*:\s*"[^"]*"', r'"\1": "[redacted-local-path]"', text)
    text = re.sub(r"(?i)[A-Z]:\\[^,\"\r\n}]+", "[redacted-local-path]", text)
    text = re.sub(r"(?i)/(Users|home)/[^,\"\r\n}]+", "[redacted-local-path]", text)
    return text


def extract_pdf_context(pdf_path: Path, max_pages: int, max_chars_per_page: int) -> dict:
    result = {"metadata": {}, "page_count": None, "pages": [], "error": None}
    try:
        import fitz  # type: ignore

        doc = fitz.open(str(pdf_path))
        result["metadata"] = dict(doc.metadata or {})
        result["page_count"] = len(doc)
        for index in range(min(max_pages, len(doc))):
            text = doc[index].get_text("text") or ""
            result["pages"].append({"page": index + 1, "text": text[:max_chars_per_page]})
        doc.close()
    except Exception as exc:  # Keep context creation best-effort.
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Zotero Translate current-chat context pack.")
    parser.add_argument("--input-pdf", "-InputPdf", required=True)
    parser.add_argument("--output-path", "-OutputPath")
    parser.add_argument("--zotero-json", "-ZoteroJson")
    parser.add_argument("--source-language", "-SourceLanguage", default="en")
    parser.add_argument("--target-language", "-TargetLanguage", required=True)
    parser.add_argument("--max-pages", "-MaxPages", type=int, default=4)
    parser.add_argument("--max-chars-per-page", "-MaxCharsPerPage", type=int, default=5000)
    parser.add_argument("--user-preferences", "-UserPreferences", default="Use concise, academically precise wording. Preserve established English acronyms and method names when commonly used.")
    parser.add_argument("--include-local-paths", "-IncludeLocalPaths", action="store_true")
    parser.add_argument("--force", "-Force", action="store_true")
    args = parser.parse_args()

    input_pdf = Path(args.input_pdf).expanduser().resolve()
    if not args.target_language.strip():
        raise ValueError("TargetLanguage must not be empty. Ask the user which language to translate into.")
    if not input_pdf.exists():
        raise FileNotFoundError(f"InputPdf does not exist: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"InputPdf must be a PDF file: {input_pdf}")

    pdf_hash = sha256_file(input_pdf)
    output_path = Path(args.output_path).expanduser() if args.output_path else Path(tempfile.gettempdir()) / "codex-zotero-translate-context" / f"{safe_name(input_pdf.stem)}-{pdf_hash[:12]}" / "context_pack.md"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not args.force:
        context_hash = sha256_file(output_path)
        print(json.dumps({
            "input": str(input_pdf),
            "contextPack": str(output_path),
            "pdfSha256": pdf_hash,
            "contextSha256": context_hash,
            "pageCount": None,
            "extractionError": None,
            "reused": True,
        }, ensure_ascii=False, indent=2))
        return 0

    extracted = extract_pdf_context(input_pdf, args.max_pages, args.max_chars_per_page)

    if args.zotero_json:
        candidate = Path(args.zotero_json).expanduser()
        zotero_block = candidate.read_text(encoding="utf-8") if candidate.exists() else args.zotero_json
        if not args.include_local_paths:
            zotero_block = redact_local_paths(zotero_block)
    else:
        zotero_block = "Not provided."

    metadata = extracted.get("metadata") or {}
    title = metadata.get("title") or input_pdf.stem
    author = metadata.get("author") or "Unknown"
    metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    if not args.include_local_paths:
        metadata_json = redact_local_paths(metadata_json)

    pages: list[str] = []
    for page in extracted.get("pages", []):
        text = str(page.get("text", "")).replace("~~~", "---")
        pages.append(f"### Page {page.get('page')}\n~~~text\n{text}\n~~~\n")
    if extracted.get("error"):
        pages.append(f"Extraction warning: {extracted['error']}\n")

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = f"""# Zotero Translate Current-Chat Context Pack

context_version: 1
created_at: {created_at}
pdf_sha256: {pdf_hash}
source_language: {args.source_language}
target_language: {args.target_language}
pdf_file: {input_pdf.name}
title: {title}
authors: {author}
page_count: {extracted.get("page_count")}

## Translation Instructions

- Translate the current input segment from the source language to the target language unless the segment is already in the target language.
- Use an academic, precise, readable style suitable for scientific papers.
- Preserve math notation, inline variables, formulas, citations, URLs, code, XML-like tags, and rich-text placeholders exactly.
- Preserve placeholders such as <b0>, </b0>, <i1>, </i1>, <formula_0>, and citation brackets.
- Do not translate model names, dataset names, benchmark names, author names, URLs, DOIs, or arXiv IDs unless a glossary entry says otherwise.
- When translating collected segments in the active conversation, return only the translated segment in the `target` field. Do not add explanations, labels, Markdown fences, or summaries.

## User Preferences

{args.user_preferences}

## Glossary

Add one mapping per line as "source => target".

## Protected Tokens

- Rich text placeholders: <b0>, </b0>, <i0>, </i0>, <b1>, </b1>, <i1>, </i1>
- Formula placeholders and variables must remain byte-identical.
- Citation forms such as [1], (Smith et al., 2025), URLs, DOIs, and arXiv IDs must remain unchanged.

## Zotero Metadata

~~~json
{zotero_block}
~~~

## PDF Metadata

~~~json
{metadata_json}
~~~

## Extracted PDF Context

{''.join(pages)}
"""
    output_path.write_text(content, encoding="utf-8")
    print(json.dumps({
        "input": str(input_pdf),
        "contextPack": str(output_path),
        "pdfSha256": pdf_hash,
        "contextSha256": sha256_file(output_path),
        "pageCount": extracted.get("page_count"),
        "extractionError": extracted.get("error"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
