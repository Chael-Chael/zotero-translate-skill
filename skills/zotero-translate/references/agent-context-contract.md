# Current-Chat Context Pack Contract

Use this reference when creating or editing `context_pack.md` for the Zotero Translate current-chat workflow.

## Purpose

`context_pack.md` provides paper-level terminology and style context for the active assistant conversation. It is not sent to a child translator process. The assistant should read it before translating `segments.jsonl`, then write `translations.jsonl`.

## Required Sections

1. Header metadata
   - `context_version`
   - `created_at`
   - `pdf_sha256`
   - `source_language`
   - `target_language`
   - `pdf_file` only; do not include the full local PDF path by default
   - title, authors, year if known

2. Translation instructions
   - Use an academic/scientific tone.
   - Translate into Simplified Chinese by default.
   - Preserve math, citations, URLs, code, rich-text placeholders, and XML-like tags exactly.
   - Return only translated text in each JSONL `target` value.

3. User preferences
   - Preferred terminology.
   - Whether to keep English technical terms in parentheses.
   - Any paper-specific naming choices.

4. Glossary
   - One line per mapping: `source => target`.
   - Include model names, datasets, methods, institutions, and key technical nouns when available.

5. Protected tokens
   - Rich text placeholders such as `<b0>`, `</b0>`, `<i1>`.
   - Formula placeholders, citation brackets, URLs, DOIs, and arXiv IDs.

6. Extracted PDF context
   - Metadata from the PDF.
   - Text from the first pages, abstract, or introduction.
   - Keep this bounded; it is guidance for the active conversation, not source text to translate wholesale.

## Privacy Rule

Do not include local filesystem paths, user names, storage folder names, or credentials in the context pack unless the user explicitly asks for local debugging details. `build_context_pack.py` redacts common Zotero path fields by default.

## Translation Contract

When translating `segments.jsonl`, the active conversation must:

- Translate each `source` field into the target language.
- Preserve each `id` exactly.
- Preserve placeholders and math notation exactly.
- Avoid explanations, Markdown fences, summaries, or extra labels inside `target`.
- Write one JSON object per line to `translations.jsonl`.
