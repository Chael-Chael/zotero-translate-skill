---
name: zotero-translate
description: Translate Zotero PDF attachments on Windows, macOS, or Linux with a current-chat workflow that uses pdf2zh/BabelDOC for PDF segmentation, formula/layout preservation, and rendering while the active assistant conversation translates collected segments. Use when an agent needs to translate a selected Zotero PDF, generate mono and/or dual PDFs, and attach the final PDF outputs back to the same Zotero parent item without translation credentials or Zotero translation plugin setup.
---

# Zotero Translate

Use this skill to translate a Zotero PDF attachment through a single current-chat route. The cross-platform Python scripts use `pdf2zh-next` for segmentation and PDF rendering, and the active assistant conversation translates the collected text segments. The workflow is agent-agnostic: any agent that can load local skills, run scripts, and access Zotero Desktop through a connector can use it.

## Defaults

- Translate the full PDF unless the user specifies pages.
- Generate both mono and dual PDFs unless the user asks for only one output type.
- Use `-WatermarkOutputMode no_watermark`.
- Attach all final PDF outputs to the same Zotero parent item.
- Keep the skill-local runtime and BabelDOC asset cache by default.
- Prefer `python scripts/run_pdf2zh.py` on all platforms. Use `.ps1` wrappers only when the user explicitly wants PowerShell commands.
- Do not require a Zotero translation plugin or a preconfigured pdf2zh/BabelDOC environment; the skill bootstraps its local runtime on first use.

## Prompt Mapping

- If the user asks for translated-only, Chinese-only, or mono output, use `-OutputMode mono`.
- If the user asks for bilingual, side-by-side, or dual output, use `-OutputMode dual`.
- If the user asks for both, or gives no output preference, use `-OutputMode both`.
- If the user specifies pages, pass the exact page range to `-Pages`; otherwise omit `-Pages` for a full PDF run.

## Workflow

1. Use Zotero MCP to identify the active regular item and PDF attachment path.
2. Run `scripts/run_pdf2zh.py` in the default collect phase.
3. Read `references/current-chat-workflow.md`, `context_pack.md`, and `segments.jsonl`.
4. Translate segments in the active conversation and write `translations.jsonl`.
5. Run `scripts/run_pdf2zh.py --phase render --run-dir <run-dir>`.
6. Use `references/zotero-attach.md` to attach every final PDF under the original Zotero parent item.
7. Verify the Zotero parent item attachments.
8. Unless the user asked to keep artifacts, run `scripts/cleanup_artifacts.py --run-dir <run-dir> --confirm-attached`.

## Commands

Default full-PDF collect phase:

```bash
python "<path-to-installed-zotero-translate-skill>/scripts/run_pdf2zh.py" \
  --input-pdf "<path-to-zotero-pdf>"
```

Collect only pages 1-3 and generate mono output during render:

```bash
python "<path-to-installed-zotero-translate-skill>/scripts/run_pdf2zh.py" \
  --input-pdf "<path-to-zotero-pdf>" \
  --pages "1-3" \
  --output-mode mono
```

Render after `translations.jsonl` has been written:

```bash
python "<path-to-installed-zotero-translate-skill>/scripts/run_pdf2zh.py" \
  --phase render \
  --run-dir "<run-dir-from-collect-output>"
```

Clean intermediate artifacts after Zotero attachment is confirmed:

```bash
python "<path-to-installed-zotero-translate-skill>/scripts/cleanup_artifacts.py" \
  --run-dir "<run-dir-from-collect-output>" \
  --confirm-attached
```

## Artifact Rules

- Each run lives under the platform temp directory at `zotero-translate-runs/<run-id>`.
- The run directory contains `run_manifest.json`, `context_pack.md`, `segments.jsonl`, `translations.jsonl`, render outputs, collect outputs, and temporary files.
- `KeepArtifacts` skips cleanup for debugging.
- Do not delete `<skill-dir>/.runtime/venv` or `~/.cache/babeldoc` during normal cleanup.

## Runtime Rules

- `run_pdf2zh.py` creates `<skill-dir>/.runtime/venv` when needed.
- If `--python-exe` is provided, use it as the base Python for the venv.
- Otherwise, use the Python interpreter that launched `run_pdf2zh.py`; PowerShell wrappers first look for `python3`, `python`, or `py -3`, then use an available bundled runtime only as a fallback.

## Validation

- Run `python scripts/ensure_runtime.py` to create or verify the skill-local runtime.
- Run `python scripts/run_pdf2zh.py --input-pdf <pdf> --pages "1" --dry-run` to inspect collect command assembly.
- Test collector and lookup helpers with a short segment before a full PDF run.
- After attaching PDFs, re-read the Zotero parent item and confirm the new attachments.
