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
- Before choosing the API route, run `scripts/check_api.py`. If it returns `"apiAvailable": false`, skip `api-translate` and use agent-batch translation directly.
- Extract a compact glossary with term agents before agent-batch translation unless the user says no auto glossary.
- Default active agent cap for the batch route: `16`. If the user says "use N parallel agents/subagents", pass `--max-parallel-agents N`.
- Do not run a preliminary smoke test or page-only trial unless the user explicitly asks for one. After the target PDF and target language are known, translate the requested scope directly; default to the full PDF.
- For agent-batch fallback, dispatch term and translation subagents with a cheap, low-latency model by default when the host allows model choice. Escalate only for failed validation, poor quality, or an explicit user/model requirement.
- Agent-batch subagents must produce term targets and segment targets themselves from the assigned JSONL, context pack, and glossary. Do not use third-party translation APIs, online translators, local MT/translation libraries, browser/search tools, `pdf2zh`/BabelDOC translation modes, or another agent/process to generate translated text.
- Never use `pdf2zh` public machine-translation backends such as `--google`, `--bing`, `GoogleTranslator`, `BingTranslator`, `deep-translator`, `googletrans`, or `translatepy`. If the configured API is unavailable, fail closed into the agent-batch route.
- Attach final PDFs to the original Zotero parent item through the Zotero Translate Bridge. Probe with `scripts/ensure_zotero_bridge.py --probe`; if unavailable, ask the user to install the release XPI from `https://github.com/Chael-Chael/zotero-translate-skill/raw/main/assets/zotero-translate-bridge-0.2.4.xpi` in Zotero Add-ons, restart Zotero, then probe again. Do not rely on profile-side automatic extension loading as the normal install path.
- The bridge only exposes `health`, `attach`, and `verify` endpoints protected by a local token. Do not add or use generic Zotero JavaScript execution endpoints for this workflow.
- Use Python scripts only; no PowerShell wrapper is required.
- Keep BabelDOC internal auto glossary disabled during collect/render; use this skill's glossary CSV only on the agent-batch/API prompt side.

## Workflow

1. Identify the active Zotero regular item and PDF attachment path.
2. Check whether the configured OpenAI-compatible API is available. Pass API settings here if the user supplied them in the same prompt:

   ```bash
   python scripts/check_api.py --api-port "<port>" --api-key "<key>" --api-model "<model>"
   ```

   If the JSON result has `"apiAvailable": false`, plan the agent-batch route, pass `--force-agent-route` during collect, and skip `api-translate`.

3. Run collect. Pass API settings here instead if the user provided them in the same prompt, and include `--force-agent-route` if `check_api.py` returned false:

   ```bash
   python scripts/run_pdf2zh.py --input-pdf "<pdf>" --lang-out "<target-language>"
   ```

4. If `check_api.py` returned `"apiAvailable": true`, run API translation unless the user explicitly asks for the agent route:

   ```bash
   python scripts/run_pdf2zh.py --phase api-translate --run-dir "<run-dir>"
   ```

5. If API translation validates successfully, skip to render. If `check_api.py` returned false or `api-translate` reports `api_unavailable`, read `references/workflow.md`, `context_pack.md`, and `segments.jsonl`, then use the agent-batch route.
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

13. Follow `references/zotero-attach.md` to ensure the bridge is installed, attach all rendered PDFs to the Zotero parent item, and verify the attachments.
14. Unless the user asked to keep artifacts, clean:

   ```bash
   python scripts/cleanup_artifacts.py --run-dir "<run-dir>" --confirm-attached
   ```

## Safe Prompt Mapping

Expose only these user-facing controls. Do not invent or pass through other `pdf2zh`/BabelDOC options unless this skill explicitly adds them.

- Pages: pass `--pages "<range>"`.
- Output mode: pass `--output-mode mono`, `--output-mode dual`, or `--output-mode both`.
- Watermark: pass `--watermark-output-mode no_watermark`, `watermarked`, or `both`.
- API: pass `--api-base-url`, `--api-port`, `--api-key`, `--api-model`, `--api-temperature`, `--api-max-tokens`, `--api-qps`, `--api-timeout`, `--api-retries`, or `--api-extra-instruction`; check availability with `scripts/check_api.py` first and branch on `apiAvailable`.
- Glossary: pass `--glossary-csv "<csv>"` during `build-batches`; CSV columns are `source,target,tgt_lng`. If the user asks to skip automatic glossary extraction, pass `--no-auto-glossary`.
- Parallel count: pass `--max-parallel-agents <N>`.
- Cleanup: honor "keep artifacts" with `--keep-artifacts` or `--cleanup-policy never`; otherwise clean only after Zotero attachment is verified.

## Validation

Before rendering, validation must pass. It checks missing/duplicate/unknown IDs, source/id mismatches, empty translations, protected token preservation, rich-text tag order, and reference-like translation warnings.
