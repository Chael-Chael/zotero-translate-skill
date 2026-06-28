# Current-Chat Translation Workflow

Use this reference after `run_pdf2zh.py` completes the collect phase.

## Inputs

The collect phase writes these files in the run directory:

- `run_manifest.json`: paths and run settings.
- `context_pack.md`: paper-level terminology and style guidance.
- `segments.jsonl`: one source segment per line.
- `translations.jsonl`: output file to create or append.

## Translation Steps

1. Read `run_manifest.json` and `context_pack.md`.
2. Read `segments.jsonl`.
3. For every segment whose `id` is not already present in `translations.jsonl`, translate the `source` field.
4. Append one JSON object per line to `translations.jsonl`.
5. Preserve every segment `id` exactly.
6. Preserve math, citations, URLs, XML-like tags, and rich-text placeholders exactly.
7. Do not write explanations, Markdown fences, labels, or commentary inside the `target` value.

## JSONL Schema

Each `segments.jsonl` line has this shape:

```json
{"id":"<sha256>","source":"<text>","normalizedSource":"<normalized text>","sourceLanguage":"en","targetLanguage":"<target-language>","status":"pending"}
```

Each `translations.jsonl` line must have this shape:

```json
{"id":"<same sha256>","source":"<same source text>","target":"<translated text>"}
```

The `source` field in `translations.jsonl` is useful for review, but `lookup_translator.py` keys on `id`.

## Batching

For large PDFs, translate in batches. Keep appending to `translations.jsonl`; do not rewrite completed lines unless fixing a known bad translation. Before rendering, verify that every segment id has a translation.

## Render

After `translations.jsonl` is complete, run:

```bash
python "$skillDir/scripts/run_pdf2zh.py" \
  --phase render \
  --run-dir "<run-dir>"
```

If render reports a missing segment, open `missing_segments.jsonl`, translate those ids, append them to `translations.jsonl`, and rerun render.
