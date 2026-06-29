<div align="center">
  <img src="./assets/zotero-translate-hero.png" alt="Zotero Translate Skill hero banner" width="100%">
</div>

<div align="center">

# Zotero Translate Skill

English | [简体中文](docs/README_zh-CN.md) | [繁體中文](docs/README_zh-TR.md) | [日本語](docs/README_ja-JP.md) | [한국어](docs/README_ko-KR.md)

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](./LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-2ea44f)
![Zotero](https://img.shields.io/badge/Zotero-PDF%20attachments-BD1F2D)

<p>
  <strong>Install a skill. Translate the paper. Keep the layout.</strong>
</p>

<p>
  Agent-native Zotero PDF translation powered by pdf2zh and BabelDOC.<br>
  No Zotero plugin. No manual setup.
</p>

[Install](#31-installation) · [Quick Start](#32-quick-start) · [CLI Usage](#35-direct-cli-usage) · [Technical Details](#4-technical-details) · [Troubleshooting](#47-troubleshooting)

</div>

## 1. What Is This?

Zotero Translate Skill is for academic reading workflows where the PDF layout matters. It collects real text segments from a Zotero PDF attachment, translates them through a configured OpenAI-compatible API when available, then renders final PDFs and attaches them back to the same Zotero parent item.

Unlike ordinary one-shot PDF translation prompts, this skill keeps a deterministic run manifest and uses `pdf2zh-next` / BabelDOC for the fragile parts: segmentation, placeholder preservation, formula/layout handling, and final PDF generation. When no API is configured or reachable, it falls back to an agent-native batch workflow with glossary extraction and validation instead of requiring a separate Zotero translation plugin.

<p align="center">
  <img src="./assets/current-chat-pipeline.svg" alt="Zotero Translate workflow pipeline" width="92%">
</p>

### 1.1 Features

| Feature | Description |
| --- | --- |
| API-first translation | Uses an OpenAI-compatible `/v1/chat/completions` endpoint when `base_url` or `api_port`, `api_key`, and `model` are configured or supplied in the prompt. |
| Agent-native fallback | If the API route is unavailable, the active agent dispatches JSONL translation batches and validates the merged results before rendering. |
| Automatic glossary support | Builds compact term-extraction batches, merges `source,target,tgt_lng` glossary CSV files, and injects matched terms into translation prompts. |
| Layout-preserving rendering | PDF segmentation, placeholder protection, formula/layout handling, and rendering are delegated to `pdf2zh-next` / BabelDOC. |
| No Zotero plugin setup | Use Zotero Desktop through your agent connector; no separate Zotero translation plugin is required. |
| Self-contained runtime | The skill bootstraps its own Python venv and BabelDOC assets on first use. |
| Zotero-native output | Final PDFs are attached to the original Zotero parent item. |
| Explicit target language | The agent must ask for the target language when the prompt does not specify one. |
| Full PDF by default | Unless the prompt specifies pages, the skill translates the whole PDF. |
| Mono + dual by default | Produces translated-only and bilingual PDFs unless the user asks for one mode. |
| Python-only scripts | Cross-platform Python entrypoints support Windows, macOS, and Linux; no PowerShell wrapper is required. |
| Manifest-based cleanup | Temporary files are cleaned only after Zotero attachment is confirmed. |

### 1.2 Output Preview

<p align="center">
  <img src="./assets/output-modes.svg" alt="Mono and dual output modes" width="86%">
</p>

The repository currently includes generated SVG diagrams. For a stronger GitHub landing page, add real screenshots from your own workflow:

- `assets/preview-zotero-attachments.png`: Zotero parent item showing the original PDF plus generated mono and dual PDFs.
- `assets/preview-mono-dual-pages.png`: side-by-side page preview of mono and dual outputs from the same paper.
- `assets/preview-agent-run.png`: the agent conversation after collect, API or fallback translation, render, and attach.

## 2. Recent Updates

- **API-first route**: `check_api.py` verifies the configured OpenAI-compatible API before `api-translate` is used.
- **Agent-batch fallback**: if the API route is unavailable, the skill builds JSONL batches for parallel agent translation with a default active-agent cap of `16`.
- **Glossary extraction**: term batches and `merge_glossary.py` create BabelDOC-compatible `source,target,tgt_lng` CSV glossaries for prompt injection.
- **Stronger validation**: `validate_translations.py` checks missing/duplicate/unknown IDs, source/id mismatches, empty targets, protected tokens, rich-text tag order, and reference-like translation warnings.
- **Python-only workflow**: the skill now uses Python entrypoints only; PowerShell wrappers are no longer required.

## 3. Use

### 3.1 Installation

#### Option A: Skills CLI

If your agent environment supports the Skills CLI, install directly from GitHub:

```bash
npx skills add https://github.com/Chael-Chael/zotero-translate-skill
```

Restart your agent client after installation so it reloads available skills.

#### Option B: Manual Install for Codex

macOS / Linux:

```bash
git clone https://github.com/Chael-Chael/zotero-translate-skill.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R zotero-translate-skill/skills/zotero-translate "${CODEX_HOME:-$HOME/.codex}/skills/zotero-translate"
```

Windows PowerShell:

```powershell
git clone https://github.com/Chael-Chael/zotero-translate-skill.git
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\zotero-translate-skill\skills\zotero-translate" "$env:USERPROFILE\.codex\skills\zotero-translate"
```

Restart Codex after copying the skill.

This option is shown because Codex has a common local skill directory. The workflow itself is not Codex-specific.

#### Option C: Other Agents

Copy [`skills/zotero-translate`](./skills/zotero-translate) into the skill directory used by your agent, or point the agent at `skills/zotero-translate/SKILL.md`.

The deterministic workflow is Python-based and portable. A compatible agent only needs to read the skill instructions, run local Python scripts, and access Zotero Desktop through a connector or equivalent local automation tool. No Zotero plugin is required.

### 3.2 Quick Start

Open Zotero, select a paper item with a PDF attachment, then ask your agent:

```text
Use $zotero-translate to translate the selected Zotero PDF into Japanese.
```

Default behavior with API configured:

1. Collect the full PDF into stable text segments.
2. Translate segments through the configured OpenAI-compatible API.
3. Validate the translated JSONL.
4. Render both mono and dual PDFs.
5. Attach both PDFs to the original Zotero parent item.
6. Verify attachments.
7. Clean the temporary run directory.

Fallback behavior without API:

1. Build term-extraction batches unless auto glossary is disabled.
2. Merge agent-produced glossary results into `auto_glossary.csv`.
3. Build translation batches with matched glossary terms.
4. Dispatch at most `16` active translation agents by default.
5. Validate, render, attach, verify, and clean.

If the prompt does not specify the target language, the agent should ask which language to translate into before running the collect phase.

### 3.3 Prompt Examples

| Prompt | Result |
| --- | --- |
| `Use $zotero-translate to translate the selected Zotero PDF into Spanish.` | Full PDF, API-first route when configured, mono + dual output. |
| `Use $zotero-translate to translate the selected Zotero PDF.` | Asks for the target language before running. |
| `Use API port 8000, key sk-..., model qwen-plus.` | Stores local API config and prefers `api-translate`. |
| `Use temperature 0.1 and qps 2.` | Passes API runtime parameters during `api-translate`. |
| `Translate only pages 1-3, mono only.` | Passes `--pages "1-3"` and `--output-mode mono`. |
| `Make a bilingual PDF only.` | Uses `--output-mode dual`. |
| `Use 8 parallel agents.` | Uses `--max-parallel-agents 8` on the fallback batch route. |
| `No auto glossary.` | Skips term extraction before fallback translation batches. |
| `Use this glossary CSV: /path/terms.csv.` | Adds a user glossary with `source,target,tgt_lng` columns. |
| `Force agent route.` | Skips API translation and uses the agent-batch route. |
| `Translate this paper but keep artifacts for debugging.` | Skips cleanup so the run directory remains available. |

### 3.4 Requirements

| Requirement | Why it is needed |
| --- | --- |
| Python 3.10+ | Creates the skill-local virtual environment and runs helper scripts. |
| Zotero Desktop | Source PDFs and final attachments live in Zotero. |
| Zotero-capable agent connector | Reads selected items and attaches final PDFs. |
| Internet on first runtime setup | Installs `pdf2zh-next`, `PyMuPDF`, and BabelDOC assets. |
| OpenAI-compatible API | Optional but preferred for direct translation; requires base URL or port, API key, and model. |
| Batch-capable agent | Needed only for the fallback route when API translation is unavailable or disabled. |

You do not need to pre-install `pdf2zh`, BabelDOC, or a Zotero translation plugin. The skill prepares its own runtime under the skill directory.

First runtime setup creates:

```text
skills/zotero-translate/.runtime/venv
~/.cache/babeldoc
```

Optional API configuration is stored in:

```text
skills/zotero-translate/.runtime/api_config.json
```

These paths are intentionally excluded from version control.

### 3.5 Direct CLI Usage

You normally run this through an agent, but the deterministic phases can be executed directly.

Configure an OpenAI-compatible API once:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase configure-api \
  --api-port 8000 \
  --api-key "sk-..." \
  --api-model "model-name"
```

Collect segments:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --input-pdf "/path/to/paper.pdf" \
  --lang-out "ja"
```

Collect selected pages and request mono output:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --input-pdf "/path/to/paper.pdf" \
  --lang-out "ja" \
  --pages "1-3" \
  --output-mode mono
```

Translate through the API route:

```bash
python skills/zotero-translate/scripts/check_api.py \
  --api-port 8000 \
  --api-key "sk-..." \
  --api-model "model-name"
```

If the JSON result has `"apiAvailable": false`, pass `--force-agent-route` during collect, skip `api-translate`, and run the fallback batch route.

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase api-translate \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

If `api-translate` reports `api_unavailable`, run the fallback batch route:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase build-glossary-batches \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"

python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase merge-glossary \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"

python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase build-batches \
  --run-dir "/tmp/zotero-translate-runs/<run-id>" \
  --max-parallel-agents 16

python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase validate \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

Render final PDFs:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase render \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

Clean a verified run:

```bash
python skills/zotero-translate/scripts/cleanup_artifacts.py \
  --run-dir "/tmp/zotero-translate-runs/<run-id>" \
  --confirm-attached
```

All maintained entrypoints are Python scripts under [`skills/zotero-translate/scripts`](./skills/zotero-translate/scripts).

## 4. Technical Details

### 4.1 Translation Routes

The preferred route is API-first:

```text
collect -> api-translate -> validate -> render -> attach -> cleanup
```

The collect phase uses `collect_segments.py` as a `pdf2zh` CLI translator. It records actual source segments into `segments.jsonl` and returns the original text to keep the collection pass moving. The API route uses `api_translate_segments.py` to call an OpenAI-compatible chat-completions endpoint and writes `api_results.jsonl`; validation merges those results into `translations.jsonl`.

When no API is configured, unreachable, or explicitly skipped, the fallback route is:

```text
collect -> term batches -> term agents -> merge glossary -> translation batches -> translation agents -> validate -> render -> attach -> cleanup
```

The fallback route uses `build_term_batches.py`, `merge_glossary.py`, and `build_batches.py` to prepare deterministic JSONL work units. The render phase always uses `lookup_translator.py` to map stable source hashes to validated translations.

### 4.2 Run Directory

Each run creates a managed directory under the platform temp folder:

```text
zotero-translate-runs/<pdf-stem>-<hash>-<timestamp>/
├── run_manifest.json
├── context_pack.md
├── segments.jsonl
├── translations.jsonl
├── missing_segments.jsonl
├── api_results.jsonl
├── auto_glossary.csv
├── term_batches/
├── glossary_results/
├── batches/
├── batch_results/
├── collect-output/
├── render-output/
└── tmp/
```

The run directory can contain source text, translated text, and glossary terms. Clean it after successful Zotero attachment unless debugging is needed.

### 4.3 Output Modes

| Output mode | pdf2zh flags | Result |
| --- | --- | --- |
| `both` | default | Mono translated PDF + dual bilingual PDF. |
| `mono` | `--no-dual` | Translated-only PDF. |
| `dual` | `--no-mono` | Bilingual PDF. |

### 4.4 Runtime Selection

`run_pdf2zh.py` creates `<skill-dir>/.runtime/venv` when needed.

Selection order:

1. `--python-exe`, if provided.
2. The Python interpreter that launched `run_pdf2zh.py`.
3. A bundled Codex Python runtime, when available.
4. `python3`, `python`, then `py -3` on Windows.

### 4.5 Privacy Model

The skill sends extracted PDF segments only to the route the user or local configuration selects.

Important boundaries:

- API route: Zotero metadata used by the run, extracted PDF segments, glossary terms, and prompt instructions are sent to the configured OpenAI-compatible endpoint.
- API credentials are stored only in `skills/zotero-translate/.runtime/api_config.json`, which is ignored by git; run manifests do not store plaintext API keys.
- Agent-batch fallback: extracted PDF segments and glossary terms are visible to the active agent and any batch agents it spawns.
- Context packs redact common local path fields by default.
- Temporary run directories may contain source and translated text until cleanup.

### 4.6 Repository Layout

```text
.
├── README.md
├── LICENSE
├── assets/
│   ├── zotero-translate-hero.png
│   ├── zotero-translate-banner.svg
│   ├── current-chat-pipeline.svg
│   └── output-modes.svg
└── skills/
    └── zotero-translate/
        ├── SKILL.md
        ├── agents/
        ├── references/
        └── scripts/
            ├── run_pdf2zh.py
            ├── check_api.py
            ├── api_translate_segments.py
            ├── build_batches.py
            ├── build_term_batches.py
            ├── merge_glossary.py
            └── validate_translations.py
```

### 4.7 Troubleshooting

| Symptom | What to check |
| --- | --- |
| `No usable Python 3 executable was found` | Install Python 3.10+ or pass `--python-exe /path/to/python`. |
| Runtime setup is slow | First run installs `pdf2zh-next`, `PyMuPDF`, fonts, and BabelDOC assets. |
| `api-translate` reports `api_unavailable` | Run `configure-api` with a reachable base URL or port, API key, and model; or use the agent-batch fallback route. |
| API output fails validation | Re-run with lower temperature, stricter `--api-extra-instruction`, or use fallback batches for the failed segments. |
| Render reports missing segments | Open `missing_segments.jsonl`, translate the listed ids, append or revalidate, and rerun render. |
| Zotero attachment fails | Confirm Zotero Desktop is open and your agent has a working Zotero connector. |
| Disk usage grows | Clean completed run directories; keep `.runtime/venv` and `~/.cache/babeldoc` for faster future runs. |

## 5. Project Information

### 5.1 Acknowledgements

This skill is built around the layout-preserving PDF workflow pioneered by [PDFMathTranslate / PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) and its `pdf2zh` / BabelDOC ecosystem. The README organization follows the style of public skill repositories such as [greensock/gsap-skills](https://github.com/greensock/gsap-skills) and [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills).

This repository is not affiliated with Zotero, PDFMathTranslate, BabelDOC, Greensock, or Obsidian.

### 5.2 License

AGPL-3.0. See [`LICENSE`](./LICENSE).
