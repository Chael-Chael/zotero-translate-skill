<div align="center">
  <img src="./assets/zotero-translate-hero.png" alt="Zotero Translate Skill hero banner" width="100%">
</div>

<div align="center">

# Zotero Translate Skill

English | [简体中文](docs/README_zh-CN.md) | [繁體中文](docs/README_zh-TW.md) | [日本語](docs/README_ja-JP.md) | [한국어](docs/README_ko-KR.md)

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](./LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-2ea44f)
![Translation](https://img.shields.io/badge/translation-current--chat-orange)
![Setup](https://img.shields.io/badge/setup-install%20skill%20only-7C3AED)
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

Zotero Translate Skill is for academic reading workflows where the PDF layout matters. It collects real text segments from a Zotero PDF attachment, asks the active agent conversation to translate those segments, then renders final PDFs and attaches them back to the same Zotero parent item.

Unlike ordinary one-shot PDF translation prompts, this skill keeps a deterministic run manifest and uses `pdf2zh-next` / BabelDOC for the fragile parts: segmentation, placeholder preservation, formula/layout handling, and final PDF generation. Compared with a traditional Zotero plugin workflow, the user-facing setup is lighter: install a skill once, then invoke it from whichever compatible agent you already use.

<p align="center">
  <img src="./assets/current-chat-pipeline.svg" alt="Current-chat PDF translation pipeline" width="92%">
</p>

### 1.1 Features

| Feature | Description |
| --- | --- |
| Agent-agnostic skill workflow | Designed for any agent that can load local skills and run bundled scripts, not only Codex. |
| Current-chat translation | The active agent conversation writes `translations.jsonl`; no provider-specific translation credentials are required. |
| Layout-preserving rendering | PDF segmentation, placeholder protection, formula/layout handling, and rendering are delegated to `pdf2zh-next` / BabelDOC. |
| No Zotero plugin setup | Use Zotero Desktop through your agent connector; no separate Zotero translation plugin is required. |
| Self-contained runtime | The skill bootstraps its own Python venv and BabelDOC assets on first use. |
| Zotero-native output | Final PDFs are attached to the original Zotero parent item. |
| Explicit target language | The agent must ask for the target language when the prompt does not specify one. |
| Full PDF by default | Unless the prompt specifies pages, the skill translates the whole PDF. |
| Mono + dual by default | Produces translated-only and bilingual PDFs unless the user asks for one mode. |
| Cross-platform scripts | Python entrypoints support Windows, macOS, and Linux; PowerShell wrappers remain for Windows users. |
| Privacy-aware context | Context packs avoid local paths and personal storage details by default. |
| Manifest-based cleanup | Temporary files are cleaned only after Zotero attachment is confirmed. |

### 1.2 Output Preview

<p align="center">
  <img src="./assets/output-modes.svg" alt="Mono and dual output modes" width="86%">
</p>

The repository currently includes generated SVG diagrams. For a stronger GitHub landing page, add real screenshots from your own workflow:

- `assets/preview-zotero-attachments.png`: Zotero parent item showing the original PDF plus generated mono and dual PDFs.
- `assets/preview-mono-dual-pages.png`: side-by-side page preview of mono and dual outputs from the same paper.
- `assets/preview-current-chat-run.png`: the agent conversation after collect, translation, render, and attach.

## 2. Recent Updates

- **Cross-platform workflow**: `run_pdf2zh.py` is now the main entrypoint for Windows, macOS, and Linux.
- **Current-chat only route**: removed background translator processes and provider-specific translation routes.
- **Multilingual documentation**: English, Simplified Chinese, Traditional Chinese, Japanese, and Korean README files are available.
- **Safer artifacts**: each run uses a unique temp directory and manifest-based cleanup.
- **UTF-8 stable helpers**: CLI translator helpers force UTF-8 stdin/stdout/stderr for multilingual text and non-ASCII PDF names.

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

Default behavior:

1. Collect the full PDF.
2. Translate segments in the active conversation into the specified target language.
3. Render both mono and dual PDFs.
4. Attach both PDFs to the original Zotero parent item.
5. Verify attachments.
6. Clean the temporary run directory.

If the prompt does not specify the target language, the agent should ask which language to translate into before running the collect phase.

### 3.3 Prompt Examples

| Prompt | Result |
| --- | --- |
| `Use $zotero-translate to translate the selected Zotero PDF into Spanish.` | Full PDF, mono + dual output. |
| `Use $zotero-translate to translate the selected Zotero PDF.` | Asks for the target language before running. |
| `Translate only pages 1-3, mono only.` | Passes `--pages "1-3"` and `--output-mode mono`. |
| `Make a bilingual PDF only.` | Uses `--output-mode dual`. |
| `Translate this paper but keep artifacts for debugging.` | Skips cleanup so the run directory remains available. |

### 3.4 Requirements

| Requirement | Why it is needed |
| --- | --- |
| Python 3.10+ | Creates the skill-local virtual environment and runs helper scripts. |
| Zotero Desktop | Source PDFs and final attachments live in Zotero. |
| Zotero-capable agent connector | Reads selected items and attaches final PDFs. |
| Internet on first runtime setup | Installs `pdf2zh-next`, `PyMuPDF`, and BabelDOC assets. |
| Enough current-chat context | The active conversation translates `segments.jsonl`. |

You do not need to pre-install `pdf2zh`, BabelDOC, or a Zotero translation plugin. The skill prepares its own runtime under the skill directory.

First runtime setup creates:

```text
skills/zotero-translate/.runtime/venv
~/.cache/babeldoc
```

These paths are intentionally excluded from version control.

### 3.5 Direct CLI Usage

You normally run this through an agent, but the deterministic phases can be executed directly.

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

After the active conversation writes `translations.jsonl`, render final PDFs:

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

PowerShell wrappers with equivalent parameters are available under [`skills/zotero-translate/scripts`](./skills/zotero-translate/scripts).

## 4. Technical Details

### 4.1 Current-Chat Translation Route

The workflow has one route:

```text
collect -> translate in current chat -> render -> attach -> cleanup
```

The collect phase uses `collect_segments.py` as a `pdf2zh` CLI translator. It records actual source segments into `segments.jsonl` and returns the original text to keep the collection pass moving. The active conversation reads the context pack and writes one translated JSON object per line to `translations.jsonl`. The render phase uses `lookup_translator.py` to map stable source hashes to translations.

### 4.2 Run Directory

Each run creates a managed directory under the platform temp folder:

```text
zotero-translate-runs/<pdf-stem>-<hash>-<timestamp>/
├── run_manifest.json
├── context_pack.md
├── segments.jsonl
├── translations.jsonl
├── missing_segments.jsonl
├── collect-output/
├── render-output/
└── tmp/
```

The run directory can contain source and translated text. Clean it after successful Zotero attachment unless debugging is needed.

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
3. For PowerShell wrappers: `python3`, `python`, `py -3`, then an available bundled runtime as a fallback.

### 4.5 Privacy Model

The skill does not send documents to a separate translation service. Translation happens in the active conversation that is already handling the user request.

Important boundaries:

- Zotero metadata and extracted PDF segments are visible to the active conversation.
- Context packs redact common local path fields by default.
- Temporary run directories may contain source and translated text until cleanup.

### 4.6 Repository Layout

```text
.
├── README.md
├── docs/
│   ├── README_zh-CN.md
│   ├── README_zh-TW.md
│   ├── README_ja-JP.md
│   └── README_ko-KR.md
├── LICENSE
├── assets/
│   ├── zotero-translate-banner.svg
│   ├── current-chat-pipeline.svg
│   └── output-modes.svg
└── skills/
    └── zotero-translate/
        ├── SKILL.md
        ├── agents/
        ├── references/
        └── scripts/
```

### 4.7 Troubleshooting

| Symptom | What to check |
| --- | --- |
| `No usable Python 3 executable was found` | Install Python 3.10+ or pass `--python-exe /path/to/python`. |
| Runtime setup is slow | First run installs `pdf2zh-next`, `PyMuPDF`, fonts, and BabelDOC assets. |
| Render reports missing segments | Open `missing_segments.jsonl`, translate the listed ids, append to `translations.jsonl`, and rerun render. |
| Zotero attachment fails | Confirm Zotero Desktop is open and your agent has a working Zotero connector. |
| Disk usage grows | Clean completed run directories; keep `.runtime/venv` and `~/.cache/babeldoc` for faster future runs. |

## 5. Project Information

### 5.1 Acknowledgements

This skill is built around the layout-preserving PDF workflow pioneered by [PDFMathTranslate / PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) and its `pdf2zh` / BabelDOC ecosystem. The README organization also follows the style of public skill repositories such as [greensock/gsap-skills](https://github.com/greensock/gsap-skills) and [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills).

This repository is not affiliated with Zotero, PDFMathTranslate, BabelDOC, Greensock, or Obsidian.

### 5.2 License

AGPL-3.0. See [`LICENSE`](./LICENSE).
