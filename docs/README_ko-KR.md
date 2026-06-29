<div align="center">
  <img src="../assets/zotero-translate-hero.png" alt="Zotero Translate Skill hero banner" width="100%">
</div>

<div align="center">

# Zotero Translate Skill

[English](../README.md) | [简体中文](README_zh-CN.md) | [繁體中文](README_zh-TR.md) | [日本語](README_ja-JP.md) | 한국어

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](../LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-2ea44f)
![Translation](https://img.shields.io/badge/translation-api--first-orange)
![Setup](https://img.shields.io/badge/setup-install%20skill%20only-7C3AED)
![Zotero](https://img.shields.io/badge/Zotero-PDF%20attachments-BD1F2D)

<p>
  <strong>skill 하나를 설치하세요. 논문을 번역하세요. 레이아웃은 그대로 유지하세요.</strong>
</p>

<p>
  pdf2zh와 BabelDOC 기반의 agent-native Zotero PDF 번역 워크플로입니다.<br>
  첨부파일을 다시 쓸 때 최소 로컬 Zotero bridge를 만듭니다.
</p>

[설치](#31-installation) · [빠른 시작](#32-quick-start) · [CLI 사용법](#35-direct-cli-usage) · [기술 세부사항](#4-technical-details) · [문제 해결](#47-troubleshooting)

</div>

## 1. 무엇인가요?

Zotero Translate Skill은 PDF 레이아웃을 유지해야 하는 학술 읽기 워크플로를 위한 도구입니다. Zotero PDF 첨부파일에서 실제 텍스트 세그먼트를 수집하고, 사용 가능한 경우 설정된 OpenAI-compatible API로 번역한 뒤, 최종 PDF를 렌더링하여 같은 Zotero 상위 항목에 다시 첨부합니다.

일반적인 일회성 PDF 번역 프롬프트와 달리, 이 skill은 결정적인 run manifest를 유지하고 취약한 작업을 `pdf2zh-next` / BabelDOC에 맡깁니다. 여기에는 세그먼트 분할, placeholder 보존, 수식과 레이아웃 처리, 최종 PDF 렌더링이 포함됩니다. API가 설정되어 있지 않거나 접근할 수 없는 경우에는 용어 추출, 배치 번역, 렌더링 전 검증을 포함한 agent-native 배치 워크플로로 fallback합니다.

<p align="center">
  <img src="../assets/current-chat-pipeline.svg" alt="Zotero Translate workflow pipeline" width="92%">
</p>

### 1.1 기능

| 기능 | 설명 |
| --- | --- |
| API-first 번역 | prompt 또는 로컬 설정에 `base_url` / `api_port`, `api_key`, `model`이 있으면 OpenAI-compatible `/v1/chat/completions`를 직접 호출합니다. |
| Agent-native fallback | API를 사용할 수 없으면 현재 agent가 JSONL 번역 배치를 분배하고, 렌더링 전에 병합 결과를 검증합니다. |
| 자동 용어 지원 | 용어 추출 배치를 만들고 `source,target,tgt_lng` glossary CSV를 병합하며, 매칭된 용어를 번역 프롬프트에 주입합니다. |
| 레이아웃 보존 렌더링 | PDF 세그먼트 분할, placeholder 보존, 수식/레이아웃 처리, 렌더링은 `pdf2zh-next` / BabelDOC가 담당합니다. |
| 로컬 Zotero bridge | Zotero 7-9 호환 최소 XPI로 첨부파일을 다시 쓰고 token으로 보호되는 로컬 endpoint를 통해 PDF를 추가합니다. |
| 자체 포함 런타임 | 첫 실행 시 skill 디렉터리 아래에 Python venv를 만들고 BabelDOC asset을 준비합니다. |
| Zotero-native 출력 | 최종 PDF가 원래 Zotero 상위 항목에 첨부됩니다. |
| 명시적 대상 언어 | prompt에 대상 언어가 없으면 agent가 먼저 확인해야 합니다. |
| 기본값은 전체 PDF | 사용자가 페이지 범위를 지정하지 않으면 전체 PDF를 번역합니다. |
| 기본값은 mono + dual | 출력 모드를 지정하지 않으면 번역 전용 PDF와 bilingual PDF를 모두 생성합니다. |
| Python-only scripts | Python entrypoint는 Windows, macOS, Linux를 지원합니다. PowerShell wrapper는 더 이상 필요하지 않습니다. |
| Manifest 기반 정리 | Zotero 첨부가 확인된 뒤에만 임시 파일을 삭제합니다. |

### 1.2 출력 미리보기

<p align="center">
  <img src="../assets/output-modes.svg" alt="Mono and dual output modes" width="86%">
</p>

현재 저장소에는 생성된 SVG 다이어그램이 포함되어 있습니다. GitHub 랜딩 페이지를 더 명확하게 만들려면 실제 워크플로 스크린샷을 추가하세요.

- `assets/preview-zotero-attachments.png`: 원본 PDF, mono 출력, dual 출력이 보이는 Zotero 상위 항목.
- `assets/preview-mono-dual-pages.png`: 같은 논문의 mono / dual 페이지를 나란히 보여주는 미리보기.
- `assets/preview-agent-run.png`: collect, API 또는 fallback 번역, render, attach 이후의 agent 대화.

## 2. 최근 업데이트

- **API-first route**: `configure-api`와 `api-translate`는 인증 정보와 모델이 있을 때 OpenAI-compatible chat completion API를 사용합니다.
- **Agent-batch fallback**: API route를 사용할 수 없으면 skill이 JSONL 배치를 만들고 agent 번역에 병렬로 분배합니다. 기본 active-agent 상한은 `16`입니다.
- **용어 추출**: 용어 배치와 `merge_glossary.py`는 프롬프트 주입에 사용할 BabelDOC-compatible `source,target,tgt_lng` glossary CSV를 만듭니다.
- **로컬 Zotero bridge**: `ensure_zotero_bridge.py --ensure`가 XPI를 Zotero profile에 자동 설치하거나 업데이트하고, Zotero를 재시작해 로컬 token을 가져옵니다. `attach_with_bridge.py`는 token으로 보호되는 `health` / `attach` / `verify` endpoint를 통해 PDF를 다시 씁니다.
- **강화된 검증**: `validate_translations.py`는 누락, 중복, 알 수 없는 ID, source/id 불일치, 빈 target, protected token, rich-text tag 순서, 참고문헌으로 보이는 세그먼트가 번역되는 위험을 검사합니다.
- **Python-only workflow**: 현재 유지되는 entrypoint는 모두 Python 스크립트이며 PowerShell wrapper는 필요 없습니다.

## 3. 사용

<a id="31-installation"></a>

### 3.1 설치

#### Option A: Skills CLI

agent 환경이 Skills CLI를 지원한다면 GitHub에서 직접 설치할 수 있습니다.

```bash
npx skills add https://github.com/Chael-Chael/zotero-translate-skill
```

설치 후 agent client를 재시작하여 사용 가능한 skills를 다시 로드하세요.

#### Option B: Codex 수동 설치

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

복사 후 Codex를 재시작하세요.

이 옵션은 Codex에 일반적인 로컬 skill 디렉터리가 있기 때문에 표시합니다. 워크플로 자체는 Codex 전용이 아닙니다.

#### Option C: 다른 Agent

[`skills/zotero-translate`](../skills/zotero-translate)를 agent가 사용하는 skill 디렉터리에 복사하거나, agent가 `skills/zotero-translate/SKILL.md`를 직접 읽도록 하세요.

결정적인 워크플로는 Python 기반이며 이식 가능합니다. 호환 agent는 skill 지침을 읽고, 로컬 Python 스크립트를 실행하고, connector 또는 동등한 로컬 자동화를 통해 Zotero Desktop에 접근할 수 있으면 됩니다. skill은 최종 첨부파일 쓰기용 최소 Zotero bridge XPI를 만들고, Zotero가 이를 로드하지 않으면 명확히 보고합니다.

#### Zotero Bridge XPI

첨부파일을 다시 써야 할 때 agent가 bridge를 자동으로 설치합니다.

```bash
python skills/zotero-translate/scripts/ensure_zotero_bridge.py --ensure
```

`--ensure`는 로드된 bridge를 probe하고 bundled manifest 버전과 비교합니다. 없거나 오래된 경우 XPI를 만들고 Zotero profile에 복사하며 add-on scan cache를 지우고 Zotero를 재시작한 뒤 token으로 보호되는 `health` endpoint를 기다립니다. 이 XPI에는 공유 token이 들어 있지 않으며 Zotero `6.999`부터 `10.99.99`까지의 호환성을 선언합니다. bridge는 첫 시작 시 사용자별 `zotero-translate-bridge.json`을 Zotero profile에 씁니다.

<a id="32-quick-start"></a>

### 3.2 빠른 시작

Zotero를 열고 PDF 첨부파일이 있는 논문 항목을 선택한 뒤 agent에게 말하세요.

```text
Use $zotero-translate to translate the selected Zotero PDF into Japanese.
```

API가 설정되어 있을 때의 기본 동작:

1. 전체 PDF를 안정적인 텍스트 세그먼트로 수집합니다.
2. 설정된 OpenAI-compatible API로 세그먼트를 번역합니다.
3. 번역 JSONL을 검증합니다.
4. mono와 dual PDF를 렌더링합니다.
5. 두 PDF를 원래 Zotero 상위 항목에 첨부합니다.
6. 첨부를 확인합니다.
7. 임시 run directory를 정리합니다.

API가 없을 때의 fallback 동작:

1. auto glossary가 비활성화되어 있지 않으면 용어 추출 배치를 만듭니다.
2. agent가 만든 용어 결과를 `auto_glossary.csv`로 병합합니다.
3. 매칭된 용어를 포함해 번역 배치를 만듭니다.
4. 기본값으로 최대 `16`개의 active translation agents를 분배합니다.
5. 검증, 렌더링, 첨부, 확인, 정리를 수행합니다.

prompt에 대상 언어가 없으면 agent는 collect phase를 시작하기 전에 대상 언어를 먼저 물어봐야 합니다.

### 3.3 Prompt 예시

| Prompt | 결과 |
| --- | --- |
| `Use $zotero-translate to translate the selected Zotero PDF into Spanish.` | 전체 PDF. API가 설정되어 있으면 API-first route. mono + dual 출력. |
| `Use $zotero-translate to translate the selected Zotero PDF.` | 먼저 대상 언어를 묻습니다. |
| `Use API port 8000, key sk-..., model qwen-plus.` | 로컬 API 설정을 저장하고 `api-translate`를 우선 사용합니다. |
| `Use temperature 0.1 and qps 2.` | `api-translate` 단계에서 API 실행 파라미터를 전달합니다. |
| `Translate only pages 1-3, mono only.` | `--pages "1-3"`와 `--output-mode mono`를 전달합니다. |
| `Make a bilingual PDF only.` | `--output-mode dual`을 사용합니다. |
| `Use 8 parallel agents.` | fallback 배치 route에서 `--max-parallel-agents 8`을 사용합니다. |
| `No auto glossary.` | fallback 번역 배치 전에 용어 추출을 건너뜁니다. |
| `Use this glossary CSV: /path/terms.csv.` | `source,target,tgt_lng` 열을 가진 사용자 glossary를 추가합니다. |
| `Force agent route.` | API 번역을 건너뛰고 agent-batch route를 사용합니다. |
| `Translate this paper but keep artifacts for debugging.` | run directory를 유지하고 정리를 건너뜁니다. |

### 3.4 요구사항

| 요구사항 | 필요한 이유 |
| --- | --- |
| Python 3.10+ | skill-local venv를 만들고 helper scripts를 실행합니다. |
| Zotero Desktop | 원본 PDF와 최종 첨부파일이 Zotero에 있습니다. |
| Zotero-capable agent connector | 선택된 상위 항목과 원본 PDF를 식별합니다. |
| 첫 런타임 설정 시 인터넷 | `pdf2zh-next`, `PyMuPDF`, BabelDOC assets를 설치합니다. |
| OpenAI-compatible API | 선택 사항이지만 우선 사용됩니다. base URL 또는 port, API key, model이 필요합니다. |
| 배치 실행 가능한 agent | API 번역이 불가능하거나 비활성화된 경우 fallback route에서만 필요합니다. |

`pdf2zh`, BabelDOC, Zotero 번역 플러그인을 미리 설치할 필요는 없습니다. skill이 자체 디렉터리 아래에 런타임을 준비하고, 첫 첨부파일 쓰기 시 bridge XPI를 만듭니다.

첫 실행 시 생성되는 항목:

```text
skills/zotero-translate/.runtime/venv
~/.cache/babeldoc
```

선택적 API 설정은 여기에 저장됩니다.

```text
skills/zotero-translate/.runtime/api_config.json
```

Bridge build artifacts and the local token are stored in:

```text
skills/zotero-translate/.runtime/zotero-translate-bridge/
```

이 경로들은 의도적으로 version control에서 제외됩니다.

<a id="35-direct-cli-usage"></a>

### 3.5 직접 CLI 사용

일반적으로 agent를 통해 사용하지만, 결정적인 phase는 직접 실행할 수 있습니다.

OpenAI-compatible API를 한 번 설정:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase configure-api \
  --api-port 8000 \
  --api-key "sk-..." \
  --api-model "model-name"
```

세그먼트 수집:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --input-pdf "/path/to/paper.pdf" \
  --lang-out "ja"
```

지정한 페이지만 수집하고 mono 출력 요청:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --input-pdf "/path/to/paper.pdf" \
  --lang-out "ja" \
  --pages "1-3" \
  --output-mode mono
```

API route로 번역:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase api-translate \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

`api-translate`가 `api_unavailable`을 반환하면 fallback batch route 실행:

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

최종 PDF 렌더링:

```bash
python skills/zotero-translate/scripts/run_pdf2zh.py \
  --phase render \
  --run-dir "/tmp/zotero-translate-runs/<run-id>"
```

bridge를 자동으로 확보하고 렌더링된 PDF 첨부:

```bash
python skills/zotero-translate/scripts/ensure_zotero_bridge.py --ensure

python skills/zotero-translate/scripts/attach_with_bridge.py \
  --run-dir "/tmp/zotero-translate-runs/<run-id>" \
  --parent-item-id "<zotero-parent-item-id>"
```

검증된 run 정리:

```bash
python skills/zotero-translate/scripts/cleanup_artifacts.py \
  --run-dir "/tmp/zotero-translate-runs/<run-id>" \
  --confirm-attached
```

현재 유지되는 entrypoint는 모두 [`skills/zotero-translate/scripts`](../skills/zotero-translate/scripts) 아래의 Python 스크립트입니다.

<a id="4-technical-details"></a>

## 4. 기술 세부사항

### 4.1 번역 route

우선 route는 API-first입니다.

```text
collect -> api-translate -> validate -> render -> attach -> cleanup
```

collect phase는 `collect_segments.py`를 `pdf2zh` CLI translator로 사용합니다. 실제 source segment를 `segments.jsonl`에 기록하고, collect pass가 계속 진행되도록 원문을 반환합니다. API route는 `api_translate_segments.py`로 OpenAI-compatible chat-completions endpoint를 호출하고 `api_results.jsonl`을 작성합니다. validation은 이를 `translations.jsonl`로 병합합니다.

API가 설정되지 않았거나, 접근할 수 없거나, 명시적으로 건너뛴 경우 fallback route는 다음과 같습니다.

```text
collect -> term batches -> term agents -> merge glossary -> translation batches -> translation agents -> validate -> render -> attach -> cleanup
```

fallback route는 `build_term_batches.py`, `merge_glossary.py`, `build_batches.py`로 결정적인 JSONL work units를 준비합니다. render phase는 항상 `lookup_translator.py`를 사용해 안정적인 source hash로 검증된 번역을 찾습니다.

### 4.2 Run Directory

각 run은 플랫폼 임시 폴더 아래에 관리되는 디렉터리를 만듭니다.

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

run directory에는 source text, translated text, glossary terms가 포함될 수 있습니다. 디버깅이 필요하지 않다면 Zotero 첨부 성공 후 정리하세요.

### 4.3 출력 모드

| Output mode | pdf2zh flags | 결과 |
| --- | --- | --- |
| `both` | default | 번역 PDF + bilingual PDF. |
| `mono` | `--no-dual` | 번역 전용 PDF. |
| `dual` | `--no-mono` | bilingual PDF. |

### 4.4 런타임 선택

`run_pdf2zh.py`는 필요할 때 `<skill-dir>/.runtime/venv`를 만듭니다.

선택 순서:

1. `--python-exe`가 제공되면 이를 우선 사용합니다.
2. `run_pdf2zh.py`를 실행한 Python interpreter.
3. 사용 가능한 경우 Codex bundled Python runtime.
4. Windows에서는 `python3`, `python`, `py -3` 순서로 시도합니다.

### 4.5 개인정보 및 데이터 경계

이 skill은 추출된 PDF 세그먼트를 사용자 또는 로컬 설정이 선택한 route로만 보냅니다.

중요한 경계:

- API route: run에 사용되는 Zotero metadata, PDF text segments, glossary terms, prompt instructions는 설정된 OpenAI-compatible endpoint로 전송됩니다.
- API credentials는 `skills/zotero-translate/.runtime/api_config.json`에만 저장되며 git에서 무시됩니다. run manifest는 plaintext API keys를 저장하지 않습니다.
- Agent-batch fallback: PDF 세그먼트와 용어는 현재 agent와 해당 agent가 만든 batch agents에 표시됩니다.
- Zotero bridge: Zotero 안에는 token으로 보호되는 로컬 `health`, `attach`, `verify` endpoint만 설치됩니다. 임의 JavaScript 실행은 노출하지 않습니다.
- Context packs는 일반적인 로컬 경로 필드를 기본적으로 제거합니다.
- 임시 run directory는 cleanup 전까지 source text와 translated text를 포함할 수 있습니다.

### 4.6 저장소 구조

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

### 4.7 문제 해결

| 증상 | 확인할 것 |
| --- | --- |
| `No usable Python 3 executable was found` | Python 3.10+를 설치하거나 `--python-exe /path/to/python`을 전달하세요. |
| 런타임 설정이 느림 | 첫 실행에서는 `pdf2zh-next`, `PyMuPDF`, fonts, BabelDOC assets를 설치합니다. |
| `api-translate`가 `api_unavailable`을 반환 | 접근 가능한 base URL 또는 port, API key, model로 `configure-api`를 실행하세요. 또는 agent-batch fallback route를 사용하세요. |
| API 출력이 검증 실패 | temperature를 낮추고 더 엄격한 `--api-extra-instruction`을 추가하거나 실패 세그먼트를 fallback batches로 넘기세요. |
| Render가 missing segments를 보고 | `missing_segments.jsonl`을 열고 나열된 id를 번역해 추가하거나 재검증한 뒤 render를 다시 실행하세요. |
| Zotero 첨부 실패 | `ensure_zotero_bridge.py --ensure`를 실행하고 JSON/stdout/stderr를 확인하세요. ready가 되면 올바른 상위 항목 ID로 `attach_with_bridge.py`를 다시 시도하세요. |
| 디스크 사용량 증가 | 완료된 run directories를 정리하세요. `.runtime/venv`와 `~/.cache/babeldoc`는 다음 실행을 빠르게 하므로 유지할 수 있습니다. |

## 5. 프로젝트 정보

### 5.1 감사의 말

이 skill은 [PDFMathTranslate / PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) 및 그 `pdf2zh` / BabelDOC 생태계가 개척한 layout-preserving PDF 워크플로를 기반으로 합니다. README 구성은 [greensock/gsap-skills](https://github.com/greensock/gsap-skills)와 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) 같은 공개 skill 저장소도 참고했습니다.

이 저장소는 Zotero, PDFMathTranslate, BabelDOC, Greensock, Obsidian과 관련이 없습니다.

### 5.2 License

AGPL-3.0. 자세한 내용은 [`LICENSE`](../LICENSE)를 참고하세요.
