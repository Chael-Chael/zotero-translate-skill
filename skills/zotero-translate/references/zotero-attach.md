# Zotero Attachment Import

Attach rendered PDFs with the bundled Zotero Translate Bridge after the render phase has written `finalPdfs` into `run_manifest.json`.

The bridge is intentionally narrow: it exposes only `health`, `attach`, and `verify` on Zotero's local HTTP server, protected by a generated local token. It does not provide arbitrary JavaScript execution.

## Ensure Bridge

Probe first:

```bash
python "$skillDir/scripts/ensure_zotero_bridge.py" --probe
```

If the bridge is unavailable, build the XPI, place the bridge package into the active Zotero profile, restart Zotero, and wait for the local endpoint:

```bash
python "$skillDir/scripts/ensure_zotero_bridge.py" \
  --install \
  --restart-zotero
```

The script writes runtime-only files under `skills/zotero-translate/.runtime/zotero-translate-bridge/`:

- `zotero-translate-bridge.xpi`
- `bridge_config.json`
- `build/`

These files contain the generated local token and must stay out of git.

If the script returns `installed_unloaded`, Zotero did not load the bridge endpoint after restart. Do not attach or clean artifacts. Report the `probe` and `install` fields from the script output; the generated XPI path is in `xpiPath`.

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

`attach_with_bridge.py` calls bridge `health`, imports each PDF through `Zotero.Attachments.importFromFile`, calls `verify`, and writes `attached`, `attachedAt`, and `attachmentVerification` back into the run manifest.

## Failure Handling

- If probe returns `unauthorized`, rerun `ensure_zotero_bridge.py --install --restart-zotero`; the XPI and config token are out of sync.
- If probe remains `404 No endpoint found` after install/restart, Zotero did not register the bridge. Do not clean artifacts; report the `installed_unloaded` state and keep the run directory.
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
