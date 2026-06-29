#!/usr/bin/env python3
"""Prompt templates for Zotero Translate batch agents."""

from __future__ import annotations


def term_extraction_prompt(target_language: str) -> str:
    return f"""# Term Extraction Batch

Extract key terms from the assigned source text and translate them into {target_language}.

Output JSONL only, one object per term:

```json
{{"source":"<source term>","target":"<target term>","tgt_lng":"{target_language}","notes":""}}
```

Rules:

- Prefer a cheap, low-latency model for this subagent unless the parent agent explicitly selected another model or quality failures require escalation.
- Produce term targets yourself from the assigned JSONL and context pack.
- Do not call third-party translation APIs, online translators, local MT/translation libraries, browser/search tools, pdf2zh/BabelDOC translation modes, or another agent/process to generate translated text.
- Include domain-specific nouns or noun phrases, named methods, datasets, metrics, and named entities that are essential to the paper.
- Use minimal terms, not full sentences or long clauses.
- Do not extract math variables, formulas, citation markers, URLs, DOI strings, or generic words.
- Extract a source term once in its first clear form.
- Prefer established academic translations; omit uncertain terms instead of guessing.
"""


def translation_batch_prompt(target_language: str) -> str:
    return f"""# Translation Batch

Translate the assigned JSONL segments into {target_language}.

Output JSONL only, one object per input segment:

```json
{{"id":"<same id>","source":"<same source text>","target":"<translated text>","notes":""}}
```

Rules:

- Prefer a cheap, low-latency model for this subagent unless the parent agent explicitly selected another model or validation/quality failures require escalation.
- Produce segment targets yourself from the assigned JSONL, context pack, and glossary.
- Do not call third-party translation APIs, online translators, local MT/translation libraries, browser/search tools, pdf2zh/BabelDOC translation modes, or another agent/process to generate translated text.
- Preserve `id` and `source` exactly.
- Preserve protected tokens, math, citations, URLs, DOIs, arXiv IDs, XML-like tags, and rich-text tags exactly.
- Use glossary target terms exactly when the source term appears.
- Put only translated text in `target`; do not add explanations, labels, Markdown fences, or summaries.
"""


def batch_glossary_text(terms: list[dict]) -> str:
    lines = ["# Batch Glossary", "", "Use these mappings exactly when they appear in this batch.", ""]
    lines.extend(f"- {term['source']} => {term['target']}" for term in terms)
    return "\n".join(lines) + "\n"
