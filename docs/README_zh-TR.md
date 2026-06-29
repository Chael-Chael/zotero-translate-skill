<div align="center">
  <img src="../assets/zotero-translate-hero.png" alt="Zotero Translate Skill hero banner" width="100%">
</div>

<div align="center">

# Zotero Translate Skill

[English](../README.md) | [简体中文](README_zh-CN.md) | 繁體中文 | [日本語](README_ja-JP.md) | [한국어](README_ko-KR.md)

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](../LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-2ea44f)
![Translation](https://img.shields.io/badge/translation-api--first-orange)
![Setup](https://img.shields.io/badge/setup-install%20skill%20only-7C3AED)
![Zotero](https://img.shields.io/badge/Zotero-PDF%20attachments-BD1F2D)

<p>
  <strong>安裝一個 skill。翻譯論文。保留版式。</strong>
</p>

<p>
  基於 pdf2zh 和 BabelDOC 的 agent-native Zotero PDF 翻譯流程。<br>
  需要寫回附件時會建立一個最小本機 Zotero bridge。
</p>

[安裝](#31-installation) · [快速開始](#32-quick-start) · [CLI 用法](#35-direct-cli-usage) · [技術細節](#4-technical-details) · [疑難排解](#47-troubleshooting)

</div>

## 1. 這是什麼？

Zotero Translate Skill 面向需要保留 PDF 版式的學術閱讀流程。它從 Zotero PDF 附件中收集真實文字片段，在可用時透過已配置的 OpenAI-compatible API 翻譯，然後渲染最終 PDF，並把輸出附件掛回同一個 Zotero 父條目。

它不是普通的一次性 PDF 翻譯提示。這個 skill 會維護確定性的 run manifest，並把容易出錯的部分交給 `pdf2zh-next` / BabelDOC：分段、佔位符保護、公式和版式處理、最終 PDF 渲染。沒有可用 API 時，它會退回到 agent-native 批次流程，包括術語抽取、批量翻譯和渲染前驗證，不需要額外的 Zotero 翻譯外掛。

<p align="center">
  <img src="../assets/current-chat-pipeline.svg" alt="Zotero Translate workflow pipeline" width="92%">
</p>

### 1.1 功能

| 功能 | 說明 |
| --- | --- |
| API 優先翻譯 | 當 prompt 或本機配置提供 `base_url` / `api_port`、`api_key` 和 `model` 時，直接呼叫 OpenAI-compatible `/v1/chat/completions`。 |
| Agent-native fallback | API 不可用時，目前 agent 會分發 JSONL 翻譯批次，並在渲染前驗證合併結果。 |
| 自動術語支援 | 建立術語抽取批次，合併 `source,target,tgt_lng` glossary CSV，並把命中的術語注入翻譯提示。 |
| 保留版式渲染 | PDF 分段、佔位符保護、公式/版式處理和渲染由 `pdf2zh-next` / BabelDOC 完成。 |
| 本機 Zotero bridge | 使用相容 Zotero 7-9 的最小 XPI 寫回附件，並透過 token 保護的本機端點附加 PDF。 |
| 自包含執行環境 | 首次執行時在 skill 目錄下建立 Python venv 並準備 BabelDOC 資產。 |
| Zotero 原生輸出 | 最終 PDF 會附加回原始 Zotero 父條目。 |
| 明確目標語言 | 如果 prompt 沒寫目標語言，agent 必須先詢問。 |
| 預設整篇 PDF | 除非使用者指定頁碼，否則翻譯完整 PDF。 |
| 預設 mono + dual | 除非使用者指定輸出模式，否則同時產生譯文 PDF 和雙語 PDF。 |
| 僅 Python 腳本 | Python 入口支援 Windows、macOS 和 Linux；不再需要 PowerShell wrapper。 |
| Manifest 清理 | 只有確認 Zotero 附件已寫入後才清理臨時檔案。 |

### 1.2 輸出預覽

<p align="center">
  <img src="../assets/output-modes.svg" alt="Mono and dual output modes" width="86%">
</p>

倉庫目前包含生成的 SVG 示意圖。為了讓 GitHub 首頁更直觀，可以補充真實工作流截圖：

- `assets/preview-zotero-attachments.png`：Zotero 父條目中顯示原 PDF、mono 輸出和 dual 輸出。
- `assets/preview-mono-dual-pages.png`：同一篇論文的 mono / dual 頁面並排預覽。
- `assets/preview-agent-run.png`：agent 完成 collect、API 或 fallback 翻譯、render、attach 的對話截圖。

## 2. 最近更新

- **API-first route**：`configure-api` 和 `api-translate` 會在憑證和模型可用時呼叫 OpenAI-compatible chat completion API。
- **Agent-batch fallback**：API 不可用時，skill 會建立 JSONL 批次並行交給 agent 翻譯，預設最多 `16` 個活躍 agent。
- **術語抽取**：術語批次和 `merge_glossary.py` 會生成 BabelDOC 相容的 `source,target,tgt_lng` glossary CSV，用於提示注入。
- **本機 Zotero bridge**：先在 Zotero Add-ons 中安裝一次 release XPI；`ensure_zotero_bridge.py --probe` 匯入本機 token，`attach_with_bridge.py` 在 bridge 載入後透過 token 保護的 `health` / `attach` / `verify` 端點寫回 PDF。
- **更強驗證**：`validate_translations.py` 檢查缺失、重複、未知 ID，source/id 不匹配，空目標文字，protected token，rich-text tag 順序，以及疑似參考文獻被翻譯的風險。
- **Python-only workflow**：目前維護的入口都是 Python 腳本，不再需要 PowerShell wrapper。

## 3. 使用

<a id="31-installation"></a>

### 3.1 安裝

#### 方式 A：Skills CLI

如果你的 agent 環境支援 Skills CLI，可以直接從 GitHub 安裝：

```bash
npx skills add https://github.com/Chael-Chael/zotero-translate-skill
```

安裝後重新啟動 agent client，讓它重新載入可用 skills。

#### 方式 B：Codex 手動安裝

macOS / Linux：

```bash
git clone https://github.com/Chael-Chael/zotero-translate-skill.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R zotero-translate-skill/skills/zotero-translate "${CODEX_HOME:-$HOME/.codex}/skills/zotero-translate"
```

Windows PowerShell：

```powershell
git clone https://github.com/Chael-Chael/zotero-translate-skill.git
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\zotero-translate-skill\skills\zotero-translate" "$env:USERPROFILE\.codex\skills\zotero-translate"
```

複製後重新啟動 Codex。

這裡列出 Codex 路徑，是因為 Codex 有常見的本機 skill 目錄。工作流本身不是 Codex 專屬。

#### 方式 C：其他 Agent

把 [`skills/zotero-translate`](../skills/zotero-translate) 複製到你的 agent 使用的 skill 目錄，或讓 agent 直接讀取 `skills/zotero-translate/SKILL.md`。

確定性流程基於 Python，具有可移植性。相容 agent 只需要能讀取 skill 指令、執行本機 Python 腳本，並透過 connector 或本機自動化存取 Zotero Desktop。skill 會為最終附件寫回建立最小 Zotero bridge XPI，並在 Zotero 未載入時明確回報。

#### Zotero Bridge XPI

首次寫回附件前，在 Zotero 中安裝一次 bridge：

1. 下載 [`zotero-translate-bridge.xpi`](https://github.com/Chael-Chael/zotero-translate-skill/raw/main/assets/zotero-translate-bridge.xpi)。
2. 在 Zotero 開啟 `Tools -> Add-ons`。
3. 點擊齒輪，選擇 `Install Add-on From File...`，選擇該 XPI。
4. 重新啟動 Zotero。
5. 執行一次 probe，讓腳本匯入本機 bridge token：

```bash
python skills/zotero-translate/scripts/ensure_zotero_bridge.py --probe
```

這個 XPI 不包含共享 token，並宣告相容 Zotero `7.0` 到 `9.*`。bridge 首次啟動會在 Zotero profile 中寫入每個使用者自己的 `zotero-translate-bridge.json`。

<a id="32-quick-start"></a>

### 3.2 快速開始

開啟 Zotero，選擇帶 PDF 附件的論文條目，然後對 agent 說：

```text
Use $zotero-translate to translate the selected Zotero PDF into Japanese.
```

API 已配置時的預設行為：

1. 將整篇 PDF 收集成穩定文字片段。
2. 透過配置好的 OpenAI-compatible API 翻譯片段。
3. 驗證翻譯 JSONL。
4. 渲染 mono 和 dual 兩種 PDF。
5. 將兩個 PDF 附加回原 Zotero 父條目。
6. 驗證附件。
7. 清理臨時 run directory。

沒有 API 時的 fallback 行為：

1. 除非停用 auto glossary，否則建立術語抽取批次。
2. 把 agent 產出的術語結果合併為 `auto_glossary.csv`。
3. 用命中的術語建立翻譯批次。
4. 預設最多分發 `16` 個活躍翻譯 agent。
5. 驗證、渲染、附加、確認並清理。

如果 prompt 沒有寫目標語言，agent 應該先詢問目標語言，再開始 collect phase。

### 3.3 Prompt 範例

| Prompt | 結果 |
| --- | --- |
| `Use $zotero-translate to translate the selected Zotero PDF into Spanish.` | 整篇 PDF，配置 API 時走 API-first route，輸出 mono + dual。 |
| `Use $zotero-translate to translate the selected Zotero PDF.` | 先詢問目標語言。 |
| `Use API port 8000, key sk-..., model qwen-plus.` | 儲存本機 API 配置並優先使用 `api-translate`。 |
| `Use temperature 0.1 and qps 2.` | 在 `api-translate` 階段傳入 API 執行參數。 |
| `Translate only pages 1-3, mono only.` | 傳入 `--pages "1-3"` 和 `--output-mode mono`。 |
| `Make a bilingual PDF only.` | 使用 `--output-mode dual`。 |
| `Use 8 parallel agents.` | fallback 批次路線使用 `--max-parallel-agents 8`。 |
| `No auto glossary.` | fallback 翻譯批次前跳過術語抽取。 |
| `Use this glossary CSV: /path/terms.csv.` | 增加一個包含 `source,target,tgt_lng` 欄位的使用者術語表。 |
| `Force agent route.` | 跳過 API 翻譯，使用 agent-batch route。 |
| `Translate this paper but keep artifacts for debugging.` | 保留 run directory，跳過清理。 |

### 3.4 要求

| 要求 | 原因 |
| --- | --- |
| Python 3.10+ | 建立 skill-local venv 並執行 helper scripts。 |
| Zotero Desktop | 來源 PDF 和最終附件都在 Zotero 中。 |
| 支援 Zotero 的 agent connector | 識別選中的父條目和來源 PDF。 |
| 首次執行需要網路 | 安裝 `pdf2zh-next`、`PyMuPDF` 和 BabelDOC 資產。 |
| OpenAI-compatible API | 可選但優先；需要 base URL 或連接埠、API key 和 model。 |
| 可分批執行的 agent | 僅在 API 不可用或被停用時用於 fallback route。 |

你不需要預裝 `pdf2zh`、BabelDOC 或 Zotero 翻譯外掛。skill 會在自己的目錄下準備執行環境，並在首次附件寫回時建立 bridge XPI。

首次執行會建立：

```text
skills/zotero-translate/.runtime/venv
~/.cache/babeldoc
```

可選 API 配置會儲存在：

```text
skills/zotero-translate/.runtime/api_config.json
```

Bridge 建構產物和本機 token 會儲存在：

```text
skills/zotero-translate/.runtime/zotero-translate-bridge/
```

這些路徑都故意排除在版本控制之外。

<a id="35-direct-cli-usage"></a>

### 3.5 直接 CLI 用法

通常應該透過 agent 使用這個 skill，但確定性 phase 也可以直接執行。

一次性配置 OpenAI-compatible API：

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase configure-api \
  --api-port 8000 \
  --api-key "sk-..." \
  --api-model "model-name"
```

收集片段：

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --input-pdf "/path/to/paper.pdf" \
  --lang-out "ja"
```

只收集指定頁並請求 mono 輸出：

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --input-pdf "/path/to/paper.pdf" \
  --lang-out "ja" \
  --pages "1-3" \
  --output-mode mono
```

透過 API route 翻譯：

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase api-translate \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

如果 `api-translate` 回傳 `api_unavailable`，執行 fallback batch route：

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

渲染最終 PDF：

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase render \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

確保 bridge 已安裝並寫回渲染後的 PDF：

```bash
python skills/zotero-translate/scripts/ensure_zotero_bridge.py --probe

python skills/zotero-translate/scripts/attach_with_bridge.py \
  --run-dir "/tmp/zotero-translate-runs/<run-id>" \
  --parent-item-id "<zotero-parent-item-id>"
```

清理已驗證的 run：

```bash
python skills/zotero-translate/scripts/cleanup_artifacts.py \
  --run-dir "/tmp/zotero-translate-runs/<run-id>" \
  --confirm-attached
```

目前維護的入口都在 [`skills/zotero-translate/scripts`](../skills/zotero-translate/scripts) 下，並且都是 Python 腳本。

<a id="4-technical-details"></a>

## 4. 技術細節

### 4.1 翻譯路線

優先路線是 API-first：

```text
collect -> api-translate -> validate -> render -> attach -> cleanup
```

collect phase 使用 `collect_segments.py` 作為 `pdf2zh` CLI translator。它把真實來源文字寫入 `segments.jsonl`，同時回傳原文以保證 collect pass 能繼續執行。API route 使用 `api_translate_segments.py` 呼叫 OpenAI-compatible chat-completions endpoint，並寫入 `api_results.jsonl`；validation 會把這些結果合併成 `translations.jsonl`。

沒有 API、API 不可達，或使用者明確跳過 API 時，fallback route 是：

```text
collect -> term batches -> term agents -> merge glossary -> translation batches -> translation agents -> validate -> render -> attach -> cleanup
```

fallback route 使用 `build_term_batches.py`、`merge_glossary.py` 和 `build_batches.py` 準備確定性的 JSONL 工作單元。render phase 始終使用 `lookup_translator.py`，透過穩定 source hash 查找已驗證譯文。

### 4.2 Run Directory

每次執行都會在系統臨時目錄下建立一個受管理目錄：

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

run directory 可能包含來源文字、譯文和術語。除非需要除錯，否則成功附加到 Zotero 後應清理。

### 4.3 輸出模式

| Output mode | pdf2zh flags | 結果 |
| --- | --- | --- |
| `both` | default | 譯文 PDF + 雙語 PDF。 |
| `mono` | `--no-dual` | 僅譯文 PDF。 |
| `dual` | `--no-mono` | 雙語 PDF。 |

### 4.4 執行環境選擇

`run_pdf2zh.py` 會在需要時建立 `<skill-dir>/.runtime/venv`。

選擇順序：

1. 如果提供了 `--python-exe`，優先使用它。
2. 啟動 `run_pdf2zh.py` 的 Python interpreter。
3. 可用時使用 Codex bundled Python runtime。
4. Windows 上依序嘗試 `python3`、`python`、`py -3`。

### 4.5 隱私模型

skill 只會把抽取出的 PDF 片段傳送到使用者或本機配置選擇的路線。

重要邊界：

- API route：run 使用的 Zotero metadata、PDF 文字片段、術語和 prompt instructions 會傳送到配置的 OpenAI-compatible endpoint。
- API credentials 只儲存在 `skills/zotero-translate/.runtime/api_config.json`，該路徑被 git 忽略；run manifest 不儲存明文 API key。
- Agent-batch fallback：PDF 片段和術語會被目前 agent 以及它分發的 batch agents 看到。
- Zotero bridge：Zotero 內只安裝 token 保護的本機 `health`、`attach`、`verify` 端點；不暴露任意 JavaScript 執行。
- Context pack 預設會清理常見本機路徑欄位。
- 臨時 run directory 在清理前可能包含來源文字和譯文。

### 4.6 倉庫結構

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
        ├── assets/
        │   └── zotero-translate-bridge/
        ├── references/
        └── scripts/
            ├── run_pdf2zh.py
            ├── check_api.py
            ├── ensure_zotero_bridge.py
            ├── attach_with_bridge.py
            ├── api_translate_segments.py
            ├── build_batches.py
            ├── build_term_batches.py
            ├── merge_glossary.py
            └── validate_translations.py
```

<a id="47-troubleshooting"></a>

### 4.7 疑難排解

| 現象 | 檢查項 |
| --- | --- |
| `No usable Python 3 executable was found` | 安裝 Python 3.10+ 或傳入 `--python-exe /path/to/python`。 |
| 執行環境設定很慢 | 首次執行會安裝 `pdf2zh-next`、`PyMuPDF`、字型和 BabelDOC 資產。 |
| `api-translate` 回傳 `api_unavailable` | 用可達 base URL 或連接埠、API key、model 執行 `configure-api`；或使用 agent-batch fallback route。 |
| API 輸出驗證失敗 | 降低 temperature，增加更嚴格的 `--api-extra-instruction`，或把失敗片段交給 fallback batches。 |
| Render 報告缺失片段 | 打開 `missing_segments.jsonl`，翻譯列出的 id，追加或重新驗證，再執行 render。 |
| Zotero 附件失敗 | 在 Zotero Add-ons 中安裝 release XPI 並重新啟動 Zotero，然後執行 `ensure_zotero_bridge.py --probe`，再用正確的父條目 ID 重試 `attach_with_bridge.py`。 |
| 磁碟占用成長 | 清理已完成的 run directories；保留 `.runtime/venv` 和 `~/.cache/babeldoc` 可加速後續執行。 |

## 5. 專案資訊

### 5.1 致謝

這個 skill 基於 [PDFMathTranslate / PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) 及其 `pdf2zh` / BabelDOC 生態中的版式保留 PDF 工作流。README 組織方式參考了 [greensock/gsap-skills](https://github.com/greensock/gsap-skills) 和 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) 等公開 skill 倉庫。

本倉庫與 Zotero、PDFMathTranslate、BabelDOC、Greensock 或 Obsidian 均無隸屬關係。

### 5.2 License

AGPL-3.0。詳見 [`LICENSE`](../LICENSE)。
