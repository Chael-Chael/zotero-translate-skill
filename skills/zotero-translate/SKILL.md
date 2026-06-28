---
name: zotero-translate
description: Translate Zotero PDF attachments with an API-first or agent-batch pdf2zh/BabelDOC workflow. Use when an agent needs to translate a selected Zotero PDF, render mono and/or bilingual PDFs, and attach the outputs back to the same Zotero parent item.
---

# Zotero Translate

Translate Zotero PDF attachments through a deterministic Python pipeline:

```text
collect -> api translate -> validate -> render -> attach -> cleanup
```

If no API config is provided or detected, use the agent-batch route:

```text
collect -> term batches -> term agents -> merge glossary -> translation batches -> translation agents -> validate -> render -> attach -> cleanup
```

## Defaults

- Ask for the target language if the prompt does not specify one.
- Translate the full PDF unless the user specifies pages.
- Generate both mono and dual PDFs unless the user asks for one mode.
- Use `--watermark-output-mode no_watermark`.
- Prefer direct OpenAI-compatible API translation when `api_base_url`/`api_port`, `api_key`, and `model` are configured or supplied in the prompt.
- If API config is unavailable or `api-translate` reports `api_unavailable`, use agent-batch translation.
- Extract a compact glossary with term agents before agent-batch translation unless the user says no auto glossary.
- Default active agent cap for the batch route: `16`. If the user says "use N parallel agents/subagents", pass `--max-parallel-agents N`.
- Attach final PDFs to the original Zotero parent item.
- Use Python scripts only; no PowerShell wrapper is required.
- Keep BabelDOC internal auto glossary disabled during collect/render; use this skill's glossary CSV only on the agent-batch/API prompt side.

## Workflow

1. Identify the active Zotero regular item and PDF attachment path.
2. If the user provides API settings, save them first:

   ```bash
   python scripts/run_pdf2zh.py --phase configure-api --api-port "<port>" --api-key "<key>" --api-model "<model>"
   ```

3. Run collect. Pass API settings here instead if the user provided them in the same prompt:

   ```bash
   python scripts/run_pdf2zh.py --input-pdf "<pdf>" --lang-out "<target-language>"
   ```

4. Try API translation unless the user explicitly asks for the agent route:

   ```bash
   python scripts/run_pdf2zh.py --phase api-translate --run-dir "<run-dir>"
   ```

5. If API translation validates successfully, skip to render. If it reports `api_unavailable`, read `references/workflow.md`, `context_pack.md`, and `segments.jsonl`, then use the agent-batch route.
6. Unless the user says no auto glossary, build term batches:

   ```bash
   python scripts/run_pdf2zh.py --phase build-glossary-batches --run-dir "<run-dir>"
   ```

7. Spawn agents for `term_batches/term_batch_*.jsonl` using the matching `term_batch_*.prompt.md`. Save each result to `glossary_results/term_batch_*.jsonl`.
8. Merge the glossary:

   ```bash
   python scripts/run_pdf2zh.py --phase merge-glossary --run-dir "<run-dir>"
   ```

9. Run translation batch build:

   ```bash
   python scripts/run_pdf2zh.py --phase build-batches --run-dir "<run-dir>" --max-parallel-agents 16
   ```

10. Spawn agents for `batches/batch_*.jsonl`, at no more than `maxParallelAgents` active workers at once. Save each result to `batch_results/batch_*.jsonl`.
11. Validate and merge:

   ```bash
   python scripts/run_pdf2zh.py --phase validate --run-dir "<run-dir>"
   ```

12. Render:

   ```bash
   python scripts/run_pdf2zh.py --phase render --run-dir "<run-dir>"
   ```

13. Follow `references/zotero-attach.md` to attach all rendered PDFs to the Zotero parent item.
14. Verify attachments. Unless the user asked to keep artifacts, clean:

   ```bash
   python scripts/cleanup_artifacts.py --run-dir "<run-dir>" --confirm-attached
   ```

## Prompt Mapping

- Pages: pass `--pages "<range>"`.
- Mono only: pass `--output-mode mono`.
- Dual/bilingual only: pass `--output-mode dual`.
- Both/default: pass `--output-mode both`.
- API base URL or port: pass `--api-base-url "<url>"` or `--api-port "<port>"`.
- API key: pass `--api-key "<key>"`; it is stored under `.runtime/api_config.json` and not written to the run manifest.
- API model: pass `--api-model "<model>"`; if omitted, `configure-api` may discover the first model from `/v1/models`.
- API parameters: pass `--api-temperature`, `--api-max-tokens`, `--api-qps`, `--api-timeout`, `--api-retries`, or `--api-extra-instruction`.
- Force agent route: pass `--force-agent-route` or skip `api-translate`.
- Parallel count: pass `--max-parallel-agents <N>`.
- No auto glossary: pass `--no-auto-glossary` and skip term batches.
- User glossary: pass `--glossary-csv "<csv>"` during `build-batches`; CSV columns are `source,target,tgt_lng`.
- Current-chat only/no batch agents: skip `build-batches`; translate `segments.jsonl` directly and validate it with `validate_translations.py`.

## Validation

Before rendering, validation must pass. It checks missing/duplicate/unknown IDs, source/id mismatches, empty translations, protected token preservation, rich-text tag order, and reference-like translation warnings.
