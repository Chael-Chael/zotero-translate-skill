#!/usr/bin/env python3
"""Translate collected segments through an OpenAI-compatible chat completions API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from build_batches import inferred_tokens, load_glossary_terms, matched_glossary, rich_text_tags, source_text, split_csv_paths


FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise ValueError(f"JSONL file does not exist: {path}")
    rows: list[dict] = []
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
            rows.append(item)
    return rows


def load_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    for item in read_jsonl(path):
        sid = str(item.get("id") or "")
        target = item.get("target", item.get("translation"))
        if sid and target is not None and str(target).strip():
            done.add(sid)
    return done


def chat_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def clean_content(content: str) -> str:
    return FENCE_RE.sub("", content.strip()).strip()


def extract_target(content: str) -> str:
    cleaned = clean_content(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned
    if isinstance(parsed, dict):
        for key in ("target", "translation", "translated_text"):
            value = parsed.get(key)
            if value is not None:
                return str(value)
    return cleaned


def call_chat_api(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float,
    temperature: float | None,
    max_tokens: int | None,
) -> str:
    payload: dict = {
        "model": model,
        "messages": messages,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None and max_tokens > 0:
        payload["max_tokens"] = max_tokens

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    request = urllib.request.Request(chat_endpoint(base_url), data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("API response did not contain choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if content is None:
        raise RuntimeError("API response did not contain message.content")
    return str(content)


def build_messages(segment: dict, target_language: str, glossary: list[dict], extra_instruction: str | None) -> list[dict]:
    text = source_text(segment)
    user_payload = {
        "id": str(segment.get("id") or ""),
        "sourceLanguage": segment.get("sourceLanguage", "en"),
        "targetLanguage": target_language,
        "source": text,
        "protectedTokens": inferred_tokens(text),
        "richTextTags": rich_text_tags(text),
        "glossary": glossary,
        "extraInstruction": extra_instruction or "",
    }
    system = (
        "You are a precise academic PDF translator. Return JSON only: "
        '{"target":"<translated text>","notes":""}. '
        "Preserve protected tokens, math, citations, URLs, DOI strings, arXiv IDs, and rich-text tags exactly. "
        "Use glossary target terms exactly when the source term appears. Put only translated text in target."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
    ]


def translate_segments(args: argparse.Namespace) -> dict:
    segments_path = args.segments.expanduser().resolve()
    output_path = args.output_results.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    segments = read_jsonl(segments_path)
    done = load_done(output_path) if args.resume else set()
    glossary_terms = load_glossary_terms(
        args.context_pack.expanduser().resolve() if args.context_pack else None,
        split_csv_paths(args.glossary_csv),
        args.target_language,
    )
    delay = 1.0 / args.qps if args.qps and args.qps > 0 else 0.0
    translated = 0
    skipped = 0
    started = time.monotonic()

    with output_path.open("a", encoding="utf-8", newline="\n") as handle:
        for index, segment in enumerate(segments, 1):
            sid = str(segment.get("id") or "")
            if not sid:
                raise ValueError(f"{segments_path}: segment {index} is missing id")
            if sid in done:
                skipped += 1
                continue
            text = source_text(segment)
            glossary = matched_glossary(glossary_terms, text, limit=80)
            messages = build_messages(segment, args.target_language, glossary, args.extra_instruction)
            last_error: Exception | None = None
            for attempt in range(args.retries + 1):
                try:
                    content = call_chat_api(
                        base_url=args.base_url,
                        api_key=args.api_key,
                        model=args.model,
                        messages=messages,
                        timeout=args.timeout,
                        temperature=args.temperature,
                        max_tokens=args.max_tokens,
                    )
                    target = extract_target(content)
                    break
                except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
                    last_error = exc
                    if attempt >= args.retries:
                        raise RuntimeError(f"{sid}: API translation failed after {args.retries + 1} attempt(s): {exc}") from exc
                    time.sleep(min(2 ** attempt, 8))
            else:
                raise RuntimeError(f"{sid}: API translation failed: {last_error}")

            row = {
                "id": sid,
                "source": text,
                "target": target,
                "notes": "api",
            }
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            translated += 1
            if delay > 0:
                time.sleep(delay)

    return {
        "status": "ok",
        "segmentsPath": str(segments_path),
        "outputResults": str(output_path),
        "totalSegments": len(segments),
        "translatedSegments": translated,
        "skippedExisting": skipped,
        "glossaryTermCount": len(glossary_terms),
        "elapsedSeconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segments", type=Path, help="segments.jsonl from the collect phase")
    parser.add_argument("--output-results", type=Path, required=True, help="API result JSONL path")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, for example http://127.0.0.1:8000/v1")
    parser.add_argument("--api-key", default=os.environ.get("ZOTERO_TRANSLATE_API_KEY") or os.environ.get("OPENAI_API_KEY") or "")
    parser.add_argument("--model", required=True)
    parser.add_argument("--target-language", required=True)
    parser.add_argument("--context-pack", type=Path)
    parser.add_argument("--glossary-csv", action="append", default=[])
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--qps", type=float, default=1.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--extra-instruction")
    parser.add_argument("--resume", action="store_true", help="skip ids already present in output results")
    args = parser.parse_args()

    if args.qps <= 0:
        raise SystemExit("--qps must be positive")
    if args.retries < 0:
        raise SystemExit("--retries must be non-negative")
    if not args.api_key:
        raise SystemExit("--api-key or ZOTERO_TRANSLATE_API_KEY is required")
    try:
        summary = translate_segments(args)
    except (ValueError, RuntimeError, urllib.error.URLError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
