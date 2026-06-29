# Zotero Attachment Import

Attach rendered PDFs with the bundled Zotero Translate Bridge after the render phase has written `finalPdfs` into `run_manifest.json`.

The bridge is intentionally narrow: it exposes only `health`, `attach`, and `verify` on Zotero's local HTTP server, protected by a generated local token. It does not provide arbitrary JavaScript execution.

## Ensure Bridge

```bash
python "$skillDir/scripts/ensure_zotero_bridge.py" --ensure
```

`--ensure` is the normal path. It probes the already loaded bridge, compares the loaded version with the bundled manifest, and if missing or outdated builds the XPI, copies it into the Zotero profile `extensions` directory, clears add-on scan caches, restarts Zotero, imports the per-profile token, and waits for `health`.

For release packaging or inspection only, build an XPI without installing it:

```bash
python "$skillDir/scripts/ensure_zotero_bridge.py" \
  --build-only
```

The script writes runtime-only files under `skills/zotero-translate/.runtime/zotero-translate-bridge/`:

- `zotero-translate-bridge.xpi`
- `bridge_config.json`
- `build/`

These files contain the generated local token and must stay out of git.

If `--ensure` fails to load the endpoint after restart, do not attach or clean artifacts. Report the script JSON/stdout/stderr and inspect Zotero add-on state or logs before retrying. Use Zotero's Add-ons UI only as an explicit manual fallback requested by the user.

## Attach And Verify

Attach every final PDF listed in `run_manifest.json`. Prefer the numeric parent item ID from the selected Zotero regular item:

```bash
python "$skillDir/scripts/attach_with_bridge.py" \
  --run-dir "<run-dir>" \
  --parent-item-id "<zotero-parent-item-id>"
```

If only the item key is available, pass both key and library ID:

```bash
python "$skillDir/scripts/attach_with_bridge.py" \
  --run-dir "<run-dir>" \
  --parent-key "<zotero-parent-key>" \
  --library-id "<zotero-library-id>"
```

`attach_with_bridge.py` runs `ensure_zotero_bridge.py --ensure` by default unless `--no-auto-install-bridge` or a manual `--token` is passed. It then calls bridge `health`, imports each PDF through `Zotero.Attachments.importFromFile`, calls `verify`, and writes `attached`, `attachedAt`, `attachmentVerification`, and bridge ensure details back into the run manifest.

## Failure Handling

- If `--ensure` returns `unauthorized`, rerun it once; the script re-imports the per-profile token written by the bridge after restart.
- If `--ensure` remains `404 No endpoint found` or exits nonzero, Zotero did not register the bridge. Do not clean artifacts; inspect Zotero add-on state/logs and retry automatic install before considering a user-confirmed manual fallback.
- If attach returns `Parent Zotero regular item not found`, re-identify the selected parent item and retry with its regular-item ID.
- If attach returns `PDF does not exist`, rerun render or inspect `finalPdfs` in `run_manifest.json`.
- If verification misses a newly attached ID, do not clean artifacts; rerun `attach_with_bridge.py` and inspect the bridge response.

## Cleanup

After bridge verification succeeds, clean intermediate run artifacts unless the user asked to keep them:

```bash
python "$skillDir/scripts/cleanup_artifacts.py" \
  --run-dir "<run-dir>" \
  --confirm-attached
```

This removes the run workspace only. It does not remove the skill-local runtime or BabelDOC asset cache.
