<div align="center">
  <img src="../assets/zotero-translate-hero.png" alt="Zotero Translate Skill hero banner" width="100%">
</div>

<div align="center">

# Zotero Translate Skill

[English](../README.md) | [简体中文](README_zh-CN.md) | [繁體中文](README_zh-TR.md) | 日本語 | [한국어](README_ko-KR.md)

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](../LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-2ea44f)
![Translation](https://img.shields.io/badge/translation-api--first-orange)
![Setup](https://img.shields.io/badge/setup-install%20skill%20only-7C3AED)
![Zotero](https://img.shields.io/badge/Zotero-PDF%20attachments-BD1F2D)

<p>
  <strong>skill をインストール。論文を翻訳。レイアウトを保持。</strong>
</p>

<p>
  pdf2zh と BabelDOC を利用する agent-native な Zotero PDF 翻訳ワークフロー。<br>
  添付ファイルを書き戻す時に、最小限のローカル Zotero bridge を作成します。
</p>

[インストール](#31-installation) · [クイックスタート](#32-quick-start) · [CLI 使用方法](#35-direct-cli-usage) · [技術詳細](#4-technical-details) · [トラブルシューティング](#47-troubleshooting)

</div>

## 1. これは何？

Zotero Translate Skill は、PDF のレイアウトを保ったまま読みたい学術論文向けの翻訳ワークフローです。Zotero の PDF 添付ファイルから実際のテキストセグメントを収集し、利用可能な場合は設定済みの OpenAI-compatible API で翻訳し、最終 PDF をレンダリングして同じ Zotero 親アイテムへ添付します。

通常の一回きりの PDF 翻訳プロンプトとは異なり、この skill は決定的な run manifest を保持し、壊れやすい処理を `pdf2zh-next` / BabelDOC に任せます。対象はセグメンテーション、プレースホルダー保護、数式とレイアウト処理、最終 PDF レンダリングです。API が設定されていない、または到達できない場合は、用語抽出、バッチ翻訳、レンダリング前検証を含む agent-native バッチワークフローへフォールバックします。

<p align="center">
  <img src="../assets/current-chat-pipeline.svg" alt="Zotero Translate workflow pipeline" width="92%">
</p>

### 1.1 機能

| 機能 | 説明 |
| --- | --- |
| API-first 翻訳 | prompt またはローカル設定で `base_url` / `api_port`、`api_key`、`model` が提供されると、OpenAI-compatible `/v1/chat/completions` を直接呼び出します。 |
| Agent-native fallback | API が利用できない場合、現在の agent が JSONL 翻訳バッチを分配し、レンダリング前にマージ結果を検証します。 |
| 自動用語サポート | 用語抽出バッチを作成し、`source,target,tgt_lng` glossary CSV をマージし、該当する用語を翻訳プロンプトへ注入します。 |
| レイアウト保持レンダリング | PDF セグメンテーション、プレースホルダー保護、数式/レイアウト処理、レンダリングは `pdf2zh-next` / BabelDOC が担当します。 |
| ローカル Zotero bridge | Zotero 7-9 互換の最小 XPI で添付ファイルを書き戻し、token 保護されたローカル endpoint で PDF を追加します。 |
| 自己完結ランタイム | 初回実行時に skill ディレクトリ内へ Python venv を作成し、BabelDOC アセットを準備します。 |
| Zotero-native 出力 | 最終 PDF は元の Zotero 親アイテムへ添付されます。 |
| 明示的な対象言語 | prompt に対象言語がない場合、agent は先に確認します。 |
| デフォルトは PDF 全体 | ページ範囲が指定されない限り、PDF 全体を翻訳します。 |
| デフォルトは mono + dual | 出力モードが指定されない限り、翻訳のみ PDF と二言語 PDF の両方を生成します。 |
| Python-only scripts | Python エントリポイントは Windows、macOS、Linux をサポートします。PowerShell wrapper は不要です。 |
| Manifest ベースのクリーンアップ | Zotero 添付が確認された後にだけ一時ファイルを削除します。 |

### 1.2 出力プレビュー

<p align="center">
  <img src="../assets/output-modes.svg" alt="Mono and dual output modes" width="86%">
</p>

このリポジトリには現在、生成された SVG 図が含まれています。GitHub ランディングページを強くするには、実際のワークフロー画面を追加してください。

- `assets/preview-zotero-attachments.png`: 元 PDF、mono 出力、dual 出力が表示された Zotero 親アイテム。
- `assets/preview-mono-dual-pages.png`: 同じ論文の mono / dual ページを並べたプレビュー。
- `assets/preview-agent-run.png`: collect、API または fallback 翻訳、render、attach 後の agent 会話。

## 2. 最近の更新

- **API-first route**: `configure-api` と `api-translate` は、認証情報とモデルが利用可能な場合に OpenAI-compatible chat completion API を使います。
- **Agent-batch fallback**: API が利用できない場合、skill は JSONL バッチを作成して agent 翻訳へ分配します。デフォルトの同時稼働上限は `16` です。
- **用語抽出**: 用語バッチと `merge_glossary.py` は、プロンプト注入に使う BabelDOC-compatible な `source,target,tgt_lng` glossary CSV を作成します。
- **ローカル Zotero bridge**: release XPI を Zotero Add-ons に一度インストールします。`ensure_zotero_bridge.py --probe` がローカル token を取り込み、bridge が読み込まれた後に `attach_with_bridge.py` が token 保護された `health` / `attach` / `verify` endpoint で PDF を書き戻します。
- **検証の強化**: `validate_translations.py` は欠落、重複、不明 ID、source/id 不一致、空の target、protected token、rich-text tag の順序、参考文献らしいセグメントの翻訳リスクを確認します。
- **Python-only workflow**: 現在メンテナンスされている入口は Python スクリプトだけで、PowerShell wrapper は不要です。

## 3. 使い方

<a id="31-installation"></a>

### 3.1 インストール

#### Option A: Skills CLI

agent 環境が Skills CLI をサポートしている場合、GitHub から直接インストールできます。

```bash
npx skills add https://github.com/Chael-Chael/zotero-translate-skill
```

インストール後、agent client を再起動して利用可能な skills を再読み込みしてください。

#### Option B: Codex への手動インストール

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

コピー後、Codex を再起動してください。

この選択肢を示しているのは、Codex に一般的なローカル skill ディレクトリがあるためです。ワークフロー自体は Codex 専用ではありません。

#### Option C: その他の Agent

[`skills/zotero-translate`](../skills/zotero-translate) を agent が使う skill ディレクトリへコピーするか、agent に `skills/zotero-translate/SKILL.md` を直接参照させてください。

決定的なワークフローは Python ベースで移植可能です。互換 agent に必要なのは、skill 指示を読み、本地 Python スクリプトを実行し、connector または同等のローカル自動化で Zotero Desktop にアクセスすることだけです。skill は最終添付ファイル書き戻し用の最小 Zotero bridge XPI を作成し、Zotero が読み込まない場合は明確に報告します。

#### Zotero Bridge XPI

添付ファイルを書き戻す前に、Zotero に bridge を一度インストールします。

1. [`zotero-translate-bridge.xpi`](https://github.com/Chael-Chael/zotero-translate-skill/raw/main/assets/zotero-translate-bridge.xpi) をダウンロードします。
2. Zotero で `Tools -> Add-ons` を開きます。
3. gear icon から `Install Add-on From File...` を選び、この XPI を選択します。
4. Zotero を再起動します。
5. probe を一度実行して、ローカル bridge token を script に取り込みます。

```bash
python skills/zotero-translate/scripts/ensure_zotero_bridge.py --probe
```

この XPI に共有 token は含まれず、Zotero の公式プラグイン互換形式に合わせて Zotero `6.999` から `9.0.*` までの互換性を宣言します。bridge は初回起動時に、ユーザーごとの `zotero-translate-bridge.json` を Zotero profile に書き込みます。

<a id="32-quick-start"></a>

### 3.2 クイックスタート

Zotero を開き、PDF 添付を持つ論文アイテムを選択してから agent に伝えます。

```text
Use $zotero-translate to translate the selected Zotero PDF into Japanese.
```

API が設定済みの場合のデフォルト動作:

1. PDF 全体を安定したテキストセグメントとして収集します。
2. 設定済みの OpenAI-compatible API でセグメントを翻訳します。
3. 翻訳 JSONL を検証します。
4. mono と dual の PDF をレンダリングします。
5. 2 つの PDF を元の Zotero 親アイテムへ添付します。
6. 添付を確認します。
7. 一時 run directory をクリーンアップします。

API がない場合の fallback 動作:

1. auto glossary が無効でない限り、用語抽出バッチを作成します。
2. agent が生成した用語結果を `auto_glossary.csv` へマージします。
3. 一致した用語を含む翻訳バッチを作成します。
4. デフォルトで最大 `16` の翻訳 agent を同時に分配します。
5. 検証、レンダリング、添付、確認、クリーンアップを行います。

prompt に対象言語がない場合、agent は collect phase の前に対象言語を確認する必要があります。

### 3.3 Prompt 例

| Prompt | 結果 |
| --- | --- |
| `Use $zotero-translate to translate the selected Zotero PDF into Spanish.` | PDF 全体。API 設定時は API-first route。mono + dual 出力。 |
| `Use $zotero-translate to translate the selected Zotero PDF.` | 先に対象言語を確認します。 |
| `Use API port 8000, key sk-..., model qwen-plus.` | ローカル API 設定を保存し、`api-translate` を優先します。 |
| `Use temperature 0.1 and qps 2.` | `api-translate` で API 実行パラメータを渡します。 |
| `Translate only pages 1-3, mono only.` | `--pages "1-3"` と `--output-mode mono` を渡します。 |
| `Make a bilingual PDF only.` | `--output-mode dual` を使います。 |
| `Use 8 parallel agents.` | fallback バッチルートで `--max-parallel-agents 8` を使います。 |
| `No auto glossary.` | fallback 翻訳バッチ前の用語抽出をスキップします。 |
| `Use this glossary CSV: /path/terms.csv.` | `source,target,tgt_lng` 列を持つユーザー glossary を追加します。 |
| `Force agent route.` | API 翻訳をスキップし、agent-batch route を使います。 |
| `Translate this paper but keep artifacts for debugging.` | run directory を残し、クリーンアップをスキップします。 |

### 3.4 要件

| 要件 | 理由 |
| --- | --- |
| Python 3.10+ | skill-local venv を作成し helper scripts を実行します。 |
| Zotero Desktop | ソース PDF と最終添付ファイルは Zotero にあります。 |
| Zotero 対応 agent connector | 選択された親アイテムと元 PDF を特定します。 |
| 初回セットアップ時のインターネット | `pdf2zh-next`、`PyMuPDF`、BabelDOC アセットをインストールします。 |
| OpenAI-compatible API | 任意ですが優先されます。base URL または port、API key、model が必要です。 |
| バッチ実行できる agent | API 翻訳が利用不可または無効化された場合の fallback route でのみ必要です。 |

`pdf2zh`、BabelDOC、Zotero 翻訳プラグインを事前にインストールする必要はありません。skill は自身のディレクトリにランタイムを準備し、初回添付ファイル書き戻し時に bridge XPI を作成します。

初回実行で作成されるもの:

```text
skills/zotero-translate/.runtime/venv
~/.cache/babeldoc
```

任意の API 設定は以下に保存されます。

```text
skills/zotero-translate/.runtime/api_config.json
```

Bridge build artifacts and the local token are stored in:

```text
skills/zotero-translate/.runtime/zotero-translate-bridge/
```

これらのパスは意図的に version control から除外されています。

<a id="35-direct-cli-usage"></a>

### 3.5 直接 CLI 使用

通常は agent 経由で使いますが、決定的な phase は直接実行できます。

OpenAI-compatible API を一度設定:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase configure-api \
  --api-port 8000 \
  --api-key "sk-..." \
  --api-model "model-name"
```

セグメント収集:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --input-pdf "/path/to/paper.pdf" \
  --lang-out "ja"
```

指定ページだけ収集し mono 出力を要求:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --input-pdf "/path/to/paper.pdf" \
  --lang-out "ja" \
  --pages "1-3" \
  --output-mode mono
```

API route で翻訳:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase api-translate \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

`api-translate` が `api_unavailable` を返した場合、fallback batch route を実行:

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

最終 PDF をレンダリング:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase render \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

bridge をインストールし、レンダリング済み PDF を添付:

```bash
python skills/zotero-translate/scripts/ensure_zotero_bridge.py --probe

python skills/zotero-translate/scripts/attach_with_bridge.py \
  --run-dir "/tmp/zotero-translate-runs/<run-id>" \
  --parent-item-id "<zotero-parent-item-id>"
```

検証済み run をクリーンアップ:

```bash
python skills/zotero-translate/scripts/cleanup_artifacts.py \
  --run-dir "/tmp/zotero-translate-runs/<run-id>" \
  --confirm-attached
```

現在メンテナンスされているエントリポイントは [`skills/zotero-translate/scripts`](../skills/zotero-translate/scripts) 配下の Python スクリプトです。

<a id="4-technical-details"></a>

## 4. 技術詳細

### 4.1 翻訳ルート

優先ルートは API-first です。

```text
collect -> api-translate -> validate -> render -> attach -> cleanup
```

collect phase は `collect_segments.py` を `pdf2zh` CLI translator として使います。実際の source segment を `segments.jsonl` に記録し、collect pass が進むように原文を返します。API route は `api_translate_segments.py` で OpenAI-compatible chat-completions endpoint を呼び出し、`api_results.jsonl` を書きます。validation はそれらを `translations.jsonl` へマージします。

API が未設定、到達不能、または明示的にスキップされた場合の fallback route:

```text
collect -> term batches -> term agents -> merge glossary -> translation batches -> translation agents -> validate -> render -> attach -> cleanup
```

fallback route は `build_term_batches.py`、`merge_glossary.py`、`build_batches.py` で決定的な JSONL work units を準備します。render phase は常に `lookup_translator.py` を使い、安定した source hash で検証済み翻訳を探します。

### 4.2 Run Directory

各 run はプラットフォームの一時ディレクトリ配下に管理ディレクトリを作成します。

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

run directory には source text、translated text、glossary terms が含まれることがあります。デバッグが必要でない限り、Zotero 添付成功後に削除してください。

### 4.3 出力モード

| Output mode | pdf2zh flags | 結果 |
| --- | --- | --- |
| `both` | default | 翻訳 PDF + 二言語 PDF。 |
| `mono` | `--no-dual` | 翻訳のみ PDF。 |
| `dual` | `--no-mono` | 二言語 PDF。 |

### 4.4 ランタイム選択

`run_pdf2zh.py` は必要に応じて `<skill-dir>/.runtime/venv` を作成します。

選択順:

1. `--python-exe` が指定されていればそれを使います。
2. `run_pdf2zh.py` を起動した Python interpreter。
3. 利用可能な場合は Codex bundled Python runtime。
4. Windows では `python3`、`python`、`py -3` の順に試します。

### 4.5 プライバシーモデル

この skill は、抽出された PDF セグメントをユーザーまたはローカル設定が選んだルートにだけ送信します。

重要な境界:

- API route: run で使われる Zotero metadata、PDF text segments、glossary terms、prompt instructions は設定された OpenAI-compatible endpoint へ送信されます。
- API credentials は `skills/zotero-translate/.runtime/api_config.json` にのみ保存され、git からは無視されます。run manifests は plaintext API keys を保存しません。
- Agent-batch fallback: PDF セグメントと用語は現在の agent と、それが生成する batch agents に見えます。
- Zotero bridge: Zotero 内には token 保護されたローカル `health`、`attach`、`verify` endpoint だけがインストールされます。任意の JavaScript 実行は公開しません。
- Context packs は一般的なローカルパス欄位をデフォルトで除去します。
- 一時 run directory は cleanup まで source text と translated text を含む場合があります。

### 4.6 リポジトリ構成

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

### 4.7 トラブルシューティング

| 症状 | 確認事項 |
| --- | --- |
| `No usable Python 3 executable was found` | Python 3.10+ をインストールするか、`--python-exe /path/to/python` を渡してください。 |
| ランタイム設定が遅い | 初回実行では `pdf2zh-next`、`PyMuPDF`、フォント、BabelDOC アセットをインストールします。 |
| `api-translate` が `api_unavailable` を返す | 到達可能な base URL または port、API key、model で `configure-api` を実行してください。または agent-batch fallback route を使ってください。 |
| API 出力が検証に失敗する | temperature を下げ、より厳格な `--api-extra-instruction` を追加するか、失敗セグメントを fallback batches に回してください。 |
| Render が missing segments を報告する | `missing_segments.jsonl` を開き、該当 id を翻訳して追加または再検証し、render を再実行してください。 |
| Zotero 添付が失敗する | Zotero Add-ons で release XPI をインストールして Zotero を再起動し、`ensure_zotero_bridge.py --probe` を実行してから、正しい親アイテム ID で `attach_with_bridge.py` を再試行してください。 |
| ディスク使用量が増える | 完了した run directories を削除してください。`.runtime/venv` と `~/.cache/babeldoc` は次回以降の高速化のため残せます。 |

## 5. プロジェクト情報

### 5.1 謝辞

この skill は [PDFMathTranslate / PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) と、その `pdf2zh` / BabelDOC エコシステムが開拓した layout-preserving PDF ワークフローを基盤にしています。README の構成は [greensock/gsap-skills](https://github.com/greensock/gsap-skills) や [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) などの公開 skill リポジトリも参考にしています。

このリポジトリは Zotero、PDFMathTranslate、BabelDOC、Greensock、Obsidian とは提携していません。

### 5.2 License

AGPL-3.0。詳細は [`LICENSE`](../LICENSE) を参照してください。
