# Zotero Attachment Import

Use Zotero MCP `zotero_script` in `mode: "write"` after the render phase has produced final PDF files. Attach every final PDF listed in `run_manifest.json` unless the user asked for only one output mode.

## Attach One PDF

Replace `PARENT_ITEM_ID`, `PDF_PATH`, and `TITLE`.

```javascript
const parentItemID = PARENT_ITEM_ID;
const pdfPath = String.raw`PDF_PATH`;
const title = "TITLE";

const parent = await Zotero.Items.getAsync(parentItemID);
if (!parent || !parent.isRegularItem()) {
  throw new Error(`Parent Zotero item not found or not regular: ${parentItemID}`);
}
env.snapshot(parent);

if (typeof IOUtils !== "undefined" && !(await IOUtils.exists(pdfPath))) {
  throw new Error(`PDF does not exist: ${pdfPath}`);
}

const attachment = await Zotero.Attachments.importFromFile({
  file: pdfPath,
  parentItemID,
  title,
  contentType: "application/pdf",
});

const attachmentID = attachment.id;
env.addUndoStep(async () => {
  const created = await Zotero.Items.getAsync(attachmentID);
  if (created) {
    await created.eraseTx();
  }
});

env.log(JSON.stringify({
  attached: {
    id: attachment.id,
    key: attachment.key,
    title: attachment.getField("title"),
    path: await attachment.getFilePathAsync?.(),
  },
  parent: {
    id: parent.id,
    key: parent.key,
    title: parent.getField("title"),
  },
}, null, 2));
```

## Verify Attachments

After attaching all generated PDFs, verify with a read-only script:

```javascript
const parent = await Zotero.Items.getAsync(PARENT_ITEM_ID);
const attachments = [];
for (const id of await parent.getAttachments()) {
  const att = await Zotero.Items.getAsync(id);
  attachments.push({
    id: att.id,
    key: att.key,
    title: att.getField("title"),
    path: await att.getFilePathAsync?.(),
    contentType: att.attachmentContentType,
  });
}
env.log(JSON.stringify({ parent: parent.getField("title"), attachments }, null, 2));
```

## Cleanup

After Zotero verification succeeds, clean intermediate run artifacts unless the user asked to keep them:

```bash
python "$skillDir/scripts/cleanup_artifacts.py" \
  --run-dir "<run-dir>" \
  --confirm-attached
```

This removes the run workspace only. It does not remove the skill-local runtime or BabelDOC asset cache.
