# Zotero Attachment Import

Attach rendered PDFs with the bundled Zotero Translate Bridge after the render phase has written `finalPdfs` into `run_manifest.json`.

The bridge is intentionally narrow: it exposes only `health`, `attach`, and `verify` on Zotero's local HTTP server, protected by a generated local token. It does not provide arbitrary JavaScript execution.

## Ensure Bridge

Probe first:

```bash
python "$skillDir/scripts/ensure_zotero_bridge.py" --probe
```

If the bridge is unavailable, ask the user to install the release XPI once:

```text
https://github.com/Chael-Chael/zotero-translate-skill/raw/main/assets/zotero-translate-bridge-0.2.3.xpi
```

In Zotero: `Tools -> Add-ons -> gear icon -> Install Add-on From File...`, then restart Zotero and rerun the probe. The release XPI is generic, declares Zotero `6.999` through `10.99.99` compatibility in the same range style as installed Zotero 9 plugins on this machine, and writes a per-profile token to `zotero-translate-bridge.json` in the Zotero profile on first startup.

For development or local builds, build an XPI manually:

```bash
python "$skillDir/scripts/ensure_zotero_bridge.py" \
  --build-only
```

The script writes runtime-only files under `skills/zotero-translate/.runtime/zotero-translate-bridge/`:

- `zotero-translate-bridge.xpi`
- `bridge_config.json`
- `build/`

These files contain the generated local token and must stay out of git.

Do not use profile-side automatic extension loading as the normal install path. If a local development install fails to load the endpoint after restart, do not attach or clean artifacts. Ask the user to install the release XPI through Zotero's Add-ons UI, then rerun `ensure_zotero_bridge.py --probe`.

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

- If probe returns `unauthorized`, restart Zotero and rerun `ensure_zotero_bridge.py --probe`; the script will re-import the per-profile token written by the bridge.
- If probe remains `404 No endpoint found`, Zotero did not register the bridge. Do not clean artifacts; ask the user to install the release XPI through Zotero's Add-ons UI and restart Zotero.
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
