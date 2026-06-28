# Translation Workflow

Default route:

```text
collect -> api translate -> validate -> render
```

Fallback route:

```text
collect -> term batches -> term agents -> merge glossary -> translation batches -> translation agents -> validate -> render
```

The collect phase writes `run_manifest.json`, `context_pack.md`, `segments.jsonl`, and `translations.jsonl` in the run directory. API translation adds `api_results.jsonl`. Term extraction adds `term_batches/`, `glossary_results/`, and `auto_glossary.csv`. Batch translation adds `batches/`, `batches/batch_manifest.json`, and `batch_results/`.

## API Route

Use this route when the user provides API settings or a local API config exists:

```bash
python "$skillDir/scripts/run_pdf2zh.py" \
  --phase configure-api \
  --api-port "<port>" \
  --api-key "<key>" \
  --api-model "<model>"
```

Then translate:

```bash
python "$skillDir/scripts/run_pdf2zh.py" \
  --phase api-translate \
  --run-dir "<run-dir>"
```

Accepted prompt-mapped options: `--api-base-url`, `--api-port`, `--api-model`, `--api-temperature`, `--api-max-tokens`, `--api-qps`, `--api-timeout`, `--api-retries`, and `--api-extra-instruction`.

If `api-translate` reports `api_unavailable`, switch to the agent-batch route below. If it succeeds, it writes validated `translations.jsonl`; go directly to render.

## Term Route

Build term batches on the fallback route unless the user says no auto glossary:

```bash
python "$skillDir/scripts/run_pdf2zh.py" \
  --phase build-glossary-batches \
  --run-dir "<run-dir>"
```

Give each term agent exactly:

- one `term_batches/term_batch_*.jsonl`
- matching `term_batch_*.prompt.md`
- `context_pack.md`

Each term result line must be one JSON object:

```json
{"source":"<source term>","target":"<target term>","tgt_lng":"<target language>","notes":""}
```

Merge term results:

```bash
python "$skillDir/scripts/run_pdf2zh.py" \
  --phase merge-glossary \
  --run-dir "<run-dir>"
```

`auto_glossary.csv` uses BabelDOC-compatible columns: `source,target,tgt_lng`.

## Batch Route

Build batches:

```bash
python "$skillDir/scripts/run_pdf2zh.py" \
  --phase build-batches \
  --run-dir "<run-dir>" \
  --max-parallel-agents 16
```

`maxParallelAgents` is a dispatch cap, not a limit on total batches. Keep at most that many active translation agents at once; if there are more batches, dispatch in waves.

If `auto_glossary.csv` exists, `build-batches` injects matched terms into each `batch_*.jsonl` and writes `batch_*.glossary.md`. User-provided CSV glossaries can be added with `--glossary-csv "<path>"`.

Give each translation agent exactly:

- one `batches/batch_*.jsonl`
- matching `batch_*.glossary.md` if present
- `context_pack.md`
- this result contract

Translation agents must not run `pdf2zh`, render PDFs, attach Zotero items, clean artifacts, or edit shared files.

## Batch Result Contract

Each output line must be one JSON object:

```json
{"id":"<same id>","source":"<same source text>","target":"<translated text>","notes":""}
```

Rules:

- Output JSONL only.
- Preserve `id` exactly.
- Preserve protected tokens, math, citations, URLs, DOIs, arXiv IDs, XML-like tags, and rich-text tags exactly.
- Put only translated text in `target`.
- Save as `<run-dir>/batch_results/batch_0001.jsonl`, matching the assigned input batch.

Validate and merge:

```bash
python "$skillDir/scripts/run_pdf2zh.py" \
  --phase validate \
  --run-dir "<run-dir>"
```

Reassign only failed or missing batches, then rerun validation.

## Current-Chat Fallback

Use this only when the user requests no batch agents or the host cannot spawn them. Translate each `segments.jsonl` entry into `translations.jsonl`:

```json
{"id":"<same id>","source":"<same source text>","target":"<translated text>"}
```

Then validate in place:

```bash
python "$skillDir/scripts/validate_translations.py" \
  "<run-dir>/segments.jsonl" \
  "<run-dir>/translations.jsonl" \
  --write-translations "<run-dir>/translations.jsonl" \
  --missing-path "<run-dir>/missing_segments.jsonl"
```
